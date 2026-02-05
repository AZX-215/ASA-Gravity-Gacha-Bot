import cv2
import numpy as np
import settings
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
        logs.logger.error(f"Missing reconnect icon '{item}' (icons{screen.screen_resolution}/ and icons1440/).")
        return None

    fx = float(getattr(screen, "scale_x", 1.0))
    fy = float(getattr(screen, "scale_y", 1.0))
    if abs(fx - 1.0) > 0.001 or abs(fy - 1.0) > 0.001:
        img = cv2.resize(img, (0, 0), fx=fx, fy=fy, interpolation=cv2.INTER_LINEAR)
    return img

location = {
    "accept":{"start_x":1220, "start_y":958 ,"width":100 ,"height":30},
    "escape":{"start_x":2330, "start_y":110 ,"width":60 ,"height":50},
    "join_last_session":{"start_x":1135, "start_y":1250 ,"width":300 ,"height":50},
    "join_game":{"start_x":446, "start_y":1000 ,"width":600 ,"height":60},
    "join_button":{"start_x":2230, "start_y":1230 ,"width":100 ,"height":50},
    "multiplayer":{"start_x":100, "start_y":110 ,"width":85 ,"height":60},
    "server_full":{"start_x":1330, "start_y":460 ,"width":250 ,"height":60},
    "red_fail":{"start_x":1330, "start_y":460 ,"width":250 ,"height":60},
    "mod_join":{"start_x":2255, "start_y":1225 ,"width":100 ,"height":60},
    "req_mods":{"start_x":965, "start_y":187 ,"width":200 ,"height":50},
    "join_text":{"start_x":900, "start_y":635 ,"width":400 ,"height":30},
    "loading_screen":{"start_x":0, "start_y":0 ,"width":500 ,"height":500},
    "searching":{"start_x":1160, "start_y":635 ,"width":120 ,"height":40},
    "no_session":{"start_x":1260, "start_y":635 ,"width":150 ,"height":40},
    "connection_timeout":{"start_x":1025, "start_y":460 ,"width":200 ,"height":55}
}



def check_template(item:str, threshold:float) -> bool:
    
    region = location[item]
    roi = _grab_region(region)
        
    lower_boundary = np.array([0,30,200])
    upper_boundary = np.array([255,255,255])

    hsv = cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,lower_boundary,upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask= mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = _read_icon(item)
    if image is None:
        return False
    hsv = cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,lower_boundary,upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template,cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val > threshold:
        #logs.logger.template(f"{item} found:{max_val}")
        return True
    #logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False

def check_template_no_bounds(item:str, threshold:float) -> bool:
    
    region = location[item]
    roi = _grab_region(region)
        
    lower_boundary = np.array([0,0,0])
    upper_boundary = np.array([255,255,255])

    hsv = cv2.cvtColor(roi,cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,lower_boundary,upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask= mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = _read_icon(item)
    if image is None:
        return False
    hsv = cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,lower_boundary,upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template,cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val > threshold:
        #logs.logger.template(f"{item} found:{max_val}")
        return True
    #logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False


def template_sleep(template:str,threshold:float,sleep_amount:float) -> bool:
    count = 0 
    while check_template(template,threshold) == False:
        if count >= sleep_amount * 10 : #  seconds of sleep
            break    
        time.sleep(0.1)
        count += 1
    return check_template(template,threshold)

def template_sleep_no_bounds(template:str,threshold:float,sleep_amount:float) -> bool:
    count = 0 
    while check_template_no_bounds(template,threshold) == False:
        if count >= sleep_amount * 10 : #  seconds of sleep
            break    
        time.sleep(0.1)
        count += 1
    return check_template_no_bounds(template,threshold)

def window_still_open(template:str,threshold:float,sleep_amount:float) -> bool: # oposite of the function above mainly to check if inventory is still open
    count = 0
    while check_template(template,threshold) == True:
        if count >= sleep_amount * 10 : #  seconds of sleep
            break    
        time.sleep(0.1)
        count += 1
    return check_template(template,threshold)

def window_still_open_no_bounds(template:str,threshold:float,sleep_amount:float) -> bool: # oposite of the function above mainly to check if inventory is still open
    count = 0
    while check_template_no_bounds(template,threshold) == True:
        if count >= sleep_amount * 10 : #  seconds of sleep
            break    
        time.sleep(0.1)
        count += 1
    return check_template_no_bounds(template,threshold)