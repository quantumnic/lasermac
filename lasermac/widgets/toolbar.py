"""Top toolbar — file ops + job control buttons."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.theme import COLORS, FONTS, button_style


class Toolbar(ctk.CTkFrame):
    """Thin toolbar strip above the canvas with file and job controls."""

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(
            parent,
            fg_color=COLORS["bg_panel"],
            height=40,
            corner_radius=0,
            **kwargs,
        )
        self.pack_propagate(False)

        # ── File operations ──
        file_group = ctk.CTkFrame(self, fg_color="transparent")
        file_group.pack(side="left", padx=(8, 4), pady=4)

        self.open_btn = ctk.CTkButton(
            file_group, text="📂 Open", width=70, height=28,
            **button_style("ghost"),
        )
        self.open_btn.pack(side="left", padx=2)

        self.save_btn = ctk.CTkButton(
            file_group, text="💾 Save", width=65, height=28,
            **button_style("ghost"),
        )
        self.save_btn.pack(side="left", padx=2)

        self.export_btn = ctk.CTkButton(
            file_group, text="⬆️ Export", width=75, height=28,
            **button_style("ghost"),
        )
        self.export_btn.pack(side="left", padx=2)

        # Separator
        ctk.CTkLabel(
            self, text="", width=1, height=20,
            fg_color=COLORS["border"],
        ).pack(side="left", padx=8, pady=8)

        # ── Job control ──
        job_group = ctk.CTkFrame(self, fg_color="transparent")
        job_group.pack(side="left", padx=4, pady=4)

        self.start_btn = ctk.CTkButton(
            job_group, text="▶ Start", width=70, height=28,
            fg_color=COLORS["connected"], hover_color="#4CD964",
            text_color="#FFFFFF", corner_radius=8,
        )
        self.start_btn.pack(side="left", padx=2)

        self.pause_btn = ctk.CTkButton(
            job_group, text="⏸ Pause", width=72, height=28,
            fg_color=COLORS["running"], hover_color="#FFB340",
            text_color="#FFFFFF", corner_radius=8,
        )
        self.pause_btn.pack(side="left", padx=2)

        self.stop_btn = ctk.CTkButton(
            job_group, text="⏹ Stop", width=65, height=28,
            **button_style("danger"),
        )
        self.stop_btn.pack(side="left", padx=2)

        # Separator
        ctk.CTkLabel(
            self, text="", width=1, height=20,
            fg_color=COLORS["border"],
        ).pack(side="left", padx=8, pady=8)

        # ── Frame + time estimate ──
        self.frame_btn = ctk.CTkButton(
            self, text="🔲 Frame", width=75, height=28,
            **button_style("default"),
        )
        self.frame_btn.pack(side="left", padx=4, pady=4)

        self.time_label = ctk.CTkLabel(
            self,
            text="⏱ Est: --",
            text_color=COLORS["text_muted"],
            font=FONTS["mono_small"],
        )
        self.time_label.pack(side="left", padx=8)

        # ── Right: progress ──
        self.progress_bar = ctk.CTkProgressBar(
            self, width=120, height=8,
            progress_color=COLORS["accent"],
            fg_color=COLORS["bg_elevated"],
        )
        self.progress_bar.pack(side="right", padx=(4, 12), pady=4)
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self,
            text="",
            text_color=COLORS["text_secondary"],
            font=FONTS["small"],
        )
        self.progress_label.pack(side="right", padx=4)

    def set_progress(self, progress: float) -> None:
        """Update progress bar and label."""
        self.progress_bar.set(progress)
        if progress <= 0:
            self.progress_label.configure(text="")
        elif progress >= 1.0:
            self.progress_label.configure(text="✅ Done")
        else:
            self.progress_label.configure(text=f"{progress * 100:.0f}%")

    def set_time_estimate(self, seconds: float | None) -> None:
        """Update time estimate display."""
        if seconds is None:
            self.time_label.configure(text="⏱ Est: --")
        else:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            self.time_label.configure(text=f"⏱ Est: {mins}m{secs:02d}s")
