from __future__ import annotations
import time
import os
import json
import logging
from datetime import datetime, timedelta

import settings

# try imports across possible layouts
try:
    from logs import gachalogs as logs
except Exception:
    import gachalogs as logs  # type: ignore

# Ensure logs directory exists for external watchers
os.makedirs("logs", exist_ok=True)

def _load_station_names():
    # Prefer custom_stations if present
    try:
        import custom_stations
        if hasattr(custom_stations, "get_custom_stations"):
            data = custom_stations.get_custom_stations()
            names = [s.get("name") if isinstance(s, dict) else getattr(s, "name", None) for s in data]
            return [n for n in names if n]
    except Exception as e:
        logs.logger.debug(f"custom_stations list fallback due to: {e}")
    # Fallback: read stations.json assuming list of objects with "name"
    try:
        with open(os.path.join("stations.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        names = [x.get("name") for x in data if isinstance(x, dict) and x.get("name")]
        return names
    except Exception as e:
        logs.logger.error(f"Failed to load stations.json: {e}")
        return []

# Abstractions that call your existing helpers without re-implementing logic

def _leave_tekpod():
    # Respect existing behavior. Try multiple known entry points.
    try:
        import render as _r
        if hasattr(_r, "leave_tekpod"):
            logs.logger.debug("leave_tekpod via render.leave_tekpod")
            _r.leave_tekpod()
            return
    except Exception as e:
        logs.logger.debug(f"render.leave_tekpod failed: {e}")
    try:
        import utils
        if hasattr(utils, "leave_tekpod"):
            logs.logger.debug("leave_tekpod via utils.leave_tekpod")
            utils.leave_tekpod()
            return
    except Exception as e:
        logs.logger.debug(f"utils.leave_tekpod failed: {e}")
    logs.logger.info("leave_tekpod helper not found; continuing without explicit exit")

def _teleport_to(name: str):
    # Use metadata + teleporter helper if available
    meta = None
    try:
        import custom_stations
        meta = custom_stations.get_station_metadata(name)
    except Exception:
        pass
    try:
        import teleporter
        if hasattr(teleporter, "teleport_not_default") and meta is not None:
            logs.logger.debug(f"teleport_not_default -> {getattr(meta,'name',name)}")
            return teleporter.teleport_not_default(meta)
        if hasattr(teleporter, "teleport"):
            logs.logger.debug(f"teleport -> {name}")
            return teleporter.teleport(name)
    except Exception as e:
        logs.logger.error(f"teleport helper failed for '{name}': {e}")
        raise

def _open_tribe_logs():
    try:
        import tribelog
        if hasattr(tribelog, "open"):
            tribelog.open()
            return
    except Exception as e:
        logs.logger.error(f"tribelog.open failed: {e}")
        raise

def _close_tribe_logs():
    try:
        import tribelog
        if hasattr(tribelog, "close"):
            tribelog.close()
    except Exception as e:
        logs.logger.debug(f"tribelog.close failed: {e}")

def _return_to_bed(name: str):
    try:
        _teleport_to(name)
    except Exception as e:
        logs.logger.error(f"return_to_bed failed: {e}")

class RenderSweepTask:
    def __init__(self, stations, priority: int):
        self.name = "render_sweep"
        self.priority = priority
        self._run_at = None
        self._stations = list(stations)

    def run(self):
        logs.logger.info("RenderSweep: start")
        _leave_tekpod()
        dwell = int(getattr(settings, "RENDER_DWELL_SECONDS", 30))
        lag = float(getattr(settings, "lag_offset", 1.0))

        for s in self._stations:
            logs.logger.info(f"RenderSweep: teleport -> {s}")
            _teleport_to(s)
            logs.logger.debug(f"RenderSweep: open tribelog for {dwell}s")
            _open_tribe_logs()
            time.sleep(dwell + max(0.0, 0.25 * lag))
            _close_tribe_logs()

        bed_name = str(getattr(settings, "RENDER_BED_NAME", getattr(settings, "bed_spawn", "renderbed")))
        logs.logger.info(f"RenderSweep: return -> {bed_name}")
        _return_to_bed(bed_name)
        logs.logger.info("RenderSweep: done")

    def on_complete(self, manager):
        minutes = int(getattr(settings, "RENDER_REPEAT_MINUTES", 60))
        delay = max(60, minutes * 60)  # minimum 60s
        manager.enqueue_delayed(RenderSweepTask(self._stations, self.priority), delay, priority=self.priority)

def build_render_task():
    if not bool(getattr(settings, "RENDER_ENABLED", True)):
        return None
    stations = _load_station_names()
    bed_name = str(getattr(settings, "RENDER_BED_NAME", getattr(settings, "bed_spawn", "renderbed")))
    stations = [s for s in stations if s and s != bed_name]
    prio = int(getattr(settings, "RENDER_PRIORITY", 9999))
    if not stations:
        logs.logger.warning("RenderSweep: no stations found")
    return RenderSweepTask(stations, prio)
