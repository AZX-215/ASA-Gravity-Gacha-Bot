from reconnect import join_menu, main_menu, multiplayer_menu, recon_utils, crash
import time
import template
import windows
import logs.gachalogs as logs


class reconnect():

    def __init__(self, server):
        self.server = server

    def check_disconected(self):
        return (
            recon_utils.check_template_no_bounds("escape", 0.7)
            or recon_utils.check_template_no_bounds("escape_obscured", 0.7)
        )

    def _joined_server(self):
        return (
            template.check_template_no_bounds("tribelog_check", 0.8)
            or template.check_template("death_regions", 0.7)
            or recon_utils.check_template_no_bounds("beds_title", 0.7)
            or recon_utils.check_template_no_bounds("download", 0.7)
        )

    def rejoin_server(self):
        start_time = time.time()
        c = crash.crash(windows.hwnd)

        while True:
            if self._joined_server():
                return

            if c.detect_crash():
                logs.logger.critical("reconnect: crash detected during reconnect, relaunching game")
                c.re_open_game()
                start_time = time.time()
                time.sleep(5)
                continue

            if (time.time() - start_time) >= 15 * 60:
                logs.logger.critical("reconnect: reconnect timed out, relaunching game")
                c.re_open_game()
                start_time = time.time()
                time.sleep(5)
                continue

            main_menu.enter_menu()
            time.sleep(0.5)
            join_menu.enter_menu()
            time.sleep(0.5)
            multiplayer_menu.join_server(self.server)
            time.sleep(0.5)
