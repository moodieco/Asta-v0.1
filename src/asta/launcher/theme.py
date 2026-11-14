"""One dark palette for every launcher window.

Two macOS/Tk facts drive this module:

* Tk 8.5's ``aqua`` theme paints, but ignores per-widget colour - every control
  came out the same grey.
* The ``clam`` theme accepts colour, but on macOS 26 lays widgets out while drawing
  nothing at all: the window renders as an empty dark rectangle.

So the palette lives here and the widgets are classic Tk (``tk.Frame``/``tk.Label``
via :mod:`asta.launcher.flatui`), which Tk draws itself and colours correctly.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

# Palette mirrors web/src/index.css so the launcher and the dashboard feel related.
BG = "#0b1012"
SURFACE = "#111819"
SURFACE_2 = "#16201f"
FIELD = "#0e1516"
BORDER = "#223130"
FG = "#e7efec"
DIM = "#8ba09a"
FAINT = "#5d6f6a"
ACCENT = "#34d399"
ACCENT_TEXT = "#0b2b22"
ACCENT_SOFT = "#12312a"
DANGER = "#fb7185"
DANGER_SOFT = "#2e161b"
WARN = "#fbbf24"

FONT = ("Helvetica Neue", 13)
FONT_SMALL = ("Helvetica Neue", 11)
FONT_TITLE = ("Helvetica Neue", 24, "bold")
FONT_HEADING = ("Helvetica Neue", 15, "bold")
FONT_MONO = ("Menlo", 11)


def apply(root: tk.Misc) -> Any:
    """Set the window background and return the flat-widget Style stand-in."""
    from asta.launcher.flatui import Style

    root.configure(background=BG)  # type: ignore[attr-defined]
    return Style(root)


def text_widget(parent: tk.Misc, **kwargs) -> tk.Text:
    """A Text widget that matches the theme (tk.Text ignores ttk styling)."""
    options = {
        "background": FIELD,
        "foreground": FG,
        "insertbackground": FG,
        "selectbackground": ACCENT_SOFT,
        "selectforeground": FG,
        "highlightthickness": 1,
        "highlightbackground": BORDER,
        "highlightcolor": ACCENT,
        "relief": "flat",
        "font": FONT_MONO,
        "padx": 8,
        "pady": 6,
    }
    options.update(kwargs)
    return tk.Text(parent, **options)
