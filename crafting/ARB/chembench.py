import ASA.stations
import ASA.stations.custom_stations
import ASA.structures
import ASA.structures.teleporter
import template
import logs.gachalogs as logs
import utils
import windows
import variables
import time 
import settings
import ASA.config 
import ASA.structures.inventory
import ASA.player.player_inventory
import bot.config
import json
import screen 
def craft_gunpowder():
    # open chem bench
    ASA.structures.inventory.open()
    if not template.template_await_true(template.check_template,1,"chem_bench",0.7):
        ASA.structures.inventory.close()
        utils.zero()
        #utils.set_yaw(metadata.yaw)
    # search for gun
    if template.check_template("chem_bench",0.7):
        ASA.structures.inventory.search_in_object("gun")
        time.sleep(0.3*settings.lag_offset)
        base_x = ASA.structures.inventory.inv_slots["x"]
        base_y = ASA.structures.inventory.inv_slots["y"]
        x = screen.map_x(base_x)
        y = screen.map_y(base_y)
        windows.move_mouse(x, y)
        windows.click(x, y)
        
        for count in range(15):
            utils.press_key("a")
    # press hover first slot
    # hold A 

    ...
def craft_sparkpowder():
    ASA.structures.inventory.open()
    if not template.template_await_true(template.check_template,1,"chem_bench",0.7):
        ASA.structures.inventory.close()
        utils.zero()
        #utils.set_yaw(metadata.yaw)
    # search for gun
    if template.check_template("chem_bench",0.7):
        ASA.structures.inventory.search_in_object("spark")
        time.sleep(0.3*settings.lag_offset)
        base_x = ASA.structures.inventory.inv_slots["x"]
        base_y = ASA.structures.inventory.inv_slots["y"]
        x = screen.map_x(base_x)
        y = screen.map_y(base_y)
        windows.move_mouse(x, y)
        windows.click(x, y)
        
        for count in range(15):
            utils.press_key("a")
    # open chem bench
    # search for gun
    # press hover first slot
    # hold A 
    ...