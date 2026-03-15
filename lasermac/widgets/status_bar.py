"""Bottom status bar — live machine state display."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.theme import COLORS, FONTS


class StatusBar(ctk.CTkFrame):
    """Compact bottom status bar showing connection, position, and state."""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(
            parent,
            fg_color=COLORS["bg_panel"],
            height=28,
            corner_radius=0,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs,
        )
        self.pack_propagate(False)

        # Connection status pill
        self.conn_label = ctk.CTkLabel(
            self,
            text="● Disconnected",
            text_color=COLORS["disconnected"],
            font=FONTS["mono_small"],
        )
        self.conn_label.pack(side="left", padx=(12, 0))

        self._sep()

        # Machine state
        self.state_label = ctk.CTkLabel(
            self,
            text="Idle",
            text_color=COLORS["idle"],
            font=FONTS["mono_small"],
        )
        self.state_label.pack(side="left", padx=4)

        self._sep()

        # Position
        self.pos_label = ctk.CTkLabel(
            self,
            text="X: 0.000  Y: 0.000",
            text_color=COLORS["text_secondary"],
            font=FONTS["mono_small"],
        )
        self.pos_label.pack(side="left", padx=4)

        self._sep()

        # Spindle / Feed
        self.sf_label = ctk.CTkLabel(
            self,
            text="S: 0  F: 0",
            text_color=COLORS["text_muted"],
            font=FONTS["mono_small"],
        )
        self.sf_label.pack(side="left", padx=4)

        self._sep()

        # Time estimate
        self.time_label = ctk.CTkLabel(
            self,
            text="🕐 Est: --",
            text_color=COLORS["text_muted"],
            font=FONTS["mono_small"],
        )
        self.time_label.pack(side="left", padx=4)

        # Right side: version
        self.version_label = ctk.CTkLabel(
            self,
            text="LaserMac v0.4.0",
            text_color=COLORS["text_muted"],
            font=FONTS["muted"],
        )
        self.version_label.pack(side="right", padx=(4, 12))

    def _sep(self) -> None:
        """Add a subtle vertical separator."""
        ctk.CTkLabel(
            self, text="│",
            text_color=COLORS["text_muted"],
            font=FONTS["mono_small"],
        ).pack(side="left", padx=6)

    def set_connected(self, connected: bool, info: str = "") -> None:
        """Update connection state."""
        if connected:
            text = f"● Connected{f'  {info}' if info else ''}"
            self.conn_label.configure(text=text, text_color=COLORS["connected"])
        else:
            self.conn_label.configure(text="● Disconnected", text_color=COLORS["disconnected"])

    def update_status(self, status) -> None:
        """Update from a GRBL status object."""
        # State
        state_colors = {
            "Idle": COLORS["idle"],
            "Run": COLORS["running"],
            "Alarm": COLORS["disconnected"],
            "Hold": COLORS["running"],
        }
        color = state_colors.get(status.state, COLORS["text_secondary"])
        self.state_label.configure(text=status.state, text_color=color)

        # Position
        self.pos_label.configure(
            text=f"X: {status.x:.3f}  Y: {status.y:.3f}"
        )

    def set_time_estimate(self, seconds: float | None) -> None:
        """Update time estimate."""
        if seconds is None:
            self.time_label.configure(text="🕐 Est: --")
        else:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            self.time_label.configure(text=f"🕐 Est: {mins}m{secs:02d}s")
