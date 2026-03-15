"""LaserMac — Modern dark theme system.

Centralized color palette, typography, and component style helpers
for a professional macOS-native look.
"""

from __future__ import annotations

import customtkinter as ctk

# ── Color Palette ───────────────────────────────────────────────────

COLORS = {
    # Backgrounds
    "bg_base": "#0F0F0F",
    "bg_panel": "#161616",
    "bg_card": "#1E1E1E",
    "bg_elevated": "#252525",
    "bg_hover": "#2A2A2A",

    # Borders
    "border": "#2E2E2E",
    "border_focus": "#4A4A4A",

    # Text
    "text_primary": "#F0F0F0",
    "text_secondary": "#A0A0A0",
    "text_muted": "#606060",

    # Accent
    "accent": "#FF6B35",
    "accent_hover": "#FF8C5A",
    "accent_muted": "#FF6B3520",

    # Operations
    "cut": "#FF3B3B",
    "cut_bg": "#FF3B3B18",
    "engrave": "#3B8EFF",
    "engrave_bg": "#3B8EFF18",
    "mark": "#34C759",
    "mark_bg": "#34C75918",

    # Status
    "connected": "#34C759",
    "disconnected": "#FF3B3B",
    "idle": "#A0A0A0",
    "running": "#FF9500",

    # Canvas
    "canvas_bg": "#0A0A0A",
    "canvas_grid": "#1A1A1A",
    "canvas_work_area": "#2A2A2A",
}

# ── Typography ──────────────────────────────────────────────────────

FONTS = {
    "title": ("", 15, "bold"),
    "heading": ("", 13, "bold"),
    "label": ("", 12),
    "small": ("", 11),
    "muted": ("", 11),
    "mono": ("Menlo", 13),
    "mono_small": ("Menlo", 11),
    "mono_large": ("Menlo", 18),
}


# ── Theme Application ──────────────────────────────────────────────

