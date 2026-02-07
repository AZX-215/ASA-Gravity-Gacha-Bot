"""
Local lightweight compatibility layer for PyAutoGUI.

Why this exists:
- Some environments have a broken/modified site-packages pyautogui that crashes on import.
- This bot only needs a tiny subset of PyAutoGUI: press/keyDown/keyUp/hotkey/write and FAILSAFE.

Implementation:
- Uses Win32 SendInput so ARK receives the input reliably (foreground required, same as PyAutoGUI).
- Supports:
  - named keys: ctrl, shift, alt, enter, tab, esc, up/down/left/right, f1-f12, space, backspace, delete
  - single characters: "a".."z", "0".."9", punctuation via Unicode typing in write()
  - direct VK integers (if callers pass ints)
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import Iterable, Union

FAILSAFE = False  # kept for compatibility; not used by this stub.

# SendInput constants
INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_UNICODE     = 0x0004
KEYEVENTF_SCANCODE    = 0x0008

MAPVK_VK_TO_VSC = 0

# wintypes doesn't always expose ULONG_PTR consistently
ULONG_PTR = getattr(wintypes, "ULONG_PTR", ctypes.c_size_t)

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]

_user32 = ctypes.windll.user32
_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT

_user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
_user32.MapVirtualKeyW.restype = wintypes.UINT

# Extended keys (need KEYEVENTF_EXTENDEDKEY when sent as scancodes)
_EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24,  # pgup, pgdn, end, home
    0x25, 0x26, 0x27, 0x28,  # arrows
    0x2D, 0x2E,              # insert, delete
    0xA3,                    # rcontrol
    0xA5,                    # rmenu (alt)
}

# Named keys to VK codes
_KEY_NAME_TO_VK = {
    "ctrl": 0x11, "control": 0x11,
    "shift": 0x10,
    "alt": 0x12, "menu": 0x12,
    "enter": 0x0D, "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B, "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08, "bs": 0x08,
    "delete": 0x2E, "del": 0x2E,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23,
    "pgup": 0x21, "pageup": 0x21,
    "pgdn": 0x22, "pagedown": 0x22,
    "insert": 0x2D, "ins": 0x2D,
}

# F-keys
for i in range(1, 13):
    _KEY_NAME_TO_VK[f"f{i}"] = 0x70 + (i - 1)

def _vk_from_key(key: Union[str, int]) -> int:
    if isinstance(key, int):
        return key

    if not isinstance(key, str) or not key:
        raise TypeError(f"Unsupported key type: {type(key)}")

    k = key.strip().lower()

    # Common synonyms / left-right variants
    if k in ("lctrl", "leftctrl", "leftcontrol"):
        return 0xA2
    if k in ("rctrl", "rightctrl", "rightcontrol"):
        return 0xA3
    if k in ("lshift", "leftshift"):
        return 0xA0
    if k in ("rshift", "rightshift"):
        return 0xA1
    if k in ("lalt", "leftalt"):
        return 0xA4
    if k in ("ralt", "rightalt"):
        return 0xA5

    if k in _KEY_NAME_TO_VK:
        return _KEY_NAME_TO_VK[k]

    # Single visible character -> VK for A-Z/0-9 when possible
    if len(k) == 1:
        ch = k
        if "a" <= ch <= "z":
            return ord(ch.upper())
        if "0" <= ch <= "9":
            return ord(ch)
        # For punctuation, fall back to Unicode typing in write(); for press(),
        # we still try VkKeyScanW. If it fails, we raise.
        vk = _user32.VkKeyScanW(ord(ch))
        if vk == -1:
            raise ValueError(f"Cannot map key '{key}' to VK")
        return vk & 0xFF

    # Try VkKeyScanW on the first character if something like 'e' was passed with whitespace
    if len(k) > 1 and len(k.split()) == 1:
        raise ValueError(f"Unknown key name '{key}'")

    raise ValueError(f"Unknown key '{key}'")

def _send_vk(vk: int, is_down: bool) -> None:
    scan = _user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_SCANCODE
    if not is_down:
        flags |= KEYEVENTF_KEYUP
    if vk in _EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY

    inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0))
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def _send_unicode_char(ch: str) -> None:
    if not ch:
        return
    code = ord(ch)
    down = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0))
    up   = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))
    _user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(down))
    _user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(up))

def keyDown(key: Union[str, int]) -> None:
    _send_vk(_vk_from_key(key), True)

def keyUp(key: Union[str, int]) -> None:
    _send_vk(_vk_from_key(key), False)

def press(keys: Union[str, int, Iterable[Union[str, int]]]) -> None:
    if isinstance(keys, (list, tuple)):
        for k in keys:
            press(k)
        return
    vk = _vk_from_key(keys)
    _send_vk(vk, True)
    _send_vk(vk, False)

def hotkey(*keys: Union[str, int]) -> None:
    if not keys:
        return
    # down in order, up in reverse
    for k in keys:
        keyDown(k)
        time.sleep(0.01)
    for k in reversed(keys):
        keyUp(k)
        time.sleep(0.01)

def write(message: str, interval: float = 0.0) -> None:
    if not message:
        return
    if interval is None:
        interval = 0.0
    for ch in message:
        _send_unicode_char(ch)
        if interval > 0:
            time.sleep(interval)

# Convenience for callers that already computed VK codes.
def _press_vk(vk: int) -> None:
    _send_vk(int(vk), True)
    _send_vk(int(vk), False)

def _key_down_vk(vk: int) -> None:
    _send_vk(int(vk), True)

def _key_up_vk(vk: int) -> None:
    _send_vk(int(vk), False)
