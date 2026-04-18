"""Read-only display of saved configuration (CLI JSON or local web page)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ticker_tracker.config import AppConfig, EncryptedConfig, default_config_path


def load_config_for_display(path: Path | None = None) -> tuple[EncryptedConfig, AppConfig]:
    enc = EncryptedConfig(path or default_config_path())
    return enc, enc.load()


def print_config_cli(*, config_path: Path | None = None) -> None:
    """Print decrypted non-secret fields as JSON to stdout."""
    enc, cfg = load_config_for_display(config_path)
    print(f"# config file: {enc.path.resolve()}", file=sys.stderr)
    print(json.dumps(cfg.to_dict(), indent=2, sort_keys=True))


def run_show_config_web(
    *,
    host: str = "127.0.0.1",
    port: int = 8767,
    config_path: Path | None = None,
) -> None:
    """Serve a read-only HTML view of the current configuration."""
    try:
        from flask import Flask, render_template
    except ImportError as e:
        print(
            "The web viewer needs Flask. Install with:\n  pip install 'ticker-tracker[web]'\n",
            file=sys.stderr,
        )
        raise SystemExit(1) from e

    enc, cfg = load_config_for_display(config_path)
    template_dir = Path(__file__).resolve().parent / "web" / "templates"
    app = Flask(__name__, template_folder=str(template_dir))

    payload = json.dumps(cfg.to_dict(), indent=2, sort_keys=True)

    @app.get("/")
    def index() -> str:
        return render_template(
            "show_config.html",
            config_path=str(enc.path.resolve()),
            payload=payload,
        )

    url = f"http://{host}:{port}/"
    print(
        f"\nTicker Tracker — current configuration (read-only)\n  {url}\n",
        file=sys.stderr,
    )
    print("Press Ctrl+C when finished.\n", file=sys.stderr)
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except OSError as exc:
        print(f"Could not bind to {host}:{port} — {exc}", file=sys.stderr)
        print(f"Try: ticker-tracker --show-config --web --port {port + 1}", file=sys.stderr)
        raise SystemExit(1) from exc
