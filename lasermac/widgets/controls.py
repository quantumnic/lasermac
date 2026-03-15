"""Machine jog controls widget — modern themed."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.grbl import GrblController
from lasermac.theme import COLORS, FONTS, Card, button_style


class ControlsPanel(ctk.CTkFrame):
    """Jog controls and machine positioning."""

    def __init__(self, parent, grbl: GrblController, **kwargs) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)
        self.grbl = grbl

        # Controls card
        card = Card(self, title="CONTROLS")
        card.pack(fill="x")

        # Axis invert options
        invert_frame = ctk.CTkFrame(card, fg_color="transparent")
        invert_frame.pack(fill="x", padx=12, pady=(4, 2))
        ctk.CTkLabel(invert_frame, text="Invert:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        self.invert_x = ctk.BooleanVar(value=False)
        self.invert_y = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            invert_frame, text="X", variable=self.invert_x, width=45,
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            fg_color=COLORS["bg_elevated"], hover_color=COLORS["bg_hover"],
            checkmark_color=COLORS["accent"],
        ).pack(side="left", padx=4)
        ctk.CTkCheckBox(
            invert_frame, text="Y", variable=self.invert_y, width=45,
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            fg_color=COLORS["bg_elevated"], hover_color=COLORS["bg_hover"],
            checkmark_color=COLORS["accent"],
        ).pack(side="left", padx=4)

        # Step size selector
        step_frame = ctk.CTkFrame(card, fg_color="transparent")
        step_frame.pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(step_frame, text="Step:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        self.step_var = ctk.StringVar(value="1.0")
        for val in ["0.1", "1.0", "10.0", "50.0"]:
            ctk.CTkRadioButton(
                step_frame, text=f"{val}mm", variable=self.step_var, value=val,
                font=FONTS["muted"], text_color=COLORS["text_secondary"],
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            ).pack(side="left", padx=3)

        # Feed rate
        feed_frame = ctk.CTkFrame(card, fg_color="transparent")
        feed_frame.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(feed_frame, text="Feed:", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        self.feed_var = ctk.StringVar(value="1000")
        ctk.CTkEntry(
            feed_frame, textvariable=self.feed_var, width=70, height=26,
            font=FONTS["mono_small"],
            fg_color=COLORS["bg_elevated"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
        ).pack(side="left", padx=5)
        ctk.CTkLabel(feed_frame, text="mm/min", font=FONTS["muted"],
                     text_color=COLORS["text_muted"]).pack(side="left")

        # Jog buttons (arrow layout)
        jog_frame = ctk.CTkFrame(card, fg_color="transparent")
        jog_frame.pack(padx=12, pady=8)

        btn_size = 44
        btn_cfg = {
            "width": btn_size,
            "height": btn_size,
            "corner_radius": 8,
            "fg_color": COLORS["bg_elevated"],
            "hover_color": COLORS["bg_hover"],
            "text_color": COLORS["text_primary"],
            "font": FONTS["label"],
        }

        ctk.CTkButton(jog_frame, text="▲\nY+", command=lambda: self._jog("Y", 1), **btn_cfg).grid(
            row=0, column=1, padx=2, pady=2
        )
        ctk.CTkButton(jog_frame, text="◀\nX-", command=lambda: self._jog("X", -1), **btn_cfg).grid(
            row=1, column=0, padx=2, pady=2
        )
        ctk.CTkButton(
            jog_frame, text="⌂", command=lambda: self.grbl.go_to_origin(),
            width=btn_size, height=btn_size, corner_radius=8,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF", font=("", 16),
        ).grid(row=1, column=1, padx=2, pady=2)
        ctk.CTkButton(jog_frame, text="▶\nX+", command=lambda: self._jog("X", 1), **btn_cfg).grid(
            row=1, column=2, padx=2, pady=2
        )
        ctk.CTkButton(jog_frame, text="▼\nY-", command=lambda: self._jog("Y", -1), **btn_cfg).grid(
            row=2, column=1, padx=2, pady=2
        )

        # Z controls (side)
        z_frame = ctk.CTkFrame(jog_frame, fg_color="transparent")
        z_frame.grid(row=0, column=3, rowspan=3, padx=8)
        ctk.CTkButton(z_frame, text="Z+", command=lambda: self._jog("Z", 1), **btn_cfg).pack(pady=2)
        ctk.CTkButton(z_frame, text="Z-", command=lambda: self._jog("Z", -1), **btn_cfg).pack(pady=2)

        # Position display
        pos_card = Card(self)
        pos_card.pack(fill="x", pady=(4, 0))

        self.pos_label = ctk.CTkLabel(
            pos_card,
            text="X: 0.000  Y: 0.000  Z: 0.000",
            font=FONTS["mono"],
            text_color=COLORS["accent"],
        )
        self.pos_label.pack(padx=12, pady=8)

        # Quick actions
        action_frame = ctk.CTkFrame(pos_card, fg_color="transparent")
        action_frame.pack(fill="x", padx=12, pady=(0, 10))

        actions = [
            ("Set Origin", self.grbl.set_origin),
            ("Go Origin", self.grbl.go_to_origin),
            ("Home", self.grbl.home),
        ]
        for text, cmd in actions:
            ctk.CTkButton(
                action_frame, text=text, command=cmd,
                width=68, height=26,
                **button_style("default"),
                font=FONTS["muted"],
            ).pack(side="left", padx=2)

        # Register status callback
        self.grbl.on_status = self._update_status

    def apply_machine_config(self, cfg: dict) -> None:
        """Auto-apply machine config from GRBL detect_machine()."""
        self.invert_x.set(cfg.get("invert_x", False))
        self.invert_y.set(cfg.get("invert_y", False))
        max_speed = int(cfg.get("max_speed", 6000))
        self.feed_var.set(str(min(1000, max_speed)))

    def _jog(self, axis: str, direction: int) -> None:
        """Execute a jog move, respecting axis invert settings."""
        if axis == "X" and self.invert_x.get():
            direction *= -1
        if axis == "Y" and self.invert_y.get():
            direction *= -1
        step = float(self.step_var.get()) * direction
        feed = int(self.feed_var.get())
        self.grbl.jog(axis, step, feed)

    def _update_status(self, status) -> None:
        """Update position display."""
        self.pos_label.configure(
            text=f"X: {status.x:.3f}  Y: {status.y:.3f}  Z: {status.z:.3f}  [{status.state}]"
        )
