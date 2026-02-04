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
import pywintypes



last_command = ""


def _clipboard_open_with_retry(max_attempts:int=25, base_sleep:float=0.02):
    """Open the Windows clipboard with retries.

    Clipboard access is occasionally denied when another process holds it.
    This wrapper prevents intermittent (5, 'OpenClipboard', 'Access is denied.') failures.
    """
    for i in range(1, max_attempts + 1):
        try:
            win32clipboard.OpenClipboard()
            return True
        except pywintypes.error as e:
            if getattr(e, "winerror", None) in (5,):
                time.sleep(base_sleep * (1 + (i // 5)))
                continue
            raise
    return False


def _clipboard_close_safely():
    try:
        win32clipboard.CloseClipboard()
    except Exception:
        pass


def _clipboard_get_text_safe(max_attempts:int=25):
    opened = False
    try:
        opened = _clipboard_open_with_retry(max_attempts=max_attempts)
        if not opened:
            return None
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
            data = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
            try:
                return data.decode("utf-8", errors="ignore") if isinstance(data, (bytes, bytearray)) else str(data)
            except Exception:
                return str(data)
        return None
    except pywintypes.error as e:
        if getattr(e, "winerror", None) in (5,):
            return None
        raise
    finally:
        if opened:
            _clipboard_close_safely()


def _clipboard_set_text_safe(text:str, max_attempts:int=25):
    opened = False
    try:
        opened = _clipboard_open_with_retry(max_attempts=max_attempts)
        if not opened:
            return False
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        return True
    except pywintypes.error as e:
        if getattr(e, "winerror", None) in (5,):
            return False
        raise
    finally:
        if opened:
            _clipboard_close_safely()

def is_open():
    return template.console_strip_check(template.console_strip_bottom()) or template.console_strip_check(template.console_strip_middle())

def enter_data(data:str):
    global last_command
    if ASA.config.up_arrow and data == last_command:
        logs.logger.debug(f"using uparrow to put {data} into the console")
        pyautogui.press("up")
    else:
        logs.logger.debug(f"using clipboard to put {data} into the console")
        if _clipboard_set_text_safe(data):
            pyautogui.hotkey("ctrl","v")
        else:
            logs.logger.warning(f"clipboard busy; typing '{data}' into the console")
            pyautogui.typewrite(data, interval=0.01)
    last_command = data
    
def console_ccc():
    data = None
    attempts = 0
    while data == None:
        attempts += 1
        logs.logger.debug(f"trying to get ccc data {attempts} / {ASA.config.console_ccc_attempts}")
        ASA.player.player_state.reset_state() #reset state at the start to make sure we can open up the console window
        count = 0
        while not is_open():
            count += 1
            utils.press_key("ConsoleKeys")
            template.template_await_true(is_open,1)
            if count >= ASA.config.console_open_attempts:
                logs.logger.error(f"console didnt open after {count} attempts")
                break
        if is_open():
            before = _clipboard_get_text_safe(max_attempts=10)

            enter_data("ccc")
            time.sleep(0.2*settings.lag_offset)
            utils.press_key("Enter")

            deadline = time.time() + (1.25 * settings.lag_offset)
            while time.time() < deadline:
                candidate = _clipboard_get_text_safe(max_attempts=10)
                if candidate and candidate != before:
                    if len(candidate.split()) >= 4:
                        data = candidate
                        break
                time.sleep(0.05)

        if attempts >= ASA.config.console_ccc_attempts:
            logs.logger.error(f"CCC is still returning NONE after {attempts} attempts")
            break        
    if data != None:    
        ccc_data = data.split()
        return ccc_data
    return data

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
        