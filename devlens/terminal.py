"""Terminal rendering helpers: ANSI colors with automatic plain-text fallback.

No third-party terminal UI library (e.g. Rich, Colorama) is used. Color
support is detected via standard library only (``sys.stdout.isatty()``
and the ``NO_COLOR`` / ``TERM`` environment conventions).
"""

from __future__ import annotations

import os
import sys

_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
}

SEVERITY_COLOR = {
    "CRITICAL": "bright_red",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "cyan",
    "INFO": "dim",
}


class Palette:
    """Wraps text in ANSI codes, or returns plain text if colors are disabled."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        prefix = "".join(_CODES.get(s, "") for s in styles)
        return f"{prefix}{text}{_CODES['reset']}"

    def severity(self, text: str, severity: str) -> str:
        return self(text, SEVERITY_COLOR.get(severity, "white"), "bold")


def color_enabled(no_color_flag: bool) -> bool:
    if no_color_flag:
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def make_palette(no_color_flag: bool) -> Palette:
    return Palette(color_enabled(no_color_flag))
