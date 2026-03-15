"""Right properties panel — context-aware settings for selected shape or tool."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.layers import (
    OPERATION_CUT,
    OPERATION_ENGRAVE,
    default_settings,
    operation_color,
    operation_label,
)
from lasermac.theme import COLORS, FONTS, Card, LabeledSlider


class PropertiesPanel(ctk.CTkFrame):
    """Right-side properties panel showing settings for selected shape or active tool."""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(
            parent,
            fg_color=COLORS["bg_panel"],
            width=280,
            corner_radius=0,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )
        self.grid_propagate(False)

        self._current_operation = "engrave"

        # Header
        ctk.CTkLabel(
            self,
            text="Properties",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
        ).pack(padx=16, pady=(16, 8), anchor="w")

        # Scrollable area
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_elevated"],
        )
        self._scroll.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        self._build_default_view()

    def _build_default_view(self, operation: str = "engrave") -> None:
        """Build default properties view for the current operation."""
        self._current_operation = operation
        for w in self._scroll.winfo_children():
            w.destroy()

        op = operation
        color = operation_color(op)
        label = operation_label(op)
        defaults = default_settings(op)

        # Operation info card
        info_card = Card(self._scroll, title="OPERATION")
        info_card.pack(fill="x", padx=8, pady=(4, 8))

        ctk.CTkLabel(
            info_card,
            text=label,
            font=FONTS["heading"],
            text_color=color,
        ).pack(padx=12, pady=(4, 8), anchor="w")

        # Speed/Power card
        sp_card = Card(self._scroll, title="LASER SETTINGS")
        sp_card.pack(fill="x", padx=8, pady=4)

        self.speed_slider = LabeledSlider(
            sp_card,
            label="Speed",
            from_=50,
            to=10000 if op != OPERATION_CUT else 2000,
            value=defaults.speed,
            unit=" mm/min",
        )
        self.speed_slider.pack(fill="x", padx=12, pady=(8, 4))

        self.power_slider = LabeledSlider(
            sp_card,
            label="Power",
            from_=0,
            to=1000,
            value=defaults.power,
            unit=" S",
        )
        self.power_slider.pack(fill="x", padx=12, pady=(4, 8))

        # Operation-specific settings
        if op == OPERATION_CUT:
            self._build_cut_settings()
        elif op == OPERATION_ENGRAVE:
            self._build_engrave_settings()
        else:
            self._build_mark_settings()

    def _build_cut_settings(self) -> None:
        """Cut-specific: passes selector."""
        cut_card = Card(self._scroll, title="CUT OPTIONS")
        cut_card.pack(fill="x", padx=8, pady=4)

        passes_frame = ctk.CTkFrame(cut_card, fg_color="transparent")
        passes_frame.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(
            passes_frame,
            text="Passes",
            text_color=COLORS["text_secondary"],
            font=FONTS["label"],
        ).pack(side="left")

        self.passes_var = ctk.StringVar(value="3")
        ctk.CTkOptionMenu(
            passes_frame,
            variable=self.passes_var,
            values=["1", "2", "3", "4", "5", "6", "8", "10"],
            width=70,
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["bg_hover"],
            button_hover_color=COLORS["border_focus"],
        ).pack(side="right")

        # Warning label
        ctk.CTkLabel(
            cut_card,
            text="⚠️ Fill disabled for CUT",
            text_color=COLORS["cut"],
            font=FONTS["muted"],
        ).pack(padx=12, pady=(0, 8), anchor="w")

        # No fill sliders for cut
        self.fill_speed_slider = None
        self.fill_power_slider = None
        self.hatch_var = ctk.StringVar(value="none")

    def _build_engrave_settings(self) -> None:
        """Engrave-specific: fill mode + fill speed/power."""
        fill_card = Card(self._scroll, title="FILL SETTINGS")
        fill_card.pack(fill="x", padx=8, pady=4)

        mode_frame = ctk.CTkFrame(fill_card, fg_color="transparent")
        mode_frame.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            mode_frame,
            text="Fill Mode",
            text_color=COLORS["text_secondary"],
            font=FONTS["label"],
        ).pack(side="left")

        defaults = default_settings(OPERATION_ENGRAVE)
        self.hatch_var = ctk.StringVar(value=defaults.fill_mode)
        ctk.CTkOptionMenu(
            mode_frame,
            variable=self.hatch_var,
            values=["none", "lines", "schraffur", "kreuz", "dots", "concentric"],
            width=110,
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["bg_hover"],
            button_hover_color=COLORS["border_focus"],
        ).pack(side="right")

        self.fill_speed_slider = LabeledSlider(
            fill_card,
            label="F.Spd",
            from_=100,
            to=10000,
            value=defaults.fill_speed,
            unit=" mm/m",
        )
        self.fill_speed_slider.pack(fill="x", padx=12, pady=4)

        self.fill_power_slider = LabeledSlider(
            fill_card,
            label="F.Pwr",
            from_=0,
            to=1000,
            value=defaults.fill_power,
            unit=" S",
        )
        self.fill_power_slider.pack(fill="x", padx=12, pady=(4, 8))

        self.passes_var = ctk.StringVar(value="1")

    def _build_mark_settings(self) -> None:
        """Mark-specific: minimal — just speed/power is enough."""
        info_card = Card(self._scroll, title="MARK INFO")
        info_card.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(
            info_card,
            text="Surface marking only.\nFast + low power.",
            text_color=COLORS["text_muted"],
            font=FONTS["small"],
        ).pack(padx=12, pady=8, anchor="w")

        self.fill_speed_slider = None
        self.fill_power_slider = None
        self.hatch_var = ctk.StringVar(value="none")
        self.passes_var = ctk.StringVar(value="1")

    def update_for_operation(self, operation: str) -> None:
        """Rebuild panel for a different operation."""
        if operation != self._current_operation:
            self._build_default_view(operation)

    def update_for_shape(self, shape_info: dict) -> None:
        """Update panel with selected shape information."""
        # Future: show shape-specific size/position info
        pass
