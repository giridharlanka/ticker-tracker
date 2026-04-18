"""Primary CLI / GUI entry (console script ``ticker-tracker``)."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ticker Tracker — portfolio summary and setup.")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run the configuration wizard (same as ticker-tracker-setup).",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the portfolio engine once (headless, no GUI).",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print saved configuration as JSON (secrets are in the keychain, not shown).",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="With --show-config: open a read-only browser page instead of printing JSON.",
    )
    parser.add_argument(
        "--show-config-host",
        default="127.0.0.1",
        metavar="ADDR",
        help="With --show-config --web: bind address (default 127.0.0.1).",
    )
    parser.add_argument(
        "--show-config-port",
        type=int,
        default=8767,
        metavar="PORT",
        help="With --show-config --web: TCP port (default 8767).",
    )
    args = parser.parse_args(argv)

    if args.web and not args.show_config:
        parser.error("--web is only valid together with --show-config")

    if args.show_config:
        if args.web:
            from ticker_tracker.show_config import run_show_config_web

            run_show_config_web(host=args.show_config_host, port=args.show_config_port)
        else:
            from ticker_tracker.show_config import print_config_cli

            print_config_cli()
        return

    if args.setup:
        from ticker_tracker.setup_wizard import main as setup_main

        setup_main()
        return

    if args.run:
        from ticker_tracker.engine import run_once

        run_once()
        return

    from ticker_tracker.ui.popup import show_popup

    show_popup()


if __name__ == "__main__":
    main()
