"""GRBL console widget — modern themed."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.grbl import GrblController
from lasermac.theme import COLORS, FONTS, button_style


class ConsolePanel(ctk.CTkFrame):
    """Console for sending G-code and viewing responses."""

    def __init__(self, parent, grbl: GrblController, **kwargs) -> None:
        kwargs.setdefault("fg_color", COLORS["bg_card"])
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", COLORS["border"])
        super().__init__(parent, **kwargs)
        self.grbl = grbl

        # Title
        ctk.CTkLabel(
            self, text="CONSOLE",
            font=FONTS["small"],
            text_color=COLORS["text_muted"],
        ).pack(pady=(8, 4), padx=12, anchor="w")

        # Output log
        self.log = ctk.CTkTextbox(
            self, height=150,
            font=FONTS["mono_small"],
            fg_color=COLORS["bg_base"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=6,
        )
        self.log.pack(fill="both", expand=True, padx=10, pady=4)
        self.log.configure(state="disabled")

        # Command input
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=4)

        self.cmd_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="G-code command...",
            font=FONTS["mono_small"],
            fg_color=COLORS["bg_elevated"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            height=28,
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.cmd_entry.bind("<Return>", self._send_command)

        ctk.CTkButton(
            input_frame, text="Send", width=55, height=28,
            command=self._send_command,
            **button_style("accent"),
        ).pack(side="right")

        # Quick commands
        quick_frame = ctk.CTkFrame(self, fg_color="transparent")
        quick_frame.pack(fill="x", padx=10, pady=(0, 8))

        buttons = [
            ("🏠 Home", lambda: self.grbl.home()),
            ("🔓 Unlock", lambda: self.grbl.unlock()),
            ("🔄 Reset", lambda: self.grbl.soft_reset()),
            ("❓ Status", lambda: self.grbl.send_realtime("?")),
        ]
        for text, cmd in buttons:
            ctk.CTkButton(
                quick_frame, text=text, width=72, height=24,
                command=cmd,
                **button_style("ghost"),
                font=FONTS["muted"],
            ).pack(side="left", padx=2)

        # Register message callback
        self.grbl.on_message = self._log_message

    def _send_command(self, event=None) -> None:
        """Send command from entry."""
        cmd = self.cmd_entry.get().strip()
        if cmd:
            self.grbl.send_command(cmd)
            self.cmd_entry.delete(0, "end")

    def _log_message(self, msg: str) -> None:
        """Append message to log."""
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
