"""Station/task routing helpers.

Loads optional station-specific behavior overrides from json_files/station_routing.json.
This keeps execution logic in Python while moving per-station layout/profile data to JSON.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import logs.gachalogs as logs


_CACHE: dict | None = None
_CACHE_MTIME: int | None = None


def _routing_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'json_files' / 'station_routing.json'


def _load_raw() -> dict:
    global _CACHE, _CACHE_MTIME
    path = _routing_path()
    try:
        stat = path.stat()
        mtime = int(stat.st_mtime_ns)
        if _CACHE is not None and _CACHE_MTIME == mtime:
            return copy.deepcopy(_CACHE)

        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            logs.logger.warning(f"station_routing.json must be a JSON object; got {type(data).__name__}. Ignoring.")
            data = {}
        _CACHE = data
        _CACHE_MTIME = mtime
        return copy.deepcopy(data)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logs.logger.error(f"Failed to load station_routing.json: {exc}")
        return {}


def slugify(value: str) -> str:
    value = str(value or '').strip().lower()
    value = ''.join(ch if ch.isalnum() else '_' for ch in value)
    while '__' in value:
        value = value.replace('__', '_')
    return value.strip('_')


def _merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def get_station_route(task_type: str, station_name: str, defaults: dict | None = None) -> dict:
    data = _load_raw()
    section = data.get(task_type, {}) if isinstance(data, dict) else {}
    route = copy.deepcopy(defaults or {})

    if isinstance(section, dict):
        route = _merge(route, section.get('defaults', {}))
        stations = section.get('stations', {})
        if isinstance(stations, dict):
            for candidate in [station_name, slugify(station_name)]:
                entry = stations.get(candidate)
                if isinstance(entry, dict):
                    route = _merge(route, entry)
    return route
