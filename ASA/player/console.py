# Patched console helpers (v11)
# Goal: eliminate crouch/punch side-effects by avoiding Ctrl+A/C hotkeys,
# while improving CCC reliability with clipboard retries + sentinel polling + console reopen recovery.
import time
import ctypes
from ctypes import wintypes

import keyboard

try:
    import settings  # optional
except Exception:
    settings = None

try:
    import screen
except Exception:
    screen = None

try:
    import windows
except Exception:
    windows = None


# --- Win32 Clipboard helpers (Unicode + retry) ---
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL


def _clip_open_retry(tries: int = 20, delay: float = 0.02) -> bool:
    for _ in range(tries):
        if user32.OpenClipboard(None):
            return True
        time.sleep(delay)
        delay = min(delay * 1.3, 0.2)
    return False


def _clip_get_text() -> str | None:
    if not _clip_open_retry():
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def _clip_set_text(text: str) -> bool:
    if not _clip_open_retry():
        return False
    try:
        user32.EmptyClipboard()
        data = (text + "\x00").encode("utf-16le")
        hglob = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not hglob:
            return False
        p = kernel32.GlobalLock(hglob)
        if not p:
            return False
        try:
            ctypes.memmove(p, data, len(data))
        finally:
            kernel32.GlobalUnlock(hglob)
        user32.SetClipboardData(CF_UNICODETEXT, hglob)
        return True
    finally:
        user32.CloseClipboard()


# --- Console interaction helpers ---
def _console_key() -> str:
    # Preserve config if present; fallback to grave.
    if settings and hasattr(settings, "console_key"):
        return getattr(settings, "console_key")
    return "`"


def open_console():
    keyboard.press_and_release(_console_key())
    time.sleep(0.08)


def close_console():
    keyboard.press_and_release(_console_key())
    time.sleep(0.08)


def _focus_console_input():
    # Best-effort: click near bottom-center of ARK client where console input line typically is.
    if not (screen and windows):
        return
    try:
        x = int(screen.map_x(1280))
        y = int(screen.map_y(1385))
        windows.click(x, y)
        time.sleep(0.03)
    except Exception:
        pass


def enter_data(data: str):
    """Paste command text into console. Clipboard with retries; fallback to typing."""
    ok = _clip_set_text(data)
    if ok:
        keyboard.press_and_release("ctrl+v")
        return
    keyboard.write(data, delay=0.002)


def _looks_like_ccc(payload: str) -> bool:
    if not payload:
        return False
    parts = payload.strip().split()
    if len(parts) < 5:
        return False
    good = 0
    for p in parts[:7]:
        try:
            float(p)
            good += 1
        except Exception:
            pass
    return good >= 5


def console_ccc(max_attempts: int = 5) -> list[str] | None:
    """Return parsed CCC payload split() or None. No Ctrl+A/C to avoid crouch/punch."""
    poll_seconds = 1.8
    poll_interval = 0.05
    sentinel = f"__CCC_SENTINEL__{int(time.time()*1000)}"

    for attempt in range(1, max_attempts + 1):
        _clip_set_text(sentinel)

        open_console()
        _focus_console_input()

        keyboard.press_and_release("ctrl+a")
        keyboard.press_and_release("backspace")

        enter_data("ccc")
        keyboard.press_and_release("enter")

        time.sleep(0.18 + 0.08 * attempt)

        t_end = time.time() + poll_seconds + 0.25 * attempt
        last = None
        while time.time() < t_end:
            txt = _clip_get_text()
            if txt is None:
                time.sleep(poll_interval)
                continue

            if txt != sentinel and txt != last:
                last = txt
                candidate = txt.strip()
                if _looks_like_ccc(candidate):
                    close_console()
                    return candidate.split()

                lines = [ln.strip() for ln in candidate.splitlines() if ln.strip()]
                if lines:
                    tail = lines[-1]
                    if _looks_like_ccc(tail):
                        close_console()
                        return tail.split()

            time.sleep(poll_interval)

        close_console()
        time.sleep(0.10)

    close_console()
    return None
