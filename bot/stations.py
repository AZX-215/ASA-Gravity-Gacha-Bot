import settings
import time
import template
import logs.gachalogs as logs
import bot.render
import utils
from ASA.strucutres import bed , teleporter , inventory
from ASA.player import buffs , console , player_state , tribelog , player_inventory
from ASA.stations import custom_stations
from bot import config , deposit , gacha , iguanadon , pego 
from crafting.ARB import megalab as megalab_crafting
from abc import ABC ,abstractmethod
global berry_station
global last_berry
last_berry = 0
berry_station = True

class base_task(ABC):
    def __init__(self):
        self.has_run_before = False
        
    @abstractmethod
    def execute(self):
        pass
    @abstractmethod
    def get_priority_level(self):
        pass
    @abstractmethod
    def get_requeue_delay(self):
        pass
    
    def mark_as_run(self):
        self.has_run_before = True

class gacha_station(base_task):
    def __init__(self,name,teleporter_name,direction):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.direction = direction


    def execute(self):
        player_state.check_state()

        if not getattr(settings, "gacha_enabled", True):
            logs.logger.info("[Gacha] Disabled via settings.gacha_enabled; skipping.")
            return
        global berry_station
        global last_berry
        
        temp = False
        time_between = time.time() - last_berry

        gacha_metadata = custom_stations.get_station_metadata(self.teleporter_name)
        gacha_metadata.side = self.direction

        berry_metadata = custom_stations.get_station_metadata(settings.berry_station)
        iguanadon_metadata = custom_stations.get_station_metadata(settings.iguanadon)

        if (berry_station or time_between > config.time_to_reberry*60*60): # if time is greater than 4 hours since the last time you went to berry station 
            teleporter.teleport_not_default(berry_metadata)                    # or if berry station is true( when you go to tekpod and drop all ) and the time between has been longer than 30 mins since youve last been 
            if settings.external_berry: 
                logs.logger.debug("sleeping for 20 seconds as external")
                time.sleep(20)#letting station spawn in if you have to tp away
            iguanadon.berry_station()
            last_berry = time.time()
            berry_station = False
            temp = True
        
        teleporter.teleport_not_default(iguanadon_metadata) # iguanadon is a centeral tp
        
        if settings.external_berry and temp: # quick fix for level 1 bug
            logs.logger.debug("reconnecting because of level 1 bug - you chose external berry will sleep for 60 seconds as a way to ensure that we are fully loaded in")
            console.console_write("reconnect")
            time.sleep(60) # takes a while for the reonnect to actually go into action

        iguanadon.iguanadon(iguanadon_metadata)
        teleporter.teleport_not_default(gacha_metadata)
        time.sleep(0.2)
        gacha.drop_off(gacha_metadata)

    def get_priority_level(self):
        # Shifted to keep room for crafting tasks between pego and gachas.
        return 4
    
    def get_requeue_delay(self):
        if settings.seeds_230:
            delay = 10700  # should take about this amount of time to do 230 slots of seeds 
        else:
            delay = 6600    # delay can be constant as it will be the same for all gachas 142 stacks took 110 mins
        return delay 

class pego_station(base_task):
    def __init__(self,name,teleporter_name,delay):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.delay = delay

    def execute(self):
        player_state.check_state()

        if not getattr(settings, "pego_enabled", True):
            logs.logger.info("[Pego] Disabled via settings.pego_enabled; skipping.")
            return
        
        pego_metadata = custom_stations.get_station_metadata(self.teleporter_name)
        dropoff_metadata = custom_stations.get_station_metadata(settings.drop_off)

        teleporter.teleport_not_default(pego_metadata)
        pego.pego_pickup(pego_metadata)
        if template.check_template("crystal_in_hotbar",0.7):
            open_crystals_metadata = custom_stations.get_station_metadata(settings.open_crystals)
            teleporter.teleport_not_default(open_crystals_metadata)  # teleport to open crystals station
            time.sleep(0.8)  # give HUD/hotbar a moment to load after TP
            deposit.open_crystals()
            time.sleep(0.2)
            deposit.dedi_deposit_alt(settings.height_ele)
            time.sleep(0.2)
            utils.zero()
            utils.set_yaw(open_crystals_metadata.yaw)
            time.sleep(0.2)
            deposit.vaults(open_crystals_metadata)
            time.sleep(0.2)
            teleporter.teleport_not_default(dropoff_metadata)
            time.sleep(0.5)
            deposit.deposit_all(dropoff_metadata)
            time.sleep(0.2)

        else:
            logs.logger.info(f"bot has no crystals in hotbar we are skipping the deposit step")

    def get_priority_level(self):
        return 2 # highest prio level as we cant have these get capped 

    def get_requeue_delay(self):
        return self.delay # delay cannot be constant as stations can cover different amounts of space each |||| 2 stacks of berries to 1 crystal 4 gachas to 1 pego
    
    
