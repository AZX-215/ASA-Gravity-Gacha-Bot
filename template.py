import screen
import numpy as np
import cv2
import os
import logs.gachalogs as logs
import settings
import time
import ASA.player.console
import json


def _grab_region(region: dict):
    # All regions are authored at 2560x1440 and screen.get_screen_roi auto-scales/centers.
    return screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])


def _read_icon(item: str, force_hdr=None):
    """Load the template icon for the current resolution.

    Template folders are keyed by vertical resolution:
      - icons1440, icons1080, icons2160, icons2880, ...

    If force_hdr is:
      - None: follow settings.use_hdr_templates (existing behavior)
      - True: prefer icons{height}_hdr/ when present
      - False: prefer icons{height}/ (SDR set)

    If an exact-match folder is missing, it falls back to the 1440 set and resizes using
    screen.scale_x/scale_y for 4K/5K.
    """

    height = int(getattr(screen, "screen_resolution", 1440) or 1440)

    def _pick_dir(h: int) -> str:
        base = f"icons{h}"
        want_hdr = getattr(settings, "use_hdr_templates", False) if force_hdr is None else bool(force_hdr)
        if want_hdr:
            hdr = f"{base}_hdr"
            if os.path.isdir(hdr):
                return hdr
        return base

    primary_dir = _pick_dir(height)
    img = cv2.imread(os.path.join(primary_dir, f"{item}.png"))
    if img is not None:
        return img

    fallback_dir = _pick_dir(1440)
    img = cv2.imread(os.path.join(fallback_dir, f"{item}.png"))
    if img is None:
        logs.logger.error(
            f"Missing icon for template '{item}' (looked in {primary_dir}/ and {fallback_dir}/)."
        )
        return None

    # Resize from 1440 baseline to current resolution.
    fx = float(getattr(screen, "scale_x", 1.0))
    fy = float(getattr(screen, "scale_y", 1.0))
    if abs(fx - 1.0) > 0.001 or abs(fy - 1.0) > 0.001:
        img = cv2.resize(img, (0, 0), fx=fx, fy=fy, interpolation=cv2.INTER_LINEAR)
    return img

def _masked_gray(bgr: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)
    masked = cv2.bitwise_and(bgr, bgr, mask=mask)
    return cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)



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
    # Teleporter READY highlight probe region (authored at 2560x1440).
    # Centered around the original single-pixel probe at (705, 290) but expanded
    # to tolerate scaling rounding, AA, HDR/gamma variance.
    "orange":{"start_x":693, "start_y":278 ,"width":24 ,"height":24},
    "chem_bench":{"start_x":1100, "start_y":245 ,"width":355 ,"height":70},
    "megalab": {"start_x":1100, "start_y":245 ,"width":355 ,"height":70},
    "indi_forge":{"start_x":1100, "start_y":245 ,"width":355 ,"height":70},
    "access_inv":{"start_x":550, "start_y":450 ,"width":1670 ,"height":880}
}
def template_await_true(func,sleep_amount:float,*args) -> bool:
    count = 0 
    while func(*args) == False:
        if count >= sleep_amount * 20 : 
            break    
        time.sleep(0.05)
        count += 1
    return func(*args)

def template_await_false(func,sleep_amount:float,*args) -> bool:
    count = 0 
    while func(*args) == True:
        if count >= sleep_amount * 20 : 
            break    
        time.sleep(0.05)
        count += 1
    return func(*args)

