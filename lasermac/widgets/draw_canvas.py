"""Direct drawing canvas — draw shapes and send to laser."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from lasermac.grbl import GrblController


@dataclass
class DrawElement:
    """A single drawn element on the canvas."""

    kind: str  # pen, line, rect, circle
    points: list[tuple[float, float]] = field(default_factory=list)
    canvas_ids: list[int] = field(default_factory=list)


class DrawCanvas(ctk.CTkFrame):
    """Drawing canvas with tools for creating laser-ready artwork."""

    TOOLS = ("pen", "line", "rect", "circle", "eraser", "select")
    CANVAS_PX = 400
    DEFAULT_WORK_MM = 400.0  # Totem S default

    def __init__(self, parent: ctk.CTkFrame, grbl: GrblController, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.grbl = grbl

        # Work area config
        self.work_w_mm = self.DEFAULT_WORK_MM
        self.work_h_mm = self.DEFAULT_WORK_MM

        # State
        self.current_tool = "pen"
        self.elements: list[DrawElement] = []
        self.redo_stack: list[DrawElement] = []
        self._current_element: DrawElement | None = None
        self._drag_start: tuple[float, float] | None = None
        self._preview_id: int | None = None
        self._selected_idx: int | None = None
        self._select_offset: tuple[float, float] = (0, 0)
        self.show_grid = True
        self.zoom_level = 1.0

        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Toolbar ──
        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 2))

        tool_icons = {
            "pen": "✏️",
            "line": "─",
            "rect": "□",
            "circle": "○",
            "eraser": "🗑️",
            "select": "🔲",
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
        ctk.CTkLabel(toolbar, text="|", width=10).pack(side="left", padx=4)

        ctk.CTkButton(toolbar, text="↩️", width=40, command=self.undo).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="↪️", width=40, command=self.redo).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="🗑 Clear", width=70, command=self.clear).pack(
            side="left", padx=2
        )

        ctk.CTkLabel(toolbar, text="|", width=10).pack(side="left", padx=4)

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

        # ── Bottom panel: speed/power + actions ──
        bottom = ctk.CTkFrame(self)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=(2, 5))

        # Speed
        sf = ctk.CTkFrame(bottom, fg_color="transparent")
        sf.pack(side="left", padx=10, pady=5)
        ctk.CTkLabel(sf, text="Speed (mm/min):").pack(side="left")
        self.speed_slider = ctk.CTkSlider(sf, from_=100, to=10000, number_of_steps=100, width=120)
        self.speed_slider.pack(side="left", padx=5)
        self.speed_slider.set(1000)

        # Power
        pf = ctk.CTkFrame(bottom, fg_color="transparent")
        pf.pack(side="left", padx=10, pady=5)
        ctk.CTkLabel(pf, text="Power (S):").pack(side="left")
        self.power_slider = ctk.CTkSlider(pf, from_=0, to=1000, number_of_steps=100, width=120)
        self.power_slider.pack(side="left", padx=5)
        self.power_slider.set(500)

        # Action buttons
        ctk.CTkButton(
            bottom,
            text="🔥 Burn This!",
            fg_color="#da3633",
            hover_color="#f85149",
            command=self._burn_click,
        ).pack(side="right", padx=5, pady=5)

        ctk.CTkButton(bottom, text="💾 G-code", command=self._save_gcode_click).pack(
            side="right", padx=2, pady=5
        )
        ctk.CTkButton(bottom, text="💾 SVG", command=self._save_svg_click).pack(
            side="right", padx=2, pady=5
        )

        # Initial draw
        self._draw_grid()
        self._highlight_tool()

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
        if tool == "pen":
            elem = DrawElement(kind="pen", points=[(x, y)])
            self._current_element = elem
        elif tool in ("line", "rect", "circle"):
            self._current_element = DrawElement(kind=tool, points=[(x, y)])

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

        if tool == "pen":
            last = self._current_element.points[-1]
            cid = self.canvas.create_line(
                last[0], last[1], x, y, fill="#00ff88", width=2, tags="drawing"
            )
            self._current_element.points.append((x, y))
            self._current_element.canvas_ids.append(cid)
        elif tool in ("line", "rect", "circle"):
            if self._preview_id is not None:
                self.canvas.delete(self._preview_id)
            sx, sy = self._drag_start  # type: ignore[misc]
            if tool == "line":
                self._preview_id = self.canvas.create_line(
                    sx, sy, x, y, fill="#00ff88", width=2, dash=(4, 4), tags="preview"
                )
            elif tool == "rect":
                self._preview_id = self.canvas.create_rectangle(
                    sx, sy, x, y, outline="#00ff88", width=2, dash=(4, 4), tags="preview"
                )
            elif tool == "circle":
                r = math.hypot(x - sx, y - sy)
                self._preview_id = self.canvas.create_oval(
                    sx - r,
                    sy - r,
                    sx + r,
                    sy + r,
                    outline="#00ff88",
                    width=2,
                    dash=(4, 4),
                    tags="preview",
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
            # Draw final shape
            for cid in elem.canvas_ids:
                self.canvas.delete(cid)
            elem.canvas_ids.clear()
            ids = self._render_element(elem)
            elem.canvas_ids = ids

        self.elements.append(elem)
        self.redo_stack.clear()

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
                return

    # ── Render helpers ──────────────────────────────────────────────

    def _render_element(self, elem: DrawElement) -> list[int]:
        ids: list[int] = []
        if elem.kind == "pen" and len(elem.points) >= 2:
            for i in range(len(elem.points) - 1):
                cid = self.canvas.create_line(
                    elem.points[i][0],
                    elem.points[i][1],
                    elem.points[i + 1][0],
                    elem.points[i + 1][1],
                    fill="#00ff88",
                    width=2,
                    tags="drawing",
                )
                ids.append(cid)
        elif elem.kind == "line" and len(elem.points) == 2:
            cid = self.canvas.create_line(
                *elem.points[0], *elem.points[1], fill="#00ff88", width=2, tags="drawing"
            )
            ids.append(cid)
        elif elem.kind == "rect" and len(elem.points) == 2:
            cid = self.canvas.create_rectangle(
                *elem.points[0], *elem.points[1], outline="#00ff88", width=2, tags="drawing"
            )
            ids.append(cid)
        elif elem.kind == "circle" and len(elem.points) == 2:
            cx, cy = elem.points[0]
            ex, ey = elem.points[1]
            r = math.hypot(ex - cx, ey - cy)
            cid = self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r, outline="#00ff88", width=2, tags="drawing"
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

    def redo(self) -> None:
        if not self.redo_stack:
            return
        elem = self.redo_stack.pop()
        ids = self._render_element(elem)
        elem.canvas_ids = ids
        self.elements.append(elem)

    def clear(self) -> None:
        self.canvas.delete("drawing")
        self.canvas.delete("preview")
        self.elements.clear()
        self.redo_stack.clear()

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

    def to_gcode(self, speed: int = 1000, power: int = 500) -> str:
        """Convert all drawn elements to G-code."""
        lines = [
            "G21         ; mm mode",
            "G90         ; absolute",
            f"G1 F{speed}    ; feed rate",
            "M5          ; laser off",
            "",
        ]

        for elem in self.elements:
            gc = self._element_to_gcode(elem, speed, power)
            if gc:
                lines.append(gc)

        lines.append("M5          ; laser off")
        lines.append("G0 X0 Y0    ; return home")
        lines.append("M2          ; end")
        return "\n".join(lines)

    def _element_to_gcode(self, elem: DrawElement, speed: int, power: int) -> str:
        if elem.kind == "pen":
            return self._draw_stroke(elem.points, speed, power)
        elif elem.kind == "line" and len(elem.points) == 2:
            return self._draw_line_gcode(*elem.points[0], *elem.points[1], speed, power)
        elif elem.kind == "rect" and len(elem.points) == 2:
            return self._draw_rect(*elem.points[0], *elem.points[1], speed, power)
        elif elem.kind == "circle" and len(elem.points) == 2:
            cx, cy = elem.points[0]
            ex, ey = elem.points[1]
            r_px = math.hypot(ex - cx, ey - cy)
            # Convert radius to mm
            canvas_size = self.CANVAS_PX * self.zoom_level
            r_mm = r_px / canvas_size * self.work_w_mm
            mx, my = self.px_to_mm(cx, cy)
            return self._draw_circle(mx, my, r_mm, speed, power)
        return ""

    def _draw_stroke(self, points: list[tuple[float, float]], speed: int, power: int) -> str:
        """Convert a freehand stroke to G-code."""
        if len(points) < 2:
            return ""
        lines: list[str] = []
        mx, my = self.px_to_mm(*points[0])
        lines.append(f"G0 X{mx} Y{my}")
        lines.append(f"M3 S{power}")
        for pt in points[1:]:
            mx, my = self.px_to_mm(*pt)
            lines.append(f"G1 X{mx} Y{my}")
        lines.append("M5")
        return "\n".join(lines)

    def _draw_rect(self, x1: float, y1: float, x2: float, y2: float, speed: int, power: int) -> str:
        """Convert a rectangle (in px) to G-code."""
        p1 = self.px_to_mm(x1, y1)
        p2 = self.px_to_mm(x2, y1)
        p3 = self.px_to_mm(x2, y2)
        p4 = self.px_to_mm(x1, y2)
        lines = [
            f"G0 X{p1[0]} Y{p1[1]}",
            f"M3 S{power}",
            f"G1 X{p2[0]} Y{p2[1]}",
            f"G1 X{p3[0]} Y{p3[1]}",
            f"G1 X{p4[0]} Y{p4[1]}",
            f"G1 X{p1[0]} Y{p1[1]}",
            "M5",
        ]
        return "\n".join(lines)

    def _draw_circle(
        self, cx: float, cy: float, r: float, speed: int, power: int, segments: int = 36
    ) -> str:
        """Convert a circle (in mm) to G-code via line segments."""
        if r <= 0:
            return ""
        lines: list[str] = []
        # Move to start point
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
        """Convert a line (in px) to G-code."""
        mx1, my1 = self.px_to_mm(x1, y1)
        mx2, my2 = self.px_to_mm(x2, y2)
        lines = [
            f"G0 X{mx1} Y{my1}",
            f"M3 S{power}",
            f"G1 X{mx2} Y{my2}",
            "M5",
        ]
        return "\n".join(lines)

    # ── Export ──────────────────────────────────────────────────────

    def burn(self, speed: int = 1000, power: int = 500) -> None:
        """Convert drawing to G-code and send to GRBL."""
        gcode = self.to_gcode(speed, power)
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
        style = 'stroke="#00ff88" stroke-width="0.5" fill="none"'
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

    # ── Button callbacks ────────────────────────────────────────────

    def _burn_click(self) -> None:
        speed = int(self.speed_slider.get())
        power = int(self.power_slider.get())
        self.burn(speed, power)

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
