# -*- coding: utf-8 -*-
"""phi.icon — load the φ app icon from phi/resources/phi_icon.png.

Qt entry point : load_qt() → QIcon
Fallback       : if the resource file is missing, renders a minimal PIL icon.
"""
from __future__ import annotations

import io
import pathlib

_RESOURCES = pathlib.Path(__file__).parent / "resources"
_ICON_PNG  = _RESOURCES / "phi_icon.png"

# Palette used by the PIL fallback only
_BG   = (13,  13,  13,  255)
_GOLD = (201, 162,  39,  255)


def _make_fallback_icon(size: int = 128):
    """Minimal PIL icon — dark circle + gold φ glyph (used if resource missing)."""
    from PIL import Image, ImageDraw, ImageFont

    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(2, size // 16)
    draw.ellipse([pad, pad, size - pad, size - pad], fill=_BG)
    draw.ellipse([pad, pad, size - pad, size - pad],
                 outline=(*_GOLD[:3], 180), width=max(1, size // 32))

    font_size  = int(size * 0.54)
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font = None
    for fp in font_paths:
        try:
            from PIL import ImageFont as _IF
            font = _IF.truetype(fp, font_size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        from PIL import ImageFont as _IF
        font = _IF.load_default()

    draw.text((size // 2, size // 2), "φ", fill=_GOLD, font=font, anchor="mm")
    return img


def load_qt(size: int = 512):
    """Return a QIcon sourced from phi/resources/phi_icon.png (PySide6).

    Uses QPixmap.loadFromData() rather than QPixmap(path) so that Qt's own
    in-memory PNG decoder is used on every platform.  On macOS, loading a PNG
    by file path delegates to Apple's ImageIO / NSImage stack, which contains
    a SIGBUS bug in PNGReadPlugin::InitializePluginData on macOS 26+ that
    cannot be caught by Python exception handlers.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPixmap

    if _ICON_PNG.exists():
        try:
            data = _ICON_PNG.read_bytes()
            px = QPixmap()
            px.loadFromData(data, "PNG")
            if not px.isNull():
                if size < 512:
                    px = px.scaled(
                        size, size,
                        aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                        mode=Qt.TransformationMode.SmoothTransformation,
                    )
                return QIcon(px)
        except Exception:
            pass

    # fallback — rendered in Python, never touches Apple's image stack
    img = _make_fallback_icon(size)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    px = QPixmap()
    px.loadFromData(buf.read(), "PNG")
    return QIcon(px)


def as_bytes(size: int = 128) -> bytes:
    """Return the icon as PNG bytes (framework-agnostic)."""
    if _ICON_PNG.exists():
        from PIL import Image
        img = Image.open(_ICON_PNG).convert("RGBA").resize(
            (size, size), Image.LANCZOS
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    buf = io.BytesIO()
    _make_fallback_icon(size).save(buf, format="PNG")
    return buf.getvalue()
