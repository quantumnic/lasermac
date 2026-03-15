"""LaserMac — Main application window.

Free macOS laser engraver controller for GRBL machines.
Modern dark UI with 3-column layout: sidebar | canvas | properties.
"""

from __future__ import annotations

import webbrowser

import customtkinter as ctk

from lasermac import updater
from lasermac.grbl import GrblController
from lasermac.theme import (
    COLORS,
    FONTS,
    Card,
    LabeledSlider,
    apply_theme,
    button_style,
)
from lasermac.widgets.connection import ConnectionPanel
from lasermac.widgets.console import ConsolePanel
from lasermac.widgets.controls import ControlsPanel
from lasermac.widgets.draw_canvas import DrawCanvas
from lasermac.widgets.job_panel import JobPanel
from lasermac.widgets.properties_panel import PropertiesPanel
from lasermac.widgets.status_bar import StatusBar
from lasermac.widgets.toolbar import Toolbar


class LaserMacApp(ctk.CTk):
    """Main LaserMac application window."""

    def __init__(self) -> None:
        super().__init__()

        self.title("LaserMac — Laser Engraver Controller")
        self.geometry("1280x860")
        self.minsize(1000, 650)

        # Apply modern dark theme
        apply_theme(self)

        # GRBL controller (shared)
        self.grbl = GrblController()

        # ── Main layout: 3-column + toolbar + status bar ──
        # Row 0: toolbar
        # Row 1: sidebar | canvas | properties
        # Row 2: status bar
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=280)
        self.grid_rowconfigure(0, weight=0)  # toolbar
        self.grid_rowconfigure(1, weight=1)  # main
        self.grid_rowconfigure(2, weight=0)  # status bar

        # ── Toolbar (top) ──
        self.toolbar = Toolbar(self)
        self.toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")

        # ── Left sidebar ──
        sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=COLORS["bg_panel"],
                               border_width=1, border_color=COLORS["border"])
        sidebar.grid(row=1, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        sidebar_scroll = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent",
            scrollbar_button_color=COLORS["bg_elevated"],
        )
        sidebar_scroll.pack(fill="both", expand=True)

        # Logo / brand
        brand_frame = ctk.CTkFrame(sidebar_scroll, fg_color="transparent")
        brand_frame.pack(fill="x", padx=12, pady=(12, 4))

        ctk.CTkLabel(
            brand_frame, text="🔥 LaserMac",
            font=("", 20, "bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand_frame, text="GRBL Laser Controller",
            text_color=COLORS["text_muted"],
            font=FONTS["muted"],
        ).pack(anchor="w")

        # Connection card
        self.connection_panel = ConnectionPanel(sidebar_scroll, self.grbl)
        self.connection_panel.pack(fill="x", padx=8, pady=4)

        # Controls panel (jog + position)
        self.controls_panel = ControlsPanel(sidebar_scroll, self.grbl)
        self.controls_panel.pack(fill="x", padx=8, pady=4)

        # Wire auto-detect → controls
        self.connection_panel.on_machine_detected = self.controls_panel.apply_machine_config

        # Laser test card
        laser_card = Card(sidebar_scroll, title="LASER TEST")
        laser_card.pack(fill="x", padx=8, pady=4)

        self.laser_power_slider = LabeledSlider(
            laser_card, label="Power", from_=0, to=100,
            value=5, unit="%",
        )
        self.laser_power_slider.pack(fill="x", padx=12, pady=(4, 2))

        self.laser_speed_slider = LabeledSlider(
            laser_card, label="Speed", from_=100, to=10000,
            value=3000, unit=" mm/m",
        )
        self.laser_speed_slider.pack(fill="x", padx=12, pady=(2, 4))

        test_frame = ctk.CTkFrame(laser_card, fg_color="transparent")
        test_frame.pack(fill="x", padx=12, pady=(2, 10))

        ctk.CTkButton(
            test_frame, text="🔴 Test ON", width=90, height=28,
            command=self._laser_test_on,
            **button_style("danger"),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            test_frame, text="⚫ OFF", width=70, height=28,
            command=self._laser_off,
            **button_style("default"),
        ).pack(side="left", padx=2)

        # ── Center: main content area ──
        center = ctk.CTkFrame(self, fg_color=COLORS["bg_base"])
        center.grid(row=1, column=1, sticky="nsew")
        center.grid_rowconfigure(0, weight=0)  # update banner
        center.grid_rowconfigure(1, weight=2)  # tabs
        center.grid_rowconfigure(2, weight=1)  # console
        center.grid_columnconfigure(0, weight=1)

        # Update banner (hidden by default)
        self._update_banner = ctk.CTkButton(
            center,
            text="",
            fg_color=COLORS["connected"],
            hover_color="#4CD964",
            height=30,
            corner_radius=0,
            command=self._open_update_url,
        )
        self._update_url: str | None = None

        # Tabview
        self.tabview = ctk.CTkTabview(
            center,
            fg_color=COLORS["bg_card"],
            segmented_button_fg_color=COLORS["bg_elevated"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_hover"],
            segmented_button_unselected_color=COLORS["bg_elevated"],
            segmented_button_unselected_hover_color=COLORS["bg_hover"],
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=4, pady=(4, 2))
        self.tabview.add("Jobs")
        self.tabview.add("Draw")

        # Job panel in Jobs tab
        jobs_tab = self.tabview.tab("Jobs")
        jobs_tab.grid_rowconfigure(0, weight=1)
        jobs_tab.grid_columnconfigure(0, weight=1)
        JobPanel(jobs_tab, self.grbl).grid(row=0, column=0, sticky="nsew")

        # Draw canvas in Draw tab
        draw_tab = self.tabview.tab("Draw")
        draw_tab.grid_rowconfigure(0, weight=1)
        draw_tab.grid_columnconfigure(0, weight=1)
        self.draw_canvas = DrawCanvas(draw_tab, self.grbl)
        self.draw_canvas.grid(row=0, column=0, sticky="nsew")

        # Console (bottom of center)
        ConsolePanel(center, self.grbl).grid(row=2, column=0, sticky="nsew", padx=4, pady=(2, 4))

        # ── Right: properties panel ──
        self.properties = PropertiesPanel(self)
        self.properties.grid(row=1, column=2, sticky="nse")

        # ── Status bar (bottom) ──
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, columnspan=3, sticky="ew")

        # Wire status updates
        self.grbl.on_status = self._on_grbl_status

        # Wire toolbar buttons
        self.toolbar.start_btn.configure(command=self._toolbar_start)
        self.toolbar.pause_btn.configure(command=self._toolbar_pause)
        self.toolbar.stop_btn.configure(command=self._toolbar_stop)

        # Cleanup on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Check for updates in background
        updater.check_async(self._on_update_result)

    def _on_grbl_status(self, status) -> None:
        """Update status bar and controls from GRBL status."""
        self.status_bar.update_status(status)
        self.controls_panel._update_status(status)

    def _on_update_result(self, result: dict | None) -> None:
        """Callback from update checker (runs in background thread)."""
        if result:
            self._update_url = result["url"]
            self._update_banner.configure(
                text=f"🔔 v{result['version']} available — Click to download"
            )
            self._update_banner.grid(row=0, column=0, sticky="ew", pady=(0, 2))

    def _open_update_url(self) -> None:
        """Open the update URL in browser."""
        if self._update_url:
            webbrowser.open(self._update_url)

    def _laser_test_on(self) -> None:
        """Turn laser on at low power for testing."""
        power = int(self.laser_power_slider.get() / 100 * 1000)
        self.grbl.send_command(f"M3 S{power}")

    def _laser_off(self) -> None:
        """Turn laser off."""
        self.grbl.send_command("M5 S0")

    def _toolbar_start(self) -> None:
        """Start job from toolbar."""
        pass  # Wired to active tab's job panel

    def _toolbar_pause(self) -> None:
        """Pause job from toolbar."""
        pass

    def _toolbar_stop(self) -> None:
        """Stop job from toolbar."""
        pass

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
