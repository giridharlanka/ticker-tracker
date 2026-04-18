"""Register or remove OS startup entries for headless ``--run``."""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
import textwrap
import xml.sax.saxutils
from pathlib import Path
from typing import Any, cast

LAUNCH_AGENT_LABEL = "com.ticker-tracker.portfolio"
WINDOWS_RUN_VALUE_NAME = "TickerTracker"
SYSTEMD_SERVICE_NAME = "ticker-tracker.service"


def _python_executable() -> str:
    return sys.executable


def _run_command_args() -> list[str]:
    """
    Default: ``python -m ticker_tracker --run`` (works with ``pip install``).

    Override with env ``TICKER_TRACKER_STARTUP_CMD`` (shell-split, e.g. a venv path).
    """
    custom = os.environ.get("TICKER_TRACKER_STARTUP_CMD")
    if custom:
        return shlex.split(custom)
    return [_python_executable(), "-m", "ticker_tracker", "--run"]


def _escape_plist_text(s: str) -> str:
    return xml.sax.saxutils.escape(s, entities={"'": "&apos;", '"': "&quot;"})


def register_startup() -> None:
    """Install a login/startup entry that runs ``main.py --run``."""
    system = platform.system()
    if system == "Darwin":
        _register_macos()
    elif system == "Windows":
        _register_windows()
    elif system == "Linux":
        _register_linux()
    else:
        raise OSError(f"Unsupported platform for startup registration: {system!r}")


def deregister_startup() -> None:
    """Remove startup registration created by :func:`register_startup`."""
    system = platform.system()
    if system == "Darwin":
        _deregister_macos()
    elif system == "Windows":
        _deregister_windows()
    elif system == "Linux":
        _deregister_linux()


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def _register_macos() -> None:
    args = _run_command_args()
    plist_dir = _plist_path().parent
    plist_dir.mkdir(parents=True, exist_ok=True)

    parts_xml = "\n        ".join(f"<string>{_escape_plist_text(a)}</string>" for a in args)
    plist_body = textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{LAUNCH_AGENT_LABEL}</string>
            <key>ProgramArguments</key>
            <array>
        {parts_xml}
            </array>
            <key>RunAtLoad</key>
            <true/>
        </dict>
        </plist>
        """
    )
    plist_path = _plist_path()
    plist_path.write_text(plist_body, encoding="utf-8")

    uid = os.getuid()
    domain = f"gui/{uid}"
    try:
        subprocess.run(
            ["launchctl", "bootout", domain, str(plist_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        pass
    subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist_path)],
        check=True,
        capture_output=True,
        text=True,
    )


def _deregister_macos() -> None:
    plist_path = _plist_path()
    if not plist_path.is_file():
        return
    uid = os.getuid()
    domain = f"gui/{uid}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        plist_path.unlink()
    except OSError:
        pass


def _register_windows() -> None:
    winreg = cast(Any, __import__("winreg"))
    cmd = subprocess.list2cmdline(_run_command_args())
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, WINDOWS_RUN_VALUE_NAME, 0, winreg.REG_SZ, cmd)


def _deregister_windows() -> None:
    winreg = cast(Any, __import__("winreg"))
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, WINDOWS_RUN_VALUE_NAME)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _systemd_user_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _systemd_unit_path() -> Path:
    return _systemd_user_dir() / SYSTEMD_SERVICE_NAME


def _register_linux() -> None:
    args = _run_command_args()
    unit_dir = _systemd_user_dir()
    unit_dir.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join(shlex.quote(a) for a in args)
    unit = textwrap.dedent(
        f"""\
        [Unit]
        Description=Ticker Tracker portfolio run (headless)

        [Service]
        Type=oneshot
        ExecStart={exec_line}

        [Install]
        WantedBy=default.target
        """
    )
    path = _systemd_unit_path()
    path.write_text(unit, encoding="utf-8")
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True)
        subprocess.run(
            ["systemctl", "--user", "enable", path.name],
            check=False,
            capture_output=True,
            text=True,
        )


def _deregister_linux() -> None:
    path = _systemd_unit_path()
    if shutil.which("systemctl") and path.is_file():
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", path.name],
            check=False,
            capture_output=True,
            text=True,
        )
    if path.is_file():
        path.unlink()
