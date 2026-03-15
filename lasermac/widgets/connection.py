"""Serial connection panel widget — modern themed."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.grbl import GrblController
from lasermac.theme import COLORS, FONTS, Card, StatusPill, button_style


class ConnectionPanel(ctk.CTkFrame):
    """Panel for serial port connection management."""

    def __init__(self, parent, grbl: GrblController, **kwargs) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)
        self.grbl = grbl

        # Connection card
        card = Card(self, title="CONNECTION")
        card.pack(fill="x")

        # Port selector row
        port_frame = ctk.CTkFrame(card, fg_color="transparent")
        port_frame.pack(fill="x", padx=12, pady=(4, 2))

        self.port_var = ctk.StringVar()
        self.port_menu = ctk.CTkOptionMenu(
            port_frame, variable=self.port_var, values=["(none)"],
            width=160, height=28,
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["bg_hover"],
            button_hover_color=COLORS["border_focus"],
            font=FONTS["small"],
        )
        self.port_menu.pack(side="left", fill="x", expand=True)

        self.refresh_btn = ctk.CTkButton(
            port_frame, text="⟳", width=28, height=28,
            command=self.refresh_ports,
            **button_style("ghost"),
        )
        self.refresh_btn.pack(side="left", padx=(4, 0))

        # Baud rate
        baud_frame = ctk.CTkFrame(card, fg_color="transparent")
        baud_frame.pack(fill="x", padx=12, pady=2)

        ctk.CTkLabel(baud_frame, text="Baud", font=FONTS["small"],
                     text_color=COLORS["text_muted"]).pack(side="left")
        self.baud_var = ctk.StringVar(value="115200")
        ctk.CTkOptionMenu(
            baud_frame,
            variable=self.baud_var,
            values=["9600", "19200", "38400", "57600", "115200", "230400"],
            width=90, height=28,
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["bg_hover"],
            button_hover_color=COLORS["border_focus"],
            font=FONTS["small"],
        ).pack(side="right")

        # Connect button
        self.connect_btn = ctk.CTkButton(
            card, text="Connect", height=32,
            command=self.toggle_connection,
            **button_style("connect"),
        )
        self.connect_btn.pack(fill="x", padx=12, pady=(4, 4))

        # Status pill
        self.status_pill = StatusPill(card)
        self.status_pill.pack(padx=12, pady=(0, 10))

        # Compat: keep status_label for external references
        self.status_label = self.status_pill

        # Callback: called with machine config dict after auto-detect
        self.on_machine_detected: callable = None

        # Register callback
        self.grbl.on_connect = self._on_connect_change

        # Initial port scan
        self.refresh_ports()

    def refresh_ports(self) -> None:
        """Refresh available serial ports with device info."""
        details = GrblController.list_ports_detail()
        if details:
            labels = [f"{d['device']}  [{d['chip']}]" for d in details]
            self._port_map = {lbl: d["device"] for lbl, d in zip(labels, details)}
            self.port_menu.configure(values=labels)
            self.port_var.set(labels[0])
            d = details[0]
            self.status_pill.set_state("detecting", f"Found: {d['description'][:35]}")
        else:
            self._port_map = {}
            self.port_menu.configure(values=["(none)"])
            self.port_var.set("(none)")
            self.status_pill.set_state("disconnected", "No devices found")

        if not self.grbl.connected:
            self.after(2000, self._auto_scan)

    def _auto_scan(self) -> None:
        """Auto-scan for newly connected devices."""
        if not self.grbl.connected:
            old = self.port_var.get()
            self.refresh_ports()
            new = self.port_var.get()
            if new != "(none)" and new != old:
                self.connect_btn.configure(
                    fg_color=COLORS["running"],
                    hover_color=COLORS["accent_hover"],
                )
                self.after(
                    1000,
                    lambda: self.connect_btn.configure(**button_style("connect")),
                )

    def toggle_connection(self) -> None:
        """Connect or disconnect."""
        if self.grbl.connected:
            self.grbl.disconnect()
        else:
            label = self.port_var.get()
            port = getattr(self, "_port_map", {}).get(label, label.split()[0])
            baud = int(self.baud_var.get())
            if port and port != "(none)":
                self.grbl.connect(port, baud)

    def _on_connect_change(self, connected: bool) -> None:
        """Update UI when connection state changes."""
        if connected:
            self.connect_btn.configure(text="Disconnect", **button_style("disconnect"))
            self.status_pill.set_state("detecting", "Connected — detecting...")
            self.after(800, self._auto_detect_machine)
        else:
            self.connect_btn.configure(text="Connect", **button_style("connect"))
            self.status_pill.set_state("disconnected")

    def _auto_detect_machine(self) -> None:
        """Read GRBL settings and auto-configure."""
        try:
            cfg = self.grbl.detect_machine()
            inv = []
            if cfg["invert_x"]:
                inv.append("X")
            if cfg["invert_y"]:
                inv.append("Y")
            inv_str = f"  Inv: {'+'.join(inv)}" if inv else ""
            self.status_pill.set_state(
                "connected",
                f"{cfg['work_x']:.0f}×{cfg['work_y']:.0f}mm S{cfg['max_power']}{inv_str}",
            )
            if hasattr(self, "on_machine_detected") and self.on_machine_detected:
                self.on_machine_detected(cfg)
        except Exception:
            self.status_pill.set_state("detecting", "Connected (detect failed)")
