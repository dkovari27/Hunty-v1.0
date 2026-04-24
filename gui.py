"""
gui.py — Hunty GUI.

Run:
    python gui.py
"""
import json
import logging
import os
import re
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------------
# Colours & fonts
# ---------------------------------------------------------------------------
BG        = "#F5F7FA"
DARK_BLUE = "#1F4E79"
MID_BLUE  = "#2E75B6"
GREEN     = "#217346"
TEXT      = "#1A1A1A"
SUBTEXT   = "#666666"
SEP_COLOR = "#D0D7E3"
FONT      = "Segoe UI"

_SETTINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings")

_ALL_COUNTRIES = [
    "Switzerland", "Germany", "United Kingdom", "Netherlands",
    "France", "Austria", "Belgium", "Denmark", "Sweden", "Norway",
    "Spain", "Italy", "Ireland", "Finland",
]

# EU member states from the list above (Switzerland, UK, Norway are not EU members)
_EU_COUNTRIES = {
    "Germany", "Netherlands", "France", "Austria", "Belgium",
    "Denmark", "Sweden", "Spain", "Italy", "Ireland", "Finland",
}


# ---------------------------------------------------------------------------
# Keyword editor dialog
# ---------------------------------------------------------------------------
class _KeywordEditorDialog:
    """Modal dialog for editing Swiss-market and global search keywords."""

    def __init__(
        self,
        parent: tk.Tk,
        swiss_keywords: list[str],
        global_keywords: list[str],
        cv_suggestions: list[str],
    ):
        self._result: tuple[list[str], list[str]] | None = None

        dlg = tk.Toplevel(parent)
        dlg.title("Edit Search Keywords")
        dlg.configure(bg=BG)
        dlg.resizable(True, True)
        dlg.transient(parent)
        dlg.grab_set()

        w, h = 540, 580
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{px}+{py}")

        tk.Label(
            dlg,
            text="One search phrase per line — case-insensitive.",
            font=(FONT, 9), fg=SUBTEXT, bg=BG, wraplength=510, justify="left",
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # ── Swiss market ─────────────────────────────────────────────────
        tk.Label(
            dlg,
            text="Swiss market — jobs.ch and Swiss company career pages:",
            font=(FONT, 9, "bold"), fg=DARK_BLUE, bg=BG,
        ).pack(anchor="w", padx=16)

        swiss_frame = tk.Frame(dlg, bg=BG)
        swiss_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 10))
        swiss_sb = tk.Scrollbar(swiss_frame)
        swiss_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._swiss_text = tk.Text(
            swiss_frame, font=(FONT, 10), wrap=tk.WORD,
            yscrollcommand=swiss_sb.set, height=7,
            relief=tk.FLAT, bd=0,
            highlightbackground=SEP_COLOR, highlightthickness=1,
        )
        self._swiss_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        swiss_sb.config(command=self._swiss_text.yview)
        self._swiss_text.insert("1.0", "\n".join(swiss_keywords))

        # ── Everything else ───────────────────────────────────────────────
        tk.Label(
            dlg,
            text="Everything else — LinkedIn, Exa and organic-chemistry.org:",
            font=(FONT, 9, "bold"), fg=DARK_BLUE, bg=BG,
        ).pack(anchor="w", padx=16)

        global_frame = tk.Frame(dlg, bg=BG)
        global_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 8))
        global_sb = tk.Scrollbar(global_frame)
        global_sb.pack(side=tk.RIGHT, fill=tk.Y)
        lines = list(global_keywords)
        if cv_suggestions:
            lines += ["", "# ── Suggested from CV (delete lines you don't want) ──"]
            lines += cv_suggestions
        self._global_text = tk.Text(
            global_frame, font=(FONT, 10), wrap=tk.WORD,
            yscrollcommand=global_sb.set, height=8,
            relief=tk.FLAT, bd=0,
            highlightbackground=SEP_COLOR, highlightthickness=1,
        )
        self._global_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        global_sb.config(command=self._global_text.yview)
        self._global_text.insert("1.0", "\n".join(lines))

        # ── Buttons ───────────────────────────────────────────────────────
        btn_frame = tk.Frame(dlg, bg=BG)
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))
        tk.Button(
            btn_frame, text="Cancel", command=dlg.destroy,
            font=(FONT, 10), bg=BG, fg=TEXT,
            relief=tk.FLAT, bd=1, padx=16, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(
            btn_frame, text="  OK  ", command=lambda: self._ok(dlg),
            font=(FONT, 10, "bold"), bg=DARK_BLUE, fg="white",
            activebackground=MID_BLUE, relief=tk.FLAT, padx=16, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT)

        parent.wait_window(dlg)

    def _ok(self, dlg: tk.Toplevel) -> None:
        def _parse(widget: tk.Text) -> list[str]:
            return [
                ln.strip() for ln in widget.get("1.0", tk.END).splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
        self._result = (_parse(self._swiss_text), _parse(self._global_text))
        dlg.destroy()

    @property
    def result(self) -> tuple[list[str], list[str]] | None:
        return self._result


# ---------------------------------------------------------------------------
# Filter words editor dialog
# ---------------------------------------------------------------------------
class _FilterEditorDialog:
    """Modal dialog for editing prefilter must-include and title-exclude terms."""

    def __init__(
        self,
        parent: tk.Tk,
        required: list[str],
        excluded: list[str],
    ):
        self._result: tuple[list[str], list[str]] | None = None

        dlg = tk.Toplevel(parent)
        dlg.title("Edit Filter Words")
        dlg.configure(bg=BG)
        dlg.resizable(True, True)
        dlg.transient(parent)
        dlg.grab_set()

        w, h = 540, 560
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{px}+{py}")

        tk.Label(
            dlg,
            text="One term per line. Matching is case-insensitive substring.",
            font=(FONT, 9), fg=SUBTEXT, bg=BG, wraplength=510, justify="left",
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # ── Must-include terms ──────────────────────────────────────────
        tk.Label(
            dlg,
            text="Must-include terms — job title OR description must contain at least one:",
            font=(FONT, 9, "bold"), fg=DARK_BLUE, bg=BG,
        ).pack(anchor="w", padx=16)

        req_frame = tk.Frame(dlg, bg=BG)
        req_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 10))
        req_sb = tk.Scrollbar(req_frame)
        req_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._req_text = tk.Text(
            req_frame, font=(FONT, 10), wrap=tk.WORD,
            yscrollcommand=req_sb.set, height=8,
            relief=tk.FLAT, bd=0,
            highlightbackground=SEP_COLOR, highlightthickness=1,
        )
        self._req_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        req_sb.config(command=self._req_text.yview)
        self._req_text.insert("1.0", "\n".join(required))

        # ── Exclude-from-title terms ─────────────────────────────────────
        tk.Label(
            dlg,
            text="Exclude from title — jobs with any of these terms in the title are dropped:",
            font=(FONT, 9, "bold"), fg=DARK_BLUE, bg=BG,
        ).pack(anchor="w", padx=16)

        excl_frame = tk.Frame(dlg, bg=BG)
        excl_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 8))
        excl_sb = tk.Scrollbar(excl_frame)
        excl_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._excl_text = tk.Text(
            excl_frame, font=(FONT, 10), wrap=tk.WORD,
            yscrollcommand=excl_sb.set, height=10,
            relief=tk.FLAT, bd=0,
            highlightbackground=SEP_COLOR, highlightthickness=1,
        )
        self._excl_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        excl_sb.config(command=self._excl_text.yview)
        self._excl_text.insert("1.0", "\n".join(excluded))

        btn_frame = tk.Frame(dlg, bg=BG)
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        tk.Button(
            btn_frame, text="Cancel", command=dlg.destroy,
            font=(FONT, 10), bg=BG, fg=TEXT,
            relief=tk.FLAT, bd=1, padx=16, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_frame, text="  OK  ", command=lambda: self._ok(dlg),
            font=(FONT, 10, "bold"), bg=DARK_BLUE, fg="white",
            activebackground=MID_BLUE, relief=tk.FLAT, padx=16, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT)

        parent.wait_window(dlg)

    def _ok(self, dlg: tk.Toplevel) -> None:
        def _parse(widget: tk.Text) -> list[str]:
            raw = widget.get("1.0", tk.END)
            return [
                ln.strip() for ln in raw.splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
        self._result = (_parse(self._req_text), _parse(self._excl_text))
        dlg.destroy()

    @property
    def result(self) -> tuple[list[str], list[str]] | None:
        return self._result


# ---------------------------------------------------------------------------
# Location exclusion editor dialog
# ---------------------------------------------------------------------------
class _LocationExclusionDialog:
    """Modal dialog for editing excluded location substrings."""

    def __init__(self, parent: tk.Tk, excluded: list[str]):
        self._result: list[str] | None = None

        dlg = tk.Toplevel(parent)
        dlg.title("Exclude Locations")
        dlg.configure(bg=BG)
        dlg.resizable(True, True)
        dlg.transient(parent)
        dlg.grab_set()

        w, h = 400, 320
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{px}+{py}")

        tk.Label(
            dlg,
            text="One location term per line — case-insensitive substring match against the job's location field.\n"
                 "e.g.  wales  ·  united states  ·  , ca,  ·  boston",
            font=(FONT, 9), fg=SUBTEXT, bg=BG, wraplength=370, justify="left",
        ).pack(anchor="w", padx=16, pady=(12, 8))

        frame = tk.Frame(dlg, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 6))
        sb = tk.Scrollbar(frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._text = tk.Text(
            frame, font=(FONT, 10), wrap=tk.WORD,
            yscrollcommand=sb.set, height=8,
            relief=tk.FLAT, bd=0,
            highlightbackground=SEP_COLOR, highlightthickness=1,
        )
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self._text.yview)
        self._text.insert("1.0", "\n".join(excluded))

        btn_frame = tk.Frame(dlg, bg=BG)
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))
        tk.Button(
            btn_frame, text="Cancel", command=dlg.destroy,
            font=(FONT, 10), bg=BG, fg=TEXT,
            relief=tk.FLAT, bd=1, padx=16, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(
            btn_frame, text="  OK  ", command=lambda: self._ok(dlg),
            font=(FONT, 10, "bold"), bg=DARK_BLUE, fg="white",
            activebackground=MID_BLUE, relief=tk.FLAT, padx=16, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT)
        parent.wait_window(dlg)

    def _ok(self, dlg: tk.Toplevel) -> None:
        raw = self._text.get("1.0", tk.END)
        self._result = [
            ln.strip() for ln in raw.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        dlg.destroy()

    @property
    def result(self) -> list[str] | None:
        return self._result


# ---------------------------------------------------------------------------
# Scheduler dialog
# ---------------------------------------------------------------------------
class _SchedulerDialog:
    """Modal dialog for configuring the local background scheduler."""

    _DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, parent: tk.Tk, config: dict):
        self._result: dict | None = None

        dlg = tk.Toplevel(parent)
        dlg.title("Scheduler Settings")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()

        w, h = 400, 330
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{px}+{py}")

        pad = dict(padx=20)

        # ── Days ──────────────────────────────────────────────────────────
        tk.Label(dlg, text="Days", font=(FONT, 9, "bold"), fg=SUBTEXT, bg=BG).pack(
            anchor="w", pady=(14, 4), **pad)

        days_frame = tk.Frame(dlg, bg=BG)
        days_frame.pack(anchor="w", **pad)
        selected_days = config.get("days", [0, 2, 4])
        self._day_vars = []
        for i, name in enumerate(self._DAY_NAMES):
            var = tk.BooleanVar(value=(i in selected_days))
            self._day_vars.append(var)
            tk.Checkbutton(
                days_frame, text=name, variable=var,
                font=(FONT, 10), bg=BG, fg=TEXT,
                activebackground=BG, selectcolor=BG, cursor="hand2",
            ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Frame(dlg, bg=SEP_COLOR, height=1).pack(fill=tk.X, pady=(8, 0), **pad)

        # ── Interval ──────────────────────────────────────────────────────
        tk.Label(dlg, text="Repeat interval", font=(FONT, 9, "bold"), fg=SUBTEXT, bg=BG).pack(
            anchor="w", pady=(8, 4), **pad)

        interval_frame = tk.Frame(dlg, bg=BG)
        interval_frame.pack(anchor="w", **pad)
        tk.Label(interval_frame, text="Every", font=(FONT, 10), fg=TEXT, bg=BG).pack(side=tk.LEFT)
        self._interval_var = tk.StringVar(value=str(config.get("interval_weeks", 1)))
        tk.Spinbox(
            interval_frame, textvariable=self._interval_var,
            from_=1, to=52, width=4,
            font=(FONT, 10), relief=tk.FLAT,
            highlightbackground=SEP_COLOR, highlightthickness=1,
        ).pack(side=tk.LEFT, padx=6)
        tk.Label(interval_frame, text="week(s)", font=(FONT, 10), fg=TEXT, bg=BG).pack(side=tk.LEFT)

        tk.Frame(dlg, bg=SEP_COLOR, height=1).pack(fill=tk.X, pady=(8, 0), **pad)

        # ── Time ──────────────────────────────────────────────────────────
        tk.Label(dlg, text="Time  (24 h, Europe/Zurich)", font=(FONT, 9, "bold"), fg=SUBTEXT, bg=BG).pack(
            anchor="w", pady=(8, 4), **pad)

        time_frame = tk.Frame(dlg, bg=BG)
        time_frame.pack(anchor="w", **pad)
        self._hour_var   = tk.StringVar(value=f"{config.get('hour',   13):02d}")
        self._minute_var = tk.StringVar(value=f"{config.get('minute',  0):02d}")
        tk.Spinbox(
            time_frame, textvariable=self._hour_var,
            values=[f"{h:02d}" for h in range(24)], width=4,
            font=(FONT, 11), relief=tk.FLAT,
            highlightbackground=SEP_COLOR, highlightthickness=1,
        ).pack(side=tk.LEFT)
        tk.Label(time_frame, text=" : ", font=(FONT, 11, "bold"), fg=TEXT, bg=BG).pack(side=tk.LEFT)
        tk.Spinbox(
            time_frame, textvariable=self._minute_var,
            values=[f"{m:02d}" for m in range(0, 60, 5)], width=4,
            font=(FONT, 11), relief=tk.FLAT,
            highlightbackground=SEP_COLOR, highlightthickness=1,
        ).pack(side=tk.LEFT)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_frame = tk.Frame(dlg, bg=BG)
        btn_frame.pack(fill=tk.X, padx=20, pady=(14, 14))
        tk.Button(
            btn_frame, text="Cancel", command=dlg.destroy,
            font=(FONT, 10), bg=BG, fg=TEXT,
            relief=tk.FLAT, bd=1, padx=16, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(
            btn_frame, text="  Save  ", command=lambda: self._save(dlg),
            font=(FONT, 10, "bold"), bg=DARK_BLUE, fg="white",
            activebackground=MID_BLUE, relief=tk.FLAT, padx=16, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT)

        parent.wait_window(dlg)

    def _save(self, dlg: tk.Toplevel) -> None:
        days = [i for i, v in enumerate(self._day_vars) if v.get()]
        if not days:
            messagebox.showwarning("Scheduler", "Select at least one day.", parent=dlg)
            return
        try:
            interval = max(1, int(self._interval_var.get()))
            hour     = int(self._hour_var.get())
            minute   = int(self._minute_var.get())
        except ValueError:
            messagebox.showwarning("Scheduler", "Invalid time or interval value.", parent=dlg)
            return
        from datetime import date
        self._result = {
            "enabled":        True,
            "days":           days,
            "interval_weeks": interval,
            "hour":           hour,
            "minute":         minute,
            "start_date":     date.today().isoformat(),
        }
        dlg.destroy()

    @property
    def result(self) -> dict | None:
        return self._result


# ---------------------------------------------------------------------------
# Countries selector dialog
# ---------------------------------------------------------------------------
class _CountriesDialog:
    """Modal dialog for selecting which countries to search."""

    def __init__(self, parent: tk.Tk, selected: list[str]):
        self._result: list[str] | None = None

        dlg = tk.Toplevel(parent)
        dlg.title("Select Countries")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()

        w, h = 360, 420
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{px}+{py}")

        # ── Title ────────────────────────────────────────────────────────
        tk.Label(
            dlg, text="Select Countries",
            font=(FONT, 12, "bold"), fg=DARK_BLUE, bg=BG,
        ).pack(anchor="w", padx=16, pady=(14, 6))

        # ── Quick-select buttons ──────────────────────────────────────────
        self._vars: dict[str, tk.BooleanVar] = {}
        for country in _ALL_COUNTRIES:
            self._vars[country] = tk.BooleanVar(value=(country in selected))

        def _select_eu() -> None:
            for c, v in self._vars.items():
                v.set(c in _EU_COUNTRIES or c == "Switzerland")

        def _select_all() -> None:
            for v in self._vars.values():
                v.set(True)

        def _select_none() -> None:
            for v in self._vars.values():
                v.set(False)

        quick_row = tk.Frame(dlg, bg=BG)
        quick_row.pack(fill=tk.X, padx=16, pady=(0, 8))

        for label, cmd in [("EU + CH", _select_eu), ("All", _select_all), ("Clear", _select_none)]:
            tk.Button(
                quick_row, text=label, command=cmd,
                font=(FONT, 9, "bold"), bg=MID_BLUE, fg="white",
                activebackground=DARK_BLUE, relief=tk.FLAT,
                padx=10, pady=3, cursor="hand2",
            ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Frame(dlg, bg=SEP_COLOR, height=1).pack(fill=tk.X, padx=16, pady=(0, 8))

        # ── Checkboxes — 2 columns ────────────────────────────────────────
        grid = tk.Frame(dlg, bg=BG)
        grid.pack(fill=tk.X, padx=16)

        half = len(_ALL_COUNTRIES) // 2 + len(_ALL_COUNTRIES) % 2
        for i, country in enumerate(_ALL_COUNTRIES):
            col = i // half
            row = i % half
            tk.Checkbutton(
                grid, text=country, variable=self._vars[country],
                font=(FONT, 10), bg=BG, fg=TEXT,
                activebackground=BG, selectcolor="white",
                anchor="w", cursor="hand2",
            ).grid(row=row, column=col, sticky="w", padx=(0, 20), pady=2)

        tk.Frame(dlg, bg=SEP_COLOR, height=1).pack(fill=tk.X, padx=16, pady=(8, 6))

        # ── Note ─────────────────────────────────────────────────────────
        tk.Label(
            dlg,
            text="Countries beyond Switzerland enable the European job boards scraper.",
            font=(FONT, 8), fg=SUBTEXT, bg=BG, wraplength=330, justify="left",
        ).pack(anchor="w", padx=16)

        # ── OK / Cancel ───────────────────────────────────────────────────
        btn_frame = tk.Frame(dlg, bg=BG)
        btn_frame.pack(fill=tk.X, padx=16, pady=(8, 14))

        tk.Button(
            btn_frame, text="Cancel", command=dlg.destroy,
            font=(FONT, 10), bg=BG, fg=TEXT,
            relief=tk.FLAT, bd=1, padx=12, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_frame, text="  OK  ", command=lambda: self._ok(dlg),
            font=(FONT, 10, "bold"), bg=DARK_BLUE, fg="white",
            activebackground=MID_BLUE, relief=tk.FLAT, padx=12, pady=5, cursor="hand2",
        ).pack(side=tk.RIGHT)

        parent.wait_window(dlg)

    def _ok(self, dlg: tk.Toplevel) -> None:
        self._result = [c for c, v in self._vars.items() if v.get()]
        dlg.destroy()

    @property
    def result(self) -> list[str] | None:
        return self._result


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class JobHunterApp:

    def __init__(self) -> None:
        from config import (
            PREFILTER_EXCLUDED_LOCATIONS,
            PREFILTER_EXCLUDED_TITLE,
            PREFILTER_REQUIRED,
            SEARCH_KEYWORDS,
            SWISS_SEARCH_KEYWORDS,
        )
        self._keywords: list[str]       = list(SEARCH_KEYWORDS)
        self._swiss_keywords: list[str] = list(SWISS_SEARCH_KEYWORDS)
        self._cv_path: str | None = None
        self._cv_suggestions: list[str] = []
        self._countries: list[str] = ["Switzerland"]
        self._prefilter_required: list[str]  = list(PREFILTER_REQUIRED)
        self._prefilter_excluded: list[str]  = list(PREFILTER_EXCLUDED_TITLE)
        self._excluded_locations: list[str]  = list(PREFILTER_EXCLUDED_LOCATIONS)
        self._scheduler_config: dict = {
            "enabled": False, "days": [0, 2, 4],
            "interval_weeks": 1, "hour": 13, "minute": 0, "start_date": None,
        }
        self._bg_scheduler = None
        self.output_path: str | None = None
        self._pdf_path: str | None = None
        self._cancel_event = threading.Event()
        self._running = False

        self.root = tk.Tk()
        self.root.title("Hunty")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self._update_scheduler_badge()

        self.root.update_idletasks()
        w, h = 490, 730
        x = (self.root.winfo_screenwidth()  - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _section_label(self, parent: tk.Widget, text: str) -> None:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=tk.X, pady=(10, 4))
        tk.Label(
            row, text=text.upper(),
            font=(FONT, 7, "bold"), fg=SUBTEXT, bg=BG,
        ).pack(side=tk.LEFT)
        tk.Frame(row, bg=SEP_COLOR, height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), pady=5,
        )

    def _settings_btn(self, parent, text, command) -> tk.Label:
        """Left-aligned label styled as a button, used in the Settings grid."""
        lbl = tk.Label(
            parent, text=text, anchor="w",
            font=(FONT, 9), fg=DARK_BLUE, bg=BG,
            padx=10, pady=3, cursor="hand2",
            highlightbackground=SEP_COLOR, highlightthickness=1,
        )
        lbl.bind("<Button-1>", lambda _e: command())
        lbl.bind("<Enter>",    lambda _e: lbl.config(fg=MID_BLUE))
        lbl.bind("<Leave>",    lambda _e: lbl.config(fg=DARK_BLUE))
        return lbl

    def _outline_btn(self, parent, text, command, **kw) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command,
            font=(FONT, 9), bg=BG, fg=DARK_BLUE,
            relief=tk.FLAT, bd=1,
            highlightbackground=SEP_COLOR, highlightthickness=1,
            padx=10, pady=3, cursor="hand2",
            **kw,
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = self.root

        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(root, bg=DARK_BLUE, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="HUNTY  🎯",
            font=(FONT, 16, "bold"), fg="white", bg=DARK_BLUE,
        ).pack(side=tk.LEFT, padx=20, pady=12)

        # ── Body ────────────────────────────────────────────────────────
        body = tk.Frame(root, bg=BG, padx=24, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        # ── Profile ──────────────────────────────────────────────────────
        self._section_label(body, "Profile")

        cv_row = tk.Frame(body, bg=BG)
        cv_row.pack(fill=tk.X, pady=(0, 4))
        self._cv_label = tk.Label(
            cv_row, text="No CV loaded",
            font=(FONT, 9), fg=SUBTEXT, bg=BG, anchor="w",
        )
        self._cv_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._outline_btn(cv_row, "Browse CV…", self._browse_cv).pack(side=tk.RIGHT)

        kw_row = tk.Frame(body, bg=BG)
        kw_row.pack(fill=tk.X, pady=(0, 2))
        self._kw_label = tk.Label(
            kw_row, text=self._kw_summary(),
            font=(FONT, 9), fg=SUBTEXT, bg=BG, anchor="w",
        )
        self._kw_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._outline_btn(kw_row, "Edit Keywords…", self._open_keyword_editor).pack(side=tk.RIGHT)

        filt_row = tk.Frame(body, bg=BG)
        filt_row.pack(fill=tk.X, pady=(0, 2))
        self._filter_label = tk.Label(
            filt_row, text=self._filter_summary(),
            font=(FONT, 9), fg=SUBTEXT, bg=BG, anchor="w",
        )
        self._filter_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._outline_btn(filt_row, "Edit Filters…", self._open_filter_editor).pack(side=tk.RIGHT)

        # ── Search Area ───────────────────────────────────────────────────
        self._section_label(body, "Search Area")

        ct_row = tk.Frame(body, bg=BG)
        ct_row.pack(fill=tk.X, pady=(0, 2))
        tk.Label(ct_row, text="Countries:", font=(FONT, 10), fg=TEXT, bg=BG, width=10, anchor="w").pack(side=tk.LEFT)
        self._countries_label = tk.Label(
            ct_row, text=self._countries_summary(),
            font=(FONT, 9), fg=SUBTEXT, bg=BG, anchor="w",
        )
        self._countries_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._outline_btn(ct_row, "Edit…", self._open_countries_dialog).pack(side=tk.RIGHT)

        excl_row = tk.Frame(body, bg=BG)
        excl_row.pack(fill=tk.X, pady=(0, 2))
        tk.Label(excl_row, text="Excluded locs.:", font=(FONT, 10), fg=TEXT, bg=BG, width=14, anchor="w").pack(side=tk.LEFT)
        self._excl_loc_label = tk.Label(
            excl_row, text=self._location_excl_summary(),
            font=(FONT, 9), fg=SUBTEXT, bg=BG, anchor="w",
        )
        self._excl_loc_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._outline_btn(excl_row, "Edit…", self._open_location_exclusion_editor).pack(side=tk.RIGHT)

        # ── Options ───────────────────────────────────────────────────────
        self._section_label(body, "Options")

        self.ai_var = tk.BooleanVar(value=False)
        toggle_frame = tk.Frame(body, bg=BG)
        toggle_frame.pack(anchor="w", pady=(0, 6))
        tk.Checkbutton(
            toggle_frame, text="Enable AI Scoring",
            variable=self.ai_var,
            font=(FONT, 11), bg=BG, fg=TEXT,
            activebackground=BG, selectcolor=BG, cursor="hand2",
        ).pack(anchor="w")
        tk.Label(
            toggle_frame,
            text="(Without AI scoring, jobs are scraped but not ranked or colour-coded)",
            font=(FONT, 8), fg=SUBTEXT, bg=BG,
        ).pack(anchor="w", padx=22)

        # ── Run ───────────────────────────────────────────────────────────
        self._section_label(body, "Run")

        self.start_btn = tk.Button(
            body, text="▶  Start Run",
            command=self._start_run,
            font=(FONT, 11, "bold"),
            bg=DARK_BLUE, fg="white",
            activebackground=MID_BLUE, activeforeground="white",
            relief=tk.FLAT, padx=24, pady=7, cursor="hand2", bd=0,
        )
        self.start_btn.pack(pady=(0, 8))

        bar_row = tk.Frame(body, bg=BG)
        bar_row.pack(fill=tk.X, pady=(0, 3))
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "JH.Horizontal.TProgressbar",
            troughcolor="#D9E1EC", background=MID_BLUE,
            thickness=14, borderwidth=0,
        )
        self.progress_var = tk.DoubleVar(value=0)
        # Pack right-to-left so the bar fills remaining space
        self.pct_label = tk.Label(
            bar_row, text="  0%",
            font=(FONT, 9, "bold"), fg=DARK_BLUE, bg=BG, width=5,
        )
        self.pct_label.pack(side=tk.RIGHT)
        self._step_label = tk.Label(
            bar_row, text="",
            font=(FONT, 8, "bold"), fg=MID_BLUE, bg=BG, width=5,
        )
        self._step_label.pack(side=tk.RIGHT, padx=(0, 4))
        self.progressbar = ttk.Progressbar(
            bar_row, variable=self.progress_var, maximum=100,
            style="JH.Horizontal.TProgressbar",
        )
        self.progressbar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_label = tk.Label(
            body, text="",
            font=(FONT, 9), fg=SUBTEXT, bg=BG,
            wraplength=440, justify=tk.LEFT,
        )
        self.status_label.pack(anchor="w", pady=(0, 6))

        excel_row = tk.Frame(body, bg=BG)
        excel_row.pack(fill=tk.X, pady=(0, 0))
        excel_row.columnconfigure(0, weight=1)
        excel_row.columnconfigure(1, weight=1)
        excel_row.columnconfigure(2, weight=1)

        self.open_btn = tk.Button(
            excel_row, text="📂  Open Excel",
            command=self._open_excel,
            font=(FONT, 10, "bold"),
            bg=GREEN, fg="white",
            activebackground="#1A5C38", activeforeground="white",
            disabledforeground="#A8D5B5",
            relief=tk.FLAT, padx=18, pady=6,
            state=tk.DISABLED, cursor="arrow", bd=0,
        )
        self.open_btn.grid(row=0, column=0, sticky="w")

        tk.Button(
            excel_row, text="📂  Open Previous…",
            command=self._open_previous_excel,
            font=(FONT, 10, "bold"),
            bg="#546E7A", fg="white",
            activebackground="#3D5A66", activeforeground="white",
            disabledforeground="#B0C8D0",
            relief=tk.FLAT, padx=18, pady=6, cursor="hand2", bd=0,
        ).grid(row=0, column=1)

        self.pdf_btn = tk.Button(
            excel_row, text="📄  Open PDF",
            command=self._open_pdf,
            font=(FONT, 10, "bold"),
            bg=MID_BLUE, fg="white",
            activebackground=DARK_BLUE, activeforeground="white",
            disabledforeground="#A8C4DC",
            relief=tk.FLAT, padx=18, pady=6,
            state=tk.DISABLED, cursor="arrow", bd=0,
        )
        self.pdf_btn.grid(row=0, column=2, sticky="e")

        self._last_run_label = tk.Label(
            body, text=self._load_last_run_text(),
            font=(FONT, 8), fg=SUBTEXT, bg=BG, anchor="w",
        )
        self._last_run_label.pack(anchor="w", pady=(4, 0))

        # ── Settings ─────────────────────────────────────────────────────
        self._section_label(body, "Settings")

        _C1 = 40  # gap between col 0 and col 1 (≈ 6 chars at this font size)

        sg = tk.Frame(body, bg=BG)
        sg.pack(fill=tk.X, pady=(0, 4))
        sg.columnconfigure(0, weight=1)
        sg.columnconfigure(1, weight=2)

        self._settings_btn(sg, "💾  Save Settings", self._save_settings).grid(
            row=0, column=0, sticky="ew", pady=(0, 6))
        self._settings_btn(sg, "📂  Load Settings", self._load_settings).grid(
            row=0, column=1, sticky="ew", pady=(0, 6), padx=(_C1, 0))

        self._settings_btn(sg, "🗑  Clear History", self._clear_history).grid(
            row=1, column=0, sticky="ew", pady=(0, 6))
        tk.Label(
            sg, text="All jobs appear as NEW on next run",
            font=(FONT, 8), fg=SUBTEXT, bg=BG,
        ).grid(row=1, column=1, sticky="w", pady=(0, 6), padx=(_C1, 0))

        self._settings_btn(sg, "🕐  Scheduler…", self._open_scheduler_dialog).grid(
            row=2, column=0, sticky="ew")
        _sched_col = tk.Frame(sg, bg=BG)
        _sched_col.grid(row=2, column=1, sticky="w", padx=(_C1, 0))
        self._scheduler_status_label = tk.Label(
            _sched_col, text="",
            font=(FONT, 8), fg=SUBTEXT, bg=BG,
        )
        self._scheduler_status_label.pack(side=tk.LEFT)
        self._deactivate_btn = tk.Button(
            _sched_col, text="✕ Deactivate",
            command=self._deactivate_scheduler,
            font=(FONT, 8), bg=BG, fg="#C00000",
            relief=tk.FLAT, bd=1,
            highlightbackground=SEP_COLOR, highlightthickness=1,
            padx=6, pady=2, cursor="hand2",
            state=tk.DISABLED,
        )
        self._deactivate_btn.pack(side=tk.LEFT, padx=(8, 0))

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def _kw_summary(self) -> str:
        ns, ng = len(self._swiss_keywords), len(self._keywords)
        suf = f"  (+{len(self._cv_suggestions)} from CV)" if self._cv_suggestions else ""
        return f"{ns} Swiss · {ng} global keyword{'s' if ng != 1 else ''}{suf}"

    def _countries_summary(self) -> str:
        if not self._countries:
            return "None selected"
        if len(self._countries) <= 3:
            return ", ".join(self._countries)
        return ", ".join(self._countries[:3]) + f" +{len(self._countries) - 3} more"

    def _filter_summary(self) -> str:
        return (
            f"{len(self._prefilter_required)} must-include, "
            f"{len(self._prefilter_excluded)} excluded title terms"
        )

    def _location_excl_summary(self) -> str:
        n = len(self._excluded_locations)
        if n == 0:
            return "None"
        sample = ", ".join(self._excluded_locations[:3])
        return sample if n <= 3 else f"{sample} +{n - 3} more"

    def _scheduler_summary(self) -> str:
        cfg = self._scheduler_config
        if not cfg.get("enabled"):
            return "—"
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        days = cfg.get("days", [])
        days_str = "/".join(day_names[d] for d in sorted(days)) if days else "—"
        h, m = cfg.get("hour", 13), cfg.get("minute", 0)
        n = cfg.get("interval_weeks", 1)
        freq = f" · ×{n}wk" if n > 1 else ""
        return f"{days_str} · {h:02d}:{m:02d}{freq}"

    # ------------------------------------------------------------------
    # CV upload
    # ------------------------------------------------------------------

    def _browse_cv(self) -> None:
        path = filedialog.askopenfilename(
            title="Select your CV",
            filetypes=[("CV files", "*.pdf *.docx"), ("All files", "*.*")],
        )
        if not path:
            return
        self._cv_path = path
        self._cv_label.config(text=f"Loading {os.path.basename(path)}…", fg=SUBTEXT)
        threading.Thread(target=self._extract_cv, args=(path,), daemon=True).start()

    def _extract_cv(self, path: str) -> None:
        try:
            from cv_extractor import extract_text, suggest_keywords
            text        = extract_text(path)
            suggestions = suggest_keywords(text)
            self._cv_suggestions = suggestions
            self.root.after(0, self._on_cv_done, path, len(suggestions))
        except Exception as exc:
            self.root.after(0, self._on_cv_error, str(exc))

    def _on_cv_done(self, path: str, count: int) -> None:
        self._cv_label.config(
            text=f"{os.path.basename(path)}  ({count} keyword suggestions extracted)",
            fg=TEXT,
        )
        self._kw_label.config(text=self._kw_summary())

    def _on_cv_error(self, msg: str) -> None:
        self._cv_label.config(text=f"Error reading CV: {msg}", fg="#C00000")

    # ------------------------------------------------------------------
    # Keyword editor
    # ------------------------------------------------------------------

    def _open_keyword_editor(self) -> None:
        dlg = _KeywordEditorDialog(
            self.root, self._swiss_keywords, self._keywords, self._cv_suggestions
        )
        if dlg.result is not None:
            self._swiss_keywords, self._keywords = dlg.result
            self._kw_label.config(text=self._kw_summary())

    # ------------------------------------------------------------------
    # Filter words editor
    # ------------------------------------------------------------------

    def _open_filter_editor(self) -> None:
        dlg = _FilterEditorDialog(
            self.root, self._prefilter_required, self._prefilter_excluded
        )
        if dlg.result is not None:
            self._prefilter_required, self._prefilter_excluded = dlg.result
            self._filter_label.config(text=self._filter_summary())

    # ------------------------------------------------------------------
    # Location exclusion editor
    # ------------------------------------------------------------------

    def _open_location_exclusion_editor(self) -> None:
        dlg = _LocationExclusionDialog(self.root, self._excluded_locations)
        if dlg.result is not None:
            self._excluded_locations = dlg.result
            self._excl_loc_label.config(text=self._location_excl_summary())

    # ------------------------------------------------------------------
    # Scheduler dialog + background scheduler
    # ------------------------------------------------------------------

    def _open_scheduler_dialog(self) -> None:
        dlg = _SchedulerDialog(self.root, self._scheduler_config)
        if dlg.result is not None:
            self._scheduler_config = dlg.result
            self._apply_scheduler()
            self._update_scheduler_badge()
            active = self._scheduler_config.get("enabled", False)
            self._deactivate_btn.config(state=tk.NORMAL if active else tk.DISABLED)

    def _deactivate_scheduler(self) -> None:
        self._scheduler_config["enabled"] = False
        self._apply_scheduler()
        self._update_scheduler_badge()
        self._deactivate_btn.config(state=tk.DISABLED)

    def _update_scheduler_badge(self) -> None:
        active = self._scheduler_config.get("enabled", False)
        text   = self._scheduler_summary()
        if active:
            self._scheduler_status_label.config(
                text=f"  {text}  ",
                font=(FONT, 8, "bold"), fg="white", bg=DARK_BLUE,
                relief=tk.FLAT, padx=2, pady=2,
            )
        else:
            self._scheduler_status_label.config(
                text=text,
                font=(FONT, 8), fg=SUBTEXT, bg=BG,
                relief=tk.FLAT, padx=0, pady=0,
            )

    def _apply_scheduler(self) -> None:
        """Stop any running scheduler and start a new one from current config."""
        if self._bg_scheduler is not None:
            try:
                self._bg_scheduler.shutdown(wait=False)
            except Exception:
                pass
            self._bg_scheduler = None

        cfg = self._scheduler_config
        if not cfg.get("enabled"):
            return

        days = cfg.get("days", [])
        if not days:
            return

        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from config import SCHEDULE_TIMEZONE

        day_abbrs = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        days_str  = ",".join(day_abbrs[d] for d in sorted(days))
        interval  = cfg.get("interval_weeks", 1)
        start_iso = cfg.get("start_date")

        def _scheduled_job() -> None:
            if interval > 1 and start_iso:
                from datetime import date, timedelta
                today          = date.today()
                start          = date.fromisoformat(start_iso)
                start_monday   = start   - timedelta(days=start.weekday())
                current_monday = today   - timedelta(days=today.weekday())
                weeks_elapsed  = (current_monday - start_monday).days // 7
                if weeks_elapsed % interval != 0:
                    return
            # Don't start a new run while one is already in progress
            if self._running:
                return
            self.root.after(0, self._start_run)

        self._bg_scheduler = BackgroundScheduler(timezone=SCHEDULE_TIMEZONE)
        self._bg_scheduler.add_job(
            _scheduled_job,
            trigger=CronTrigger(
                day_of_week=days_str,
                hour=cfg.get("hour", 13),
                minute=cfg.get("minute", 0),
                timezone=SCHEDULE_TIMEZONE,
            ),
            misfire_grace_time=3600,
        )
        self._bg_scheduler.start()

    def _on_close(self) -> None:
        if self._bg_scheduler is not None:
            try:
                self._bg_scheduler.shutdown(wait=False)
            except Exception:
                pass
        self.root.destroy()

    # ------------------------------------------------------------------
    # Countries dialog
    # ------------------------------------------------------------------

    def _open_countries_dialog(self) -> None:
        dlg = _CountriesDialog(self.root, self._countries)
        if dlg.result is not None:
            self._countries = dlg.result or ["Switzerland"]
            self._countries_label.config(text=self._countries_summary())

    # ------------------------------------------------------------------
    # Clear seen-job history
    # ------------------------------------------------------------------

    def _clear_history(self) -> None:
        from config import OUTPUT_DIR
        history_path = os.path.join(OUTPUT_DIR, "seen_jobs_history.json")
        if not os.path.isfile(history_path):
            messagebox.showinfo("Clear History", "No history file found — already clear.")
            return
        if messagebox.askyesno(
            "Clear History",
            "All jobs will appear as NEW on the next run.\n\nClear seen-job history?",
        ):
            try:
                os.remove(history_path)
                self.status_label.config(
                    text="History cleared — all jobs will appear as NEW next run.",
                    fg=SUBTEXT,
                )
            except Exception as exc:
                messagebox.showerror("Error", f"Could not delete history:\n{exc}")

    # ------------------------------------------------------------------
    # Run controls
    # ------------------------------------------------------------------

    def _start_run(self) -> None:
        self._cancel_event.clear()
        self._running = True
        self.start_btn.config(
            text="⬛  Stop", command=self._cancel_run,
            bg="#8B0000", activebackground="#6B0000",
        )
        self.open_btn.config(state=tk.DISABLED, cursor="arrow")
        self.pdf_btn.config(state=tk.DISABLED, cursor="arrow")
        self.output_path = None
        self._pdf_path = None
        self.progress_var.set(0)
        self.pct_label.config(text="  0%")
        self._step_label.config(text="")
        self.status_label.config(text="Starting…", fg=SUBTEXT)

        threading.Thread(
            target=self._run_pipeline,
            args=(
                self.ai_var.get(),
                list(self._keywords) or None,
                list(self._swiss_keywords) or None,
                "Switzerland",
                list(self._countries) or None,
                list(self._prefilter_required),
                list(self._prefilter_excluded),
                list(self._excluded_locations),
            ),
            daemon=True,
        ).start()

    def _cancel_run(self) -> None:
        self._cancel_event.set()
        self.start_btn.config(state=tk.DISABLED, text="  Cancelling…")
        self.status_label.config(text="Cancelling — finishing current source, then exporting…", fg=SUBTEXT)

    def _open_excel(self) -> None:
        if self.output_path and os.path.exists(self.output_path):
            os.startfile(self.output_path)

    def _open_pdf(self) -> None:
        if self._pdf_path and os.path.exists(self._pdf_path):
            os.startfile(self._pdf_path)

    def _open_previous_excel(self) -> None:
        from config import OUTPUT_DIR
        initial = OUTPUT_DIR if os.path.isdir(OUTPUT_DIR) else "."
        path = filedialog.askopenfilename(
            title="Open previous results",
            initialdir=initial,
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if path:
            os.startfile(path)

    # ------------------------------------------------------------------
    # Settings save / load
    # ------------------------------------------------------------------

    def _save_settings(self) -> None:
        os.makedirs(_SETTINGS_DIR, exist_ok=True)
        path = filedialog.asksaveasfilename(
            title="Save Search Settings",
            initialdir=_SETTINGS_DIR,
            defaultextension=".json",
            filetypes=[("JSON settings", "*.json")],
        )
        if not path:
            return
        data = {
            "name":                os.path.splitext(os.path.basename(path))[0],
            "saved_at":            datetime.now().isoformat(timespec="seconds"),
            "countries":           list(self._countries),
            "keywords":            list(self._keywords),
            "swiss_keywords":      list(self._swiss_keywords),
            "enable_ai":           bool(self.ai_var.get()),
            "prefilter_required":  list(self._prefilter_required),
            "prefilter_excluded":  list(self._prefilter_excluded),
            "excluded_locations":  list(self._excluded_locations),
            "scheduler":           dict(self._scheduler_config),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Saved", f"Settings saved:\n{os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def _load_settings(self) -> None:
        os.makedirs(_SETTINGS_DIR, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Load Search Settings",
            initialdir=_SETTINGS_DIR,
            filetypes=[("JSON settings", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror("Load Error", f"Could not read settings:\n{exc}")
            return

        if isinstance(data.get("keywords"), list):
            self._keywords = data["keywords"]
            self._kw_label.config(text=self._kw_summary())
        if isinstance(data.get("swiss_keywords"), list):
            self._swiss_keywords = data["swiss_keywords"]
            self._kw_label.config(text=self._kw_summary())
        if isinstance(data.get("countries"), list):
            self._countries = data["countries"] or ["Switzerland"]
            self._countries_label.config(text=self._countries_summary())
        if "enable_ai" in data:
            self.ai_var.set(bool(data["enable_ai"]))
        if isinstance(data.get("prefilter_required"), list):
            self._prefilter_required = data["prefilter_required"]
            self._filter_label.config(text=self._filter_summary())
        if isinstance(data.get("prefilter_excluded"), list):
            self._prefilter_excluded = data["prefilter_excluded"]
            self._filter_label.config(text=self._filter_summary())
        if isinstance(data.get("excluded_locations"), list):
            self._excluded_locations = data["excluded_locations"]
            self._excl_loc_label.config(text=self._location_excl_summary())
        if isinstance(data.get("scheduler"), dict):
            self._scheduler_config = data["scheduler"]
            self._apply_scheduler()
            self._update_scheduler_badge()
            active = self._scheduler_config.get("enabled", False)
            self._deactivate_btn.config(state=tk.NORMAL if active else tk.DISABLED)

        name = data.get("name") or os.path.splitext(os.path.basename(path))[0]
        self.status_label.config(text=f"Settings loaded: {name}", fg=SUBTEXT)

    # ------------------------------------------------------------------
    # Pipeline thread
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        enable_ai: bool,
        keywords: list[str] | None,
        swiss_keywords: list[str] | None,
        location: str,
        countries: list[str] | None,
        prefilter_required: list[str] | None = None,
        prefilter_excluded: list[str] | None = None,
        excluded_locations: list[str] | None = None,
    ) -> None:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from main import run_job_scraper

            result = run_job_scraper(
                progress_callback=self._on_progress,
                enable_ai_scoring=enable_ai,
                keywords_override=keywords,
                swiss_keywords_override=swiss_keywords,
                location_override=location,
                countries_override=countries,
                prefilter_required_override=prefilter_required,
                prefilter_excluded_override=prefilter_excluded,
                prefilter_excluded_locations_override=excluded_locations,
                cancel_event=self._cancel_event,
            )
            path, new_count = result if isinstance(result, tuple) else (result, None)

            pdf_path = None
            if path:
                try:
                    from pdf_writer import generate_pdf, load_jobs_from_excel
                    jobs = load_jobs_from_excel(path, new_only=True)
                    if not jobs:
                        jobs = load_jobs_from_excel(path, new_only=False)
                    if jobs:
                        pdf_path = path.replace(".xlsx", ".pdf")
                        generate_pdf(jobs, pdf_path)
                except Exception as pdf_exc:
                    logging.getLogger(__name__).warning("PDF generation failed: %s", pdf_exc)

            self.root.after(0, self._on_complete, path, new_count, pdf_path)
        except Exception as exc:
            self.root.after(0, self._on_error, str(exc))

    # ------------------------------------------------------------------
    # Thread → GUI callbacks
    # ------------------------------------------------------------------

    def _on_progress(self, pct: float, message: str) -> None:
        self.root.after(0, self._apply_progress, pct, message)

    def _apply_progress(self, pct: float, message: str) -> None:
        self.progress_var.set(pct)
        self.pct_label.config(text=f"{int(pct):3d}%")
        m = re.match(r'^\[(\d+)/(\d+)\]\s*(.*)', message)
        if m:
            self._step_label.config(text=f"{m.group(1)}/{m.group(2)}")
            self.status_label.config(text=m.group(3), fg=SUBTEXT)
        else:
            self.status_label.config(text=message, fg=SUBTEXT)

    def _on_complete(self, output_path: str | None, new_count: int | None = None, pdf_path: str | None = None) -> None:
        self._running = False
        self.progress_var.set(100)
        self.pct_label.config(text="100%")
        self._step_label.config(text="")
        self.start_btn.config(
            state=tk.NORMAL, text="▶  Start Run", command=self._start_run,
            bg=DARK_BLUE, activebackground=MID_BLUE,
        )
        if output_path:
            self.output_path = output_path
            self._pdf_path = pdf_path
            name      = os.path.basename(output_path)
            new_label = f"  —  {new_count} new" if new_count is not None else ""
            self.status_label.config(text=f"✓  Saved: {name}{new_label}", fg=GREEN)
            self.open_btn.config(state=tk.NORMAL, cursor="hand2")
            if pdf_path and os.path.exists(pdf_path):
                self.pdf_btn.config(state=tk.NORMAL, cursor="hand2")
            self._save_last_run(new_count)
            self._last_run_label.config(text=self._load_last_run_text())
        else:
            self.status_label.config(text="Run complete — no jobs found.", fg=SUBTEXT)

    def _on_error(self, msg: str) -> None:
        self._running = False
        self._step_label.config(text="")
        self.status_label.config(text=f"Error: {msg}", fg="#C00000")
        self.start_btn.config(
            state=tk.NORMAL, text="▶  Start Run", command=self._start_run,
            bg=DARK_BLUE, activebackground=MID_BLUE,
        )

    # ------------------------------------------------------------------
    # Last-run persistence
    # ------------------------------------------------------------------

    def _load_last_run_text(self) -> str:
        from config import OUTPUT_DIR
        path = os.path.join(OUTPUT_DIR, "last_run.json")
        if not os.path.isfile(path):
            return "Last run: —"
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            ts  = data.get("timestamp", "")
            new = data.get("new_count")
            if ts:
                dt     = datetime.fromisoformat(ts)
                ts_str = dt.strftime("%d %b %H:%M")
                new_str = f" — {new} new" if new is not None else ""
                return f"Last run: {ts_str}{new_str}"
        except Exception:
            pass
        return "Last run: —"

    def _save_last_run(self, new_count: int | None) -> None:
        from config import OUTPUT_DIR
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, "last_run.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "new_count": new_count,
                }, f)
        except Exception:
            pass

    # ------------------------------------------------------------------

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    app = JobHunterApp()
    app.run()