import settings
import time
import template
import logs.gachalogs as logs
import windows
from bot import config, deposit, gacha, iguanadon, pego
from crafting.ARB import megalab as megalab_crafting

from ASA.player import player_state, teleporter, inventory, tribelog, buffs
from ASA.player import utils
from bot import custom_stations
from bot.custom_stations import (
    gacha_station_metadata,
    pego_station_metadata,
    iguanadon_station_metadata,
    sparkpowder_station_metadata,
    gunpowder_station_metadata,
    decay_prevention_station_metadata,
    render_station_metadata,
)

# A "one shot" task runs only once and is not re-queued.
one_shot_names = {
    "collect",
    "grinder",
    "drop_off",
    "watchdog_render_task",
}

# --------------------------------------------------------------------------------------
# Base Task
# --------------------------------------------------------------------------------------
class base_task:
    def __init__(self):
        self.delay = 0
        self.one_shot = False
        self.initial_delay = 0

    def execute(self):
        raise NotImplementedError()

    def get_priority_level(self):
        return 0

    def get_requeue_delay(self):
        # If a task has an "initial_delay" it is only applied the first time
        # the task is queued; after that, we fall back to .delay.
        return self.delay

    def is_one_shot(self):
        return self.one_shot


# --------------------------------------------------------------------------------------
# Gacha
# --------------------------------------------------------------------------------------
class gacha_station(base_task):
    def __init__(self, name, teleporter_name, delay=0, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)
        self.one_shot = False

    def execute(self):
        player_state.check_state()

        if not getattr(settings, "gacha_enabled", True):
            logs.logger.info("[Gacha] Disabled in settings; skipping.")
            return

        meta = custom_stations.get_station_metadata(self.teleporter_name)
        logs.logger.info(f"[Gacha] Teleport -> Station: {self.teleporter_name}")
        teleporter.teleport_not_default(meta)
        time.sleep(0.5 * getattr(settings, "lag_offset", 1.0))

        # Align camera to station-facing yaw/pitch baseline
        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

        # Run gacha logic (existing behavior)
        gacha.gacha_station(meta)

        # Restore yaw/pitch
        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

    def get_priority_level(self):
        return 2


# --------------------------------------------------------------------------------------
# Pego
# --------------------------------------------------------------------------------------
class pego_station(base_task):
    def __init__(self, name, teleporter_name, delay=0, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)
        self.one_shot = False

    def execute(self):
        player_state.check_state()

        if not getattr(settings, "pego_enabled", True):
            logs.logger.info("[Pego] Disabled in settings; skipping.")
            return

        meta = custom_stations.get_station_metadata(self.teleporter_name)
        logs.logger.info(f"[Pego] Teleport -> Station: {self.teleporter_name}")
        teleporter.teleport_not_default(meta)
        time.sleep(0.5 * getattr(settings, "lag_offset", 1.0))

        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

        pego.pego_station(meta)

        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

    def get_priority_level(self):
        return 2


# --------------------------------------------------------------------------------------
# Iguana (if applicable)
# --------------------------------------------------------------------------------------
class iguanadon_station(base_task):
    def __init__(self, name, teleporter_name, delay=0, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)
        self.one_shot = False

    def execute(self):
        player_state.check_state()

        if not getattr(settings, "iguanadon_enabled", False):
            logs.logger.info("[Iguanadon] Disabled in settings; skipping.")
            return

        meta = custom_stations.get_station_metadata(self.teleporter_name)
        logs.logger.info(f"[Iguanadon] Teleport -> Station: {self.teleporter_name}")
        teleporter.teleport_not_default(meta)
        time.sleep(0.5 * getattr(settings, "lag_offset", 1.0))

        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

        iguanadon.iguanadon_station(meta)

        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

    def get_priority_level(self):
        return 2


