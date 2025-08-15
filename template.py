import screen
import numpy as np
import cv2
import logs.gachalogs as logs
import settings
import time
import ASA.player.console
import json

# -------------------------------------------------
# Regions of interest (unchanged)
# -------------------------------------------------
roi_regions = {
    "bed_radical": {"start_x":1120, "start_y":345 ,"width":250 ,"height":250},
    "beds_title": {"start_x":100, "start_y":100 ,"width":740 ,"height":180},
    "console": {"start_x":0, "start_y":1400 ,"width":50 ,"height":40},
    "crop_plot": {"start_x":1100, "start_y":250 ,"width":310 ,"height":150},
    "crystal_in_hotbar": {"start_x":750, "start_y":1250 ,"width":1060 ,"height":250},
    "death_regions": {"start_x":100, "start_y":100 ,"width":700 ,"height":200},
    "dedi": {"start_x":1100, "start_y":245 ,"width":355 ,"height":70},
    "vault": {"start_x":1100, "start_y":245 ,"width":355 ,"height":150},
    "grinder": {"start_x":1100, "start_y":245 ,"width":355 ,"height":70},
    "exit_resume": {"start_x":550, "start_y":450 ,"width":1670 ,"height":880},
    "inventory": {"start_x":200, "start_y":125 ,"width":360 ,"height":150},
    "ready_clicked_bed": {"start_x":580, "start_y":250 ,"width":150 ,"height":1000},
    "seed_inv": {"start_x":550, "start_y":450 ,"width":1670 ,"height":880},
    "slot_capped": {"start_x":2240, "start_y":1314 ,"width":150 ,"height":100},
    "teleporter_title": {"start_x":200, "start_y":135 ,"width":405 ,"height":185},
    "tribelog_check": {"start_x":1150, "start_y":35 ,"width":150 ,"height":150},
    "waiting_inv": {"start_x":2000, "start_y":100 ,"width":500,"height":250},
    "bed_icon": {"start_x":800, "start_y":200 ,"width":1690 ,"height":1100},
    "teleporter_icon": {"start_x":800, "start_y":200 ,"width":1690 ,"height":1100},
    "teleporter_icon_pressed": {"start_x":800, "start_y":200 ,"width":1690 ,"height":1100},
    "first_slot" :{"start_x": 220, "start_y": 305, "width": 130, "height": 130},
    "player_stats": {"start_x":1120, "start_y":240 ,"width":300 ,"height":900},
    "show_buff":{"start_x":1200, "start_y":1150 ,"width":200 ,"height":50},
    "snow_owl_pellet":{"start_x":200, "start_y":150 ,"width":600 ,"height":600},
    "orange":{"start_x":705, "start_y":290 ,"width":1 ,"height":1},
    "chem_bench":{"start_x":1100, "start_y":245 ,"width":355 ,"height":70},
    "indi_forge":{"start_x":1100, "start_y":245 ,"width":355 ,"height":70},
    "access_inv":{"start_x":550, "start_y":450 ,"width":1670 ,"height":880}
}

# -------------------------------------------------
# HDR-robust preprocessing (used when settings.hdr_enabled == True)
# -------------------------------------------------

def _to_gray_preprocessed(img: np.ndarray) -> np.ndarray:
    """Convert to grayscale with CLAHE + min/max normalize. Handles BGRA/BGR."""
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if img.ndim == 3 and img.shape[2] == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img  # already grayscale
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    return cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

def _scale(v: int) -> int:
    """Scale 1440p ROIs down to 1080p when needed."""
    return int(v * 0.75)

def _roi(region_name: str) -> np.ndarray:
    region = roi_regions[region_name]
    if screen.screen_resolution == 1440:
        roi = screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])
    else:
        roi = screen.get_screen_roi(_scale(region["start_x"]), _scale(region["start_y"]), _scale(region["width"]), _scale(region["height"]))
    return roi

def _roi_gray(region_name: str) -> np.ndarray:
    return _to_gray_preprocessed(_roi(region_name))

