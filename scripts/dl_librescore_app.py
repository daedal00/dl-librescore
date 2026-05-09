#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
dl-librescore — Desktop sheet music downloader.
Lightweight tkinter GUI that wraps the SeleniumBase PDF backend.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# ── helpers ──────────────────────────────────────────────────────────

def resource_path(relative: str) -> Path:
    """Get absolute path to a resource, works for dev and PyInstaller."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base) / relative


BACKEND = resource_path("seleniumbase_pdf.py")


def find_output_dir() -> Path:
    """Default download directory: ~/Downloads/dl-librescore"""
    home = Path.home()
    return home / "Downloads" / "dl-librescore"


# ── app ──────────────────────────────────────────────────────────────

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LibreScore Downloader")
        self.root.resizable(True, True)
        self.root.minsize(480, 420)

        # Style
        style = ttk.Style(self.root)
        style.theme_use("clam")

        self._build_ui()
        self._running = False
        self._output_file: Path | None = None

    # ── UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 16, "pady": 6}

        # Header
        header = ttk.Label(
            self.root,
            text="🎼 Download Sheet Music",
            font=("Helvetica", 18, "bold"),
        )
        header.pack(pady=(20, 4))

        sub = ttk.Label(
            self.root,
            text="Paste a MuseScore URL to download as PDF, MIDI, or MP3",
            foreground="gray",
        )
        sub.pack(pady=(0, 12))

        # URL
        ttk.Label(self.root, text="MuseScore URL").pack(anchor="w", **pad)
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(self.root, textvariable=self.url_var, font=("monospace", 11))
        url_entry.pack(fill="x", padx=16)
        url_entry.insert(0, "https://musescore.com/user/")

        # Format
        ttk.Label(self.root, text="Format").pack(anchor="w", **pad)
        fmt_frame = ttk.Frame(self.root)
        fmt_frame.pack(fill="x", padx=16)
        self.format_var = tk.StringVar(value="pdf")
        for val, label in [("pdf", "PDF"), ("midi", "MIDI"), ("mp3", "MP3")]:
            ttk.Radiobutton(
                fmt_frame, text=label, variable=self.format_var, value=val
            ).pack(side="left", padx=(0, 12))

        # Output folder
        ttk.Label(self.root, text="Save to").pack(anchor="w", **pad)
        out_frame = ttk.Frame(self.root)
        out_frame.pack(fill="x", padx=16)
        self.out_var = tk.StringVar(value=str(find_output_dir()))
        out_entry = ttk.Entry(out_frame, textvariable=self.out_var, font=("monospace", 10))
        out_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(out_frame, text="Browse…", command=self._pick_dir).pack(side="right", padx=(8, 0))

        # Progress
        self.progress_var = tk.StringVar(value="Ready")
        prog_label = ttk.Label(
            self.root,
            textvariable=self.progress_var,
            foreground="#58a6ff",
        )
        prog_label.pack(anchor="w", padx=16, pady=(12, 2))

        self.log_text = tk.Text(
            self.root,
            height=8,
            font=("monospace", 10),
            bg="#0d1117",
            fg="#c9d1d9",
            insertbackground="white",
            relief="flat",
            borderwidth=0,
        )
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))
        self.dl_btn = ttk.Button(btn_frame, text="Download", command=self._start_download)
        self.dl_btn.pack(side="left")
        self.open_btn = ttk.Button(btn_frame, text="Open File", command=self._open_file, state="disabled")
        self.open_btn.pack(side="left", padx=(8, 0))
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="right")

    # ── actions ──────────────────────────────────────────────────────

    def _pick_dir(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.out_var.set(path)

    def _log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def _set_progress(self, msg: str):
        self.progress_var.set(msg)

    def _start_download(self):
        url = self.url_var.get().strip()
        if not url.startswith("https://musescore.com/"):
            messagebox.showerror("Error", "Please enter a valid MuseScore URL.")
            return

        out_dir = Path(self.out_var.get())
        out_dir.mkdir(parents=True, exist_ok=True)

        fmt = self.format_var.get()
        suffix = "pdf" if fmt == "pdf" else ("mid" if fmt == "midi" else "mp3")
        self._output_file = out_dir / f"download.{suffix}"

        self._running = True
        self.dl_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self._set_progress("Starting…")
        self.log_text.delete("1.0", "end")

        thread = threading.Thread(target=self._run_backend, args=(url, fmt), daemon=True)
        thread.start()

    def _run_backend(self, url: str, fmt: str):
        out_file = str(self._output_file)
        try:
            if fmt == "pdf":
                # PDF uses the SeleniumBase browser fallback (most reliable)
                proc = subprocess.Popen(
                    ["uv", "run", str(BACKEND), url, out_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert proc.stdout
                for line in proc.stdout:
                    if not self._running:
                        proc.terminate()
                        return
                    line = line.strip()
                    if line:
                        self.root.after(0, self._log, line)
                        if not line.startswith("{"):
                            self.root.after(0, self._set_progress, line)
                proc.wait()
                if proc.returncode != 0:
                    raise subprocess.CalledProcessError(proc.returncode, proc.args)
            else:
                # MIDI / MP3: try the CLI (Node.js) — may fail if API auth is blocked
                cli_js = resource_path("cli.js") if (resource_path("cli.js").exists()) else None
                if not cli_js:
                    raise FileNotFoundError("CLI not found. Install Node.js and run: npm run build")
                proc = subprocess.Popen(
                    ["node", str(cli_js), "-i", url, "-t", fmt, "-o", str(self._output_file.parent), "-v"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert proc.stdout
                for line in proc.stdout:
                    if not self._running:
                        proc.terminate()
                        return
                    line = line.strip()
                    if line:
                        self.root.after(0, self._log, line)
                proc.wait()
                if proc.returncode != 0:
                    raise subprocess.CalledProcessError(proc.returncode, proc.args)

            # Find the actual output file (CLI may rename it)
            actual = None
            for f in self._output_file.parent.glob("*"):
                if f.is_file() and f.suffix.lstrip(".") in ("pdf", "mid", "mp3"):
                    actual = f
                    break
            if actual:
                self._output_file = actual

            self.root.after(0, self._on_success)

        except subprocess.CalledProcessError as e:
            self.root.after(0, self._on_error, f"Process failed (exit {e.returncode})")
        except Exception as e:
            self.root.after(0, self._on_error, str(e))

    def _on_success(self):
        self._running = False
        self._set_progress("✅ Done!")
        self.dl_btn.config(state="normal")
        self.open_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self._log("Download complete. Click 'Open File' to view.")

    def _on_error(self, msg: str):
        self._running = False
        self._set_progress("❌ Failed")
        self.dl_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")
        self._log(f"ERROR: {msg}")

    def _open_file(self):
        if self._output_file and self._output_file.exists():
            import platform
            system = platform.system()
            if system == "Darwin":
                subprocess.run(["open", str(self._output_file)])
            elif system == "Windows":
                os.startfile(str(self._output_file))  # type: ignore
            else:
                subprocess.run(["xdg-open", str(self._output_file)])

    def _cancel(self):
        self._running = False
        self._set_progress("Cancelled")
        self.dl_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")


# ── main ─────────────────────────────────────────────────────────────

def main():
    # Check for uv
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        messagebox.showerror(
            "Missing uv",
            "This app requires 'uv' (Python package manager).\n\n"
            "Install it from: https://docs.astral.sh/uv/getting-started/installation/\n"
            "Then restart the app.",
        )
        sys.exit(1)

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
