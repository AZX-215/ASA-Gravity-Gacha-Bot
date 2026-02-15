import template
import logs.gachalogs as logs
import utils
import windows
import variables
import screen
import time 
import settings
import ASA.config 
import ASA.stations.custom_stations
import ASA.player.tribelog
import ASA.player.player_inventory
import ASA.player.buffs
import pyautogui
import local_player

def is_open():
    return template.check_template("beds_title",0.7) #bed title is found in both death and fast travel screens
    
def is_dead():
    return template.check_template("death_regions",0.7)
    
def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(f"trying to close the bed {attempts} / {ASA.config.teleporter_close_attempts}")
        windows.click(variables.get_pixel_loc("back_button_tp_x"),variables.get_pixel_loc("back_button_tp_y"))
        time.sleep(0.2*settings.lag_offset)

        if attempts >= ASA.config.teleporter_close_attempts:
            logs.logger.error(f"unable to close the bed after {ASA.config.teleporter_close_attempts} attempts")
            break
            


def _use_key_char() -> str:
    try:
        return chr(utils.keymap_return(local_player.get_input_settings("Use")))
    except Exception:
        # Fallback: default ASA use key is usually 'E'
        return "e"


def open_fast_travel_screen(yaw: float | None = None, pitch_down_degrees: float = 15.0, attempts: int = 4) -> bool:
    """Open the bed/tekpod Fast Travel screen from in-world interaction.

    Assumes the character is close enough to a bed/tekpod to open its radial menu.
    Returns True if the bed list screen opens (beds_title detected).
    """
    use_ch = _use_key_char()

    # Best-effort close other UIs.
    try:
        ASA.player.tribelog.close()
    except Exception:
        pass
    try:
        ASA.player.player_inventory.close()
    except Exception:
        pass

    for attempt in range(1, int(attempts or 1) + 1):
        try:
            # Stand up / clear movement state (best-effort).
            try:
                utils.press_key(local_player.get_input_settings("Run"))
            except Exception:
                pass

            utils.zero()

            if yaw is None:
                try:
                    yaw = float(getattr(settings, "station_yaw", 0.0))
                except Exception:
                    yaw = None

            if yaw is not None:
                try:
                    utils.set_yaw(float(yaw))
                except Exception:
                    pass

            try:
                utils.turn_down(float(pitch_down_degrees or 0))
            except Exception:
                pass

            time.sleep(0.25 * getattr(settings, "lag_offset", 1.0))

            # Hold Use to open radial
            pyautogui.keyDown(use_ch)

            if not template.template_await_true(template.check_template_no_bounds, 1.0, "bed_radical", 0.6):
                # retry short hold once
                pyautogui.keyUp(use_ch)
                time.sleep(0.2 * getattr(settings, "lag_offset", 1.0))
                pyautogui.keyDown(use_ch)
                time.sleep(0.45 * getattr(settings, "lag_offset", 1.0))

            if not template.check_template_no_bounds("bed_radical", 0.6):
                pyautogui.keyUp(use_ch)
                logs.logger.debug(f"[BedFastTravel] Radial not detected (attempt {attempt}/{attempts}).")
                time.sleep(0.35 * getattr(settings, "lag_offset", 1.0))
                continue

            # Try user-tuned Fast Travel coordinate first, then try a small sweep around it.
            fx = variables.get_pixel_loc("radical_fast_travel_x")
            fy = variables.get_pixel_loc("radical_fast_travel_y")

            # Anchor around laydown (known-good) if fast-travel coords are missing.
            if fx is None or fy is None:
                fx = variables.get_pixel_loc("radical_laydown_x")
                fy = variables.get_pixel_loc("radical_laydown_y")

            dx = screen.map_w(220)
            dy = screen.map_h(220)

            candidates = [
                (fx, fy),
                (fx + dx, fy),
                (fx + dx, fy + dy),
                (fx, fy + dy),
                (fx - dx, fy + dy),
                (fx - dx, fy),
                (fx - dx, fy - dy),
                (fx, fy - dy),
                (fx + dx, fy - dy),
            ]

            for (cx, cy) in candidates:
                windows.move_mouse(cx, cy)
                time.sleep(0.25 * getattr(settings, "lag_offset", 1.0))
                pyautogui.keyUp(use_ch)

                # Wait briefly for bed list screen
                if template.template_await_true(template.check_template, 1.4, "beds_title", 0.7):
                    return True

                # If we hit the wrong radial option (e.g. Rename), we can get stuck in a dialog.
                # Always attempt to close any modal/UI before trying the next candidate.
                try:
                    pyautogui.press("esc")
                    time.sleep(0.2 * getattr(settings, "lag_offset", 1.0))
                except Exception:
                    pass

                # If we accidentally laid down / entered a pod, try to get out before next candidate.
                try:
                    if ASA.player.buffs.check_buffs().check_buffs() == 1:
                        pyautogui.press(use_ch)
                        time.sleep(0.9 * getattr(settings, "lag_offset", 1.0))
                        if ASA.player.buffs.check_buffs().check_buffs() == 1:
                            time.sleep(1.0 * getattr(settings, "lag_offset", 1.0))
                            pyautogui.press(use_ch)
                            time.sleep(0.9 * getattr(settings, "lag_offset", 1.0))
                except Exception:
                    pass

                # Re-open radial for next candidate
                pyautogui.keyDown(use_ch)
                time.sleep(0.35 * getattr(settings, "lag_offset", 1.0))

            # Ensure Use key is released
            try:
                pyautogui.keyUp(use_ch)
            except Exception:
                pass

            logs.logger.debug(f"[BedFastTravel] Bed list screen not opened (attempt {attempt}/{attempts}).")
            time.sleep(0.45 * getattr(settings, "lag_offset", 1.0))

        except Exception as e:
            try:
                pyautogui.keyUp(use_ch)
            except Exception:
                pass
            logs.logger.debug(f"[BedFastTravel] Exception opening Fast Travel screen (attempt {attempt}/{attempts}): {e}")
            time.sleep(0.5 * getattr(settings, "lag_offset", 1.0))

    return False