def _tpl_gray(item: str) -> np.ndarray | None:
    path = f"icons{screen.screen_resolution}/{item}.png"
    tpl = cv2.imread(path, cv2.IMREAD_COLOR)
    if tpl is None:
        logs.logger.template(f"template missing: {path}")
        return None
    return _to_gray_preprocessed(tpl)

def _match(item: str, threshold: float, region_name: str | None = None):
    """Return (ok, max_val, max_loc) for template match on preprocessed grayscale."""
    roi_name = region_name if region_name else (item if item in roi_regions else "inventory")
    gray_roi = _roi_gray(roi_name)
    gray_tpl = _tpl_gray(item)
    if gray_tpl is None:
        return False, 0.0, (0, 0)
    res = cv2.matchTemplate(gray_roi, gray_tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return (max_val > threshold), float(max_val), max_loc

# -------------------------------------------------
# Await helpers (unchanged)
# -------------------------------------------------
def template_await_true(func, sleep_amount: float, *args) -> bool:
    count = 0
    while func(*args) == False:
        if count >= sleep_amount * 20:
            break
        time.sleep(0.05)
        count += 1
    return func(*args)

def template_await_false(func, sleep_amount: float, *args) -> bool:
    count = 0
    while func(*args) == True:
        if count >= sleep_amount * 20:
            break
        time.sleep(0.05)
        count += 1
    return not func(*args)

# -------------------------------------------------
# Template checks
#   - If hdr_enabled: grayscale+CLAHE matching
#   - Else: original HSV-masked pipeline (SDR)
# -------------------------------------------------
def _check_template_sdr(item: str, threshold: float) -> bool:
    region = roi_regions[item]
    if screen.screen_resolution == 1440:
        roi = screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])
    else:
        roi = screen.get_screen_roi(_scale(region["start_x"]), _scale(region["start_y"]), _scale(region["width"]), _scale(region["height"]))
    # original broad mask for robustness in SDR
    lower_boundary = np.array([0, 30, 200])
    upper_boundary = np.array([255, 255, 255])
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) if roi.shape[2] == 3 else cv2.cvtColor(roi, cv2.COLOR_BGRA2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_roi = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_roi, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"icons{screen.screen_resolution}/{item}.png")
    if image is None:
        logs.logger.template(f"template missing: icons{screen.screen_resolution}/{item}.png")
        return False
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    gray_tpl = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, gray_tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val}")
        return True
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False

def check_template(item: str, threshold: float) -> bool:
    if getattr(settings, "hdr_enabled", False):
        ok, max_val, _ = _match(item, threshold)
        if ok:
            logs.logger.template(f"{item} found:{max_val}")
            return True
        logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
        return False
    else:
        return _check_template_sdr(item, threshold)

def check_template_no_bounds(item: str, threshold: float) -> bool:
    # HDR path equals check_template; SDR path uses a fully-open mask (0–255)
    if getattr(settings, "hdr_enabled", False):
        return check_template(item, threshold)
    # SDR open-mask version
    region = roi_regions[item]
    if screen.screen_resolution == 1440:
        roi = screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])
    else:
        roi = screen.get_screen_roi(_scale(region["start_x"]), _scale(region["start_y"]), _scale(region["width"]), _scale(region["height"]))
    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) if roi.shape[2] == 3 else cv2.cvtColor(roi, cv2.COLOR_BGRA2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_roi = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_roi, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"icons{screen.screen_resolution}/{item}.png")
    if image is None:
        logs.logger.template(f"template missing: icons{screen.screen_resolution}/{item}.png")
        return False
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    gray_tpl = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, gray_tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val}")
        return True
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False

