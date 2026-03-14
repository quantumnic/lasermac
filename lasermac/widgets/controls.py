"""Machine jog controls widget."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.grbl import GrblController


class ControlsPanel(ctk.CTkFrame):
    """Jog controls and machine positioning."""

    def __init__(self, parent, grbl: GrblController, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.grbl = grbl

        # Title
        ctk.CTkLabel(self, text="🎮 Controls", font=("", 16, "bold")).pack(
            pady=(10, 5), padx=10, anchor="w"
        )

        # Axis invert options (for machines where X or Y is mirrored)
        invert_frame = ctk.CTkFrame(self, fg_color="transparent")
        invert_frame.pack(fill="x", padx=10, pady=(0, 2))
        ctk.CTkLabel(invert_frame, text="Invert:").pack(side="left")
        self.invert_x = ctk.BooleanVar(value=False)
        self.invert_y = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(invert_frame, text="X", variable=self.invert_x, width=50).pack(
            side="left", padx=4
        )
        ctk.CTkCheckBox(invert_frame, text="Y", variable=self.invert_y, width=50).pack(
            side="left", padx=4
        )

        # Step size selector
        step_frame = ctk.CTkFrame(self, fg_color="transparent")
        step_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(step_frame, text="Step:").pack(side="left")
        self.step_var = ctk.StringVar(value="1.0")
        for val in ["0.1", "1.0", "10.0", "50.0"]:
            ctk.CTkRadioButton(step_frame, text=f"{val}mm", variable=self.step_var, value=val).pack(
                side="left", padx=5
            )

        # Feed rate
        feed_frame = ctk.CTkFrame(self, fg_color="transparent")
        feed_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(feed_frame, text="Feed:").pack(side="left")
        self.feed_var = ctk.StringVar(value="1000")
        ctk.CTkEntry(feed_frame, textvariable=self.feed_var, width=80).pack(side="left", padx=5)
        ctk.CTkLabel(feed_frame, text="mm/min").pack(side="left")

        # Jog buttons (arrow layout)
        jog_frame = ctk.CTkFrame(self, fg_color="transparent")
        jog_frame.pack(padx=10, pady=10)

        btn_size = 50
        btn_cfg = {
            "width": btn_size,
            "height": btn_size,
            "fg_color": "#333333",
            "hover_color": "#444444",
        }

        # Y+
        ctk.CTkButton(jog_frame, text="▲\nY+", command=lambda: self._jog("Y", 1), **btn_cfg).grid(
            row=0, column=1, padx=2, pady=2
        )

        # X-
        ctk.CTkButton(jog_frame, text="◀\nX-", command=lambda: self._jog("X", -1), **btn_cfg).grid(
            row=1, column=0, padx=2, pady=2
        )

        # Home icon
        ctk.CTkButton(
            jog_frame,
            text="⌂",
            command=lambda: self.grbl.go_to_origin(),
            width=btn_size,
            height=btn_size,
            fg_color="#1a5276",
            hover_color="#2471a3",
        ).grid(row=1, column=1, padx=2, pady=2)

        # X+
        ctk.CTkButton(jog_frame, text="▶\nX+", command=lambda: self._jog("X", 1), **btn_cfg).grid(
            row=1, column=2, padx=2, pady=2
        )

        # Y-
        ctk.CTkButton(jog_frame, text="▼\nY-", command=lambda: self._jog("Y", -1), **btn_cfg).grid(
            row=2, column=1, padx=2, pady=2
        )

        # Z controls
        z_frame = ctk.CTkFrame(jog_frame, fg_color="transparent")
        z_frame.grid(row=0, column=3, rowspan=3, padx=10)

        ctk.CTkButton(z_frame, text="Z+", command=lambda: self._jog("Z", 1), **btn_cfg).pack(pady=2)
        ctk.CTkButton(z_frame, text="Z-", command=lambda: self._jog("Z", -1), **btn_cfg).pack(
            pady=2
        )

        # Position display
        self.pos_label = ctk.CTkLabel(self, text="X: 0.000  Y: 0.000  Z: 0.000", font=("Menlo", 13))
        self.pos_label.pack(padx=10, pady=5)

        # Quick actions
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=10, pady=(0, 10))

        actions = [
            ("Set Origin", self.grbl.set_origin),
            ("Go Origin", self.grbl.go_to_origin),
            ("Home", self.grbl.home),
        ]
        for text, cmd in actions:
            ctk.CTkButton(
                action_frame,
                text=text,
                command=cmd,
                width=90,
                fg_color="#333333",
                hover_color="#444444",
            ).pack(side="left", padx=2)

        # Register status callback
        self.grbl.on_status = self._update_status

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