# --------------------------------------------------------------------------------------
# Sparkpowder (Megalab)
# --------------------------------------------------------------------------------------
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
        # Gate by BOTH the global crafting toggle and the sparkpowder feature toggle.
        if not getattr(settings, "crafting", False) or not getattr(settings, "sparkpowder_enabled", False):
            logs.logger.info("[Sparkpowder] Disabled in settings (crafting and/or sparkpowder_enabled); skipping.")
            return

        attempts_max = int(getattr(config, "sparkpowder_attempts", 3) or 3)
        lag = float(getattr(settings, "lag_offset", 1.0) or 1.0)

        for attempt in range(1, attempts_max + 1):
            meta = None
            try:
                player_state.check_state()

                meta = custom_stations.get_station_metadata(self.teleporter_name)
                logs.logger.info(f"[Sparkpowder] Attempt {attempt}/{attempts_max} -> Station: {self.teleporter_name}")
                teleporter.teleport_not_default(meta)
                time.sleep(0.5 * lag)

                # Ensure pitch starts neutral
                utils.pitch_zero()
                time.sleep(0.15 * lag)

                # Stations face the common yaw; Megalab.
                utils.turn_right(getattr(settings, "sparkpowder_turn_degrees", 180))
                time.sleep(0.25 * lag)

                # Look up to face the Megalab
                utils.turn_up(getattr(settings, "sparkpowder_look_degrees", 45))
                time.sleep(0.25 * lag)

                # Open Megalab inventory, transfer existing sparkpowder, then craft more
                inventory.open()

                # One internal "open retry" inside each outer attempt
                if not template.template_await_true(template.check_template, 1, "megalab", 0.7):
                    logs.logger.warning("[Sparkpowder] Megalab template not detected after open; retrying once")
                    inventory.close()
                    time.sleep(0.25 * lag)
                    player_state.check_state()
                    inventory.open()

                if not template.template_await_true(template.check_template, 1, "megalab", 0.7):
                    inventory.close()
                    raise RuntimeError("Unable to open Megalab inventory (template not detected)")

                ok = megalab_crafting.run_sparkpowder_cycle(
                    craft_seconds=getattr(settings, "sparkpowder_craft_seconds", 2.0)
                )
                inventory.close()
                time.sleep(0.25 * lag)

                if not ok:
                    raise RuntimeError("Megalab sparkpowder cycle returned False")

                # Return pitch back to neutral (we looked up earlier)
                utils.turn_down(getattr(settings, "sparkpowder_look_degrees", 45))
                time.sleep(0.25 * lag)

                # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
                utils.pitch_zero()
                utils.set_yaw(meta.yaw)

                # Deposit to the station's dedicated storage boxes
                deposit.dedi_deposit_custom_1(self.deposit_height)
                time.sleep(0.25 * lag)

                # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
                utils.pitch_zero()
                utils.set_yaw(meta.yaw)

                logs.logger.info("[Sparkpowder] Completed successfully.")
                return

            except RuntimeError as e:
                logs.logger.warning(f"[Sparkpowder] Attempt {attempt}/{attempts_max} failed: {e}")
            except Exception as e:
                logs.logger.exception(f"[Sparkpowder] Attempt {attempt}/{attempts_max} crashed: {e}")
            finally:
                # Best-effort cleanup so the next attempt starts clean
                try:
                    inventory.close()
                except Exception:
                    pass
                try:
                    utils.pitch_zero()
                except Exception:
                    pass
                try:
                    if meta is not None:
                        utils.set_yaw(meta.yaw)
                except Exception:
                    pass

            if attempt < attempts_max:
                time.sleep(0.8 * lag)

        logs.logger.error(f"[Sparkpowder] Failed after {attempts_max} attempts.")

    def get_priority_level(self):
        return 3


