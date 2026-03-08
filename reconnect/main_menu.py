from reconnect import recon_utils
import windows
import screen


buttons = {
    "accept_x": 1255, "accept_y": 980,
    "join_last_session_x": 1250, "join_last_session_y": 1260,
    "start_x": 1270, "start_y": 1150,
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
    return (
        recon_utils.check_template_no_bounds("join_last_session", 0.7)
        or disconnect()
        or network_failure()
    )


def disconnect():
    return recon_utils.check_template_no_bounds("connection_timeout", 0.7)


def network_failure():
    return recon_utils.check_template_no_bounds("network_failure", 0.7)


def join_last():
    if not is_open():
        return
    if disconnect():
        windows.click(get_pixel_loc("accept_x"), get_pixel_loc("accept_y"))
        recon_utils.window_still_open_no_bounds("accept", 0.7, 1)
    if network_failure():
        windows.click(get_pixel_loc("accept_x"), get_pixel_loc("accept_y"))
        recon_utils.window_still_open_no_bounds("network_failure", 0.7, 1)

    windows.click(get_pixel_loc("join_last_session_x"), get_pixel_loc("join_last_session_y"))
    recon_utils.window_still_open_no_bounds("join_last_session", 0.7, 1)


def enter_menu():
    if not is_open():
        return
    if disconnect():
        windows.click(get_pixel_loc("accept_x"), get_pixel_loc("accept_y"))
        recon_utils.window_still_open_no_bounds("accept", 0.7, 1)
    if network_failure():
        windows.click(get_pixel_loc("accept_x"), get_pixel_loc("accept_y"))
        recon_utils.window_still_open_no_bounds("network_failure", 0.7, 1)

    windows.click(get_pixel_loc("accept_x"), get_pixel_loc("accept_y"))
    windows.click(get_pixel_loc("start_x"), get_pixel_loc("start_y"))
    recon_utils.window_still_open_no_bounds("join_last_session", 0.7, 1)
