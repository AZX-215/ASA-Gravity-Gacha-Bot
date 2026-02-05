import ASA.player.player_inventory
import ASA.player.player_state
import template
import logs.gachalogs as logs
import utils
import windows
import variables
import time 
import settings
import ASA.config 
import pyautogui
import win32clipboard
from ctypes import wintypes



# --- Clipboard helpers (hardened) ---
def _clipboard_open_retry(max_tries: int = 20, base_sleep: float = 0.02) -> bool:
    for i in range(max_tries):
        try:
            win32clipboard.OpenClipboard()
            return True
        except Exception:
            time.sleep(base_sleep * (i + 1) * max(1.0, getattr(settings, "lag_offset", 1.0)))
    return False

def _clipboard_close_safely():
    try:
        win32clipboard.CloseClipboard()
    except Exception:
        pass

def _set_clipboard_text(text: str) -> bool:
    if not _clipboard_open_retry():
        return False
    try:
        win32clipboard.EmptyClipboard()
        # Prefer Unicode; fall back if needed
        try:
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        except Exception:
            win32clipboard.SetClipboardText(text, win32clipboard.CF_TEXT)
        return True
    finally:
        _clipboard_close_safely()

def _get_clipboard_text() -> str | None:
    if not _clipboard_open_retry():
        return None
    try:
        # Try Unicode first
        try:
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            try:
                return win32clipboard.GetClipboardData()
            except Exception:
                return None
    finally:
        _clipboard_close_safely()

def _focus_console_input():
    """Click near bottom-center of the ARK window to ensure console text box has focus."""
    try:
        rect = wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(windows.hwnd, ctypes.byref(rect)):
            x = int((rect.left + rect.right) / 2)
            y = int(rect.bottom - 60)
            pyautogui.click(x=x, y=y)
            time.sleep(0.05 * max(1.0, getattr(settings, "lag_offset", 1.0)))
    except Exception:
        pass

def _poll_for_ccc(max_wait_s: float = 0.6, sentinel: str | None = None) -> str | None:
    """Poll clipboard briefly for a non-empty value (and not the sentinel if provided)."""
    t_end = time.time() + (max_wait_s * max(1.0, getattr(settings, "lag_offset", 1.0)))
    while time.time() < t_end:
        txt = _get_clipboard_text()
        if txt and isinstance(txt, str):
            if sentinel is None or txt != sentinel:
                return txt
        time.sleep(0.05 * max(1.0, getattr(settings, "lag_offset", 1.0)))
    return None

def _looks_like_ccc(txt: str) -> bool:
    # CCC output the bot expects is space-separated numbers (often 6 fields).
    # We just require at least 5 tokens and that the first token parses as int.
    if not txt or not isinstance(txt, str):
        return False
    parts = txt.strip().split()
    if len(parts) < 5:
        return False
    try:
        int(parts[0])
        float(parts[3])
        return True
    except Exception:
        return False


last_command = ""

def is_open():
    return template.console_strip_check(template.console_strip_bottom()) or template.console_strip_check(template.console_strip_middle())

def enter_data(data: str):
    global last_command
    if ASA.config.up_arrow and data == last_command:
        logs.logger.debug(f"using uparrow to put {data} into the console")
        pyautogui.press("up")
    else:
        logs.logger.debug(f"using clipboard to put {data} into the console")
        ok = _set_clipboard_text(data)
        if ok:
            pyautogui.hotkey("ctrl", "v")
        else:
            # Clipboard busy; fallback to typing (slower but reliable)
            logs.logger.warning("clipboard busy; typing command into console instead")
            pyautogui.typewrite(data, interval=0.01)
    last_command = data

def console_ccc():
    """Runs 'ccc' in the console and returns clipboard text containing the output.
    Keeps original behavior first; if CCC repeatedly fails, uses a guarded copy fallback
    (focus console input + Ctrl+A/Ctrl+C) to refresh clipboard without leaking keys to gameplay.
    """
    data = None
    attempts = 0
    while data is None:
        attempts += 1
        logs.logger.debug(f"trying to get ccc data {attempts} / {ASA.config.console_ccc_attempts}")
        ASA.player.player_state.reset_state()

        count = 0
        while not is_open():
            count += 1
            utils.press_key("ConsoleKeys")
            template.template_await_true(is_open, 1)
            if count >= ASA.config.console_open_attempts:
                logs.logger.error(f"console didnt open after {count} attempts")
                break

        if is_open():
            sentinel = f"__CCC_SENTINEL__{int(time.time()*1000)}"
            _set_clipboard_text(sentinel)

            enter_data("ccc")
            time.sleep(0.2 * max(1.0, getattr(settings, "lag_offset", 1.0)))
            utils.press_key("Enter")

            # Original behavior: read clipboard after a brief delay, but with polling + validation
            data = _poll_for_ccc(max_wait_s=0.7, sentinel=sentinel)
            if data and _looks_like_ccc(data):
                return data

            # Guarded fallback: only if CCC didn't appear/validate
            logs.logger.debug("ccc clipboard did not update; attempting guarded copy fallback")
            _focus_console_input()
            try:
                pyautogui.hotkey("ctrl", "a")
                pyautogui.hotkey("ctrl", "c")
            except Exception:
                pass
            data = _poll_for_ccc(max_wait_s=0.7, sentinel=sentinel)
            if data and _looks_like_ccc(data):
                return data

            data = None  # keep looping

        if attempts >= ASA.config.console_ccc_attempts:
            logs.logger.error(f"CCC is still returning NONE after {attempts} attempts")
            break

    return None



def console_write(text:str):
    attempts = 0
    while not is_open():
        attempts += 1
        utils.press_key("ConsoleKeys")
        template.template_await_true(is_open,1)
        if attempts >= ASA.config.console_open_attempts:
            logs.logger.error(f"console didnt open after {attempts} attempts unable to input {text}")
            break

    if is_open():
        enter_data(text)
        time.sleep(0.1*settings.lag_offset)
        utils.press_key("Enter")
        
        time.sleep(0.1*settings.lag_offset) # slow to try and prevent opening clipboard to empty data
        