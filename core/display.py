"""Display utility functions for Playwright screen resolution detection."""

import ctypes
from typing import Tuple

def get_screen_resolution() -> Tuple[int, int]:
    """
    Detect the user's primary monitor resolution dynamically.
    Returns:
        Tuple[int, int]: The width and height in pixels.
    """
    try:
        user32 = ctypes.windll.user32
        # DPI awareness is usually needed for accurate physical pixels, 
        # but Playwright viewport expects CSS pixels which match these metrics directly.
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        
        # Fallback to sensible defaults if something fails
        if width <= 0 or height <= 0:
            return (1536, 864)
            
        return (width, height)
    except Exception:
        # Fallback to a common laptop resolution
        return (1536, 864)
