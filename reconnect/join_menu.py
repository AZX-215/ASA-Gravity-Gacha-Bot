from reconnect import recon_utils
import screen
import windows


buttons = {
    "join_game_x": 919, "join_game_y": 710,
    "back_x": 1280, "back_y": 1280,
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
    return recon_utils.check_template_no_bounds("join_game", 0.7)


def enter_menu():
    if not is_open():
        return
    location = recon_utils.template_find("join_game")
    if location is None:
        location = (get_pixel_loc("join_game_x"), get_pixel_loc("join_game_y"))
    windows.click(location[0], location[1])
    recon_utils.window_still_open_no_bounds("join_game", 0.7, 1)


def exit_menu():
    if not is_open():
        return
    windows.click(get_pixel_loc("back_x"), get_pixel_loc("back_y"))
    recon_utils.window_still_open_no_bounds("join_game", 0.7, 1)
