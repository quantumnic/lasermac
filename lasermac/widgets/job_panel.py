"""Job panel widget — file loading, preview, and job control."""

from __future__ import annotations

import os
from tkinter import filedialog

import customtkinter as ctk

from lasermac.gcode import GcodeJob, GcodeSender, estimate_time, load_gcode, load_gcode_from_string
from lasermac.grbl import GrblController
from lasermac.image_converter import image_to_gcode
from lasermac.preview import PreviewCanvas
from lasermac.svg_converter import svg_to_gcode

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"}
GCODE_EXTENSIONS = {".nc", ".gcode", ".gc", ".ngc", ".tap"}
SVG_EXTENSIONS = {".svg"}


class JobPanel(ctk.CTkFrame):
    """Panel for loading files, previewing toolpaths, and controlling jobs."""

    def __init__(self, parent, grbl: GrblController, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.grbl = grbl
        self.sender = GcodeSender(grbl)
        self.current_job: GcodeJob | None = None

        # Title + load button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(header, text="📁 Job", font=("", 16, "bold")).pack(side="left")
        ctk.CTkButton(
            header, text="Load File", command=self._load_file, width=100
        ).pack(side="right")

        # File info
        self.file_label = ctk.CTkLabel(self, text="No file loaded", text_color="#888888")
        self.file_label.pack(padx=10, anchor="w")

        # Preview canvas
        self.preview = PreviewCanvas(self)

        # Image conversion settings (hidden by default)
        self.img_settings = ctk.CTkFrame(self)
        self._setup_image_settings()

        # Overrides
        override_frame = ctk.CTkFrame(self, fg_color="transparent")
        override_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(override_frame, text="Speed:").pack(side="left")
        self.speed_var = ctk.StringVar(value="3000")
        ctk.CTkEntry(override_frame, textvariable=self.speed_var, width=60).pack(side="left", padx=2)
        ctk.CTkLabel(override_frame, text="mm/min").pack(side="left", padx=(0, 10))

        ctk.CTkLabel(override_frame, text="Power:").pack(side="left")
        self.power_var = ctk.StringVar(value="1000")
        ctk.CTkEntry(override_frame, textvariable=self.power_var, width=60).pack(side="left", padx=2)
        ctk.CTkLabel(override_frame, text="S").pack(side="left")

        # Progress
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(self, text="0%")
        self.progress_label.pack(padx=10)

        # Control buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.start_btn = ctk.CTkButton(
            btn_frame, text="▶ Start", command=self._start_job,
            fg_color="#2ea043", hover_color="#3fb950", width=80,
        )
        self.start_btn.pack(side="left", padx=2)

        self.pause_btn = ctk.CTkButton(
            btn_frame, text="⏸ Pause", command=self._pause_job,
            fg_color="#d29922", hover_color="#e3b341", width=80,
        )
        self.pause_btn.pack(side="left", padx=2)

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="⏹ Stop", command=self._stop_job,
            fg_color="#da3633", hover_color="#f85149", width=80,
        )
        self.stop_btn.pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="🔲 Frame", command=self._run_frame,
            fg_color="#333333", hover_color="#444444", width=80,
        ).pack(side="left", padx=2)

        # Register callbacks
        self.sender.on_progress = self._update_progress
        self.sender.on_complete = self._on_complete

    def _setup_image_settings(self) -> None:
        """Setup image conversion settings panel."""
        ctk.CTkLabel(self.img_settings, text="Image Settings", font=("", 13, "bold")).pack(
            padx=10, pady=(5, 2), anchor="w"
        )

        row1 = ctk.CTkFrame(self.img_settings, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(row1, text="Width (mm):").pack(side="left")
        self.img_width_var = ctk.StringVar(value="100")
        ctk.CTkEntry(row1, textvariable=self.img_width_var, width=60).pack(side="left", padx=5)

        ctk.CTkLabel(row1, text="DPI:").pack(side="left", padx=(10, 0))
        self.img_dpi_var = ctk.StringVar(value="10")
        ctk.CTkEntry(row1, textvariable=self.img_dpi_var, width=40).pack(side="left", padx=5)

        row2 = ctk.CTkFrame(self.img_settings, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(row2, text="Mode:").pack(side="left")
        self.img_mode_var = ctk.StringVar(value="threshold")
        ctk.CTkOptionMenu(
            row2, variable=self.img_mode_var,
            values=["threshold", "floyd", "grayscale"], width=120,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            row2, text="Convert", command=self._convert_image, width=80,
            fg_color="#1a5276", hover_color="#2471a3",
        ).pack(side="right")

    def _load_file(self) -> None:
        """Open file dialog and load a file."""
        filetypes = [
            ("All supported", "*.nc *.gcode *.gc *.ngc *.png *.jpg *.jpeg *.bmp *.svg"),
            ("G-code", "*.nc *.gcode *.gc *.ngc *.tap"),
            ("Images", "*.png *.jpg *.jpeg *.bmp *.tiff"),
            ("SVG", "*.svg"),
        ]
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if not filepath:
            return

        ext = os.path.splitext(filepath)[1].lower()
        self.file_label.configure(text=os.path.basename(filepath))

        if ext in GCODE_EXTENSIONS:
            self.img_settings.pack_forget()
            self.current_job = load_gcode(filepath)
            self._show_preview()
        elif ext in IMAGE_EXTENSIONS:
            self._current_image_path = filepath
            self.img_settings.pack(fill="x", padx=10, pady=5, before=self.progress_bar)
            self._convert_image()
        elif ext in SVG_EXTENSIONS:
            self.img_settings.pack_forget()
            gcode = svg_to_gcode(
                filepath,
                speed=int(self.speed_var.get()),
                power=int(self.power_var.get()),
            )
            self.current_job = load_gcode_from_string(gcode, os.path.basename(filepath))
            self._show_preview()

    def _convert_image(self) -> None:
        """Convert loaded image to G-code."""
        if not hasattr(self, "_current_image_path"):
            return

        gcode = image_to_gcode(
            self._current_image_path,
            width_mm=float(self.img_width_var.get()),
            dpi=int(self.img_dpi_var.get()),
            mode=self.img_mode_var.get(),
            speed=int(self.speed_var.get()),
            power_max=int(self.power_var.get()),
        )
        self.current_job = load_gcode_from_string(gcode, "image_engrave")
        self._show_preview()

    def _show_preview(self) -> None:
        """Update preview canvas."""
        if self.current_job:
            self.preview.draw_gcode(self.current_job.lines)
            est = estimate_time(self.current_job.lines)
            mins = int(est // 60)
            secs = int(est % 60)
            self.file_label.configure(
                text=f"{self.current_job.filename} — {self.current_job.total_lines} lines — ~{mins}m{secs}s"
            )

    def _start_job(self) -> None:
        """Start the current job."""
        if self.current_job and self.grbl.connected:
            self.sender.start(self.current_job)

    def _pause_job(self) -> None:
        """Pause/resume the current job."""
        if self.current_job and self.current_job.paused:
            self.sender.resume()
            self.pause_btn.configure(text="⏸ Pause")
        else:
            self.sender.pause()
            self.pause_btn.configure(text="▶ Resume")

    def _stop_job(self) -> None:
        """Stop the current job."""
        self.sender.stop()
        self.progress_bar.set(0)
        self.progress_label.configure(text="Stopped")

    def _run_frame(self) -> None:
        """Trace the job bounding box."""
        if self.current_job and self.grbl.connected:
            b = self.current_job.bounds
            self.grbl.run_frame(b[0], b[1], b[2], b[3])

    def _update_progress(self, progress: float) -> None:
        """Update progress bar."""
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"{progress * 100:.1f}%")

    def _on_complete(self) -> None:
        """Job completed."""
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="✅ Complete")