def _match_template(gray_roi: np.ndarray, gray_icon: np.ndarray) -> float:
    res = cv2.matchTemplate(gray_roi, gray_icon, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return float(max_val)

def check_template(item: str, threshold: float) -> bool:
    """Resolution-aware template match with HDR + mask fallbacks.

    Primary path:
      - Masked (bright-foreground) match using the currently-selected icon set.

    Fallbacks (only if primary fails):
      - Try the opposite icon set (HDR vs SDR).
      - Try an unmasked grayscale match (less strict) with a slightly reduced threshold.

    This is intended to stabilize detection across HDR/SDR and minor gamma/contrast variance
    without changing call sites.
    """
    region = roi_regions[item]
    roi = _grab_region(region)

    lower_boundary = np.array([0, 30, 200])
    upper_boundary = np.array([255, 255, 255])
    gray_roi = _masked_gray(roi, lower_boundary, upper_boundary)

    def _attempt(icon_img, use_bounds: bool, thr: float) -> float:
        if icon_img is None:
            return -1.0
        if use_bounds:
            g_icon = _masked_gray(icon_img, lower_boundary, upper_boundary)
            return _match_template(gray_roi, g_icon)
        # no-bounds (full grayscale)
        g_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        g_icon = cv2.cvtColor(icon_img, cv2.COLOR_BGR2GRAY)
        return _match_template(g_roi, g_icon)

    icon = _read_icon(item)
    score = _attempt(icon, True, threshold)

    if score > threshold:
        logs.logger.template(f"{item} found:{score}")
        return True

    # Fallback 1: opposite HDR/SDR icon set (if it exists).
    alt_icon = _read_icon(item, force_hdr=not getattr(settings, "use_hdr_templates", False))
    if alt_icon is not None:
        alt_score = _attempt(alt_icon, True, threshold)
        if alt_score > threshold:
            logs.logger.template(f"{item} found:{alt_score} (alt icon set)")
            return True
        score = max(score, alt_score)

    # Fallback 2: no-bounds match (reduce threshold slightly; clamp to avoid too many false positives).
    if getattr(settings, "template_fallback_no_bounds", True):
        fb_thr = max(0.55, float(threshold) - 0.08)
        nb_score = _attempt(icon, False, fb_thr)
        if nb_score > fb_thr:
            logs.logger.template(f"{item} found:{nb_score} (no-bounds fallback thr={fb_thr})")
            return True
        if alt_icon is not None:
            nb2 = _attempt(alt_icon, False, fb_thr)
            if nb2 > fb_thr:
                logs.logger.template(f"{item} found:{nb2} (alt+no-bounds fallback thr={fb_thr})")
                return True
            score = max(score, nb_score, nb2)
        else:
            score = max(score, nb_score)

    logs.logger.template(f"{item} not found:{score} threshold:{threshold}")
    return False

def check_template_no_bounds(item: str, threshold: float) -> bool:
    region = roi_regions[item]
    roi = _grab_region(region)

    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    icon = _read_icon(item)
    if icon is None:
        return False
    gray_icon = cv2.cvtColor(icon, cv2.COLOR_BGR2GRAY)

    score = _match_template(gray_roi, gray_icon)
    if score > threshold:
        logs.logger.template(f"{item} found:{score}")
        return True

    # Opposite icon set fallback for HDR/SDR mismatch.
    alt_icon = _read_icon(item, force_hdr=not getattr(settings, "use_hdr_templates", False))
    if alt_icon is not None:
        alt_score = _match_template(gray_roi, cv2.cvtColor(alt_icon, cv2.COLOR_BGR2GRAY))
        if alt_score > threshold:
            logs.logger.template(f"{item} found:{alt_score} (alt icon set)")
            return True
        score = max(score, alt_score)

    logs.logger.template(f"{item} not found:{score} threshold:{threshold}")
    return False

def return_location(item: str, threshold: float):
    # Assumes the check for the item on the screen has already been done.
    region = roi_regions[item]
    roi = _grab_region(region)

    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])

    gray_roi = _masked_gray(roi, lower_boundary, upper_boundary)

    icon = _read_icon(item)
    if icon is None:
        return 0
    gray_icon = _masked_gray(icon, lower_boundary, upper_boundary)

    res = cv2.matchTemplate(gray_roi, gray_icon, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val} at:{max_loc}")
        return max_loc
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return 0


def teleport_icon(threshold: float) -> bool:
    region = roi_regions["teleporter_icon"]
    roi = _grab_region(region)

    lower_boundary = np.array([0, 0, 150])
    upper_boundary = np.array([255, 255, 255])

    gray_roi = _masked_gray(roi, lower_boundary, upper_boundary)

    icon = _read_icon("teleporter_icon")
    if icon is None:
        return False
    gray_icon = _masked_gray(icon, lower_boundary, upper_boundary)

    res = cv2.matchTemplate(gray_roi, gray_icon, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)

    if max_val > threshold:
        logs.logger.template(f"teleporter_icon found:{max_val}")
        return True
    logs.logger.template(f"teleporter_icon not found:{max_val} threshold:{threshold}")
    return False


def inventory_first_slot(item: str, threshold: float) -> bool:
    region = roi_regions["first_slot"]
    roi = _grab_region(region)

    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])

    gray_roi = _masked_gray(roi, lower_boundary, upper_boundary)

    icon = _read_icon(item)
    if icon is None:
        return False
    gray_icon = _masked_gray(icon, lower_boundary, upper_boundary)

    res = cv2.matchTemplate(gray_roi, gray_icon, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)

    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val}")
        return True
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False


def check_buffs(buff: str, threshold: float) -> bool:
    region = roi_regions["player_stats"]
    roi = _grab_region(region)

    lower_boundary = np.array([0, 0, 180])
    upper_boundary = np.array([255, 255, 255])

    gray_roi = _masked_gray(roi, lower_boundary, upper_boundary)

    icon = _read_icon(buff)
    if icon is None:
        return False
    gray_icon = _masked_gray(icon, lower_boundary, upper_boundary)

    res = cv2.matchTemplate(gray_roi, gray_icon, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)

    if max_val > threshold:
        logs.logger.template(f"{buff} found:{max_val}")
        return True
    logs.logger.template(f"{buff} not found:{max_val} threshold:{threshold}")
    return False