def fast_travel_to(bed_name: str, yaw: float | None = None, pitch_down_degrees: float = 15.0, attempts: int = 4) -> bool:
    """Open Fast Travel screen from a bed/tekpod and spawn at the destination bed."""
    if not open_fast_travel_screen(yaw=yaw, pitch_down_degrees=pitch_down_degrees, attempts=attempts):
        logs.logger.error(f"[BedFastTravel] Failed to open Fast Travel screen for destination '{bed_name}'.")
        return False

    return spawn_in(bed_name, allow_implant=False, post_spawn_tribelog_bump=False)


def spawn_in(bed_name: str, allow_implant: bool = True, post_spawn_tribelog_bump: bool = True) -> bool:
    # If the bed/fast travel screen isn't open, optionally force it via implant (legacy behavior).
    if not is_open():
        if allow_implant:
            ASA.player.player_inventory.implant_eat()
        else:
            logs.logger.error("bed.spawn_in called but bed screen is not open (allow_implant=False).")
            return False

    if is_open():
        state = "death screen" if is_dead() else "fast travel screen"
        logs.logger.debug(f"char is in the {state}")
        search_bar_x = variables.get_pixel_loc("search_bar_bed_dead_x" if is_dead() else "search_bar_bed_alive_x")
        windows.click(search_bar_x, variables.get_pixel_loc("search_bar_bed_y")) #search bar y axis is the same for both death/alive 
        
        utils.ctrl_a() #CTRL A removes all previous data in the search bar 
        utils.write(bed_name)

        time.sleep(0.2*settings.lag_offset)
        windows.click(variables.get_pixel_loc("first_bed_slot_x"),variables.get_pixel_loc("first_bed_slot_y"))

        # Wait for the selected bed row to show READY state.
        # Retry once to avoid false negatives due to timing / scaling.
        if not template.template_await_true(template.check_teleporter_orange,3):
            time.sleep(0.25*settings.lag_offset)
            windows.click(variables.get_pixel_loc("first_bed_slot_x"),variables.get_pixel_loc("first_bed_slot_y"))
            time.sleep(0.5*settings.lag_offset)

        if not template.template_await_true(template.check_teleporter_orange,3):
            logs.logger.error(
                f"bed '{bed_name}' was not detected as READY (or could not be found). Exiting bed screen now"
            )
            close()
            return
               
        windows.click(variables.get_pixel_loc("spawn_button_x"),variables.get_pixel_loc("spawn_button_y"))

        if template.template_await_true(template.white_flash,2):
            logs.logger.debug(f"white flash detected waiting for up too 5 seconds")
            template.template_await_false(template.white_flash,5)

        time.sleep(10) # animation spawn in is about 7 seconds 

        if post_spawn_tribelog_bump:
            ASA.player.tribelog.open()
            ASA.player.tribelog.close()
        return True

    return False
