import ASA.player
import ASA.player.player_state
import template
import logs.gachalogs as logs
import utils
import windows
import variables
import time 
import settings
import ASA.config 
import screen
inv_slots = { 
    "x" : 1660,
    "y" : 320,
    "distance" : 125
}
def is_open():
    return template.check_template("inventory",0.7)
    
def open():
    attempts = 0 
    while not is_open():
        attempts += 1
        logs.logger.debug(f"trying to open strucuture inventory {attempts} / {ASA.config.inventory_open_attempts}")
        utils.press_key("AccessInventory")
        if template.template_await_true(template.check_template,2,"inventory",0.7):
            logs.logger.debug(f"inventory opened")
            if template.template_await_true(template.check_template,1,"waiting_inv",0.8):
                start = time.time()
                logs.logger.debug(f"waiting for up too 10 seconds due to the reciving remote inventory is present")
                template.template_await_false(template.check_template,10,"waiting_inv",0.8)
                logs.logger.debug(f"{time.time() - start} seconds taken for the reciving remote inventory to go away")
                break
            
        #check state of the char before redoing
        else:
            ASA.player.player_state.check_state()
        if attempts >= ASA.config.inventory_open_attempts:
            logs.logger.error(f"unable to open up the objects inventory")
            break
    time.sleep(0.4*settings.lag_offset)    
def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(f"trying to close objects inventory {attempts} / {ASA.config.inventory_close_attempts}")
        windows.click(variables.get_pixel_loc("close_inv_x"), variables.get_pixel_loc("close_inv_y"))
        template.template_await_false(template.check_template,2,"inventory",0.7)
            
        if attempts >= ASA.config.inventory_close_attempts:
            logs.logger.error(f"unable to close the objects inventory after {attempts} attempts") 
            #check state of the char the reason we can do it now is that the latter should spam click close inv 
            ASA.player.player_state.check_state()
            break
    time.sleep(0.4*settings.lag_offset)    
#these functions assume that the inventory is already open
def search_in_object(item:str): 
    if is_open():    
        logs.logger.debug(f"searching in structure/dino for {item}")
        time.sleep(0.4*settings.lag_offset)
        windows.click(variables.get_pixel_loc("search_object_x"),variables.get_pixel_loc("transfer_all_y"))
        utils.ctrl_a() 
        time.sleep(0.4*settings.lag_offset)
        utils.write(item)
        time.sleep(0.4*settings.lag_offset)
    
def drop_all_obj():
    if is_open():    
        logs.logger.debug(f"dropping all items from object")
        time.sleep(0.4*settings.lag_offset)
        windows.click(variables.get_pixel_loc("drop_all_obj_x"),variables.get_pixel_loc("transfer_all_y")) 
        time.sleep(0.4*settings.lag_offset)

def transfer_all_from(): 
    if is_open():
        logs.logger.debug(f"transfering all from object")
        time.sleep(0.4*settings.lag_offset)
        windows.click(variables.get_pixel_loc("transfer_all_from_x"), variables.get_pixel_loc("transfer_all_y"))
        time.sleep(0.4*settings.lag_offset)



def select_object_inventory_tab():
    """Clicks the structure-side 'INVENTORY' tab (right panel)."""
    if is_open():
        windows.click(
            variables.get_pixel_loc("structure_inventory_tab_x"),
            variables.get_pixel_loc("structure_inventory_tab_y"),
        )
        time.sleep(0.3 * settings.lag_offset)


def select_object_crafting_tab():
    """Clicks the structure-side 'CRAFTING' tab (right panel)."""
    if is_open():
        windows.click(
            variables.get_pixel_loc("structure_crafting_tab_x"),
            variables.get_pixel_loc("structure_crafting_tab_y"),
        )
        time.sleep(0.3 * settings.lag_offset)

def popcorn_top_row():
    if is_open():
        for count in range(6):
            time.sleep(0.3 * settings.lag_offset)
            base_x = inv_slots["x"] + (count * inv_slots["distance"]) + 30  # authored at 2560x1440
            base_y = inv_slots["y"] + 30

            x = screen.map_x(base_x)
            y = screen.map_y(base_y)

            windows.move_mouse(x, y)
            time.sleep(0.3 * settings.lag_offset)
            utils.press_key("DropItem")

def auto_stack(settle_seconds=None) -> bool:
    """Click Auto Stack reliably.

    - Tries template-based click first (when templates exist and match).
    - Always falls back to fixed coords (variables.auto_stack_x/auto_stack_y).
    - Never aborts the click just because template matching failed.
    """
    if not is_open():
        return False

    settle = settle_seconds
    if settle is None:
        settle = float(getattr(settings, "auto_stack_settle_seconds", 0.75))

    try:
        # 1) Template-location click (preferred when it works)
        key = None
        loc = None
        try:
            if template.check_template("auto_stack_icon", 0.65):
                key = "auto_stack_icon"
                loc = template.return_location("auto_stack_icon", 0.65)
            elif template.check_template("auto_stack", 0.70):
                key = "auto_stack"
                loc = template.return_location("auto_stack", 0.70)
        except Exception as e:
            logs.logger.debug(f"auto_stack template match failed (continuing with fallback): {e}")

        if key and loc and loc != 0:
            try:
                region = template.roi_regions[key]
                origin_x = screen.map_x(region["start_x"])
                origin_y = screen.map_y(region["start_y"])

                img = template._read_icon(key)
                w = int(img.shape[1]) if img is not None else 20
                h = int(img.shape[0]) if img is not None else 20

                click_x = int(origin_x + loc[0] + (w / 2))
                click_y = int(origin_y + loc[1] + (h / 2))

                windows.click(click_x, click_y)
                time.sleep(max(0.2, settle) * settings.lag_offset)
                return True
            except Exception as e:
                logs.logger.debug(f"auto_stack template click failed (continuing with fallback): {e}")

        # 2) Fixed coordinate fallback
        x = variables.get_pixel_loc("auto_stack_x")
        y = variables.get_pixel_loc("auto_stack_y")
        if x is None or y is None:
            return False

        windows.click(x, y)
        time.sleep(max(0.2, settle) * settings.lag_offset)
        return True
    except Exception as e:
        logs.logger.error(f"auto_stack failed: {e}")
        return False
