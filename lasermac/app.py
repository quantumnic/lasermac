"""LaserMac — Main application window.

Free macOS laser engraver controller for GRBL machines.
"""

from __future__ import annotations

import customtkinter as ctk

from lasermac.grbl import GrblController
from lasermac.widgets.connection import ConnectionPanel
from lasermac.widgets.console import ConsolePanel
from lasermac.widgets.controls import ControlsPanel
from lasermac.widgets.job_panel import JobPanel


class LaserMacApp(ctk.CTk):
    """Main LaserMac application window."""

    def __init__(self) -> None:
        super().__init__()

        self.title("LaserMac — Laser Engraver Controller")
        self.geometry("1200x800")
        self.minsize(900, 600)

        # Dark theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # GRBL controller (shared)
        self.grbl = GrblController()

        # Layout: left sidebar + right main area
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left sidebar
        sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        # Logo
        ctk.CTkLabel(
            sidebar, text="🔥 LaserMac", font=("", 22, "bold")
        ).pack(pady=(15, 5), padx=10, anchor="w")
        ctk.CTkLabel(
            sidebar, text="GRBL Laser Controller", text_color="#888888", font=("", 12)
        ).pack(padx=10, anchor="w")

        # Connection panel
        ConnectionPanel(sidebar, self.grbl).pack(fill="x", padx=5, pady=5)

        # Controls panel
        ControlsPanel(sidebar, self.grbl).pack(fill="x", padx=5, pady=5)

        # Laser test controls
        laser_frame = ctk.CTkFrame(sidebar)
        laser_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(laser_frame, text="🔦 Laser", font=("", 16, "bold")).pack(
            pady=(10, 5), padx=10, anchor="w"
        )

        power_frame = ctk.CTkFrame(laser_frame, fg_color="transparent")
        power_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(power_frame, text="Power %:").pack(side="left")
        self.laser_power = ctk.CTkSlider(power_frame, from_=0, to=100, number_of_steps=100)
        self.laser_power.pack(side="left", fill="x", expand=True, padx=5)
        self.laser_power.set(5)

        speed_frame = ctk.CTkFrame(laser_frame, fg_color="transparent")
        speed_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(speed_frame, text="Speed:").pack(side="left")
        self.laser_speed = ctk.CTkSlider(speed_frame, from_=100, to=10000, number_of_steps=100)
        self.laser_speed.pack(side="left", fill="x", expand=True, padx=5)
        self.laser_speed.set(3000)

        test_frame = ctk.CTkFrame(laser_frame, fg_color="transparent")
        test_frame.pack(fill="x", padx=10, pady=(2, 10))

        ctk.CTkButton(
            test_frame, text="🔴 Test ON", width=80,
            command=self._laser_test_on,
            fg_color="#da3633", hover_color="#f85149",
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            test_frame, text="⚫ OFF", width=60,
            command=self._laser_off,
            fg_color="#333333", hover_color="#444444",
        ).pack(side="left", padx=2)

        # Right area: job panel + console
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right.grid_rowconfigure(0, weight=2)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Job panel (top)
        JobPanel(right, self.grbl).grid(row=0, column=0, sticky="nsew", pady=(0, 5))

        # Console (bottom)
        ConsolePanel(right, self.grbl).grid(row=1, column=0, sticky="nsew")

        # Cleanup on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _laser_test_on(self) -> None:
        """Turn laser on at low power for testing."""
        power = int(self.laser_power.get() / 100 * 1000)
        self.grbl.send_command(f"M3 S{power}")

    def _laser_off(self) -> None:
        """Turn laser off."""
        self.grbl.send_command("M5 S0")

    def _on_close(self) -> None:
        """Clean shutdown."""
        self.grbl.disconnect()
        self.destroy()


def main() -> None:
    """Launch LaserMac."""
    app = LaserMacApp()
    app.mainloop()


if __name__ == "__main__":
    main()