# --------------------------------------------------------------------------------------
# Gunpowder (Megalab)
# --------------------------------------------------------------------------------------
class gunpowder_station(base_task):
    def __init__(self, name, teleporter_name, delay=0, deposit_height=3, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name

        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)

        self.deposit_height = deposit_height
        self.one_shot = False

    def execute(self):
        # Gate by BOTH the global crafting toggle and the gunpowder feature toggle.
        if not getattr(settings, "crafting", False) or not getattr(settings, "gunpowder_enabled", False):
            logs.logger.info("[Gunpowder] Disabled in settings (crafting and/or gunpowder_enabled); skipping.")
            return

        attempts_max = int(getattr(config, "gunpowder_attempts", 3) or 3)
        lag = float(getattr(settings, "lag_offset", 1.0) or 1.0)

        for attempt in range(1, attempts_max + 1):
            meta = None
            try:
                player_state.check_state()

                meta = custom_stations.get_station_metadata(self.teleporter_name)
                logs.logger.info(f"[Gunpowder] Attempt {attempt}/{attempts_max} -> Station: {self.teleporter_name}")
                teleporter.teleport_not_default(meta)
                time.sleep(0.5 * lag)

                # Ensure pitch starts neutral before we do our look-up/down offsets
                utils.pitch_zero()
                time.sleep(0.15 * lag)

                # Look down to face the Megalab
                look_deg = abs(float(getattr(settings, "gunpowder_look_degrees", 25.0)))
                utils.turn_down(look_deg)
                time.sleep(0.25 * lag)

                # Open Megalab inventory, transfer existing gunpowder, then craft more
                inventory.open()

                # One internal "open retry" inside each outer attempt
                if not template.template_await_true(template.check_template, 1, "megalab", 0.7):
                    logs.logger.warning("[Gunpowder] Megalab template not detected after open; retrying once")
                    inventory.close()
                    time.sleep(0.25 * lag)
                    player_state.check_state()
                    inventory.open()

                if not template.template_await_true(template.check_template, 1, "megalab", 0.7):
                    inventory.close()
                    raise RuntimeError("Unable to open Megalab inventory (template not detected)")

                ok = megalab_crafting.run_gunpowder_cycle(
                    craft_seconds=getattr(settings, "gunpowder_craft_seconds", 2.0)
                )
                inventory.close()
                time.sleep(0.25 * lag)

                if not ok:
                    raise RuntimeError("Megalab gunpowder cycle returned False")

                # Return pitch back to neutral (we looked down earlier)
                utils.turn_up(look_deg)
                time.sleep(0.25 * lag)

                # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
                utils.pitch_zero()
                utils.set_yaw(meta.yaw)

                # Turn to face deposit boxes if configured
                turn_deg_raw = getattr(settings, "gunpowder_turn_degrees", 180.0)
                try:
                    turn_deg = float(turn_deg_raw)
                except Exception:
                    turn_deg = 0.0
                if abs(turn_deg) > 0.1:
                    utils.turn_right(abs(turn_deg))
                    time.sleep(0.25 * lag)

                # Deposit to the station's dedicated storage boxes
                deposit.dedi_deposit_custom_2(self.deposit_height)
                time.sleep(0.25 * lag)

                # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
                utils.pitch_zero()
                utils.set_yaw(meta.yaw)

                logs.logger.info("[Gunpowder] Completed successfully.")
                return

            except RuntimeError as e:
                logs.logger.warning(f"[Gunpowder] Attempt {attempt}/{attempts_max} failed: {e}")
            except Exception as e:
                logs.logger.exception(f"[Gunpowder] Attempt {attempt}/{attempts_max} crashed: {e}")
            finally:
                try:
                    inventory.close()
                except Exception:
                    pass
                try:
                    utils.pitch_zero()
                except Exception:
                    pass
                try:
                    if meta is not None:
                        utils.set_yaw(meta.yaw)
                except Exception:
                    pass

            if attempt < attempts_max:
                time.sleep(0.8 * lag)

        logs.logger.error(f"[Gunpowder] Failed after {attempts_max} attempts.")

    def get_priority_level(self):
        return 3


