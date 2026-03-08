import settings
import time
import template
import logs.gachalogs as logs
import bot.render
import utils
from ASA.structures import bed , teleporter , inventory
from ASA.player import buffs , console , player_state , tribelog , player_inventory
from ASA.stations import custom_stations
from bot import config , deposit , gacha , iguanadon , pego , withdrawal
from crafting.ARB import megalab as megalab_crafting
from crafting.ARB import steam_forge
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

        # "delay" is the re-queue interval (mirrors pego behavior).
        # "initial_delay" is an optional one-time startup offset (defaults to 0 so it queues immediately).
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)

        self.deposit_height = deposit_height
        self.one_shot = False
    def execute(self):
        attempts_max = int(getattr(config, "sparkpowder_attempts", 3) or 3)

        for attempt in range(1, attempts_max + 1):
            meta = None
            try:
                player_state.check_state()

                # Gate by BOTH the global crafting toggle and the sparkpowder feature toggle.
                if not getattr(settings, "crafting", False) or not getattr(settings, "sparkpowder_enabled", False):
                    logs.logger.info("[Sparkpowder] Disabled in settings (crafting and/or sparkpowder_enabled); skipping.")
                    return

                meta = custom_stations.get_station_metadata(self.teleporter_name)
                logs.logger.info(f"[Sparkpowder] Teleport -> Station: {self.teleporter_name}")
                teleporter.teleport_not_default(meta)
                time.sleep(0.5 * getattr(settings, "lag_offset", 1.0))

                # Ensure pitch starts neutral
                utils.pitch_zero()
                time.sleep(0.15 * settings.lag_offset)

                # Stations face the common yaw; Megalab.
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

                if not template.template_await_true(template.check_template, 1, "megalab", 0.7):
                    raise RuntimeError("Unable to open Megalab inventory (template not detected).")

                ok = megalab_crafting.run_sparkpowder_cycle(
                    craft_seconds=getattr(settings, "sparkpowder_craft_seconds", 2.0)
                )
                if not ok:
                    raise RuntimeError("Sparkpowder craft cycle failed (megalab helper returned False).")

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
                return

            except Exception as e:
                logs.logger.warning(f"[Sparkpowder] Attempt {attempt}/{attempts_max} failed: {e}")

                # Best-effort cleanup so the next attempt starts in a sane state.
                try:
                    inventory.close()
                except Exception:
                    pass
                try:
                    if meta is not None:
                        utils.pitch_zero()
                        utils.set_yaw(meta.yaw)
                except Exception:
                    pass

                time.sleep(0.75 * getattr(settings, "lag_offset", 1.0))

        logs.logger.error(f"[Sparkpowder] Failed after {attempts_max} attempts; giving up until next schedule.")


    def get_priority_level(self):
        # After pego (2), before gacha (4)
        return 3

    def get_requeue_delay(self):
        # Mirror pego: re-queue interval comes from this station's delay (json_files/sparkpowder.json).
        if self.delay and self.delay > 0:
            return self.delay
        return getattr(settings, "sparkpowder_requeue_delay", 1800)