class sparkpowder_station(base_task):

    def __init__(self, name, teleporter_name, delay=0, deposit_height=3, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        # Re-queue delay (seconds) per station (from json_files/sparkpowder.json)
        self.delay = float(delay or 0)
        # Optional per-station initial delay before first run
        self.initial_delay = float(initial_delay or 0)
        self.deposit_height = deposit_height
        self.one_shot = False  # task_manager checks this to avoid re-queueing

    def execute(self):
        player_state.check_state()

        # Gate by BOTH the global crafting toggle and the sparkpowder feature toggle.
        if not getattr(settings, "crafting", False) or not getattr(settings, "sparkpowder_enabled", False):
            logs.logger.info("[Sparkpowder] Disabled in settings (crafting and/or sparkpowder_enabled); skipping.")
            return

        meta = custom_stations.get_station_metadata(self.teleporter_name)
        logs.logger.info(f"[Sparkpowder] Teleport -> Station: {self.teleporter_name}")
        teleporter.teleport_not_default(meta)
        time.sleep(0.5 * getattr(settings, "lag_offset", 1.0))

        # Ensure pitch starts neutral before we do our look-up/down offsets
        utils.pitch_zero()
        time.sleep(0.15 * settings.lag_offset)

        # Stations face the common yaw; Megalab/Dedis are behind.
        utils.turn_right(getattr(settings, "sparkpowder_turn_degrees", 180))
        time.sleep(0.25 * settings.lag_offset)

        # Look up to face the Megalab
        utils.turn_up(getattr(settings, "sparkpowder_look_degrees", 45))
        time.sleep(0.25 * settings.lag_offset)

        # Open Megalab inventory, transfer existing sparkpowder, then craft more
        inventory.open()
        if not template.template_await_true(template.check_template, 1, "megalab", 0.7):
            logs.logger.warning("[Sparkpowder] Megalab template not detected after open; retrying once")
            inventory.close()
            time.sleep(0.25 * settings.lag_offset)
            player_state.check_state()
            inventory.open()

        if template.template_await_true(template.check_template, 1, "megalab", 0.7):
            megalab_crafting.run_sparkpowder_cycle(craft_seconds=getattr(settings, "sparkpowder_craft_seconds", 2.0))
        else:
            logs.logger.error("[Sparkpowder] Unable to open Megalab inventory; skipping craft/deposit for this station")
            inventory.close()
            utils.pitch_zero()
            utils.set_yaw(meta.yaw)
            return

        inventory.close()
        time.sleep(0.25 * settings.lag_offset)

        # Return pitch back to neutral (we looked up earlier)
        utils.turn_down(getattr(settings, "sparkpowder_look_degrees", 45))
        time.sleep(0.25 * settings.lag_offset)

         # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
        utils.pitch_zero()
        utils.set_yaw(meta.yaw)
        
        # Deposit to the station's dedicated storage boxes
        deposit.dedi_deposit_custom_1(self.deposit_height)
        time.sleep(0.25 * settings.lag_offset)

        # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

    def get_priority_level(self):
        # After pego (2), before gacha (4)
        return 3

    def get_requeue_delay(self):
        # Prefer the per-station delay from sparkpowder.json; fall back to a global default.
        if getattr(self, "delay", 0):
            return float(self.delay)
        return getattr(settings, "sparkpowder_requeue_delay", 1800)


class gunpowder_station(base_task):

    def __init__(self, name, teleporter_name, delay=0, deposit_height=3, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        # Re-queue delay (seconds) per station (from json_files/gunpowder.json)
        self.delay = float(delay or 0)
        # Optional per-station initial delay before first run
        self.initial_delay = float(initial_delay or 0)
        self.deposit_height = deposit_height
        self.one_shot = False  # task_manager checks this to avoid re-queueing

    def execute(self):
        player_state.check_state()

        # Gate by BOTH the global crafting toggle and the gunpowder feature toggle.
        if not getattr(settings, "crafting", False) or not getattr(settings, "gunpowder_enabled", False):
            logs.logger.info("[Gunpowder] Disabled in settings (crafting and/or gunpowder_enabled); skipping.")
            return

        meta = custom_stations.get_station_metadata(self.teleporter_name)
        logs.logger.info(f"[Gunpowder] Teleport -> Station: {self.teleporter_name}")
        teleporter.teleport_not_default(meta)
        time.sleep(0.5 * getattr(settings, "lag_offset", 1.0))

        # Ensure pitch starts neutral before we do our look-up/down offsets
        utils.pitch_zero()
        time.sleep(0.15 * settings.lag_offset)

        # Look down to face the Megalab
        look_deg = float(getattr(settings, "gunpowder_look_degrees", 25.0) or 25.0)
        utils.turn_down(look_deg)
        time.sleep(0.25 * settings.lag_offset)

        # Open Megalab inventory, transfer existing gunpowder, then craft more
        inventory.open()
        if not template.template_await_true(template.check_template, 1, "megalab", 0.7):
            logs.logger.warning("[Gunpowder] Megalab template not detected after open; retrying once")
            inventory.close()
            time.sleep(0.25 * settings.lag_offset)
            player_state.check_state()
            inventory.open()

        if template.template_await_true(template.check_template, 1, "megalab", 0.7):
            megalab_crafting.run_gunpowder_cycle(craft_seconds=getattr(settings, "gunpowder_craft_seconds", 2.0))
        else:
            logs.logger.error("[Gunpowder] Unable to open Megalab inventory; skipping craft/deposit for this station")
            inventory.close()
            utils.pitch_zero()
            utils.set_yaw(meta.yaw)
            return

        inventory.close()
        time.sleep(0.25 * settings.lag_offset)

        # Return pitch back to neutral (we looked down earlier)
        utils.turn_up(look_deg)
        time.sleep(0.25 * settings.lag_offset)

        # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

        
        turn_deg = float(getattr(settings, "gunpowder_turn_degrees", 180.0) or 180.0)
        if abs(turn_deg) > 0.1:
            utils.turn_right(turn_deg)
            time.sleep(0.25 * settings.lag_offset)

        # Deposit to the station's dedicated storage boxes
        deposit.dedi_deposit_custom_2(self.deposit_height)
        time.sleep(0.25 * settings.lag_offset)

        # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

    def get_priority_level(self):
        # Same priority tier as sparkpowder (between pego and gacha)
        return 3

    def get_requeue_delay(self):
        # Prefer the per-station delay from gunpowder.json; fall back to a global default.
        if getattr(self, "delay", 0):
            return float(self.delay)
        return getattr(settings, "gunpowder_requeue_delay", 3000)
class render_station(base_task):
    def __init__(self):
        super().__init__()
        self.name = settings.bed_spawn
        
    def execute(self):
        global berry_station 
        if bot.render.render_flag == False: # ! changed this and deleted a statement. review orginal if not broken.
            logs.logger.debug(f"render flag:{bot.render.render_flag} we are trying to get into the pod now")
            player_state.reset_state()
            teleporter.teleport_not_default(settings.bed_spawn)
            time.sleep(0.5)
            bot.render.enter_tekpod()
            player_inventory.open()
            player_inventory.drop_all_inv()
            player_inventory.close()
            tribelog.open()
            time.sleep(0.5)
    def get_priority_level(self):
        return 8

    def get_requeue_delay(self):
        return 90 # after triggered we will wait for 60 seconds reduces the amount of cpu usage 
    
class snail_pheonix(base_task):
    def __init__(self,name,teleporter_name,direction,depo):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.direction = direction
        self.depo_tp = depo

    def execute(self):
        if not getattr(settings, "gacha_enabled", True):
            logs.logger.info("[Gacha:Collect] Disabled via settings.gacha_enabled; skipping.")
            return

        gacha_metadata = custom_stations.get_station_metadata(self.teleporter_name)
        gacha_metadata.side = self.direction

        player_state.check_state()
        teleporter.teleport_not_default(gacha_metadata)
        time.sleep(0.2)
        gacha.collection(gacha_metadata)
        time.sleep(0.2)
        teleporter.teleport_not_default(self.depo_tp)
        time.sleep(0.2)
        deposit.dedi_deposit(settings.height_ele)
        time.sleep(0.2)
        
    def get_priority_level(self):
        # Shifted to remain after normal gachas.
        return 5
    def get_requeue_delay(self):
        return 13200

class pause(base_task):
    def __init__(self,time):
        super().__init__()
        self.name = "pause"
        self.time = time
    def execute(self):
        player_state.check_state()
        teleporter.teleport_not_default(settings.bed_spawn)
        time.sleep(0.2)
        bot.render.enter_tekpod()
        tribelog.open()
        time.sleep(self.time)
        bot.render.leave_tekpod()
        
    def get_priority_level(self):
        return 1

    def get_requeue_delay(self):
        return 0  