def teleport_icon(threshold: float) -> bool:
    if getattr(settings, "hdr_enabled", False):
        ok, max_val, _ = _match("teleporter_icon", threshold, region_name="teleporter_icon")
        if ok:
            logs.logger.template(f"teleporter_icon found:{max_val}")
            return True
        logs.logger.template(f"teleporter_icon not found:{max_val} threshold:{threshold}")
        return False
    # SDR path
    region = roi_regions["teleporter_icon"]
    if screen.screen_resolution == 1440:
        roi = screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])
    else:
        roi = screen.get_screen_roi(_scale(region["start_x"]), _scale(region["start_y"]), region["width"], region["height"])
    lower_boundary = np.array([0, 0, 150])
    upper_boundary = np.array([255, 255, 255])
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) if roi.shape[2] == 3 else cv2.cvtColor(roi, cv2.COLOR_BGRA2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_roi = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_roi, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"icons{screen.screen_resolution}/teleporter_icon.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    gray_tpl = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, gray_tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    if max_val > threshold:
        logs.logger.template(f"teleporter_icon found:{max_val}")
        return True
    logs.logger.template(f"teleporter_icon not found:{max_val} threshold:{threshold}")
    return False

def inventory_first_slot(threshold: float) -> bool:
    if getattr(settings, "hdr_enabled", False):
        ok, max_val, _ = _match("first_slot", threshold, region_name="first_slot")
        if ok:
            logs.logger.template(f"first_slot found:{max_val}")
            return True
        logs.logger.template(f"first_slot not found:{max_val} threshold:{threshold}")
        return False
    # SDR path
    region = roi_regions["first_slot"]
    if screen.screen_resolution == 1440:
        roi = screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])
    else:
        roi = screen.get_screen_roi(_scale(region["start_x"]), _scale(region["start_y"]), region["width"], region["height"])
    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) if roi.shape[2] == 3 else cv2.cvtColor(roi, cv2.COLOR_BGRA2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_roi = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_roi, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"icons{screen.screen_resolution}/first_slot.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    gray_tpl = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, gray_tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    if max_val > threshold:
        logs.logger.template(f"first_slot found:{max_val}")
        return True
    logs.logger.template(f"first_slot not found:{max_val} threshold:{threshold}")
    return False

def check_buffs(buff: str, threshold: float) -> bool:
    if getattr(settings, "hdr_enabled", False):
        ok, max_val, _ = _match(buff, threshold, region_name="show_buff")
        if ok:
            logs.logger.template(f"{buff} found:{max_val}")
            return True
        logs.logger.template(f"{buff} not found:{max_val} threshold:{threshold}")
        return False
    # SDR path
    region = roi_regions["show_buff"]
    if screen.screen_resolution == 1440:
        roi = screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])
    else:
        roi = screen.get_screen_roi(_scale(region["start_x"]), _scale(region["start_y"]), _scale(region["width"]), _scale(region["height"]))
    lower_boundary = np.array([0, 30, 200])
    upper_boundary = np.array([255, 255, 255])
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) if roi.shape[2] == 3 else cv2.cvtColor(roi, cv2.COLOR_BGRA2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_roi = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_roi, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"icons{screen.screen_resolution}/{buff}.png")
    if image is None:
        logs.logger.template(f"template missing: icons{screen.screen_resolution}/{buff}.png")
        return False
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    gray_tpl = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, gray_tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    if max_val > threshold:
        logs.logger.template(f"{buff} found:{max_val}")
        return True
    logs.logger.template(f"{buff} not found:{max_val} threshold:{threshold}")
        # too much indentation in previous line would raise error - ensure correct
    return False

def check_teleporter_orange():
    # Under HDR, prefer icon detection (single-pixel HSV is brittle).
    if getattr(settings, "hdr_enabled", False):
        try:
            return teleport_icon(0.6)
        except Exception:
            pass

    # Legacy single-pixel HSV check (SDR)
    region = roi_regions["orange"]
    if screen.screen_resolution == 1440:
        roi = screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])
    else:
        roi = screen.get_screen_roi(_scale(region["start_x"]), _scale(region["start_y"]), region["width"], region["height"])

    if roi.ndim == 3 and roi.shape[2] == 4:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(hsv, cv2.COLOR_BGR2HSV)
    else:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    lower_boundary = np.array([10, 211, 50])
    upper_boundary = np.array([15, 255, 100])

    pixel_hsv = hsv[0, 0]
    ok = np.all(pixel_hsv >= lower_boundary) and np.all(pixel_hsv <= upper_boundary)
    logs.logger.template(f"check orange {ok}")
    return ok

