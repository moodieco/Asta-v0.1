"""Classic-Tk widget shim.

Why this exists: on macOS 26 with the Tk 8.5 that ships in Command Line Tools, the
``clam`` ttk theme lays every widget out but paints nothing - the window comes out
as a uniform dark rectangle. Native ``aqua`` paints but ignores per-widget colour,
which is the grey-on-grey the user saw first.

Classic Tk widgets (``tk.Frame``, ``tk.Label``, ``tk.Text``, ``tk.Entry``,
``tk.LabelFrame``) are drawn by Tk itself and honour ``bg``/``fg``, so the UI is
built from those. ``tk.Button`` is native-drawn and ignores colour, so buttons are
a Frame + Label pair with mouse bindings, and checkboxes/comboboxes are rebuilt the
same way.

The classes below accept the ttk-ish arguments the call sites already use
(``style=``, ``padding=``, ``state=``), so screens can stay readable.
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable, Dict, Optional

from asta.launcher.theme import (
    ACCENT,
    ACCENT_SOFT,
    ACCENT_TEXT,
    BG,
    BORDER,
    DANGER,
    DANGER_SOFT,
    DIM,
    FAINT,
    FG,
    FIELD,
    FONT,
    FONT_HEADING,
    FONT_MONO,
    FONT_SMALL,
    FONT_TITLE,
    SURFACE,
    SURFACE_2,
    WARN,
)

__all__ = [
    "Button",
    "Checkbutton",
    "Combobox",
    "Entry",
    "Frame",
    "Label",
    "LabelFrame",
    "Separator",
    "Style",
]

LABEL_STYLES: Dict[str, Dict[str, Any]] = {
    "Title.TLabel": {"font": FONT_TITLE, "fg": FG},
    "Heading.TLabel": {"font": FONT_HEADING, "fg": FG},
    "Muted.TLabel": {"font": FONT_SMALL, "fg": DIM},
    "Faint.TLabel": {"font": FONT_SMALL, "fg": FAINT},
    "Mono.TLabel": {"font": FONT_MONO, "fg": FG},
    "MonoDim.TLabel": {"font": FONT_MONO, "fg": DIM},
    "StatusOk.TLabel": {"font": FONT_HEADING, "fg": ACCENT},
    "StatusDown.TLabel": {"font": FONT_HEADING, "fg": DANGER},
    "": {"font": FONT, "fg": FG},
}

BUTTON_STYLES: Dict[str, Dict[str, str]] = {
    "Accent.TButton": {"bg": ACCENT, "fg": ACCENT_TEXT, "hover": "#4ee0ae", "border": ACCENT, "off_bg": ACCENT_SOFT, "off_fg": DIM},
    "Danger.TButton": {"bg": DANGER_SOFT, "fg": DANGER, "hover": "#3a1b21", "border": "#4a2028", "off_bg": SURFACE, "off_fg": FAINT},
    "": {"bg": SURFACE_2, "fg": FG, "hover": BORDER, "border": BORDER, "off_bg": SURFACE, "off_fg": FAINT},
}


class Style:  # minimal stand-in so `theme.apply()` callers keep working
    def __init__(self, root: Optional[tk.Misc] = None):
        self.root = root

    def theme_use(self, name: Optional[str] = None) -> Any:
        return "classic" if name is None else None

    def configure(self, *args: Any, **kwargs: Any) -> None:
        return None

    def map(self, *args: Any, **kwargs: Any) -> None:
        return None

    def lookup(self, style: str, option: str, default: Any = "") -> Any:
        if option in ("background", "bg"):
            if style.startswith("Card"):
                return SURFACE
            if style.startswith("Accent"):
                return ACCENT
            if style.startswith("Danger"):
                return DANGER_SOFT
            return SURFACE_2
        if option in ("foreground", "fg"):
            return DANGER if style.startswith("Danger") else FG
        return default


def _apply_common(widget: tk.Widget, **kwargs: Any) -> None:
    widget.configure(**kwargs)


class Frame(tk.Frame):
    def __init__(self, master: Any = None, style: str = "", padding: Any = None, **kwargs: Any):
        bg = SURFACE if style.startswith("Card") else BG
        pad = padding if isinstance(padding, int) else 0
        if isinstance(padding, tuple) and len(padding) == 2:
            kwargs.setdefault("padx", padding[1])
            kwargs.setdefault("pady", padding[0])
        kwargs.setdefault("padx", pad)
        kwargs.setdefault("pady", pad)
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, **kwargs)


class Label(tk.Label):
    def __init__(self, master: Any = None, style: str = "", **kwargs: Any):
        spec = LABEL_STYLES.get(style, LABEL_STYLES[""])
        parent_bg = master.cget("bg") if master is not None and "bg" in master.keys() else BG
        kwargs.setdefault("bg", parent_bg)
        kwargs.setdefault("fg", spec["fg"])
        kwargs.setdefault("font", spec["font"])
        kwargs.setdefault("anchor", "w")
        super().__init__(master, **kwargs)

    def configure(self, **kwargs: Any) -> None:  # noqa: D401 - tk API
        if "style" in kwargs:
            spec = LABEL_STYLES.get(kwargs.pop("style"), LABEL_STYLES[""])
            kwargs.setdefault("font", spec["font"])
            kwargs.setdefault("fg", spec["fg"])
        super().configure(**kwargs)


class LabelFrame(tk.LabelFrame):
    def __init__(self, master: Any = None, text: str = "", padding: Any = 10, style: str = "", **kwargs: Any):
        bg = SURFACE if style.startswith("Card") else BG
        pad = padding if isinstance(padding, int) else 0
        super().__init__(
            master,
            text=text,
            bg=bg,
            fg=DIM,
            font=FONT_SMALL,
            bd=1,
            relief="solid",
            highlightthickness=0,
            labelanchor="nw",
            padx=pad,
            pady=pad // 2 if pad else 0,
        )


class Separator(tk.Frame):
    def __init__(self, master: Any = None, **kwargs: Any):
        super().__init__(master, bg=BORDER, height=1, highlightthickness=0, bd=0, **kwargs)


class Button(tk.Frame):
    """Flat button: Frame + Label with hover/press/disabled states."""

    def __init__(
        self,
        master: Any = None,
        text: str = "",
        command: Optional[Callable[[], None]] = None,
        style: str = "",
        **kwargs: Any,
    ):
        self._spec = BUTTON_STYLES.get(style, BUTTON_STYLES[""])
        self._state = "normal"
        self._command = command
        width = kwargs.pop("width", None)
        super().__init__(master, bg=self._spec["border"], highlightthickness=0, bd=0, cursor="pointinghand")
        label_options: Dict[str, Any] = {
            "text": text,
            "bg": self._spec["bg"],
            "fg": self._spec["fg"],
            "font": FONT,
            "anchor": "center",
            "padx": 12,
            "pady": 7,
            "cursor": "pointinghand",
        }
        if width:
            label_options["width"] = int(width)
        self._label = tk.Label(self, **label_options)
        self._label.pack(fill="both", expand=True, padx=1, pady=1)
        for widget in (self, self._label):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<ButtonPress-1>", self._on_press)
            widget.bind("<ButtonRelease-1>", self._on_release)

    # -- state ------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self._state == "normal"

    def _paint(self, bg: str, fg: str) -> None:
        self._label.configure(bg=bg, fg=fg)

    def _on_enter(self, _event: Any = None) -> None:
        if self.enabled:
            self._paint(self._spec["hover"], self._spec["fg"])

    def _on_leave(self, _event: Any = None) -> None:
        if self.enabled:
            self._paint(self._spec["bg"], self._spec["fg"])

    def _on_press(self, _event: Any = None) -> None:
        if self.enabled:
            self._paint(self._spec["border"], self._spec["fg"])

    def _on_release(self, _event: Any = None) -> None:
        if not self.enabled:
            return
        self._paint(self._spec["bg"], self._spec["fg"])
        if self._command is not None:
            self._command()

    # -- ttk-ish API ------------------------------------------------------
    def configure(self, **kwargs: Any) -> None:  # noqa: D401 - tk API
        if "state" in kwargs:
            self._state = str(kwargs.pop("state"))
            if self.enabled:
                super().configure(bg=self._spec["border"])
                self._paint(self._spec["bg"], self._spec["fg"])
            else:
                super().configure(bg=SURFACE)
                self._paint(self._spec["off_bg"], self._spec["off_fg"])
        if "text" in kwargs:
            self._label.configure(text=kwargs.pop("text"))
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if kwargs:
            super().configure(**kwargs)

    config = configure

    def cget(self, key: str) -> Any:
        if key == "state":
            return self._state
        if key == "text":
            return self._label.cget("text")
        return super().cget(key)

    def invoke(self) -> None:
        if self.enabled and self._command is not None:
            self._command()


class Entry(tk.Entry):
    def __init__(self, master: Any = None, **kwargs: Any):
        parent_bg = master.cget("bg") if master is not None and "bg" in master.keys() else BG
        super().__init__(
            master,
            bg=FIELD,
            fg=FG,
            insertbackground=FG,
            disabledbackground=SURFACE,
            disabledforeground=FAINT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            bd=0,
            font=FONT,
            **kwargs,
        )
        if parent_bg not in (BG, SURFACE):
            self.configure(bg=FIELD)


class Checkbutton(tk.Frame):
    """Checkbox drawn as a small box glyph + label (native tk checkbuttons ignore colours)."""

    def __init__(self, master: Any = None, text: str = "", variable: Optional[tk.Variable] = None, **kwargs: Any):
        self.variable = variable or tk.BooleanVar(value=False)
        super().__init__(master, bg=master.cget("bg"), highlightthickness=0, bd=0, cursor="pointinghand")
        self._box = tk.Label(
            self,
            text="",
            width=2,
            bg=FIELD,
            fg=ACCENT,
            font=FONT,
            anchor="center",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            cursor="pointinghand",
        )
        self._box.pack(side="left")
        self._text = tk.Label(
            self,
            text=text,
            bg=master.cget("bg"),
            fg=FG,
            font=FONT,
            anchor="w",
            cursor="pointinghand",
        )
        self._text.pack(side="left", padx=(8, 0))
        for widget in (self, self._box, self._text):
            widget.bind("<Button-1>", self._toggle)
        self._sync()

    def _sync(self) -> None:
        self._box.configure(text="✓" if self.variable.get() else "", fg=ACCENT if self.variable.get() else FIELD)

    def _toggle(self, _event: Any = None) -> None:
        self.variable.set(not bool(self.variable.get()))
        self._sync()


class Combobox(tk.OptionMenu):
    """Read-only option list that matches the palette (tk.OptionMenu accepts colours)."""

    def __init__(self, master: Any = None, textvariable: Optional[tk.Variable] = None,
                 values: Optional[list] = None, **kwargs: Any):
        kwargs.pop("state", None)  # ttk.Combobox option; OptionMenu is always select-only
        width = kwargs.pop("width", None)
        self._variable = textvariable or tk.StringVar()
        values = values or [""]
        super().__init__(master, self._variable, *values)
        menu = self["menu"]
        menu.configure(bg=SURFACE, fg=FG, activebackground=ACCENT_SOFT, activeforeground=ACCENT, bd=0)
        self.configure(
            bg=SURFACE_2,
            fg=FG,
            activebackground=BORDER,
            activeforeground=FG,
            highlightthickness=0,
            bd=0,
            font=FONT_SMALL,
            anchor="w",
            padx=8,
        )
        if width:
            self.configure(width=int(width))
        self._variable.set(values[0])


def make_style(root: tk.Misc) -> Style:
    return Style(root)


def warn_color() -> str:
    return WARN
