import cv2
import numpy as np
import screen
import time
import logs.gachalogs as logs


def _grab_region(region: dict):
    return screen.get_screen_roi(region["start_x"], region["start_y"], region["width"], region["height"])


def _read_icon(item: str):
    img = cv2.imread(f"icons{screen.screen_resolution}/{item}.png")
    if img is not None:
        return img

    img = cv2.imread(f"icons1440/{item}.png")
    if img is None:
        logs.logger.error(
            f"Missing reconnect icon '{item}' (icons{screen.screen_resolution}/ and icons1440/)."
        )
        return None

    fx = float(getattr(screen, "scale_x", 1.0))
    fy = float(getattr(screen, "scale_y", 1.0))
    if abs(fx - 1.0) > 0.001 or abs(fy - 1.0) > 0.001:
        img = cv2.resize(img, (0, 0), fx=fx, fy=fy, interpolation=cv2.INTER_LINEAR)
    return img


location = {
    "accept": {"start_x": 1220, "start_y": 958, "width": 100, "height": 30},
    "escape": {"start_x": 2330, "start_y": 110, "width": 60, "height": 50},
    "escape_obscured": {"start_x": 2330, "start_y": 110, "width": 60, "height": 50},
    "join_last_session": {"start_x": 1135, "start_y": 1250, "width": 300, "height": 50},
    "join_game": {"start_x": 400, "start_y": 1000, "width": 700, "height": 60},
    "join_button": {"start_x": 2230, "start_y": 1230, "width": 100, "height": 50},
    "multiplayer": {"start_x": 100, "start_y": 110, "width": 85, "height": 60},
    "server_full": {"start_x": 1330, "start_y": 460, "width": 250, "height": 60},
    "red_fail": {"start_x": 1230, "start_y": 485, "width": 250, "height": 60},
    "mod_join": {"start_x": 2255, "start_y": 1225, "width": 100, "height": 60},
    "req_mods": {"start_x": 965, "start_y": 187, "width": 200, "height": 50},
    "join_text": {"start_x": 900, "start_y": 635, "width": 400, "height": 30},
    "loading_screen": {"start_x": 0, "start_y": 0, "width": 500, "height": 500},
    "searching": {"start_x": 1160, "start_y": 635, "width": 120, "height": 40},
    "no_session": {"start_x": 1260, "start_y": 635, "width": 150, "height": 40},
    "connection_timeout": {"start_x": 1025, "start_y": 460, "width": 200, "height": 55},
    "search": {"start_x": 2100, "start_y": 245, "width": 100, "height": 40},
    "download": {"start_x": 575, "start_y": 1220, "width": 200, "height": 25},
    "beds_title": {"start_x": 100, "start_y": 100, "width": 740, "height": 180},
    "tribelog_check": {"start_x": 1150, "start_y": 35, "width": 150, "height": 150},
    "network_failure": {"start_x": 1050, "start_y": 450, "width": 300, "height": 70},
}


def _match_template(item: str, lower_boundary: np.ndarray, upper_boundary: np.ndarray):
    region = location[item]
    roi = _grab_region(region)

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_roi = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_roi, cv2.COLOR_BGR2GRAY)

    image = _read_icon(item)
    if image is None:
        return None, None, None

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    gray_template = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, gray_template, cv2.TM_CCOEFF_NORMED)
    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(res)
    return gray_template, max_val, max_loc


def check_template(item: str, threshold: float) -> bool:
    _template, max_val, _max_loc = _match_template(
        item,
        np.array([0, 30, 200]),
        np.array([255, 255, 255]),
    )
    return bool(max_val is not None and max_val > threshold)


def check_template_no_bounds(item: str, threshold: float) -> bool:
    _template, max_val, _max_loc = _match_template(
        item,
        np.array([0, 0, 0]),
        np.array([255, 255, 255]),
    )
    return bool(max_val is not None and max_val > threshold)


def template_sleep(template: str, threshold: float, sleep_amount: float) -> bool:
    count = 0
    while check_template(template, threshold) is False:
        if count >= sleep_amount * 10:
            break
        time.sleep(0.1)
        count += 1
    return check_template(template, threshold)


def template_sleep_no_bounds(template: str, threshold: float, sleep_amount: float) -> bool:
    count = 0
    while check_template_no_bounds(template, threshold) is False:
        if count >= sleep_amount * 10:
            break
        time.sleep(0.1)
        count += 1
    return check_template_no_bounds(template, threshold)


def window_still_open(template: str, threshold: float, sleep_amount: float) -> bool:
    count = 0
    while check_template(template, threshold) is True:
        if count >= sleep_amount * 10:
            break
        time.sleep(0.1)
        count += 1
    return check_template(template, threshold)


def window_still_open_no_bounds(template: str, threshold: float, sleep_amount: float) -> bool:
    count = 0
    while check_template_no_bounds(template, threshold) is True:
        if count >= sleep_amount * 10:
            break
        time.sleep(0.1)
        count += 1
    return check_template_no_bounds(template, threshold)


def template_find(item: str, threshold: float = 0.65):
    image, max_val, max_loc = _match_template(
        item,
        np.array([0, 0, 0]),
        np.array([255, 255, 255]),
    )
    if image is None or max_val is None or max_loc is None or max_val < threshold:
        return None

    region = location[item]
    height, width = image.shape[:2]
    start_x = int(region["start_x"] + max_loc[0])
    start_y = int(region["start_y"] + max_loc[1])
    return (start_x + width // 2, start_y + height // 2)