class charcoal_station(base_task):

    def __init__(
        self,
        name,
        teleporter_name,
        delay=0,
        station_yaw=0.0,
        deposit_teleporter="dedi_deposit_charcoal",
        deposit_yaw=0.0,
        height=3,
        wood_withdraw_teleporter_1="wood_dedi_station_1",
        wood_withdraw_teleporter_2="wood_dedi_station_2",
        initial_delay=0,
    ):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name

        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)
        self.station_yaw = float(station_yaw or 0.0)

        self.deposit_teleporter = deposit_teleporter
        self.deposit_yaw = float(deposit_yaw or 0.0)
        self.height = int(height or 3)

        self.wood_withdraw_teleporter_1 = wood_withdraw_teleporter_1
        self.wood_withdraw_teleporter_2 = wood_withdraw_teleporter_2

        self.one_shot = False

    def execute(self):
        attempts_max = int(getattr(config, "charcoal_attempts", 3) or 3)

        for attempt in range(1, attempts_max + 1):
            meta = None
            try:
                player_state.check_state()

                if not getattr(settings, "crafting", False) or not getattr(settings, "charcoal_enabled", False):
                    logs.logger.info("[Charcoal] Disabled in settings (crafting and/or charcoal_enabled); skipping.")
                    return

                meta = custom_stations.get_station_metadata(self.teleporter_name)
                logs.logger.info(f"[Charcoal] Teleport -> Station: {self.teleporter_name}")
                teleporter.teleport_not_default(meta)
                time.sleep(0.7 * getattr(settings, "lag_offset", 1.0))

                # Face the forge yaw for this station
                utils.pitch_zero()
                utils.set_yaw(self.station_yaw if self.station_yaw is not None else meta.yaw)
                time.sleep(0.3 * getattr(settings, "lag_offset", 1.0))

                # Take charcoal only (filter prevents ingots from being pulled)
                steam_forge.take_all_charcoal_only()
                time.sleep(0.4 * getattr(settings, "lag_offset", 1.0))

                # Drop off charcoal
                logs.logger.info(f"[Charcoal] Teleport -> Dropoff: {self.deposit_teleporter}")
                drop_meta = custom_stations.get_station_metadata(self.deposit_teleporter)
                teleporter.teleport_not_default(drop_meta)
                time.sleep(0.7 * getattr(settings, "lag_offset", 1.0))

                utils.pitch_zero()
                utils.set_yaw(self.deposit_yaw if self.deposit_yaw is not None else drop_meta.yaw)
                time.sleep(0.3 * getattr(settings, "lag_offset", 1.0))

                deposit.dedi_deposit_charcoal(self.height)
                time.sleep(0.4 * getattr(settings, "lag_offset", 1.0))

                # Withdraw wood from two wood dedis (placeholders for now)
                logs.logger.info(f"[Charcoal] Teleport -> Wood Withdraw 1: {self.wood_withdraw_teleporter_1}")
                w1 = custom_stations.get_station_metadata(self.wood_withdraw_teleporter_1)
                teleporter.teleport_not_default(w1)
                time.sleep(0.7 * getattr(settings, "lag_offset", 1.0))
                withdrawal.wood_dedi_withdraw_placeholder(self.wood_withdraw_teleporter_1)

                logs.logger.info(f"[Charcoal] Teleport -> Wood Withdraw 2: {self.wood_withdraw_teleporter_2}")
                w2 = custom_stations.get_station_metadata(self.wood_withdraw_teleporter_2)
                teleporter.teleport_not_default(w2)
                time.sleep(0.7 * getattr(settings, "lag_offset", 1.0))
                withdrawal.wood_dedi_withdraw_placeholder(self.wood_withdraw_teleporter_2)

                # Return to station
                logs.logger.info(f"[Charcoal] Teleport -> Station (return): {self.teleporter_name}")
                teleporter.teleport_not_default(meta)
                time.sleep(0.8 * getattr(settings, "lag_offset", 1.0))

                utils.pitch_zero()
                utils.set_yaw(self.station_yaw if self.station_yaw is not None else meta.yaw)
                time.sleep(0.3 * getattr(settings, "lag_offset", 1.0))

                # Withdraw element (3) from the element dedi adjacent to the station
                withdrawal.element_withdraw_at_charcoal_station()

                # Transfer wood+element into forge
                steam_forge.transfer_all_to_forge()

                # Turn on forge ONLY if we see the Turn On prompt
                turned_on = steam_forge.try_turn_on()
                if turned_on:
                    logs.logger.info("[Charcoal] Forge turned on.")
                else:
                    logs.logger.info("[Charcoal] Forge not turned on (already on or not ready).")

                # Restore station yaw
                utils.pitch_zero()
                utils.set_yaw(self.station_yaw if self.station_yaw is not None else meta.yaw)
                return

            except Exception as e:
                logs.logger.warning(f"[Charcoal] Attempt {attempt}/{attempts_max} failed: {e}")
                try:
                    from ASA.structures import inventory
                    inventory.close()
                except Exception:
                    pass
                try:
                    if meta is not None:
                        utils.pitch_zero()
                        utils.set_yaw(self.station_yaw if self.station_yaw is not None else meta.yaw)
                except Exception:
                    pass

                time.sleep(0.75 * getattr(settings, "lag_offset", 1.0))

        logs.logger.error(f"[Charcoal] Failed after {attempts_max} attempts; giving up until next schedule.")

    def get_priority_level(self):
        # Same overall priority as sparkpowder/gunpowder; ordering is handled by initial_delay offsets.
        return 3

    def get_requeue_delay(self):
        if self.delay and self.delay > 0:
            # Add a small offset so charcoal schedules after sparkpowder but before gunpowder when aligned.
            return self.delay + 0.05
        return getattr(settings, "charcoal_requeue_delay", 1800)

