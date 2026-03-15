"""Direct drawing canvas — draw shapes and send to laser.

Central concept: every shape has an operation type (cut / engrave / mark)
that determines its color on canvas, its G-code settings, and export order.

Colors:
    CUT     = Red (#FF3333)   — thick line, outline only
    ENGRAVE = Blue (#3399FF)  — normal line, supports fill
    MARK    = Green (#33CC33) — thin line, surface only

G-code export order: Mark → Engrave → Cut (cut always last!)
"""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk

from lasermac.layers import (
    OPERATION_CUT,
    OPERATION_ENGRAVE,
    OPERATION_MARK,
    OPERATIONS,
    OperationSettings,
    default_settings,
    gcode_sort_key,
    operation_color,
    operation_label,
    operation_line_width,
)

if TYPE_CHECKING:
    from lasermac.grbl import GrblController


@dataclass
class DrawElement:
    """A single drawn element on the canvas.

    Each element has its own operation type and settings — this is the
    core design: you see red = cut, blue = engrave, green = mark at a glance.
    """

    kind: str  # pen, line, rect, circle, ellipse, polygon
    points: list[tuple[float, float]] = field(default_factory=list)
    canvas_ids: list[int] = field(default_factory=list)
    settings: OperationSettings = field(default_factory=lambda: default_settings(OPERATION_ENGRAVE))

    @property
    def operation(self) -> str:
        return self.settings.operation

    @operation.setter
    def operation(self, value: str) -> None:
        if value != self.settings.operation:
            self.settings = default_settings(value)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "points": self.points,
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> DrawElement:
        settings = OperationSettings.from_dict(d.get("settings", {}))
        return cls(kind=d["kind"], points=d.get("points", []), settings=settings)


