from __future__ import annotations

from datetime import datetime
from pathlib import Path


def capture_screenshot(output_dir: str | Path, prefix: str) -> Path | None:
    """Capture the full desktop after a failed POS step, returning None on failure."""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_prefix = "".join(ch for ch in prefix if ch.isalnum() or ch in ("-", "_")) or "screenshot"
    target = target_dir / f"{safe_prefix}-{datetime.now():%Y%m%d-%H%M%S}.png"
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            shot = sct.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            image.save(target)
        return target
    except Exception:
        return None
