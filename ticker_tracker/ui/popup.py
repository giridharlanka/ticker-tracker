"""Tkinter startup window: profile (email) selection and portfolio run."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import messagebox, ttk
from typing import Any


def _center_window(root: tk.Tk, width: int, height: int) -> None:
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")


def show_popup() -> None:
    """Blocking Tk UI until the user closes the window."""
    from ticker_tracker.config import AppConfig, EncryptedConfig
    from ticker_tracker.engine import run as engine_run

    root = tk.Tk()
    root.title("Portfolio Tracker")
    root.resizable(False, False)
    _center_window(root, 360, 220)

    try:
        cfg: AppConfig = EncryptedConfig().load()
    except Exception as exc:  # noqa: BLE001 — show any load failure in UI
        messagebox.showerror("Portfolio Tracker", f"Could not load config:\n{exc}", parent=root)
        root.destroy()
        return

    main_f = ttk.Frame(root, padding=12)
    main_f.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_f, text="Run portfolio summary").pack(anchor=tk.W)

    emails = list(cfg.email_ids or [])
    if emails:
        recip_text = ", ".join(emails)
        ttk.Label(
            main_f,
            text=f"Each run emails all {len(emails)} address(es) in setup:\n{recip_text}",
            wraplength=340,
        ).pack(anchor=tk.W, fill=tk.X, pady=(6, 4))
    else:
        ttk.Label(
            main_f,
            text="(Add notification emails in setup.)",
            foreground="gray",
        ).pack(anchor=tk.W, pady=(6, 4))

    btn_row = ttk.Frame(main_f)
    btn_row.pack(fill=tk.X, pady=(4, 2))
    run_btn = ttk.Button(btn_row, text="Run now")
    run_btn.pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btn_row, text="Skip", command=root.destroy).pack(side=tk.LEFT)

    progress = ttk.Progressbar(main_f, mode="indeterminate", length=320)
    progress.pack(fill=tk.X, pady=(4, 4))

    status_var = tk.StringVar(value="Ready.")
    status_lbl = tk.Label(
        main_f,
        textvariable=status_var,
        wraplength=320,
        justify=tk.LEFT,
        anchor="w",
    )
    status_lbl.pack(anchor=tk.W, fill=tk.X)

    link_frame = ttk.Frame(main_f)
    link_var = tk.StringVar(value="")
    link_label = tk.Label(
        link_frame,
        textvariable=link_var,
        fg="blue",
        cursor="hand2",
        font=("TkDefaultFont", 10, "underline"),
        wraplength=320,
        justify=tk.LEFT,
    )
    link_label.pack(anchor=tk.W)
    drive_url_holder: dict[str, str] = {}

    def open_drive(_event: object | None = None) -> None:
        url = drive_url_holder.get("url", "")
        if url:
            webbrowser.open(url)

    link_label.bind("<Button-1>", open_drive)

    close_btn = ttk.Button(main_f, text="Close", command=root.destroy)
    close_btn.pack_forget()

    def set_status(text: str, *, error: bool = False) -> None:
        status_var.set(text)
        status_lbl.configure(fg=("red" if error else "black"))

    def on_status(msg: str) -> None:
        root.after(0, partial(set_status, msg, error=False))

    def finish_success(result: dict[str, Any]) -> None:
        progress.stop()
        run_btn.configure(state=tk.NORMAL)
        url = result.get("drive_url") or ""
        drive_url_holder["url"] = str(url)
        if url:
            link_var.set(url)
            link_frame.pack(anchor=tk.W, pady=(4, 0))
        else:
            link_frame.pack_forget()
        close_btn.pack(anchor=tk.E, pady=(8, 0))

    def finish_error(exc: BaseException) -> None:
        progress.stop()
        run_btn.configure(state=tk.NORMAL)
        link_frame.pack_forget()
        set_status(str(exc), error=True)

    def run_worker() -> None:
        root.after(0, partial(progress.start, 12))
        root.after(0, partial(run_btn.configure, state=tk.DISABLED))
        root.after(0, partial(set_status, "Fetching prices...", error=False))
        try:
            result = engine_run(
                app_config=cfg,
                status_callback=on_status,
            )
            root.after(0, partial(finish_success, result))
        except Exception as exc:  # noqa: BLE001
            root.after(0, partial(finish_error, exc))

    def on_run() -> None:
        if not emails:
            messagebox.showinfo(
                "Portfolio Tracker",
                "Add at least one notification email in setup before running.",
                parent=root,
            )
            return
        close_btn.pack_forget()
        link_frame.pack_forget()
        threading.Thread(target=run_worker, daemon=True).start()

    run_btn.configure(command=on_run)
    root.mainloop()
