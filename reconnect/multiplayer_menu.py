from reconnect import recon_utils
import time
import screen
import windows
import utils
import template
import logs.gachalogs as logs


buttons = {
    "search_x": 2230, "search_y": 260,
    "first_server_x": 2230, "first_server_y": 438,
    "join_x": 2230, "join_y": 1260,
    "refresh_x": 1240, "refresh_y": 1250,
    "back_x": 230, "back_y": 1180,
    "cancel_x": 1426, "cancel_y": 970,
    "red_okay_x": 1270, "red_okay_y": 880,
    "mod_join_x": 700, "mod_join_y": 1250,
}


def get_pixel_loc(location: str):
    value = buttons.get(location)
    if value is None:
        return None
    if location.endswith("_x"):
        return screen.map_x(value)
    if location.endswith("_y"):
        return screen.map_y(value)
    return value


def is_open():
    return recon_utils.check_template_no_bounds("multiplayer", 0.7)


def search_bar_search(server_name: str):
    if not is_open():
        return False

    location = recon_utils.template_find("search")
    if location is None:
        location = (get_pixel_loc("search_x"), get_pixel_loc("search_y"))

    windows.click(location[0], location[1])
    time.sleep(0.15)
    windows.click(location[0], location[1])
    time.sleep(0.15)
    utils.ctrl_a()
    time.sleep(0.15)
    utils.write(server_name)
    time.sleep(0.25)
    return True


def _join_mod_menu_if_open():
    if recon_utils.check_template_no_bounds("req_mods", 0.7):
        logs.logger.debug("reconnect: required mods prompt detected")
        time.sleep(0.5)
        windows.click(get_pixel_loc("mod_join_x"), get_pixel_loc("mod_join_y"))
        time.sleep(1.0)
        recon_utils.window_still_open_no_bounds("req_mods", 0.7, 5)
        recon_utils.window_still_open("join_text", 0.7, 20)
        return True
    return False


def _wait_for_world_load():
    if recon_utils.template_sleep_no_bounds("loading_screen", 0.7, 0.5):
        recon_utils.window_still_open_no_bounds("loading_screen", 0.7, 12)

    count = 0
    while count < 600:
        if template.check_template_no_bounds("tribelog_check", 0.8):
            return True
        if recon_utils.check_template_no_bounds("beds_title", 0.7):
            return True
        if recon_utils.check_template_no_bounds("download", 0.7):
            return True
        if template.check_template("death_regions", 0.7):
            return True
        utils.press_key("ShowTribeManager")
        time.sleep(0.1)
        count += 1
    return False


def _handle_failure_popups():
    if recon_utils.check_template_no_bounds("server_full", 0.7):
        logs.logger.warning("reconnect: server full detected")
        windows.click(get_pixel_loc("cancel_x"), get_pixel_loc("cancel_y"))
        recon_utils.window_still_open_no_bounds("server_full", 0.7, 2)
        time.sleep(0.5)
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        return True

    if recon_utils.check_template_no_bounds("red_fail", 0.7):
        logs.logger.warning("reconnect: red failure dialog detected")
        windows.click(get_pixel_loc("red_okay_x"), get_pixel_loc("red_okay_y"))
        recon_utils.window_still_open_no_bounds("red_fail", 0.7, 2)
        time.sleep(0.5)
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        return True

    if recon_utils.check_template_no_bounds("no_session", 0.7):
        logs.logger.warning("reconnect: no session found")
        time.sleep(1.0)
        windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
        time.sleep(1.0)
        return True

    return False


def join_server(server_name):
    if _join_mod_menu_if_open():
        return False

    if not is_open():
        utils.press_key("ShowTribeManager")
        return False

    logs.logger.debug(f"reconnect: joining server {server_name}")
    if not search_bar_search(server_name):
        return False

    windows.click(get_pixel_loc("first_server_x"), get_pixel_loc("first_server_y"))
    time.sleep(0.35)

    if recon_utils.check_template_no_bounds("join_button", 0.7):
        windows.click(get_pixel_loc("join_x"), get_pixel_loc("join_y"))
        time.sleep(0.5)
    else:
        logs.logger.warning("reconnect: join button was not detected after selecting server")
        windows.click(get_pixel_loc("refresh_x"), get_pixel_loc("refresh_y"))
        time.sleep(0.5)
        return False

    recon_utils.window_still_open("join_text", 0.7, 20)
    _join_mod_menu_if_open()

    if _wait_for_world_load():
        time.sleep(5)
        return True

    if _handle_failure_popups():
        return False

    if recon_utils.template_sleep_no_bounds("searching", 0.7, 0.5):
        recon_utils.window_still_open_no_bounds("searching", 0.7, 10)
        time.sleep(1.5)

    windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
    utils.press_key("ShowTribeManager")
    return False
