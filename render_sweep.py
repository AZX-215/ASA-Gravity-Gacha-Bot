# render_sweep.py
from __future__ import annotations
from pathlib import Path
import sys
import importlib, importlib.util
import json
import time
from datetime import datetime, timedelta
from typing import List

import settings

try:
    from logs import gachalogs as logs
except Exception:
    import gachalogs as logs  # type: ignore

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

def _import_module(name: str):
    """Import module by name, else load from file next to this script."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        p = BASE_DIR / f"{name}.py"
        if p.exists():
            spec = importlib.util.spec_from_file_location(name, str(p))
            mod = importlib.util.module_from_spec(spec)  # type: ignore
            assert spec and spec.loader
            spec.loader.exec_module(mod)  # type: ignore
            sys.modules[name] = mod
            return mod
        raise

def _load_station_names() -> List[str]:
    # custom_stations.get_custom_stations() -> list of dicts with "name"
    try:
        cs = _import_module("custom_stations")
        if hasattr(cs, "get_custom_stations"):
            data = cs.get_custom_stations()
            if isinstance(data, list) and data:
                names = [x.get("name") for x in data if isinstance(x, dict) and x.get("name")]
                if names:
                    return names
    except Exception as e:
        logs.logger.debug(f"_load_station_names: custom_stations list fallback due to: {e}")

    # stations.json in repo root or json_files/
    for p in (BASE_DIR / "stations.json", BASE_DIR / "json_files" / "stations.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                names = [d.get("name") for d in data if isinstance(d, dict) and d.get("name")]
            elif isinstance(data, dict):
                names = list(data.keys())
            else:
                names = []
            if names:
                return names
        except FileNotFoundError:
            continue
        except Exception as e:
            logs.logger.error(f"_load_station_names: Failed to load {p.name}: {e}")

    # stations.py with STATIONS = [ {'name': ...}, ... ]
    try:
        sp = _import_module("stations")
        if hasattr(sp, "STATIONS"):
            names = [s["name"] for s in getattr(sp, "STATIONS") if isinstance(s, dict) and s.get("name")]
            if names:
                return names
    except Exception as e:
        logs.logger.debug(f"_load_station_names: stations.py fallback failed: {e}")

    logs.logger.warning("RenderSweep: no stations found")
    return []

def _leave_tekpod():
    # prefer render.leave_tekpod()
    try:
        _r = _import_module("render")
        if hasattr(_r, "leave_tekpod"):
            logs.logger.debug("leave_tekpod via render.leave_tekpod")
            _r.leave_tekpod()
            return
    except Exception as e:
        logs.logger.debug(f"_leave_tekpod: render.leave_tekpod failed: {e}")

    # fallback to utils.leave_tekpod()
    try:
        utils = _import_module("utils")
        if hasattr(utils, "leave_tekpod"):
            logs.logger.debug("leave_tekpod via utils.leave_tekpod")
            utils.leave_tekpod()
            return
    except Exception as e:
        logs.logger.debug(f"_leave_tekpod: utils.leave_tekpod failed: {e}")

    logs.logger.info("leave_tekpod helper not found; continuing without explicit exit")

def _teleport_to(name: str):
    # obtain metadata if available
    meta = None
    try:
        cs = _import_module("custom_stations")
        if hasattr(cs, "get_station_metadata"):
            meta = cs.get_station_metadata(name)
    except Exception:
        meta = None

    try:
        tp = _import_module("teleporter")
        if meta is not None and hasattr(tp, "teleport_not_default"):
            return tp.teleport_not_default(meta)
        if hasattr(tp, "teleport"):
            return tp.teleport(name)
        raise RuntimeError("teleporter has no teleport function")
    except Exception as e:
        logs.logger.error(f"_teleport_to: teleport helper failed for '{name}': {e}")
        raise

def _open_tribe_logs():
    tr = _import_module("tribelog")
    if hasattr(tr, "open"):
        return tr.open()
    raise RuntimeError("tribelog.open not found")

def _close_tribe_logs():
    try:
        tr = _import_module("tribelog")
        if hasattr(tr, "close"):
            tr.close()
    except Exception as e:
        logs.logger.debug(f"_close_tribe_logs: {e}")

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
        delay = max(60, minutes * 60)
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
