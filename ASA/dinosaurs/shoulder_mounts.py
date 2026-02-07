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
import local_player

region = template.roi_regions["access_inv"]
def access_shoulder_mount():
    utils.key_down("Reload")
    # check for the location of the access_inv
    if template.template_await_true(template.check_template_no_bounds,1,"access_inv",0.7):
        x , y = template.return_location("access_inv",0.7) 
        x0 = screen.map_x(region["start_x"])
        y0 = screen.map_y(region["start_y"])
        x = x0 + x
        y = y0 + y
        windows.move_mouse(x+20,y+20)
        time.sleep(1)
        utils.key_up("Reload")
        
        if template.template_await_true(template.check_template,2,"inventory",0.7):
            logs.logger.debug(f"inventory opened")
            if template.template_await_true(template.check_template,1,"waiting_inv",0.8):
                start = time.time()
                logs.logger.debug(f"waiting for up too 10 seconds due to the reciving remote inventory is present")
                template.template_await_false(template.check_template,10,"waiting_inv",0.8)
                logs.logger.debug(f"{time.time() - start} seconds taken for the reciving remote inventory to go away")