def apply_theme(root: ctk.CTk) -> None:
    """Apply the LaserMac dark theme to the root window."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root.configure(fg_color=COLORS["bg_base"])


# ── Style Helpers ───────────────────────────────────────────────────

def card_style(**overrides) -> dict:
    """Return kwargs for a modern Card frame."""
    style = {
        "fg_color": COLORS["bg_card"],
        "corner_radius": 10,
        "border_width": 1,
        "border_color": COLORS["border"],
    }
    style.update(overrides)
    return style


def panel_style(**overrides) -> dict:
    """Return kwargs for a panel (sidebar/properties)."""
    style = {
        "fg_color": COLORS["bg_panel"],
        "corner_radius": 0,
    }
    style.update(overrides)
    return style


def button_style(variant: str = "default", **overrides) -> dict:
    """Return kwargs for themed buttons.

    Variants: default, primary, danger, ghost, accent.
    """
    styles = {
        "default": {
            "fg_color": COLORS["bg_elevated"],
            "hover_color": COLORS["bg_hover"],
            "text_color": COLORS["text_primary"],
            "corner_radius": 8,
        },
        "primary": {
            "fg_color": COLORS["accent"],
            "hover_color": COLORS["accent_hover"],
            "text_color": "#FFFFFF",
            "corner_radius": 8,
        },
        "danger": {
            "fg_color": "#DA3633",
            "hover_color": "#F85149",
            "text_color": "#FFFFFF",
            "corner_radius": 8,
        },
        "ghost": {
            "fg_color": "transparent",
            "hover_color": COLORS["bg_hover"],
            "text_color": COLORS["text_secondary"],
            "corner_radius": 8,
        },
        "accent": {
            "fg_color": COLORS["accent"],
            "hover_color": COLORS["accent_hover"],
            "text_color": "#FFFFFF",
            "corner_radius": 8,
        },
        "connect": {
            "fg_color": COLORS["connected"],
            "hover_color": "#4CD964",
            "text_color": "#FFFFFF",
            "corner_radius": 8,
        },
        "disconnect": {
            "fg_color": COLORS["disconnected"],
            "hover_color": "#FF5555",
            "text_color": "#FFFFFF",
            "corner_radius": 8,
        },
    }
    style = styles.get(variant, styles["default"]).copy()
    style.update(overrides)
    return style


# ── Reusable Components ─────────────────────────────────────────────

class Card(ctk.CTkFrame):
    """Rounded card with subtle border and optional title."""

    def __init__(self, parent, title: str = "", **kw) -> None:
        defaults = card_style()
        defaults.update(kw)
        super().__init__(parent, **defaults)

        if title:
            ctk.CTkLabel(
                self,
                text=title,
                text_color=COLORS["text_secondary"],
                font=FONTS["small"],
                anchor="w",
            ).pack(padx=12, pady=(8, 4), anchor="w")


class LabeledSlider(ctk.CTkFrame):
    """Slider with left label and right live-value display."""

    def __init__(
        self,
        parent,
        label: str,
        from_: float = 0,
        to: float = 100,
        value: float = 50,
        number_of_steps: int = 100,
        unit: str = "",
        value_format: str = "{:.0f}",
        **kw,
    ) -> None:
        super().__init__(parent, fg_color="transparent", **kw)
        self._unit = unit
        self._fmt = value_format

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text=label,
            text_color=COLORS["text_secondary"],
            font=FONTS["label"],
            width=65,
            anchor="w",
        ).grid(row=0, column=0, padx=(0, 4), sticky="w")

        self.slider = ctk.CTkSlider(
            self,
            from_=from_,
            to=to,
            number_of_steps=number_of_steps,
            height=20,            # taller = easier to grab
            button_length=16,     # bigger handle
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            progress_color=COLORS["accent"],
            fg_color=COLORS["bg_elevated"],
            command=self._on_change,
        )
        self.slider.grid(row=0, column=1, sticky="ew", padx=(4, 8), pady=4)
        self.slider.set(value)

        self._value_label = ctk.CTkLabel(
            self,
            text=self._format(value),
            text_color=COLORS["text_primary"],
            font=FONTS["mono_small"],
            width=70,            # wider for values like "10000"
            anchor="e",
        )
        self._value_label.grid(row=0, column=2, padx=(4, 0), sticky="e")

        self._callback = None

    def _format(self, val: float) -> str:
        return self._fmt.format(val) + self._unit

    def _on_change(self, val: float) -> None:
        self._value_label.configure(text=self._format(val))
        if self._callback:
            self._callback(val)

    def set(self, value: float) -> None:
        self.slider.set(value)
        self._value_label.configure(text=self._format(value))

    def get(self) -> float:
        return self.slider.get()

    def on_change(self, callback) -> None:
        self._callback = callback


class StatusPill(ctk.CTkLabel):
    """Colored pill showing connection state."""

    def __init__(self, parent, **kw) -> None:
        super().__init__(
            parent,
            text="● Disconnected",
            text_color=COLORS["disconnected"],
            font=FONTS["small"],
            **kw,
        )

    def set_state(self, state: str, text: str = "") -> None:
        """Update pill state: connected, disconnected, detecting, alarm."""
        color_map = {
            "connected": COLORS["connected"],
            "disconnected": COLORS["disconnected"],
            "detecting": COLORS["running"],
            "alarm": COLORS["running"],
        }
        color = color_map.get(state, COLORS["text_muted"])
        display = text or state.capitalize()
        self.configure(text=f"● {display}", text_color=color)


class OperationButton(ctk.CTkButton):
    """Large colored button for cut/engrave/mark operation selection."""

    _OP_COLORS = {
        "cut": (COLORS["cut"], "#CC2222"),
        "engrave": (COLORS["engrave"], "#2E77CC"),
        "mark": (COLORS["mark"], "#22AA22"),
    }

    def __init__(self, parent, operation: str, text: str, active: bool = False, **kw) -> None:
        self._operation = operation
        self._active = active
        colors = self._OP_COLORS.get(operation, (COLORS["accent"], COLORS["accent_hover"]))

        fg = colors[0] if active else COLORS["bg_elevated"]
        hover = colors[1] if active else COLORS["bg_hover"]
        text_color = "#FFFFFF" if active else COLORS["text_muted"]

        super().__init__(
            parent,
            text=text,
            fg_color=fg,
            hover_color=hover,
            text_color=text_color,
            corner_radius=8,
            height=36,
            font=FONTS["label"],
            **kw,
        )

    def set_active(self, active: bool) -> None:
        """Toggle active state."""
        self._active = active
        colors = self._OP_COLORS.get(self._operation, (COLORS["accent"], COLORS["accent_hover"]))
        if active:
            self.configure(
                fg_color=colors[0],
                hover_color=colors[1],
                text_color="#FFFFFF",
            )
        else:
            self.configure(
                fg_color=COLORS["bg_elevated"],
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_muted"],
            )
