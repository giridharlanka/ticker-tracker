"""Local-only Flask UI for first-time setup (optional dependency)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from flask import Flask, render_template, request

from ticker_tracker.config import EncryptedConfig, default_config_path
from ticker_tracker.setup_core import (
    DEFAULT_COLUMN_LETTERS,
    KNOWN_FINANCE_SOURCES,
    RECOMMENDED_COLUMNS,
    apply_setup,
    build_column_map_from_recommended_form,
    parse_emails_blob,
    parse_market_overrides_blob,
)
from ticker_tracker.setup_help import HELPS, TITLES


def _finance_labels() -> list[tuple[str, str]]:
    return [
        ("yahoo", "Yahoo Finance (no API key)"),
        ("alpha_vantage", "Alpha Vantage"),
        ("twelve_data", "Twelve Data"),
        ("finnhub", "Finnhub"),
        ("polygon", "Polygon.io"),
    ]


def _fx_choices() -> list[tuple[str, str]]:
    return [
        ("frankfurter", "Frankfurter (free, recommended)"),
        ("open_exchange_rates", "Open Exchange Rates (API key)"),
        ("fixer", "Fixer (API key)"),
        ("currencylayer", "Currencylayer (API key)"),
    ]


def _default_form() -> dict[str, Any]:
    cols = {f"col_{k}": v for k, v in DEFAULT_COLUMN_LETTERS.items()}
    return {
        "google_sheets_id": "",
        "holdings_sheet_name": "Holdings",
        "emails": "",
        "base_currency": "SGD",
        "fx_source": "frankfurter",
        "fx_api_key": "",
        "market_overrides": "",
        "run_on_startup": False,
        "upload_to_drive": False,
        "finance_selected": [],
        **{f"key_{s}": "" for s in KNOWN_FINANCE_SOURCES if s != "yahoo"},
        **cols,
    }


def _form_from_request(form: Any) -> dict[str, Any]:
    out = _default_form()
    out["google_sheets_id"] = (form.get("google_sheets_id") or "").strip()
    out["holdings_sheet_name"] = (form.get("holdings_sheet_name") or "").strip() or "Holdings"
    out["emails"] = form.get("emails") or ""
    out["base_currency"] = (form.get("base_currency") or "").strip()
    out["fx_source"] = (form.get("fx_source") or "frankfurter").strip().lower()
    out["fx_api_key"] = (form.get("fx_api_key") or "").strip() or ""
    out["market_overrides"] = form.get("market_overrides") or ""
    out["run_on_startup"] = form.get("run_on_startup") == "1"
    out["upload_to_drive"] = form.get("upload_to_drive") == "1"
    selected: list[str] = []
    for sid in KNOWN_FINANCE_SOURCES:
        if form.get(f"finance_{sid}") == "1":
            selected.append(sid)
        if sid != "yahoo":
            out[f"key_{sid}"] = (form.get(f"key_{sid}") or "").strip()
    out["finance_selected"] = selected
    for field, _ in RECOMMENDED_COLUMNS:
        out[f"col_{field}"] = (form.get(f"col_{field}") or "").strip()
    return out


def create_app(encrypted_config: EncryptedConfig) -> Flask:
    template_dir = Path(__file__).resolve().parent / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    app.config["TICKER_ENCRYPTED_CONFIG"] = encrypted_config

    default_cols = {
        field: DEFAULT_COLUMN_LETTERS.get(field, "") for field, _ in RECOMMENDED_COLUMNS
    }

    @app.get("/")
    def get_form() -> str:
        return render_template(
            "setup.html",
            errors=[],
            saved=False,
            form=_default_form(),
            helps=HELPS,
            titles=TITLES,
            recommended_columns=RECOMMENDED_COLUMNS,
            finance_labels=_finance_labels(),
            fx_choices=_fx_choices(),
            default_cols=default_cols,
        )

    @app.post("/")
    def post_form() -> str:
        enc: EncryptedConfig = app.config["TICKER_ENCRYPTED_CONFIG"]
        form_data = _form_from_request(request.form)
        emails = parse_emails_blob(form_data["emails"])
        overrides = parse_market_overrides_blob(form_data["market_overrides"])
        column_map = build_column_map_from_recommended_form(form_data)

        finance_sources = list(form_data["finance_selected"])
        finance_api_keys: dict[str, str] = {}
        for sid in finance_sources:
            if sid != "yahoo":
                finance_api_keys[sid] = str(form_data.get(f"key_{sid}") or "")

        fx_key = form_data["fx_api_key"] or None
        if not fx_key:
            fx_key = None

        cfg, issues = apply_setup(
            google_sheets_id=form_data["google_sheets_id"],
            holdings_sheet_name=form_data["holdings_sheet_name"],
            column_map=column_map,
            email_ids=emails,
            finance_sources=finance_sources,
            finance_api_keys=finance_api_keys,
            base_currency=form_data["base_currency"],
            fx_source=form_data["fx_source"],
            fx_api_key=fx_key,
            market_currency_overrides=overrides,
            run_on_startup=bool(form_data["run_on_startup"]),
            upload_to_drive=bool(form_data["upload_to_drive"]),
            encrypted_config=enc,
        )
        saved = cfg is not None
        if saved and cfg is not None:
            try:
                from ticker_tracker.ui.startup_registration import (
                    deregister_startup,
                    register_startup,
                )

                if cfg.run_on_startup:
                    register_startup()
                else:
                    deregister_startup()
            except Exception as exc:  # noqa: BLE001
                print(f"Warning: startup registration failed: {exc}", file=sys.stderr)

        return render_template(
            "setup.html",
            errors=issues,
            saved=saved,
            form=form_data,
            helps=HELPS,
            titles=TITLES,
            recommended_columns=RECOMMENDED_COLUMNS,
            finance_labels=_finance_labels(),
            fx_choices=_fx_choices(),
            default_cols=default_cols,
        )

    return app


def run_setup_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    config_path: Path | None = None,
    debug: bool = False,
) -> None:
    """Start a blocking local web server for setup (binds to *host* only by default)."""
    path = config_path or default_config_path()
    enc = EncryptedConfig(path)
    app = create_app(enc)
    print(f"\nTicker Tracker setup — open in your browser:\n  http://{host}:{port}/\n")
    print("Press Ctrl+C in this terminal when you are finished.\n")
    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except OSError as e:
        print(f"Could not bind to {host}:{port} — {e}", file=sys.stderr)
        print("Try a different port: ticker-tracker-setup --web --port 9876", file=sys.stderr)
        raise SystemExit(1) from e