class gunpowder_station(base_task):

    def __init__(self, name, teleporter_name, delay=0, deposit_height=3, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name

        # "delay" is the re-queue interval (mirrors pego behavior).
        # "initial_delay" is an optional one-time startup offset (defaults to 0 so it queues immediately).
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)

        self.deposit_height = deposit_height
        self.one_shot = False
    def execute(self):
        attempts_max = int(getattr(config, "gunpowder_attempts", 3) or 3)

        for attempt in range(1, attempts_max + 1):
            meta = None
            try:
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
                look_deg = abs(float(getattr(settings, "gunpowder_look_degrees", 25.0)))
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

                if not template.template_await_true(template.check_template, 1, "megalab", 0.7):
                    raise RuntimeError("Unable to open Megalab inventory (template not detected).")

                ok = megalab_crafting.run_gunpowder_cycle(
                    craft_seconds=getattr(settings, "gunpowder_craft_seconds", 2.0)
                )
                if not ok:
                    raise RuntimeError("Gunpowder craft cycle failed (megalab helper returned False).")

                inventory.close()
                time.sleep(0.25 * settings.lag_offset)

                # Return pitch back to neutral (we looked down earlier)
                utils.turn_up(look_deg)
                time.sleep(0.25 * settings.lag_offset)

                # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
                utils.pitch_zero()
                utils.set_yaw(meta.yaw)

                turn_deg_raw = getattr(settings, "gunpowder_turn_degrees", 180.0)
                turn_deg = float(turn_deg_raw) if turn_deg_raw is not None else 0.0
                if abs(turn_deg) > 0.1:
                    utils.turn_right(abs(turn_deg))
                    time.sleep(0.25 * settings.lag_offset)

                # Deposit to the station's dedicated storage boxes
                deposit.dedi_deposit_custom_2(self.deposit_height)
                time.sleep(0.25 * settings.lag_offset)

                # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
                utils.pitch_zero()
                utils.set_yaw(meta.yaw)
                return

            except Exception as e:
                logs.logger.warning(f"[Gunpowder] Attempt {attempt}/{attempts_max} failed: {e}")

                # Best-effort cleanup so the next attempt starts in a sane state.
                try:
                    inventory.close()
                except Exception:
                    pass
                try:
                    if meta is not None:
                        utils.pitch_zero()
                        utils.set_yaw(meta.yaw)
                except Exception:
                    pass

                time.sleep(0.75 * getattr(settings, "lag_offset", 1.0))

        logs.logger.error(f"[Gunpowder] Failed after {attempts_max} attempts; giving up until next schedule.")


    def get_priority_level(self):
        # Same priority tier as sparkpowder (between pego and gacha)
        return 3

    def get_requeue_delay(self):
        # Mirror pego: re-queue interval comes from this station's delay (json_files/gunpowder.json).
        if self.delay and self.delay > 0:
            return self.delay
        return getattr(settings, "gunpowder_requeue_delay", 1800)


