# 🔥 LaserMac

**Free, open-source macOS laser engraver controller for GRBL machines.**

A modern alternative to LightBurn — built with Python and CustomTkinter. Works with Totem S, xTool, Ortur, Atomstack, and any GRBL-compatible laser engraver or CNC machine.

![LaserMac Screenshot](docs/screenshot.png)
*Screenshot coming soon*

---

## ✨ Features

- **🔌 Serial Connection** — Auto-detect ports, one-click connect, baud rate selection
- **📟 GRBL Console** — Send raw G-code, live output log, quick commands (Home, Unlock, Reset)
- **🎮 Jog Controls** — X/Y/Z arrows with configurable step sizes (0.1–50mm)
- **📁 File Loading** — Open `.nc`, `.gcode`, `.gc` files directly
- **🖼️ Image Engraving** — Convert PNG/JPG/BMP to G-code with multiple dithering modes
  - Floyd-Steinberg dithering
  - Threshold (black/white)
  - Grayscale line engraving
- **✏️ SVG Vector Cutting** — Convert SVG paths to G-code for vector cuts
- **👁️ Live Preview** — Matplotlib-powered toolpath visualization
- **▶️ Job Control** — Start, Pause, Stop with progress bar and time estimate
- **🔦 Laser Test** — Power/speed sliders for safe test firing
- **🔲 Frame Trace** — Trace the job bounding box with laser off before engraving
- **⚡ Speed & Power Overrides** — Adjust on the fly

## 🖥️ Supported Machines

- **Totem S** laser engraver
- **xTool D1** / D1 Pro
- **Ortur** Laser Master series
- **Atomstack** A5 / S10 / X20 Pro
- **Sculpfun** S9 / S30
- Any machine running **GRBL firmware** over USB serial

## 📦 Installation

### From PyPI (recommended)

```bash
pip install lasermac
```

### From source

```bash
git clone https://github.com/quantumnic/lasermac.git
cd lasermac
pip install -e .
```

## 🚀 Usage

```bash
lasermac
```

That's it. The app launches with a dark-themed GUI.

### Quick Start

1. **Connect** — Select your serial port and click Connect
2. **Unlock** — Click 🔓 Unlock if the machine shows an alarm
3. **Load** — Load a G-code file, image, or SVG
4. **Preview** — Check the toolpath in the preview panel
5. **Frame** — Click 🔲 Frame to trace the bounding box (laser off)
6. **Start** — Click ▶ Start to begin engraving

### Image Engraving

1. Load a PNG/JPG/BMP file
2. Set width (mm), DPI, and dithering mode
3. Click Convert to generate G-code
4. Preview and start

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send console command |

## 🏗️ Architecture

```
lasermac/
├── main.py                    # Entry point
├── lasermac/
│   ├── app.py                 # Main window (CustomTkinter)
│   ├── grbl.py                # GRBL serial controller
│   ├── gcode.py               # G-code parser + sender
│   ├── image_converter.py     # Image → G-code (raster)
│   ├── svg_converter.py       # SVG → G-code (vector)
│   ├── preview.py             # Matplotlib toolpath preview
│   └── widgets/
│       ├── connection.py      # Serial connection panel
│       ├── console.py         # G-code console
│       ├── controls.py        # Jog controls
│       └── job_panel.py       # Job loading & control
└── tests/
    ├── test_grbl.py
    ├── test_gcode.py
    └── test_image_converter.py
```

## 🧪 Development

```bash
git clone https://github.com/quantumnic/lasermac.git
cd lasermac
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -q

# Lint
ruff check lasermac/ tests/
```

## 📄 License

MIT License — free to use, modify, and distribute.

## 🤝 Contributing

Contributions welcome! Open issues or PRs on [GitHub](https://github.com/quantumnic/lasermac).

## 🙏 Acknowledgments

- [GRBL](https://github.com/grbl/grbl) — The open-source CNC firmware
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — Modern Python UI
- Built as a free alternative to [LightBurn](https://lightburnsoftware.com/)