class DrawCanvas(ctk.CTkFrame):
    """Drawing canvas with operation-aware tools.

    The active operation (cut/engrave/mark) determines what color new shapes
    are drawn in and what G-code settings they get. This is THE central UX.
    """

    TOOLS = ("select", "pen", "line", "rect", "circle", "eraser")
    CANVAS_PX = 400
    DEFAULT_WORK_MM = 400.0

    def __init__(self, parent: ctk.CTkFrame, grbl: GrblController, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.grbl = grbl

        # Work area config
        self.work_w_mm = self.DEFAULT_WORK_MM
        self.work_h_mm = self.DEFAULT_WORK_MM

        # State
        self.current_tool = "pen"
        self.current_operation = OPERATION_ENGRAVE
        self.elements: list[DrawElement] = []
        self.redo_stack: list[DrawElement] = []
        self._current_element: DrawElement | None = None
        self._drag_start: tuple[float, float] | None = None
        self._preview_id: int | None = None
        self._selected_idx: int | None = None
        self._select_offset: tuple[float, float] = (0, 0)
        self.show_grid = True
        self.zoom_level = 1.0
        self.snap_grid = 0.0  # 0 = off, else snap in mm

        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Toolbar row 1: tools + undo/redo ──
        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 2))

        tool_icons = {
            "select": "🔲",
            "pen": "✏️",
            "line": "─",
            "rect": "□",
            "circle": "○",
            "eraser": "🗑️",
        }
        self._tool_buttons: dict[str, ctk.CTkButton] = {}
        for t in self.TOOLS:
            btn = ctk.CTkButton(
                toolbar,
                text=tool_icons.get(t, t),
                width=40,
                command=lambda t=t: self.set_tool(t),
            )
            btn.pack(side="left", padx=2)
            self._tool_buttons[t] = btn

        # Separator
        ctk.CTkLabel(toolbar, text="│", width=10).pack(side="left", padx=4)

        # ── OPERATION BUTTONS — the central UX element ──
        self._op_buttons: dict[str, ctk.CTkButton] = {}
        op_configs = {
            OPERATION_CUT: ("✂️ Cut", "#FF3333", "#CC2222"),
            OPERATION_ENGRAVE: ("✏️ Engrave", "#3399FF", "#2277DD"),
            OPERATION_MARK: ("🖊️ Mark", "#33CC33", "#22AA22"),
        }
        for op, (label, color, hover) in op_configs.items():
            btn = ctk.CTkButton(
                toolbar,
                text=label,
                width=90,
                fg_color=color if op == self.current_operation else "#333333",
                hover_color=hover,
                command=lambda o=op: self.set_operation(o),
            )
            btn.pack(side="left", padx=2)
            self._op_buttons[op] = btn

        # Separator
        ctk.CTkLabel(toolbar, text="│", width=10).pack(side="left", padx=4)

        ctk.CTkButton(toolbar, text="↩️", width=40, command=self.undo).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="↪️", width=40, command=self.redo).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="🗑 Clear", width=70, command=self.clear).pack(
            side="left", padx=2
        )

        ctk.CTkLabel(toolbar, text="│", width=10).pack(side="left", padx=4)

        self._grid_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(toolbar, text="Grid", variable=self._grid_var, command=self._redraw).pack(
            side="left", padx=4
        )

        ctk.CTkButton(toolbar, text="🔍+", width=35, command=self._zoom_in).pack(
            side="left", padx=2
        )
        ctk.CTkButton(toolbar, text="🔍−", width=35, command=self._zoom_out).pack(
            side="left", padx=2
        )

        # ── Canvas ──
        canvas_frame = ctk.CTkFrame(self)
        canvas_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.CANVAS_PX,
            height=self.CANVAS_PX,
            bg="#1a1a2e",
            highlightthickness=0,
        )
        self.canvas.pack(expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Keyboard shortcuts
        self.bind_all("<Control-z>", lambda e: self.undo())
        self.bind_all("<Control-y>", lambda e: self.redo())

        # ── Layer legend (bottom of canvas) ──
        legend_frame = ctk.CTkFrame(self, fg_color="transparent", height=25)
        legend_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10)
        self._legend_labels: dict[str, ctk.CTkLabel] = {}
        for op in OPERATIONS:
            color = operation_color(op)
            lbl = ctk.CTkLabel(
                legend_frame,
                text=f"● {op.upper()} (0)",
                text_color=color,
                font=("", 11),
            )
            lbl.pack(side="left", padx=10)
            self._legend_labels[op] = lbl

        # ── Bottom panel: operation settings + actions ──
        bottom = ctk.CTkFrame(self)
        bottom.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(2, 5))

        # Operation settings (dynamic)
        self._settings_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        self._settings_frame.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self._build_settings_panel()

        # Action buttons (right side)
        actions = ctk.CTkFrame(bottom, fg_color="transparent")
        actions.pack(side="right", padx=5, pady=5)

        ctk.CTkButton(
            actions,
            text="🔥 Burn This!",
            fg_color="#da3633",
            hover_color="#f85149",
            command=self._burn_click,
        ).pack(side="right", padx=5)

        ctk.CTkButton(actions, text="💾 G-code", command=self._save_gcode_click).pack(
            side="right", padx=2
        )
        ctk.CTkButton(actions, text="💾 SVG", command=self._save_svg_click).pack(
            side="right", padx=2
        )

        # Initial draw
        self._draw_grid()
        self._highlight_tool()
        self._highlight_operation()

    def _build_settings_panel(self) -> None:
        """Build the operation settings panel based on current operation."""
        for w in self._settings_frame.winfo_children():
            w.destroy()

        op = self.current_operation
        color = operation_color(op)
        label = operation_label(op)

        ctk.CTkLabel(
            self._settings_frame,
            text=label + " Settings",
            font=("", 13, "bold"),
            text_color=color,
        ).pack(side="left", padx=(0, 10))

        # Speed
        sf = ctk.CTkFrame(self._settings_frame, fg_color="transparent")
        sf.pack(side="left", padx=5)
        ctk.CTkLabel(sf, text="Speed:").pack(side="left")
        defaults = default_settings(op)
        max_speed = 10000 if op != OPERATION_CUT else 2000
        self.speed_slider = ctk.CTkSlider(
            sf, from_=50, to=max_speed, number_of_steps=100, width=100
        )
        self.speed_slider.pack(side="left", padx=3)
        self.speed_slider.set(defaults.speed)

        # Power
        pf = ctk.CTkFrame(self._settings_frame, fg_color="transparent")
        pf.pack(side="left", padx=5)
        ctk.CTkLabel(pf, text="Power:").pack(side="left")
        self.power_slider = ctk.CTkSlider(pf, from_=0, to=1000, number_of_steps=100, width=100)
        self.power_slider.pack(side="left", padx=3)
        self.power_slider.set(defaults.power)

        if op == OPERATION_CUT:
            # Passes selector
            paf = ctk.CTkFrame(self._settings_frame, fg_color="transparent")
            paf.pack(side="left", padx=5)
            ctk.CTkLabel(paf, text="Passes:").pack(side="left")
            self.passes_var = ctk.StringVar(value=str(defaults.passes))
            ctk.CTkOptionMenu(
                paf,
                variable=self.passes_var,
                values=["1", "2", "3", "4", "5", "6", "8", "10"],
                width=60,
            ).pack(side="left", padx=3)

            # Warning: no fill for cut
            ctk.CTkLabel(
                self._settings_frame,
                text="⚠️ Fill disabled for CUT",
                text_color="#FF6633",
                font=("", 11),
            ).pack(side="left", padx=10)

            # No fill sliders
            self.fill_speed_slider = None
            self.fill_power_slider = None
            self.hatch_var = ctk.StringVar(value="none")

        elif op == OPERATION_ENGRAVE:
            # Fill mode
            hf = ctk.CTkFrame(self._settings_frame, fg_color="transparent")
            hf.pack(side="left", padx=5)
            ctk.CTkLabel(hf, text="Fill:").pack(side="left")
            self.hatch_var = ctk.StringVar(value=defaults.fill_mode)
            ctk.CTkOptionMenu(
                hf,
                variable=self.hatch_var,
                values=["none", "lines", "schraffur", "kreuz", "dots", "concentric"],
                width=100,
            ).pack(side="left", padx=3)

            # Fill speed
            fsf = ctk.CTkFrame(self._settings_frame, fg_color="transparent")
            fsf.pack(side="left", padx=5)
            ctk.CTkLabel(fsf, text="F.Spd:").pack(side="left")
            self.fill_speed_slider = ctk.CTkSlider(
                fsf, from_=100, to=10000, number_of_steps=100, width=80
            )
            self.fill_speed_slider.pack(side="left", padx=3)
            self.fill_speed_slider.set(defaults.fill_speed)

            # Fill power
            fpf = ctk.CTkFrame(self._settings_frame, fg_color="transparent")
            fpf.pack(side="left", padx=5)
            ctk.CTkLabel(fpf, text="F.Pwr:").pack(side="left")
            self.fill_power_slider = ctk.CTkSlider(
                fpf, from_=0, to=1000, number_of_steps=100, width=80
            )
            self.fill_power_slider.pack(side="left", padx=3)
            self.fill_power_slider.set(defaults.fill_power)

            self.passes_var = ctk.StringVar(value="1")

        else:  # MARK
            self.fill_speed_slider = None
            self.fill_power_slider = None
            self.hatch_var = ctk.StringVar(value="none")
            self.passes_var = ctk.StringVar(value="1")

    # ── Operation selection ─────────────────────────────────────────

    def set_operation(self, operation: str) -> None:
        """Set the active operation — new shapes will use this."""
        if operation in OPERATIONS:
            self.current_operation = operation
            self._highlight_operation()
            self._build_settings_panel()

    def _highlight_operation(self) -> None:
        """Highlight the active operation button."""
        op_colors = {
            OPERATION_CUT: "#FF3333",
            OPERATION_ENGRAVE: "#3399FF",
            OPERATION_MARK: "#33CC33",
        }
        for op, btn in self._op_buttons.items():
            if op == self.current_operation:
                btn.configure(fg_color=op_colors[op])
            else:
                btn.configure(fg_color="#333333")

    def _update_legend(self) -> None:
        """Update the layer legend counts."""
        counts: dict[str, int] = {op: 0 for op in OPERATIONS}
        for elem in self.elements:
            counts[elem.operation] = counts.get(elem.operation, 0) + 1
        for op, lbl in self._legend_labels.items():
            lbl.configure(text=f"● {op.upper()} ({counts.get(op, 0)})")

    # ── Tool selection ──────────────────────────────────────────────

    def set_tool(self, tool: str) -> None:
        if tool in self.TOOLS:
            self.current_tool = tool
            self._highlight_tool()

    def _highlight_tool(self) -> None:
        for name, btn in self._tool_buttons.items():
            if name == self.current_tool:
                btn.configure(fg_color="#1f6aa5")
            else:
                btn.configure(fg_color=["#3a7ebf", "#1f538d"])

    # ── Grid / zoom ─────────────────────────────────────────────────

    def _draw_grid(self) -> None:
        self.canvas.delete("grid")
        if not self._grid_var.get():
            return
        step_mm = 50
        px_per_mm = self.CANVAS_PX * self.zoom_level / self.work_w_mm
        step_px = step_mm * px_per_mm
        size = int(self.CANVAS_PX * self.zoom_level)
        x = step_px
        while x < size:
            self.canvas.create_line(x, 0, x, size, fill="#2a2a4a", tags="grid")
            x += step_px
        y = step_px
        while y < size:
            self.canvas.create_line(0, y, size, y, fill="#2a2a4a", tags="grid")
            y += step_px

    def _zoom_in(self) -> None:
        if self.zoom_level < 4.0:
            self.zoom_level = min(4.0, self.zoom_level * 1.25)
            self._apply_zoom()

    def _zoom_out(self) -> None:
        if self.zoom_level > 0.25:
            self.zoom_level = max(0.25, self.zoom_level / 1.25)
            self._apply_zoom()

    def _apply_zoom(self) -> None:
        size = int(self.CANVAS_PX * self.zoom_level)
        self.canvas.config(width=size, height=size)
        self._redraw()

    # ── Mouse events ────────────────────────────────────────────────

    def on_mouse_down(self, event: tk.Event) -> None:
        x, y = float(event.x), float(event.y)
        tool = self.current_tool

        if tool == "select":
            self._try_select(x, y)
            return

        if tool == "eraser":
            self._try_erase(x, y)
            return

        self._drag_start = (x, y)
        settings = self._current_settings()

        if tool == "pen":
            elem = DrawElement(kind="pen", points=[(x, y)], settings=settings)
            self._current_element = elem
        elif tool in ("line", "rect", "circle"):
            self._current_element = DrawElement(kind=tool, points=[(x, y)], settings=settings)

    def on_mouse_move(self, event: tk.Event) -> None:
        x, y = float(event.x), float(event.y)
        tool = self.current_tool

        if tool == "select" and self._selected_idx is not None:
            self._move_selected(x, y)
            return

        if tool == "eraser":
            self._try_erase(x, y)
            return

        if self._current_element is None:
            return

        color = operation_color(self.current_operation)
        lw = operation_line_width(self.current_operation)

        if tool == "pen":
            last = self._current_element.points[-1]
            cid = self.canvas.create_line(
                last[0], last[1], x, y, fill=color, width=lw, tags="drawing"
            )
            self._current_element.points.append((x, y))
            self._current_element.canvas_ids.append(cid)
        elif tool in ("line", "rect", "circle"):
            if self._preview_id is not None:
                self.canvas.delete(self._preview_id)
            sx, sy = self._drag_start  # type: ignore[misc]
            if tool == "line":
                self._preview_id = self.canvas.create_line(
                    sx, sy, x, y, fill=color, width=lw, dash=(4, 4), tags="preview"
                )
            elif tool == "rect":
                self._preview_id = self.canvas.create_rectangle(
                    sx, sy, x, y, outline=color, width=lw, dash=(4, 4), tags="preview"
                )
            elif tool == "circle":
                r = math.hypot(x - sx, y - sy)
                self._preview_id = self.canvas.create_oval(
                    sx - r, sy - r, sx + r, sy + r,
                    outline=color, width=lw, dash=(4, 4), tags="preview",
                )

    def on_mouse_up(self, event: tk.Event) -> None:
        x, y = float(event.x), float(event.y)
        tool = self.current_tool

        if tool == "select":
            self._selected_idx = None
            return

        if tool == "eraser":
            return

        if self._preview_id is not None:
            self.canvas.delete(self._preview_id)
            self._preview_id = None

        if self._current_element is None:
            return

        elem = self._current_element
        self._current_element = None
        self._drag_start = None

        if tool == "pen":
            if len(elem.points) < 2:
                return
        elif tool in ("line", "rect", "circle"):
            if not elem.points:
                return
            sx, sy = elem.points[0]
            elem.points = [(sx, sy), (x, y)]
            for cid in elem.canvas_ids:
                self.canvas.delete(cid)
            elem.canvas_ids.clear()
            ids = self._render_element(elem)
            elem.canvas_ids = ids

        self.elements.append(elem)
        self.redo_stack.clear()
        self._update_legend()

    def _current_settings(self) -> OperationSettings:
        """Build OperationSettings from current UI sliders."""
        op = self.current_operation
        settings = default_settings(op)
        settings.speed = int(self.speed_slider.get())
        settings.power = int(self.power_slider.get())
        settings.passes = int(self.passes_var.get()) if hasattr(self, "passes_var") else 1

        if op == OPERATION_CUT:
            settings.fill_mode = "none"  # CUT never fills
        elif op == OPERATION_ENGRAVE:
            settings.fill_mode = self.hatch_var.get() if hasattr(self, "hatch_var") else "none"
            if self.fill_speed_slider:
                settings.fill_speed = int(self.fill_speed_slider.get())
            if self.fill_power_slider:
                settings.fill_power = int(self.fill_power_slider.get())
        else:
            settings.fill_mode = "none"

        return settings

    # ── Select / move ───────────────────────────────────────────────

    def _try_select(self, x: float, y: float) -> None:
        items = self.canvas.find_closest(x, y)
        if not items:
            return
        item_id = items[0]
        for idx, elem in enumerate(self.elements):
            if item_id in elem.canvas_ids:
                self._selected_idx = idx
                self._select_offset = (x, y)
                return

    def _move_selected(self, x: float, y: float) -> None:
        if self._selected_idx is None:
            return
        elem = self.elements[self._selected_idx]
        dx = x - self._select_offset[0]
        dy = y - self._select_offset[1]
        self._select_offset = (x, y)
        for cid in elem.canvas_ids:
            self.canvas.move(cid, dx, dy)
        elem.points = [(px + dx, py + dy) for px, py in elem.points]

    # ── Eraser ──────────────────────────────────────────────────────

    def _try_erase(self, x: float, y: float) -> None:
        items = self.canvas.find_closest(x, y)
        if not items:
            return
        item_id = items[0]
        for idx, elem in enumerate(self.elements):
            if item_id in elem.canvas_ids:
                for cid in elem.canvas_ids:
                    self.canvas.delete(cid)
                self.elements.pop(idx)
                self._update_legend()
                return

    # ── Render helpers ──────────────────────────────────────────────

    def _render_element(self, elem: DrawElement) -> list[int]:
        """Render an element on canvas using its operation color."""
        ids: list[int] = []
        color = operation_color(elem.operation)
        lw = operation_line_width(elem.operation)

        if elem.kind == "pen" and len(elem.points) >= 2:
            for i in range(len(elem.points) - 1):
                cid = self.canvas.create_line(
                    elem.points[i][0], elem.points[i][1],
                    elem.points[i + 1][0], elem.points[i + 1][1],
                    fill=color, width=lw, tags="drawing",
                )
                ids.append(cid)
        elif elem.kind == "line" and len(elem.points) == 2:
            cid = self.canvas.create_line(
                *elem.points[0], *elem.points[1], fill=color, width=lw, tags="drawing"
            )
            ids.append(cid)
        elif elem.kind == "rect" and len(elem.points) == 2:
            cid = self.canvas.create_rectangle(
                *elem.points[0], *elem.points[1], outline=color, width=lw, tags="drawing"
            )
            ids.append(cid)
        elif elem.kind == "circle" and len(elem.points) == 2:
            cx, cy = elem.points[0]
            ex, ey = elem.points[1]
            r = math.hypot(ex - cx, ey - cy)
            cid = self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline=color, width=lw, tags="drawing",
            )
            ids.append(cid)
        return ids

    # ── History ─────────────────────────────────────────────────────

    def undo(self) -> None:
        if not self.elements:
            return
        elem = self.elements.pop()
        for cid in elem.canvas_ids:
            self.canvas.delete(cid)
        self.redo_stack.append(elem)
        self._update_legend()

    def redo(self) -> None:
        if not self.redo_stack:
            return
        elem = self.redo_stack.pop()
        ids = self._render_element(elem)
        elem.canvas_ids = ids
        self.elements.append(elem)
        self._update_legend()

    def clear(self) -> None:
        self.canvas.delete("drawing")
        self.canvas.delete("preview")
        self.elements.clear()
        self.redo_stack.clear()
        self._update_legend()

    # ── Redraw ──────────────────────────────────────────────────────

    def _redraw(self) -> None:
        self.show_grid = self._grid_var.get()
        self.canvas.delete("all")
        self._draw_grid()
        for elem in self.elements:
            ids = self._render_element(elem)
            elem.canvas_ids = ids

    # ── Coordinate conversion ───────────────────────────────────────

    def px_to_mm(self, px_x: float, px_y: float) -> tuple[float, float]:
        """Convert canvas pixels to mm, accounting for zoom."""
        canvas_size = self.CANVAS_PX * self.zoom_level
        mm_x = px_x / canvas_size * self.work_w_mm
        mm_y = px_y / canvas_size * self.work_h_mm
        return round(mm_x, 3), round(mm_y, 3)

    # ── G-code generation ───────────────────────────────────────────

    def to_gcode(
        self,
        speed: int = 1000,
        power: int = 500,
        fill_speed: int = 1500,
        fill_power: int = 600,
    ) -> str:
        """Convert all drawn elements to G-code.

        Export order: Mark → Engrave → Cut (cut always last!).
        Each element uses its own per-shape settings.
        The speed/power params are fallbacks only.
        """
        lines = [
            "; Generated by LaserMac v0.3.0",
            "; Export order: Mark → Engrave → Cut",
            "G21         ; mm mode",
            "G90         ; absolute",
            "M5          ; laser off",
            "",
        ]

        # Sort elements: mark → engrave → cut
        sorted_elements = sorted(self.elements, key=lambda e: gcode_sort_key(e.operation))

        current_op = None
        for elem in sorted_elements:
            if elem.operation != current_op:
                current_op = elem.operation
                label = operation_label(current_op)
                lines.append(f"; ── {label} ──")
                lines.append("")

            s = elem.settings
            gc = self._element_to_gcode(
                elem,
                speed=s.speed or speed,
                power=s.power or power,
                fill_speed=s.fill_speed or fill_speed,
                fill_power=s.fill_power or fill_power,
                hatch=s.fill_mode if s.operation != OPERATION_CUT else "none",
                passes=s.passes if s.operation == OPERATION_CUT else 1,
            )
            if gc:
                lines.append(gc)

        lines.append("M5          ; laser off")
        lines.append("G0 X0 Y0    ; return home")
        lines.append("M2          ; end")
        return "\n".join(lines)

    def _element_to_gcode(
        self,
        elem: DrawElement,
        speed: int,
        power: int,
        fill_speed: int = 1500,
        fill_power: int = 600,
        hatch: str = "none",
        passes: int = 1,
    ) -> str:
        gc = ""
        if elem.kind == "pen":
            gc = self._draw_stroke(elem.points, speed, power)
        elif elem.kind == "line" and len(elem.points) == 2:
            gc = self._draw_line_gcode(*elem.points[0], *elem.points[1], speed, power)
        elif elem.kind == "rect" and len(elem.points) == 2:
            gc = self._draw_rect(
                *elem.points[0], *elem.points[1],
                speed, power,
                fill_speed=fill_speed, fill_power=fill_power,
                hatch=hatch,
            )
        elif elem.kind == "circle" and len(elem.points) == 2:
            cx, cy = elem.points[0]
            ex, ey = elem.points[1]
            r_px = math.hypot(ex - cx, ey - cy)
            canvas_size = self.CANVAS_PX * self.zoom_level
            r_mm = r_px / canvas_size * self.work_w_mm
            mx, my = self.px_to_mm(cx, cy)
            gc = self._draw_circle(mx, my, r_mm, speed, power)

        # Multi-pass for CUT
        if passes > 1 and gc:
            gc_lines = gc.split("\n")
            repeated = []
            for p in range(passes):
                repeated.append(f"; Pass {p + 1}/{passes}")
                repeated.extend(gc_lines)
            gc = "\n".join(repeated)

        return gc

    def _draw_stroke(self, points: list[tuple[float, float]], speed: int, power: int) -> str:
        if len(points) < 2:
            return ""
        lines: list[str] = []
        mx, my = self.px_to_mm(*points[0])
        lines.append(f"G0 X{mx} Y{my}")
        lines.append(f"M3 S{power}")
        lines.append(f"G1 F{speed}")
        for pt in points[1:]:
            mx, my = self.px_to_mm(*pt)
            lines.append(f"G1 X{mx} Y{my}")
        lines.append("M5")
        return "\n".join(lines)

    def _draw_rect(
        self, x1: float, y1: float, x2: float, y2: float,
        speed: int, power: int,
        fill_speed: int = 1500, fill_power: int = 600,
        hatch: str = "none", hatch_spacing: float = 0.8,
    ) -> str:
        p1 = self.px_to_mm(x1, y1)
        p2 = self.px_to_mm(x2, y1)
        p3 = self.px_to_mm(x2, y2)
        p4 = self.px_to_mm(x1, y2)
        lines = [
            f"G0 X{p1[0]} Y{p1[1]}",
            f"M3 S{power}",
            f"G1 X{p2[0]} Y{p2[1]} F{speed}",
            f"G1 X{p3[0]} Y{p3[1]} F{speed}",
            f"G1 X{p4[0]} Y{p4[1]} F{speed}",
            f"G1 X{p1[0]} Y{p1[1]} F{speed}",
            "M5",
        ]
        rx1, ry1 = min(p1[0], p3[0]), min(p1[1], p3[1])
        rx2, ry2 = max(p1[0], p3[0]), max(p1[1], p3[1])
        if hatch in ("lines", "schraffur", "kreuz"):
            lines.append(f"; hatch fill ({hatch}) F{fill_speed} S{fill_power}")
            lines += self._hatch_gcode(
                rx1, ry1, rx2, ry2, mode=hatch, sp=hatch_spacing,
                speed=fill_speed, power=fill_power,
            )
        return "\n".join(lines)

    def _hatch_gcode(
        self, x1: float, y1: float, x2: float, y2: float,
        mode: str = "schraffur", sp: float = 0.8,
        speed: int = 1500, power: int = 600,
    ) -> list[str]:
        gc: list[str] = []
        w, h = x2 - x1, y2 - y1

        def seg(ax, ay, bx, by):
            gc.append(f"G0 X{round(ax, 3)} Y{round(ay, 3)}")
            gc.append(f"M3 S{power}")
            gc.append(f"G1 X{round(bx, 3)} Y{round(by, 3)} F{speed}")
            gc.append("M5")

        if mode == "lines":
            y = y1 + sp
            tog = False
            while y < y2 - 0.1:
                if tog:
                    seg(x1 + 0.1, y, x2 - 0.1, y)
                else:
                    seg(x2 - 0.1, y, x1 + 0.1, y)
                y += sp
                tog = not tog

        elif mode in ("schraffur", "kreuz"):
            d = -h
            tog = False
            while d < w:
                sx = x1
                sy = y1 - d if d < 0 else y1
                if d < 0 and y1 - d > y2:
                    sy = y2
                    sx = x1 + (y2 - y1 + d)
                elif d >= 0:
                    sx = x1 + d
                ex = sx + h
                ey = sy + h
                if ex > x2:
                    ey = sy + (x2 - sx)
                    ex = x2
                if ey > y2:
                    ex = sx + (y2 - sy)
                    ey = y2
                ex = min(ex, x2)
                ey = min(ey, y2)
                sx = max(sx, x1)
                sy = max(sy, y1)
                if abs(ex - sx) > 0.2 or abs(ey - sy) > 0.2:
                    if tog:
                        seg(sx, sy, ex, ey)
                    else:
                        seg(ex, ey, sx, sy)
                d += sp
                tog = not tog

            if mode == "kreuz":
                d = 0
                tog = False
                while d < w + h:
                    if d < w:
                        sx, sy = x2 - d, y1
                    else:
                        sx, sy = x1, y1 + (d - w)
                    ex, ey = sx - h, sy + h
                    if ex < x1:
                        ey = sy + (sx - x1)
                        ex = x1
                    if ey > y2:
                        ex = sx - (y2 - sy)
                        ey = y2
                    ex = max(ex, x1)
                    ey = min(ey, y2)
                    sx = min(sx, x2)
                    if abs(ex - sx) > 0.2 or abs(ey - sy) > 0.2:
                        if tog:
                            seg(sx, sy, ex, ey)
                        else:
                            seg(ex, ey, sx, sy)
                    d += sp
                    tog = not tog
        return gc

    def _draw_circle(
        self, cx: float, cy: float, r: float, speed: int, power: int, segments: int = 36
    ) -> str:
        if r <= 0:
            return ""
        lines: list[str] = []
        start_x = round(cx + r, 3)
        start_y = round(cy, 3)
        lines.append(f"G0 X{start_x} Y{start_y}")
        lines.append(f"M3 S{power}")
        for i in range(1, segments + 1):
            angle = 2 * math.pi * i / segments
            px = round(cx + r * math.cos(angle), 3)
            py = round(cy + r * math.sin(angle), 3)
            lines.append(f"G1 X{px} Y{py}")
        lines.append("M5")
        return "\n".join(lines)

    def _draw_line_gcode(
        self, x1: float, y1: float, x2: float, y2: float, speed: int, power: int
    ) -> str:
        mx1, my1 = self.px_to_mm(x1, y1)
        mx2, my2 = self.px_to_mm(x2, y2)
        lines = [
            f"G0 X{mx1} Y{my1}",
            f"M3 S{power}",
            f"G1 X{mx2} Y{my2} F{speed}",
            "M5",
        ]
        return "\n".join(lines)

    # ── Export ──────────────────────────────────────────────────────

    def burn(
        self,
        speed: int = 1000,
        power: int = 500,
        fill_speed: int = 1500,
        fill_power: int = 600,
        hatch: str = "none",
    ) -> None:
        """Convert drawing to G-code and send to GRBL."""
        gcode = self.to_gcode(speed, power, fill_speed=fill_speed, fill_power=fill_power)
        for line in gcode.split("\n"):
            line = line.split(";")[0].strip()
            if line:
                self.grbl.send_command(line)

    def save_gcode(self, path: str, speed: int = 1000, power: int = 500) -> None:
        """Save drawing as G-code file."""
        gcode = self.to_gcode(speed, power)
        with open(path, "w") as f:
            f.write(gcode)

    def save_svg(self, path: str) -> None:
        """Save drawing as SVG file."""
        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{self.work_w_mm}mm" height="{self.work_h_mm}mm" '
            f'viewBox="0 0 {self.work_w_mm} {self.work_h_mm}">',
        ]
        for elem in self.elements:
            svg_lines.append(self._element_to_svg(elem))
        svg_lines.append("</svg>")
        with open(path, "w") as f:
            f.write("\n".join(svg_lines))

    def _element_to_svg(self, elem: DrawElement) -> str:
        color = operation_color(elem.operation)
        lw = operation_line_width(elem.operation) * 0.5
        style = f'stroke="{color}" stroke-width="{lw}" fill="none"'

        if elem.kind == "pen" and len(elem.points) >= 2:
            pts_mm = [self.px_to_mm(*p) for p in elem.points]
            d = f"M {pts_mm[0][0]},{pts_mm[0][1]}"
            for p in pts_mm[1:]:
                d += f" L {p[0]},{p[1]}"
            return f'  <path d="{d}" {style}/>'
        elif elem.kind == "line" and len(elem.points) == 2:
            p1 = self.px_to_mm(*elem.points[0])
            p2 = self.px_to_mm(*elem.points[1])
            return f'  <line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" {style}/>'
        elif elem.kind == "rect" and len(elem.points) == 2:
            p1 = self.px_to_mm(*elem.points[0])
            p2 = self.px_to_mm(*elem.points[1])
            x = min(p1[0], p2[0])
            y = min(p1[1], p2[1])
            w = abs(p2[0] - p1[0])
            h = abs(p2[1] - p1[1])
            return f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" {style}/>'
        elif elem.kind == "circle" and len(elem.points) == 2:
            cx, cy = self.px_to_mm(*elem.points[0])
            ex, ey = self.px_to_mm(*elem.points[1])
            r = math.hypot(ex - cx, ey - cy)
            return f'  <circle cx="{cx}" cy="{cy}" r="{round(r, 3)}" {style}/>'
        return ""

    def get_elements_as_dicts(self) -> list[dict]:
        """Export elements for project save."""
        return [e.to_dict() for e in self.elements]

    def load_elements_from_dicts(self, data: list[dict]) -> None:
        """Load elements from project data."""
        self.clear()
        for d in data:
            elem = DrawElement.from_dict(d)
            self.elements.append(elem)
        self._redraw()
        self._update_legend()

    # ── Button callbacks ────────────────────────────────────────────

    def _burn_click(self) -> None:
        speed = int(self.speed_slider.get())
        power = int(self.power_slider.get())
        fill_speed = int(self.fill_speed_slider.get()) if self.fill_speed_slider else 1500
        fill_power = int(self.fill_power_slider.get()) if self.fill_power_slider else 600
        hatch = self.hatch_var.get() if hasattr(self, "hatch_var") else "none"
        self.burn(speed, power, fill_speed=fill_speed, fill_power=fill_power, hatch=hatch)

    def _save_gcode_click(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".gcode", filetypes=[("G-code", "*.gcode *.nc *.ngc")]
        )
        if path:
            speed = int(self.speed_slider.get())
            power = int(self.power_slider.get())
            self.save_gcode(path, speed, power)

    def _save_svg_click(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".svg", filetypes=[("SVG", "*.svg")])
        if path:
            self.save_svg(path)