class decay_prevention_station(base_task):

    def __init__(self, name, teleporter_name, delay=0, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name

        # "delay" is the re-queue interval (mirrors pego behavior).
        # "initial_delay" is an optional one-time startup offset (defaults to 0 so it queues immediately).
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)

        self.one_shot = False
    def execute(self):
        attempts_max = int(getattr(config, "decay_prevention_attempts", 3) or 3)

        for attempt in range(1, attempts_max + 1):
            meta = None
            try:
                player_state.check_state()

                if not getattr(settings, "decay_prevention_enabled", False):
                    logs.logger.info("[DecayPrevention] Disabled in settings; skipping.")
                    return

                meta = custom_stations.get_station_metadata(self.teleporter_name)
                logs.logger.info(f"[DecayPrevention] Teleport -> Station: {self.teleporter_name}")
                teleporter.teleport_not_default(meta)

                # Allow the world to render before we do anything else.
                post_tp = float(getattr(settings, "decay_prevention_post_tp_delay", 15.0) or 0.0)
                time.sleep(post_tp * getattr(settings, "lag_offset", 1.0))

                # Keep tribe log open long enough to fully render / stream the area.
                tribelog.open()
                if not tribelog.is_open():
                    raise RuntimeError("Tribe log did not open (template not detected).")

                time.sleep(float(getattr(settings, "decay_prevention_open_seconds", 20.0) or 20.0))

                tribelog.close()
                if tribelog.is_open():
                    raise RuntimeError("Tribe log did not close (still detected).")

                # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
                utils.pitch_zero()
                utils.set_yaw(meta.yaw)
                return

            except Exception as e:
                logs.logger.warning(f"[DecayPrevention] Attempt {attempt}/{attempts_max} failed: {e}")

                # Best-effort cleanup so the next attempt starts in a sane state.
                try:
                    tribelog.close()
                except Exception:
                    pass
                try:
                    if meta is not None:
                        utils.pitch_zero()
                        utils.set_yaw(meta.yaw)
                except Exception:
                    pass

                time.sleep(1.0 * getattr(settings, "lag_offset", 1.0))

        logs.logger.error(f"[DecayPrevention] Failed after {attempts_max} attempts; giving up until next schedule.")


    def get_priority_level(self):
        # Run alongside crafting (3) so it won't be starved by large gacha queues.
        # Pego (2) still stays above it.
        return 3

    def get_requeue_delay(self):
        if self.delay and self.delay > 0:
            return self.delay
        return getattr(settings, "decay_prevention_requeue_delay", 21600)



