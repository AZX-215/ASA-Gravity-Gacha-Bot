import ctypes
import time
import local_player
import windows
import pyautogui
import logs.gachalogs as logs
import ASA.player.console
import ASA.player.player_state
"""
FUNCTIONS FOR KEYBOARD 
"""
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102

keymap = {
    "tab":0x09,"escape" :0x1B,"return":0x0D, "enter":0x0D, "leftcontrol":0xA2, "zero": 0x30,
    "one":0x31, "two":0x32, "three":0x33 , "four":0x34 , "five":0x35 , "six":0x36 , "seven":0x37,
    "eight":0x38, "nine":0x39, "thumbmousebutton": 0x05, "thumbmousebutton2": 0x06, "spacebar": 0x20,"hyphen":0xBD,
    "leftshift":0xA0 , "tilde":0xC0
}

default_keymap = { 
    "use": "e", "consolekeys": "tilde", "showtribemanager": "l", "showmyinventory": "i", "accessinventory": "f", "dropitem":"o",
    "pausemenu": "escape","reload":"r","run":"leftshift","crouch":"c","useitem1": "one","useitem2": "two","useitem3": "three","useitem4": "four",
    "useitem5": "five","useitem6": "six","useitem7": "seven","useitem8": "eight","useitem9": "nine","useitem10": "zero"
}

hwnd = windows.hwnd
ctypes.windll.user32.VkKeyScanA.argtypes = [ctypes.c_char]
ctypes.windll.user32.VkKeyScanA.restype = ctypes.c_short  

def keymap_return(key_input):
    key = key_input.lower()

    if key in default_keymap: # this would only be triggered if the input.ini file is empty || base key mpa

        key = default_keymap[key]
        if key in keymap:
            return keymap[key]

    if key in keymap:
        return keymap[key]
 
    if len(key) == 1:
        result = ctypes.windll.user32.VkKeyScanA(ord(key))
   
        vk_code = result & 0xFF
        
        return vk_code

def press_key(input_action):
    """Press an ARK input binding name or a raw key string.

    This uses SendInput (via the local pyautogui stub) because PostMessage-based
    key injection is intermittently ignored by ARK/UE input in long runs.
    """
    try:
        key_name = local_player.get_input_settings(input_action)
    except Exception:
        key_name = input_action

    vk_code = keymap_return(key_name)
    try:
        pyautogui._press_vk(vk_code)
    except Exception:
        # Fallback: attempt named key press (best effort).
        try:
            pyautogui.press(str(key_name))
        except Exception:
            pass
    time.sleep(0.05)

def post_charecter(char):
    """Back-compat typo: type a single character."""
    pyautogui.write(str(char), interval=0.0)

def write(text):
    """Type text into the active ARK UI control (console/search)."""
    pyautogui.write(text, interval=0.002)

def ctrl_a():
    """Select all in the currently focused text field."""
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.05)

"""
FUNCTIONS FOR MOUSE MOVEMENT
"""

current_yaw = 0
current_pitch = 0
player_pitch_minimum = -80
player_pitch_max = 87

def normalize_yaw(yaw):
    yaw = (yaw % 360 + 360) % 360
    if (yaw > 180):
        yaw -= 360
    return yaw 

def set_yaw(yaw):
    global current_yaw
    ccc_data = ASA.player.console.console_ccc()
    if not ccc_data or len(ccc_data) < 4:
        logs.logger.error("set_yaw - unable to read ccc yaw (ccc_data is None/short); skipping yaw adjustment")
        return False

    try:
        current_yaw = float(ccc_data[3])
        logs.logger.debug(f"setting yaw as {current_yaw}")
    except Exception as e:
        logs.logger.error(f"set_yaw - error parsing ccc_data[3]: {e}")
        return False

    diff = ((yaw - current_yaw) + 180) % 360 - 180
    if diff < 0:
        turn_left(-diff)
    else:
        turn_right(diff)
    current_yaw = normalize_yaw(yaw)
    return True

def set_pitch(pitch):
    global current_pitch
    change = current_pitch - pitch 
    if change < 0:
        turn_up(-change)
    else:
        turn_down(change)
    current_pitch = pitch

def yaw_zero(ccc_data = None):
    global current_yaw

    if ccc_data == None:
        ccc_data = ASA.player.console.console_ccc()
    if not ccc_data or len(ccc_data) < 4:
        logs.logger.error("yaw_zero - unable to read ccc yaw (ccc_data is None/short)")
        return False
    try:
        if float(ccc_data[3]) > 0:
            turn_left(float(ccc_data[3]))
        else:
            turn_right(-float(ccc_data[3]))
        current_yaw = 0
    except Exception as e:
        logs.logger.error(f"error processing ccc_data[3]: {e}")
        #ark.check_state()
        return False
    return True

def pitch_zero(ccc_data = None):
    global current_pitch
    
    if ccc_data == None:
        ccc_data = ASA.player.console.console_ccc()
    if not ccc_data or len(ccc_data) < 5:
        logs.logger.error("pitch_zero - unable to read ccc pitch (ccc_data is None/short)")
        return False
    try:
        if float(ccc_data[4]) > 0:
            turn_down(float(ccc_data[4]))
        else:
            turn_up(-float(ccc_data[4]))
        current_pitch = 0
    except Exception as e:
        logs.logger.error(f"error processing ccc_data[4]: {e}")
        return False
    return True
        #ark.check_state()

def zero():
    logs.logger.debug("setting view angles back to 0")
    global current_yaw
    global current_pitch
    ccc_data = ASA.player.console.console_ccc()

    yaw_zero(ccc_data)
    pitch_zero(ccc_data)
    

def turn_right(degrees):
    global current_yaw
    windows.turn(degrees, 0)
    current_yaw = normalize_yaw(current_yaw + degrees)

def turn_left(degrees):
    global current_yaw
    windows.turn(-degrees, 0)
    current_yaw = normalize_yaw(current_yaw + (-degrees))
    

def turn_down(degrees):
    global current_pitch
    allowed = min(abs(player_pitch_minimum - current_pitch), degrees)
    windows.turn(0, allowed)
    current_pitch -= allowed


def turn_up(degrees):
    global current_pitch
    allowed = min(abs(player_pitch_max - current_pitch), degrees)
    windows.turn(0, -allowed)
    current_pitch += allowed
