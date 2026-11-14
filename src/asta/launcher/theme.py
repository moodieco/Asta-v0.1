"""One dark theme for every Tk window in the launcher.

macOS ships Tk 8.5, whose ``aqua`` theme paints every control the same system grey
and ignores most colour options. Switching to ``clam`` and styling each widget class
explicitly is the only way to get a deliberate look on that combination.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

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


def apply(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:  # pragma: no cover - exotic Tk builds
        pass

    root.configure(background=BG)  # type: ignore[attr-defined]

    style.configure(".", background=BG, foreground=FG, font=FONT, borderwidth=0)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE, relief="solid", borderwidth=1)
    style.configure("Header.TFrame", background=BG)

    style.configure("TLabel", background=BG, foreground=FG, font=FONT)
    style.configure("Title.TLabel", background=BG, foreground=FG, font=FONT_TITLE)
    style.configure("Heading.TLabel", background=BG, foreground=FG, font=FONT_HEADING)
    style.configure("Muted.TLabel", background=BG, foreground=DIM, font=FONT_SMALL)
    style.configure("Faint.TLabel", background=BG, foreground=FAINT, font=FONT_SMALL)
    style.configure("Mono.TLabel", background=BG, foreground=FG, font=FONT_MONO)
    style.configure("MonoDim.TLabel", background=BG, foreground=DIM, font=FONT_MONO)
    style.configure("StatusOk.TLabel", background=BG, foreground=ACCENT, font=FONT_HEADING)
    style.configure("StatusDown.TLabel", background=BG, foreground=DANGER, font=FONT_HEADING)

    style.configure(
        "TButton",
        background=SURFACE_2,
        foreground=FG,
        bordercolor=BORDER,
        lightcolor=SURFACE_2,
        darkcolor=SURFACE_2,
        relief="flat",
        padding=(12, 7),
        font=FONT,
    )
    style.map(
        "TButton",
        background=[("pressed", BORDER), ("active", BORDER), ("disabled", SURFACE)],
        foreground=[("disabled", FAINT)],
        bordercolor=[("active", ACCENT)],
    )
    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground=ACCENT_TEXT,
        bordercolor=ACCENT,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        font=("Helvetica Neue", 13, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", "#2bbd8b"), ("active", "#4ee0ae"), ("disabled", ACCENT_SOFT)],
        foreground=[("disabled", DIM)],
    )
    style.configure(
        "Danger.TButton",
        background=DANGER_SOFT,
        foreground=DANGER,
        bordercolor="#4a2028",
        lightcolor=DANGER_SOFT,
        darkcolor=DANGER_SOFT,
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#3a1b21"), ("disabled", SURFACE)],
        foreground=[("disabled", FAINT)],
    )

    style.configure(
        "Card.TLabelframe",
        background=SURFACE,
        bordercolor=BORDER,
        relief="solid",
        borderwidth=1,
        padding=10,
    )
    style.configure("Card.TLabelframe.Label", background=SURFACE, foreground=DIM, font=FONT_SMALL)
    style.configure("TLabelframe", background=BG, bordercolor=BORDER, relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=BG, foreground=DIM, font=FONT_SMALL)

    style.configure(
        "TEntry",
        fieldbackground=FIELD,
        background=FIELD,
        foreground=FG,
        insertcolor=FG,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=6,
    )
    style.map("TEntry", bordercolor=[("focus", ACCENT)])

    style.configure(
        "TCombobox",
        fieldbackground=FIELD,
        background=SURFACE_2,
        foreground=FG,
        arrowcolor=DIM,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=5,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", FIELD)],
        foreground=[("readonly", FG)],
        bordercolor=[("focus", ACCENT)],
    )

    style.configure(
        "TCheckbutton",
        background=BG,
        foreground=FG,
        indicatorbackground=FIELD,
        indicatorforeground=ACCENT,
        focuscolor=BG,
        font=FONT,
    )
    style.map(
        "TCheckbutton",
        background=[("active", BG)],
        indicatorbackground=[("selected", ACCENT_SOFT), ("active", FIELD)],
    )

    style.configure("TSeparator", background=BORDER)
    style.configure("Horizontal.TSeparator", background=BORDER)
    style.configure("Vertical.TScrollbar", background=SURFACE_2, troughcolor=BG, bordercolor=BG)
    return style


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
