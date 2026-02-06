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

last_command = ""


def is_open():
    return template.console_strip_check(template.console_strip_bottom()) or template.console_strip_check(template.console_strip_middle())


def _open_clipboard_retry(tries: int = 20, delay: float = 0.02) -> bool:
    """
    OpenClipboard can intermittently fail when another process briefly holds the clipboard.
    Retry with small backoff to avoid crashing / returning None.
    """
    for _ in range(tries):
        try:
            win32clipboard.OpenClipboard()
            return True
        except Exception:
            time.sleep(delay)
            delay = min(delay * 1.3, 0.2)
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
            # Fallback if CF_UNICODETEXT isn't available in some environments
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
            # Might be CF_TEXT or empty
            try:
                return win32clipboard.GetClipboardData()
            except Exception:
                return ""
    finally:
        _close_clipboard_safely()


def enter_data(data: str):
    """
    Original behavior: paste command via clipboard, with optional up-arrow optimization.
    Hardened: clipboard open/write retries; fallback to typing if clipboard remains busy.
    """
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
            # Clipboard is busy; type as a safe fallback (slower, but avoids failure)
            pyautogui.write(data, interval=0.002)
    last_command = data


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


def console_ccc():
    """
    Matches the original bot's logic (run ccc, then read clipboard) but makes it reliable:
      - retries clipboard open/read
      - sets sentinel before running ccc, then polls for clipboard to update
      - validates payload shape so stale clipboard content won't be misread as ccc
    Important: does NOT use Ctrl+C, to avoid crouch/punch if console focus slips.
    """
    data = None
    attempts = 0

    while data is None:
        attempts += 1
        logs.logger.debug(f"trying to get ccc data {attempts} / {ASA.config.console_ccc_attempts}")
        ASA.player.player_state.reset_state()  # ensure we can open console

        # Open console (original pattern)
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
            time.sleep(0.2 * settings.lag_offset)
            utils.press_key("Enter")

            # Poll for clipboard change (lag tolerant)
            poll_end = time.time() + (1.5 * settings.lag_offset)
            last = None
            while time.time() < poll_end:
                txt = _get_clipboard_text()
                if txt is None:
                    time.sleep(0.05 * settings.lag_offset)
                    continue
                if txt != sentinel and txt != last:
                    last = txt
                    candidate = (txt or "").strip()
                    if _looks_like_ccc(candidate):
                        data = candidate
                        break
                    # sometimes console copies multi-line; try last line
                    lines = [ln.strip() for ln in candidate.splitlines() if ln.strip()]
                    if lines and _looks_like_ccc(lines[-1]):
                        data = lines[-1]
                        break
                time.sleep(0.05 * settings.lag_offset)

        if attempts >= ASA.config.console_ccc_attempts:
            logs.logger.error(f"CCC is still returning NONE after {attempts} attempts")
            break

    if data is not None:
        return data.split()
    return None
