"""Auto-update checker — checks GitHub releases for new versions."""

from __future__ import annotations

import json
import threading
import urllib.request
from typing import Callable

GITHUB_REPO = "quantumnic/lasermac"
CURRENT_VERSION = "0.1.0"


def check_for_update() -> dict | None:
    """Return info about latest release if newer, else None."""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "LaserMac"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        latest = data["tag_name"].lstrip("v")
        if _is_newer(latest, CURRENT_VERSION):
            return {
                "version": latest,
                "url": data["html_url"],
                "notes": data["body"][:200] if data.get("body") else "",
            }
    except Exception:
        pass
    return None


def _is_newer(latest: str, current: str) -> bool:
    """Compare semver strings. Returns True if latest > current."""
    try:
        from packaging.version import Version

        return Version(latest) > Version(current)
    except Exception:
        # Fallback: tuple comparison
        def _parts(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split(".") if x.isdigit())

        return _parts(latest) > _parts(current)


def check_async(callback: Callable[[dict | None], None]) -> None:
    """Check for update in background thread, call callback with result."""

    def _run() -> None:
        result = check_for_update()
        callback(result)

    threading.Thread(target=_run, daemon=True).start()
