"""
select_countries.py — GUI for choosing which European countries to include
in the job search.  Saves the selection directly to config.py.

Run:  python select_countries.py
"""
import re
import tkinter as tk
from pathlib import Path

import openpyxl

_CONFIG  = Path(__file__).parent / "config.py"
_EXCEL   = Path(__file__).parent / "European_Job_Search_Websites.xlsx"
_SKIP    = {"Pan-European"}   # not a real country to select


def _load_countries() -> list[str]:
    wb = openpyxl.load_workbook(_EXCEL)
    ws = wb.active
    seen, countries = set(), []
    for row in ws.iter_rows(min_row=2, values_only=True):
        c = str(row[0] or "").strip()
        if c and c not in _SKIP and c not in seen:
            seen.add(c)
            countries.append(c)
    return sorted(countries)


def _read_current() -> list[str]:
    """Parse EUROPEAN_COUNTRIES from config.py."""
    text = _CONFIG.read_text(encoding="utf-8")
    m = re.search(r"EUROPEAN_COUNTRIES\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not m:
        return []
    items = re.findall(r'["\']([^"\']+)["\']', m.group(1))
    return items


def _save_to_config(selected: list[str]) -> None:
    text = _CONFIG.read_text(encoding="utf-8")
    if selected:
        inner = ", ".join(f'"{c}"' for c in selected)
        new_val = f"[{inner}]"
    else:
        new_val = "[]"
    new_text = re.sub(
        r"(EUROPEAN_COUNTRIES\s*=\s*)\[.*?\]",
        rf"\g<1>{new_val}",
        text,
        flags=re.DOTALL,
    )
    _CONFIG.write_text(new_text, encoding="utf-8")


def main() -> None:
    countries = _load_countries()
    current   = set(_read_current())

    root = tk.Tk()
    root.title("European Job Search — Country Selector")
    root.resizable(False, False)

    # ── header ──────────────────────────────────────────────────────────────
    header = tk.Label(
        root,
        text="Select countries to include in the European job search",
        font=("Segoe UI", 11, "bold"),
        padx=14, pady=10,
    )
    header.pack(anchor="w")

    # ── scrollable checkbox area ─────────────────────────────────────────────
    frame_outer = tk.Frame(root)
    frame_outer.pack(fill="both", expand=True, padx=14)

    canvas = tk.Canvas(frame_outer, width=340, height=360, highlightthickness=0)
    scrollbar = tk.Scrollbar(frame_outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas)
    canvas.create_window((0, 0), window=inner, anchor="nw")

    vars_: dict[str, tk.BooleanVar] = {}
    for country in countries:
        var = tk.BooleanVar(value=country in current)
        vars_[country] = var
        tk.Checkbutton(
            inner, text=country, variable=var,
            font=("Segoe UI", 10), anchor="w",
        ).pack(fill="x", padx=6, pady=1)

    inner.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))

    # ── select all / clear ───────────────────────────────────────────────────
    btn_row = tk.Frame(root)
    btn_row.pack(fill="x", padx=14, pady=(6, 0))

    def select_all():
        for v in vars_.values():
            v.set(True)

    def clear_all():
        for v in vars_.values():
            v.set(False)

    tk.Button(btn_row, text="Select All", width=12, command=select_all).pack(side="left", padx=(0, 6))
    tk.Button(btn_row, text="Clear All",  width=12, command=clear_all).pack(side="left")

    # ── status label ─────────────────────────────────────────────────────────
    status = tk.Label(root, text="", font=("Segoe UI", 9), fg="green", pady=4)
    status.pack()

    # ── save button ──────────────────────────────────────────────────────────
    def save():
        selected = [c for c, v in vars_.items() if v.get()]
        _save_to_config(selected)
        if selected:
            status.config(text=f"Saved: {', '.join(selected)}", fg="green")
        else:
            status.config(text="Saved: all countries (empty list = search all)", fg="blue")

    tk.Button(
        root, text="Save Selection",
        font=("Segoe UI", 10, "bold"),
        bg="#1F4E79", fg="white",
        padx=16, pady=6,
        command=save,
    ).pack(pady=(0, 12))

    root.mainloop()


if __name__ == "__main__":
    main()