def white_flash():
    roi = screen.get_screen_roi(500, 500, 100, 100)
    total_pixels = roi.size
    num_255_pixels = np.count_nonzero(roi == 255)
    percentage_255 = (num_255_pixels / total_pixels) * 100
    logs.logger.template(f"white flash {percentage_255 >= 80}")
    return percentage_255 >= 80

_console_bounds_initialized = False
lower_console_bound = 120
upper_console_bound = 140

def get_file():
    file_path = "json_files/console.json"
    try:
        with open(file_path, 'r') as file:
            data = file.read().strip()
            if not data:
                return []
            return json.loads(data)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def get_bounds():
    global lower_console_bound, upper_console_bound
    data = get_file()
    if isinstance(data, dict) and "lower" in data and "upper" in data:
        lower_console_bound = int(data["lower"])
        upper_console_bound = int(data["upper"])
    return lower_console_bound, upper_console_bound

def set_bounds(lower: int, upper: int):
    global lower_console_bound, upper_console_bound
    lower_console_bound, upper_console_bound = int(lower), int(upper)
    try:
        with open("json_files/console.json", "w") as f:
            json.dump({"lower": lower_console_bound, "upper": upper_console_bound}, f)
    except Exception:
        pass

def console_strip_bottom():
    if screen.screen_resolution == 1440:
        return screen.get_screen_roi(0, 1419, 2560, 2)
    else:
        return screen.get_screen_roi(0, 1059, 1920, 2)

def console_strip_top():
    if screen.screen_resolution == 1440:
        return screen.get_screen_roi(0, 0, 2560, 2)
    else:
        return screen.get_screen_roi(0, 0, 1920, 2)

def _ensure_console_bounds():
    """Compute average gray on bottom strip and widen bounds under HDR."""
    global _console_bounds_initialized
    if _console_bounds_initialized:
        return
    try:
        gray_roi = _to_gray_preprocessed(console_strip_bottom())
        avg = float(np.mean(gray_roi))
        if getattr(settings, "hdr_enabled", False):
            set_bounds(int(avg - 15), int(avg + 15))
        else:
            set_bounds(int(avg - 5), int(avg + 5))
        _console_bounds_initialized = True
        logs.logger.template(f"console bounds auto-calibrated around {avg:.2f}")
    except Exception as e:
        logs.logger.template(f"console bounds auto-calibration failed: {e}")

def console_strip_check(roi):
    _ensure_console_bounds()
    if roi.ndim == 3 and roi.shape[2] == 4:
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGRA2GRAY)
    elif roi.ndim == 3:
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        gray_roi = roi
    lower, upper = get_bounds()
    gray_mask = (gray_roi >= lower) & (gray_roi <= upper)
    num_gray_pixels = int(np.count_nonzero(gray_mask))
    total_pixels = int(gray_roi.size)
    percentage_gray = (num_gray_pixels / total_pixels) * 100 if total_pixels else 0.0
    logs.logger.template(f"percentage gray {percentage_gray}")
    return percentage_gray >= 80

def check_both_strips():
    roi1 = console_strip_top()
    roi2 = console_strip_bottom()
    return console_strip_check(roi1) or console_strip_check(roi2)

def change_console_mask():
    # Manual recompute (tight) – auto-cal expands for HDR
    gray_roi = cv2.cvtColor(console_strip_bottom(), cv2.COLOR_BGR2GRAY)
    average = np.mean(gray_roi)
    set_bounds(int(average - 5), int(average + 5))

def output_hsv():
    print("outputs hsv colours so you can change the bounds of functions")
    region = roi_regions["orange"]
    if screen.screen_resolution == 1440:
        roi = screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])
    else:
        roi = screen.get_screen_roi(_scale(region["start_x"]), _scale(region["start_y"]), region["width"], region["height"])
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    print(f"{hsv[0, 0]} -> for orange teleporter")
    gray_roi = cv2.cvtColor(console_strip_bottom(), cv2.COLOR_BGR2GRAY)
    average = np.mean(gray_roi)
    print(f"if console was open the average console colour was : {average:.2f} add/subtract ~15 for HDR")

if __name__ == "__main__":
    time.sleep(0.5)
    output_hsv()
