"""GRBL console widget."""

from __future__ import annotations

import customtkinter as ctk

from lasermac.grbl import GrblController


class ConsolePanel(ctk.CTkFrame):
    """Console for sending G-code and viewing responses."""

    def __init__(self, parent, grbl: GrblController, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.grbl = grbl

        # Title
        ctk.CTkLabel(self, text="📟 Console", font=("", 16, "bold")).pack(
            pady=(10, 5), padx=10, anchor="w"
        )

        # Output log
        self.log = ctk.CTkTextbox(self, height=200, font=("Menlo", 12))
        self.log.pack(fill="both", expand=True, padx=10, pady=5)
        self.log.configure(state="disabled")

        # Command input
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=5)

        self.cmd_entry = ctk.CTkEntry(
            input_frame, placeholder_text="G-code command...", font=("Menlo", 12)
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.cmd_entry.bind("<Return>", self._send_command)

        ctk.CTkButton(
            input_frame, text="Send", width=60, command=self._send_command
        ).pack(side="right")

        # Quick commands
        quick_frame = ctk.CTkFrame(self, fg_color="transparent")
        quick_frame.pack(fill="x", padx=10, pady=(0, 10))

        buttons = [
            ("🏠 Home", lambda: self.grbl.home()),
            ("🔓 Unlock", lambda: self.grbl.unlock()),
            ("🔄 Reset", lambda: self.grbl.soft_reset()),
            ("❓ Status", lambda: self.grbl.send_realtime("?")),
        ]
        for text, cmd in buttons:
            ctk.CTkButton(
                quick_frame, text=text, width=80, command=cmd,
                fg_color="#333333", hover_color="#444444",
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
