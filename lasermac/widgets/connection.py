"""Serial connection panel widget."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.grbl import GrblController


class ConnectionPanel(ctk.CTkFrame):
    """Panel for serial port connection management."""

    def __init__(self, parent, grbl: GrblController, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.grbl = grbl

        # Title
        ctk.CTkLabel(self, text="🔌 Connection", font=("", 16, "bold")).pack(
            pady=(10, 5), padx=10, anchor="w"
        )

        # Port selector
        port_frame = ctk.CTkFrame(self, fg_color="transparent")
        port_frame.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(port_frame, text="Port:").pack(side="left")
        self.port_var = ctk.StringVar()
        self.port_menu = ctk.CTkOptionMenu(
            port_frame, variable=self.port_var, values=["(none)"], width=200
        )
        self.port_menu.pack(side="left", padx=5)

        self.refresh_btn = ctk.CTkButton(port_frame, text="⟳", width=30, command=self.refresh_ports)
        self.refresh_btn.pack(side="left")

        # Baud rate
        baud_frame = ctk.CTkFrame(self, fg_color="transparent")
        baud_frame.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(baud_frame, text="Baud:").pack(side="left")
        self.baud_var = ctk.StringVar(value="115200")
        ctk.CTkOptionMenu(
            baud_frame,
            variable=self.baud_var,
            values=["9600", "19200", "38400", "57600", "115200", "230400"],
            width=120,
        ).pack(side="left", padx=5)

        # Connect button
        self.connect_btn = ctk.CTkButton(
            self,
            text="Connect",
            command=self.toggle_connection,
            fg_color="#2ea043",
            hover_color="#3fb950",
        )
        self.connect_btn.pack(fill="x", padx=10, pady=5)

        # Status indicator
        self.status_label = ctk.CTkLabel(self, text="● Disconnected", text_color="#ff6b6b")
        self.status_label.pack(padx=10, pady=(0, 10))

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
            # Build display labels: "cu.usbserial-0001 [CH340]"
            labels = [f"{d['device']}  [{d['chip']}]" for d in details]
            self._port_map = {lbl: d["device"] for lbl, d in zip(labels, details)}
            self.port_menu.configure(values=labels)
            self.port_var.set(labels[0])
            # Show device info in status
            d = details[0]
            self.status_label.configure(
                text=f"● Found: {d['description'][:40]}", text_color="#e3b341"
            )
        else:
            self._port_map = {}
            self.port_menu.configure(values=["(none)"])
            self.port_var.set("(none)")
            self.status_label.configure(text="● No devices found", text_color="#ff6b6b")

        # Schedule next auto-scan in 2s if not connected
        if not self.grbl.connected:
            self.after(2000, self._auto_scan)

    def _auto_scan(self) -> None:
        """Auto-scan for newly connected devices."""
        if not self.grbl.connected:
            old = self.port_var.get()
            self.refresh_ports()
            new = self.port_var.get()
            if new != "(none)" and new != old:
                # New device plugged in — flash the button
                self.connect_btn.configure(fg_color="#e3b341", hover_color="#d4a017")
                self.after(
                    1000,
                    lambda: self.connect_btn.configure(fg_color="#2ea043", hover_color="#3fb950"),
                )

    def toggle_connection(self) -> None:
        """Connect or disconnect."""
        if self.grbl.connected:
            self.grbl.disconnect()
        else:
            label = self.port_var.get()
            # Resolve label → actual device path
            port = getattr(self, "_port_map", {}).get(label, label.split()[0])
            baud = int(self.baud_var.get())
            if port and port != "(none)":
                self.grbl.connect(port, baud)

    def _on_connect_change(self, connected: bool) -> None:
        """Update UI when connection state changes."""
        if connected:
            self.connect_btn.configure(text="Disconnect", fg_color="#da3633", hover_color="#f85149")
            self.status_label.configure(text="● Connected — detecting...", text_color="#e3b341")
            self.after(800, self._auto_detect_machine)
        else:
            self.connect_btn.configure(text="Connect", fg_color="#2ea043", hover_color="#3fb950")
            self.status_label.configure(text="● Disconnected", text_color="#ff6b6b")

    def _auto_detect_machine(self) -> None:
        """Read GRBL settings and auto-configure."""
        try:
            cfg = self.grbl.detect_machine()
            inv = []
            if cfg["invert_x"]:
                inv.append("X")
            if cfg["invert_y"]:
                inv.append("Y")
            inv_str = f"  Inverted: {'+'.join(inv)}" if inv else ""
            self.status_label.configure(
                text=f"● {cfg['work_x']:.0f}×{cfg['work_y']:.0f}mm  S{cfg['max_power']}{inv_str}",
                text_color="#3fb950",
            )
            if hasattr(self, "on_machine_detected") and self.on_machine_detected:
                self.on_machine_detected(cfg)
        except Exception:
            self.status_label.configure(text="● Connected (detect failed)", text_color="#e3b341")