def check_teleporter_orange():
    """Return True if the currently selected bed/teleporter entry is in a 'Ready' state.

    The original bot used a single HSV pixel probe (very sensitive but brittle).
    The v4 patch used a large-column HSV % which can miss the highlight when it's small.

    This version combines:
      1) Template match against 'ready_clicked_bed' (fast and reliable when the template is accurate)
      2) A small HSV probe patch around the original orange pixel location (705,290 at 1440 baseline)
    """

    # 1) Template match signal (resolution-aware via _read_icon()).
    try:
        if check_template("ready_clicked_bed", 0.60):
            logs.logger.template("teleporter ready (template)")
            return True
    except Exception:
        pass

    # 2) Orange probe patch (restores the intent of the original single-pixel check,
    # but uses a small area to tolerate rounding/AA/HDR).
    region = roi_regions.get("orange")
    if not region:
        return False

    roi = _grab_region(region)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Broad orange/yellow range; highlight color varies by gamma/HDR.
    # Hue: 0-55, Sat: 60+, Val: 60+
    lower = np.array([0, 60, 60])
    upper = np.array([55, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    hits = int(np.count_nonzero(mask))
    # Require a small number of orange-ish pixels; scale minimum by patch size.
    min_hits = max(6, int((roi.shape[0] * roi.shape[1]) * 0.01))
    ok = hits >= min_hits
    logs.logger.template(f"teleporter ready (probe) {ok} hits={hits} min_hits={min_hits}")
    return ok


def white_flash():
    roi = screen.get_screen_roi(500,500,100,100)
    total_pixels = roi.size
    num_255_pixels = np.count_nonzero(roi == 255)
    percentage_255 = (num_255_pixels / total_pixels) * 100
    logs.logger.template(f"white flash {percentage_255 >= 80}")
    return percentage_255 >= 80

def get_file():
    file_path = "json_files/console.json"
    try:
        with open(file_path, 'r') as file:
            data = file.read().strip()
            if not data:
                return []
            return json.loads(data)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return []
    
def get_bounds():
    bounds = get_file()
    return bounds

def set_bounds(lower_bound: int, upper_bound: int):
    file_path = "json_files/console.json"
    new_bounds = [{
        "upper_bound": upper_bound,
        "lower_bound": lower_bound
    }]

    with open(file_path, 'w') as file:
        json.dump(new_bounds, file, indent=4)

bounds = get_bounds()
upper_console_bound = bounds[0]["upper_bound"]
lower_console_bound = bounds[0]["lower_bound"]

def console_strip_bottom():
    # bottom-most strip used to detect if the console is open (base coords)
    return screen.get_screen_roi(0, 1419, 2560, 2)

def console_strip_middle():
    # mid strip used to detect if the console is open (base coords)
    return screen.get_screen_roi(0, 1065, 2560, 2)

def console_strip_check(roi):
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray_mask = (gray_roi >= lower_console_bound) & (gray_roi <= upper_console_bound)
    num_gray_pixels = np.count_nonzero(gray_mask)

    total_pixels = gray_roi.size
    percentage_gray = (num_gray_pixels / total_pixels) * 100
    logs.logger.template(f"percentage gray {percentage_gray}")
    return percentage_gray >= 80

def check_both_strips():
    roi1 = console_strip_bottom()
    roi2 = console_strip_middle()
    return console_strip_check(roi1) or console_strip_check(roi2)


def change_console_mask():
    gray_roi = cv2.cvtColor(console_strip_bottom(), cv2.COLOR_BGR2GRAY)
    average = np.mean(gray_roi)
    set_bounds((average - 5), (average + 5))

def output_hsv():
    print("outputs hsv colours so you can change the bounds of functions")
    region = roi_regions["orange"]
    roi = _grab_region(region)

    hsv = cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    print(f"{hsv[0, 0]} -> for orange teleporter lines 248 and 249") 
    roi = screen.get_screen_roi(0, 1419, 2560, 2)
    gray_roi = cv2.cvtColor(console_strip_bottom(), cv2.COLOR_BGR2GRAY)
    average = np.mean(gray_roi)
    print(f"if console was open the average console colour was : {average} go to console.json and set +and - 5 from this in the respected section IE upperbound = average+5 ")
    input("") # keeps script open for user to edit there files

if __name__ == "__main__":
    time.sleep(2)
    #change_console_mask()
    output_hsv()
    time.sleep(0.5)
    pass
    
