import ASA.player.player_state
import template
import logs.gachalogs as logs
import utils
import windows
import variables
import time 
import settings
import ASA.config 
import ASA.stations.custom_stations
import ASA.player.tribelog

def is_open():
    return template.check_template("teleporter_title",0.7)
    
def open():
    """
    player should already be looking down at the teleporter this just opens and WILL try and correct if there are issues 
    """
    attempts = 0 
    while not is_open():
        attempts += 1
        logs.logger.debug(f"trying to open teleporter {attempts} / {ASA.config.teleporter_open_attempts}")
        utils.press_key("Use")
    
        if not template.template_await_true(template.check_template,2,"teleporter_title",0.7):
            logs.logger.warning("teleporter didnt open retrying now")
            ASA.player.player_state.check_state()
            # check state of char which should close out of any windows we are in or rejoin the game
            utils.pitch_zero() # reseting the chars pitch/yaw
            utils.turn_down(80)
            time.sleep(0.5*settings.lag_offset) 
        else:
            logs.logger.debug(f"teleporter opened")   

        if attempts >= ASA.config.teleporter_open_attempts:
            logs.logger.error(f"unable to open up the teleporter after {ASA.config.teleporter_open_attempts} attempts")
            break
            
def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(f"trying to close the teleporter {attempts} / {ASA.config.teleporter_close_attempts}")
        windows.click(variables.get_pixel_loc("back_button_tp_x"),variables.get_pixel_loc("back_button_tp_y"))
        time.sleep(0.5*settings.lag_offset)

        if attempts >= ASA.config.teleporter_close_attempts:
            logs.logger.error(f"unable to close the teleporter after {ASA.config.teleporter_close_attempts} attempts")
            break
    
def teleport_not_default(arg):

    if isinstance(arg, ASA.stations.custom_stations.station_metadata):
        stationdata = arg
    else:
        stationdata = ASA.stations.custom_stations.get_station_metadata(arg)

    teleporter_name = stationdata.name
    time.sleep(0.5*settings.lag_offset)
    utils.turn_down(80)
    time.sleep(0.5*settings.lag_offset)
    open() 
    time.sleep(0.5*settings.lag_offset) #waiting for teleport_icon to populate on the screen before we check
    if is_open():
        if not template.teleport_icon(0.55):
            start = time.time()
            logs.logger.debug("teleport icons are not on the teleport screen; waiting up to 15 seconds for them to appear")
            template.template_await_true(template.teleport_icon,15,0.55)
            logs.logger.debug(f"time taken for teleporter icon to appear : {time.time() - start}")

        # Focus search, type name, and confirm with ENTER.
        def _type_search(name: str):
            windows.click(variables.get_pixel_loc("search_bar_bed_alive_x"), variables.get_pixel_loc("search_bar_bed_y"))
            time.sleep(0.10*settings.lag_offset)
            utils.ctrl_a()
            utils.write(name)
            time.sleep(0.10*settings.lag_offset)
            utils.press_key("enter")

        _type_search(teleporter_name)
        time.sleep(0.6*settings.lag_offset)

        # Robust selection + READY confirmation.
        # We prefer READY confirmation, but we do not hard-fail if it isn't detected; instead we attempt the teleport
        # and verify via white-flash / UI transition.
        ready = False
        for sel_attempt in range(1, 4):
            windows.click(variables.get_pixel_loc("first_bed_slot_x"), variables.get_pixel_loc("first_bed_slot_y"))
            time.sleep(0.35*settings.lag_offset)
            if template.template_await_true(template.check_teleporter_orange, 1.5):
                ready = True
                break

            # Recovery nudges
            if sel_attempt == 1:
                # Sometimes the list doesn't apply until Enter or the click doesn't register.
                utils.press_key("enter")
                time.sleep(0.25*settings.lag_offset)
            elif sel_attempt == 2:
                # Re-type search once to ensure we're on the right entry.
                _type_search(teleporter_name)
                time.sleep(0.6*settings.lag_offset)

        if not ready:
            logs.logger.warning(
                f"teleporter READY not confirmed for '{teleporter_name}'. "
                f"Attempting teleport anyway and verifying via UI transition."
            )

        # Attempt teleport up to 2 times and verify it actually fired.
        teleported = False
        for tp_attempt in range(1, 3):
            # Ensure selection is on first row before clicking spawn.
            windows.click(variables.get_pixel_loc("first_bed_slot_x"), variables.get_pixel_loc("first_bed_slot_y"))
            time.sleep(0.25*settings.lag_offset)
            windows.click(variables.get_pixel_loc("spawn_button_x"), variables.get_pixel_loc("spawn_button_y"))

            if template.template_await_true(template.white_flash, 2):
                logs.logger.debug("white flash detected; waiting for it to clear")
                template.template_await_false(template.white_flash, 5)
                teleported = True
                break

            # If the teleporter UI closed without a flash, still treat as success.
            if template.template_await_false(template.check_template, 1.5, "teleporter_title", 0.7) == False:
                teleported = True
                break

            logs.logger.debug(f"teleport did not trigger (attempt {tp_attempt}/2); retrying")
            time.sleep(0.5*settings.lag_offset)

        if not teleported:
            logs.logger.error(f"teleport failed to trigger for '{teleporter_name}'. Capturing debug images and exiting teleporter UI.")
            try:
                template.debug_capture(
                    "teleporter_failed",
                    extra_regions={
                        "teleporter_title": template.roi_regions["teleporter_title"],
                        "teleporter_icon": template.roi_regions["teleporter_icon"],
                        "orange": template.roi_regions["orange"],
                        "ready_clicked_bed": template.roi_regions["ready_clicked_bed"],
                    },
                )
            except Exception:
                pass
            close()
        else:
            # A quick tribelog open/close is used elsewhere in the bot to stabilize post-teleport UI state.
            ASA.player.tribelog.open()
            ASA.player.tribelog.close()
        time.sleep(0.5*settings.lag_offset)
        if settings.singleplayer: # single player for some reason changes view angles when you tp 
            utils.current_pitch = 0
            utils.turn_down(80)
            time.sleep(0.5)
        utils.turn_up(80)
        time.sleep(0.5) 
        utils.set_yaw(stationdata.yaw)
        
            


                
                              

                
                