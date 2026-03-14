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

        self.refresh_btn = ctk.CTkButton(
            port_frame, text="⟳", width=30, command=self.refresh_ports
        )
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
            self, text="Connect", command=self.toggle_connection,
            fg_color="#2ea043", hover_color="#3fb950",
        )
        self.connect_btn.pack(fill="x", padx=10, pady=5)

        # Status indicator
        self.status_label = ctk.CTkLabel(
            self, text="● Disconnected", text_color="#ff6b6b"
        )
        self.status_label.pack(padx=10, pady=(0, 10))

        # Register callback
        self.grbl.on_connect = self._on_connect_change

        # Initial port scan
        self.refresh_ports()

    def refresh_ports(self) -> None:
        """Refresh available serial ports."""
        ports = GrblController.list_ports()
        if ports:
            self.port_menu.configure(values=ports)
            self.port_var.set(ports[0])
        else:
            self.port_menu.configure(values=["(none)"])
            self.port_var.set("(none)")

    def toggle_connection(self) -> None:
        """Connect or disconnect."""
        if self.grbl.connected:
            self.grbl.disconnect()
        else:
            port = self.port_var.get()
            baud = int(self.baud_var.get())
            if port and port != "(none)":
                self.grbl.connect(port, baud)

    def _on_connect_change(self, connected: bool) -> None:
        """Update UI when connection state changes."""
        if connected:
            self.connect_btn.configure(
                text="Disconnect", fg_color="#da3633", hover_color="#f85149"
            )
            self.status_label.configure(text="● Connected", text_color="#3fb950")
        else:
            self.connect_btn.configure(
                text="Connect", fg_color="#2ea043", hover_color="#3fb950"
            )
            self.status_label.configure(text="● Disconnected", text_color="#ff6b6b")
