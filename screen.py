import ctypes
from ctypes import wintypes
import time

import mss
import numpy as np

# Make the process DPI-aware so Windows doesn't virtualize coordinates on HiDPI displays.
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

# Baseline (authoring) resolution for all hard-coded coordinates / ROIs.
BASE_WIDTH = 2560
BASE_HEIGHT = 1440

DEFAULT_WINDOW_TITLE = "ArkAscended"

# Public globals populated at import-time (and refreshable via refresh()).
screen_resolution: int  # backwards-compat alias: the game window client height in pixels
screen_width: int
screen_height: int

# Client-area top-left on the desktop (for mss grabs).
client_left: int
client_top: int

# mss "monitor" dict for full client area.
mon: dict

# Coordinate mapping parameters
ui_mode: str  # "centered_16_9" (default) or "stretch"
scale_x: float
scale_y: float
offset_x: float
offset_y: float


def _find_hwnd(title: str) -> int:
    return ctypes.windll.user32.FindWindowW(None, title)


def _get_client_area(hwnd: int):
    """
    Returns (client_left, client_top, client_width, client_height) in *desktop* coordinates.
    Uses GetClientRect + ClientToScreen so borders/titlebar are excluded.
    """
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("GetClientRect failed")

    # Convert client (0,0) to screen coordinates.
    pt = wintypes.POINT(0, 0)
    if not ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        raise RuntimeError("ClientToScreen failed")

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    return int(pt.x), int(pt.y), int(width), int(height)


def refresh(window_title: str = DEFAULT_WINDOW_TITLE):
    """
    Re-detect the game window client size and recompute scaling + capture region.
    Call this if you change resolution while the bot is running.
    """
    global screen_resolution, screen_width, screen_height
    global client_left, client_top, mon
    global ui_mode, scale_x, scale_y, offset_x, offset_y

    hwnd = _find_hwnd(window_title)
    if not hwnd:
        print(f'Could not find window titled "{window_title}". Start the game first.')
        time.sleep(5)
        raise SystemExit(1)

    left, top, width, height = _get_client_area(hwnd)

    screen_width = width
    screen_height = height
    screen_resolution = height  # legacy name used across the repo

    # Read settings lazily to avoid circular imports.
    try:
        import settings  # type: ignore
        ui_mode = getattr(settings, "ui_layout_mode", "centered_16_9")
    except Exception:
        ui_mode = "centered_16_9"

    ui_mode = (ui_mode or "centered_16_9").strip().lower()

    if ui_mode == "stretch":
        scale_x = screen_width / float(BASE_WIDTH)
        scale_y = screen_height / float(BASE_HEIGHT)
        offset_x = 0.0
        offset_y = 0.0
    else:
        # Default: treat UI as a 16:9 canvas that scales with HEIGHT and stays centered on wider aspects.
        scale_x = screen_height / float(BASE_HEIGHT)
        scale_y = scale_x
        expected_ui_width = BASE_WIDTH * scale_x
        offset_x = max(0.0, (screen_width - expected_ui_width) / 2.0)
        offset_y = 0.0

    client_left = left
    client_top = top

    mon = {"top": client_top, "left": client_left, "width": screen_width, "height": screen_height}

    print(
        f"[screen] client={screen_width}x{screen_height} "
        f"mode={ui_mode} scale_x={scale_x:.4f} scale_y={scale_y:.4f} offset_x={offset_x:.1f}"
    )


# Initialize at import time.
refresh()


def map_x(base_x: float) -> int:
    """Map a BASE_WIDTH coordinate (x) into current client coordinates."""
    return int(round(offset_x + (base_x * scale_x)))


def map_y(base_y: float) -> int:
    """Map a BASE_HEIGHT coordinate (y) into current client coordinates."""
    return int(round(offset_y + (base_y * scale_y)))


def map_w(base_w: float) -> int:
    """Map a BASE_WIDTH length (w) into current client length."""
    return int(round(base_w * scale_x))


def map_h(base_h: float) -> int:
    """Map a BASE_HEIGHT length (h) into current client length."""
    return int(round(base_h * scale_y))


def get_screen_roi(start_x: int, start_y: int, width: int, height: int, base_coords: bool = True):
    """
    Capture an ROI using mss and return a numpy array.

    - base_coords=True: inputs are authored for 2560x1440 and will be scaled/center-offset automatically.
    - base_coords=False: inputs are already client coordinates (no scaling applied).
    """
    if base_coords:
        cx = map_x(start_x)
        cy = map_y(start_y)
        cw = max(1, map_w(width))
        ch = max(1, map_h(height))
    else:
        cx, cy, cw, ch = int(start_x), int(start_y), int(width), int(height)

    region = {"top": client_top + cy, "left": client_left + cx, "width": cw, "height": ch}
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        return np.array(screenshot)


def client_to_desktop(x: int, y: int):
    """Convert client-area coords to desktop coords (for pyautogui)."""
    return (client_left + int(x), client_top + int(y))