# --------------------------------------------------------------------------------------
# Decay Prevention
# --------------------------------------------------------------------------------------
class decay_prevention_station(base_task):
    def __init__(self, name, teleporter_name, delay=0, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)
        self.one_shot = False

    def execute(self):
        if not getattr(settings, "decay_prevention_enabled", False):
            logs.logger.info("[DecayPrevention] Disabled in settings; skipping.")
            return

        attempts_max = int(getattr(config, "decay_prevention_attempts", 3) or 3)
        lag = float(getattr(settings, "lag_offset", 1.0) or 1.0)

        for attempt in range(1, attempts_max + 1):
            meta = None
            try:
                player_state.check_state()

                meta = custom_stations.get_station_metadata(self.teleporter_name)
                logs.logger.info(f"[DecayPrevention] Attempt {attempt}/{attempts_max} -> Station: {self.teleporter_name}")
                teleporter.teleport_not_default(meta)

                # Allow the world to render before we do anything else.
                post_tp = float(getattr(settings, "decay_prevention_post_tp_delay", 15.0) or 0.0)
                time.sleep(post_tp * lag)

                tribelog.open()
                time.sleep(0.2 * lag)

                if not tribelog.is_open():
                    raise RuntimeError("Tribelog did not open (template not detected)")

                # Keep tribe log open long enough to fully render / stream the area.
                hold = float(getattr(settings, "decay_prevention_open_seconds", 20.0) or 20.0)
                time.sleep(hold * lag)

                tribelog.close()

                # Restore station-facing yaw + neutral pitch so the next task doesn't start misaligned
                utils.pitch_zero()
                utils.set_yaw(meta.yaw)

                logs.logger.info("[DecayPrevention] Completed successfully.")
                return

            except RuntimeError as e:
                logs.logger.warning(f"[DecayPrevention] Attempt {attempt}/{attempts_max} failed: {e}")
            except Exception as e:
                logs.logger.exception(f"[DecayPrevention] Attempt {attempt}/{attempts_max} crashed: {e}")
            finally:
                try:
                    tribelog.close()
                except Exception:
                    pass
                try:
                    utils.pitch_zero()
                except Exception:
                    pass
                try:
                    if meta is not None:
                        utils.set_yaw(meta.yaw)
                except Exception:
                    pass

            if attempt < attempts_max:
                time.sleep(0.8 * lag)

        logs.logger.error(f"[DecayPrevention] Failed after {attempts_max} attempts.")

    def get_priority_level(self):
        return 4


# --------------------------------------------------------------------------------------
# Render Station (existing)
# --------------------------------------------------------------------------------------
class render_station(base_task):
    def __init__(self, name, teleporter_name, delay=0, initial_delay=0):
        super().__init__()
        self.name = name
        self.teleporter_name = teleporter_name
        self.delay = float(delay or 0)
        self.initial_delay = float(initial_delay or 0)
        self.one_shot = False

    def execute(self):
        player_state.check_state()

        if not getattr(settings, "render_enabled", False):
            logs.logger.info("[Render] Disabled in settings; skipping.")
            return

        meta = custom_stations.get_station_metadata(self.teleporter_name)
        logs.logger.info(f"[Render] Teleport -> Station: {self.teleporter_name}")
        teleporter.teleport_not_default(meta)

        time.sleep(float(getattr(settings, "render_post_tp_delay", 10.0) or 10.0) * getattr(settings, "lag_offset", 1.0))

        # Render task is game-specific; keep existing behavior if present
        # (The watchdog task manages “render-only” stabilization)
        try:
            from bot import render_logic
            render_logic.run_render(meta)
        except Exception:
            logs.logger.exception("[Render] render_logic failed")

        utils.pitch_zero()
        utils.set_yaw(meta.yaw)

    def get_priority_level(self):
        return 3
