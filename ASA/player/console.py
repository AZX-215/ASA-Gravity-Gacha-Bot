import re
import time
import win32clipboard

import ASA.config
import ASA.player.player_state
import logs.gachalogs as logs
import settings
import template
import utils
import windows
import screen


last_command = ""


def is_open() -> bool:
    # Prefer strip checks (fast) with a template fallback (more robust in HDR/contrast variance).
    try:
        if template.console_strip_check(template.console_strip_bottom()) or template.console_strip_check(template.console_strip_middle()):
            return True
    except Exception:
        pass
    try:
        return template.check_template_no_bounds("console", 0.60)
    except Exception:
        return False


def _open_clipboard_retry(tries: int = 25, delay: float = 0.02) -> bool:
    for _ in range(tries):
        try:
            win32clipboard.OpenClipboard()
            return True
        except Exception:
            time.sleep(delay)
            delay = min(delay * 1.3, 0.25)
    return False


def _close_clipboard_safely():
    try:
        win32clipboard.CloseClipboard()
    except Exception:
        pass


def _set_clipboard_text(text: str) -> bool:
    if not _open_clipboard_retry():
        return False
    try:
        win32clipboard.EmptyClipboard()
        try:
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        except Exception:
            win32clipboard.SetClipboardText(text)
        return True
    except Exception:
        return False
    finally:
        _close_clipboard_safely()


def _get_clipboard_text() -> str | None:
    if not _open_clipboard_retry():
        return None
    try:
        try:
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            try:
                return win32clipboard.GetClipboardData()
            except Exception:
                return ""
    finally:
        _close_clipboard_safely()


def _console_focus_input() -> bool:
    # Click inside the console input line (bottom area). This improves reliability for Ctrl+A/C.
    if not is_open():
        return False
    try:
        x = screen.map_x(220)
        y = screen.map_y(1412)
        windows.move_mouse(x, y)
        windows.click(x, y)
        time.sleep(0.06 * settings.lag_offset)
        return True
    except Exception:
        return False


def _open_console() -> bool:
    for attempt in range(1, ASA.config.console_open_attempts + 1):
        utils.press_key("ConsoleKeys")
        template.template_await_true(is_open, 1)
        if is_open():
            return True
        time.sleep(0.06 * settings.lag_offset)
    logs.logger.error(f"console didnt open after {ASA.config.console_open_attempts} attempts")
    return False


def _close_console():
    # Console is a toggle; attempt to close if open.
    if not is_open():
        return
    for _ in range(3):
        utils.press_key("ConsoleKeys")
        template.template_await_false(is_open, 1)
        if not is_open():
            return
        time.sleep(0.06 * settings.lag_offset)


def _looks_like_ccc_line(line: str) -> bool:
    if not line:
        return False
    parts = line.strip().split()
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


def _parse_ccc_text(payload: str) -> list[str] | None:
    if not payload:
        return None

    # Prefer last matching line (console copies can be multi-line).
    lines = [ln.strip() for ln in payload.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if _looks_like_ccc_line(ln):
            return ln.split()[:7]

    # Fallback: find 5+ floats anywhere (e.g., if formatting is odd).
    nums = re.findall(r"-?\d+(?:\.\d+)?", payload)
    if len(nums) >= 5:
        return nums[:7]
    return None


def _poll_clipboard_change(sentinel: str, timeout_s: float) -> str | None:
    end = time.time() + timeout_s
    last = None
    while time.time() < end:
        txt = _get_clipboard_text()
        if txt is None:
            time.sleep(0.05 * settings.lag_offset)
            continue
        if txt != sentinel and txt != last:
            last = txt
            if txt and txt.strip():
                return txt
        time.sleep(0.05 * settings.lag_offset)
    return None


def _type_command(text: str):
    # Targeted WM_CHAR typing to the ARK window (avoids focus issues from global hotkeys).
    utils.ctrl_a()
    utils.write(text)


def _force_copy_console(sentinel: str) -> list[str] | None:
    # Deterministic recovery: copy console content into clipboard and parse the last CCC line.
    if not is_open():
        return None
    if not _console_focus_input():
        return None

    _set_clipboard_text(sentinel)
    time.sleep(0.03 * settings.lag_offset)

    # Ctrl+A / Ctrl+C must only be sent when console is confirmed open, or 'C' can reach gameplay.
    if not is_open():
        return None
    utils.ctrl_a()
    time.sleep(0.04 * settings.lag_offset)
    utils.ctrl_c()

    txt = _poll_clipboard_change(sentinel, timeout_s=0.8 * settings.lag_offset)
    return _parse_ccc_text(txt or "")


def console_ccc():
    """Return CCC data as a token list (x y z pitch yaw ...).

    Reliability changes vs original:
      - Command entry uses targeted WM_CHAR typing (not Ctrl+V / pyautogui), so the bot is not dependent on window focus.
      - Clipboard access is retry/backoff hardened.
      - If the game stops auto-copying CCC to clipboard on long runs, we fall back to a safe *in-console* copy
        (Ctrl+A/Ctrl+C) *only when console is verified open* to avoid crouch/punch side effects.
    """
    for attempt in range(1, ASA.config.console_ccc_attempts + 1):
        logs.logger.debug(f"trying to get ccc data {attempt} / {ASA.config.console_ccc_attempts}")

        # Keep this - it prevents CCC runs while stuck in inventories/menus.
        ASA.player.player_state.reset_state()

        if not _open_console():
            continue

        _console_focus_input()

        sentinel = f"__CCC_SENTINEL__{int(time.time()*1000)}"
        _set_clipboard_text(sentinel)

        # Run CCC
        _type_command("ccc")
        time.sleep(0.10 * settings.lag_offset)
        utils.press_key("Enter")

        # Primary path: CCC auto-copies to clipboard
        txt = _poll_clipboard_change(sentinel, timeout_s=1.2 * settings.lag_offset)
        parsed = _parse_ccc_text(txt or "")
        if parsed:
            _close_console()
            return parsed

        # Recovery path: deterministic copy from the console UI itself
        parsed = _force_copy_console(sentinel)
        if parsed:
            _close_console()
            return parsed

        _close_console()

    logs.logger.error(f"CCC is still returning NONE after {ASA.config.console_ccc_attempts} attempts")
    return None