class decay_prevention_bed_route(base_task):
    """Bed/Tekpod-only decay prevention route.

    Walks a configured list of Tekpod bed names (fast travel) and, at each stop:
      - waits for render
      - opens tribe log for a configurable duration
    Travel between stops is done ONLY via bed/tekpod Fast Travel (no teleporters).
    """

    def __init__(self, name: str, stops: list[dict], delay: float = 0, initial_delay: float = 0):
        super().__init__()
        self.name = name or "DecayPreventionBeds"
        self.stops = stops or []
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)

    def execute(self):
        attempts_max = int(getattr(config, "decay_prevention_beds_attempts", 3) or 3)

        for attempt in range(1, attempts_max + 1):
            try:
                player_state.check_state()

                if not getattr(settings, "decay_prevention_beds_enabled", False):
                    logs.logger.info("[DecayPreventionBeds] Disabled in settings; skipping.")
                    return

                if not self.stops:
                    logs.logger.error("[DecayPreventionBeds] No stops configured (decay_prevention_beds.json is empty).")
                    return

                lag = float(getattr(settings, "lag_offset", 1.0) or 1.0)
                post_spawn_default = float(getattr(settings, "decay_beds_post_spawn_delay", 20.0) or 0.0)
                open_default = float(getattr(settings, "decay_beds_open_seconds", 10.0) or 10.0)
                pitch_down = float(getattr(settings, "decay_beds_pitch_down_degrees", 15.0) or 0.0)
                start_at_first = bool(getattr(settings, "decay_beds_start_at_first", True))
                loop_back = bool(getattr(settings, "decay_beds_loop_back_to_first", False))

                for idx, stop in enumerate(self.stops):
                    stop_name = stop.get("name") or stop.get("station") or stop.get("bed") or f"Stop_{idx+1}"
                    bed_name = stop.get("bed") or stop.get("bed_name") or stop.get("name")

                    if not bed_name:
                        logs.logger.warning(f"[DecayPreventionBeds] Invalid stop entry (missing bed): {stop}")
                        continue

                    # Optional per-stop yaw; if omitted, bed.open_fast_travel_screen falls back to settings.station_yaw.
                    yaw = stop.get("yaw", None)

                    # Travel to the stop (except first stop if we assume we already start there).
                    if idx == 0 and not start_at_first:
                        logs.logger.info(f"[DecayPreventionBeds] Starting at: {stop_name}")
                    else:
                        logs.logger.info(f"[DecayPreventionBeds] FastTravel -> {stop_name} ({bed_name})")
                        ok = bed.fast_travel_to(bed_name, yaw=yaw, pitch_down_degrees=pitch_down,
                                                attempts=int(getattr(settings, "decay_beds_fast_travel_attempts", 4) or 4))
                        if not ok:
                            raise RuntimeError(f"Fast travel failed for '{bed_name}'")

                    # Allow the world to render/stream before opening tribe logs.
                    post_spawn = float(stop.get("post_spawn_delay", post_spawn_default) or 0.0)
                    if post_spawn > 0:
                        time.sleep(post_spawn * lag)

                    tribelog.open()
                    if not tribelog.is_open():
                        raise RuntimeError("Tribe log did not open (template not detected).")

                    open_secs = float(stop.get("open_seconds", open_default) or open_default)
                    time.sleep(open_secs)

                    tribelog.close()
                    if tribelog.is_open():
                        raise RuntimeError("Tribe log did not close (still detected).")

                    # Restore yaw/pitch if provided so the next fast travel attempt starts sane.
                    utils.pitch_zero()
                    if yaw is not None:
                        try:
                            utils.set_yaw(float(yaw))
                        except Exception:
                            pass

                    inter_delay = float(stop.get("inter_delay", getattr(settings, "decay_beds_inter_station_delay", 0.0)) or 0.0)
                    if inter_delay > 0:
                        time.sleep(inter_delay * lag)

                # Optional: loop back to the first stop at the end of a route pass.
                if loop_back and self.stops:
                    first = self.stops[0]
                    first_bed = first.get("bed") or first.get("bed_name") or first.get("name")
                    first_yaw = first.get("yaw", None)
                    if first_bed:
                        logs.logger.info(f"[DecayPreventionBeds] LoopBack -> {first_bed}")
                        bed.fast_travel_to(first_bed, yaw=first_yaw, pitch_down_degrees=pitch_down,
                                           attempts=int(getattr(settings, "decay_beds_fast_travel_attempts", 4) or 4))

                return

            except Exception as e:
                logs.logger.warning(f"[DecayPreventionBeds] Attempt {attempt}/{attempts_max} failed: {e}")

                # Best-effort cleanup so the next attempt starts in a sane state.
                try:
                    tribelog.close()
                except Exception:
                    pass
                try:
                    utils.pitch_zero()
                except Exception:
                    pass
                time.sleep(1.0 * getattr(settings, "lag_offset", 1.0))

        logs.logger.error(f"[DecayPreventionBeds] Failed after {attempts_max} attempts; giving up until next schedule.")

    def get_priority_level(self):
        # Same lane as decay_prevention_station (3).
        return 3

    def get_requeue_delay(self):
        if self.delay and self.delay > 0:
            return self.delay
        return getattr(settings, "decay_prevention_beds_requeue_delay", 21600)


class render_station(base_task):

    def __init__(self):
        super().__init__()
        self.name = settings.bed_spawn

    def execute(self):
            # Render station is a home/idle location.
            # Only run the full render workflow when render_flag is set elsewhere (e.g., via command).
            player_state.check_state()
            self.record_execution()

            if not settings.enable_render:
                return

            if not station.render_flag:
                # Idle: stay in tekpod and do not teleport/spawn.
                try:
                    player_state.enter_tekpod()
                except Exception:
                    pass
                time.sleep(0.5 * settings.lag_offset)
                return

            # render_flag True -> run the render workflow
            player_state.exit_tekpod()
            teleporters.teleport_not_default(self.bed_spawn)
            time.sleep(1.0 * settings.lag_offset)
            player_state.enter_tekpod()
            station.render_flag = False

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
