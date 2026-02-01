import json
import re
from pathlib import Path

import settings
import logs.gachalogs as logs


class station_metadata():
    def __init__(self):
        super().__init__()
        self.name = None
        self.xpos = None
        self.ypos = None
        self.zpos = None
        self.yaw = None
        self.pitch = 0
        self.side = None
        self.resource = None


def _json_load_relaxed(raw: str, file_path: str):
    raw = (raw or "").lstrip("\ufeff").strip()
    if not raw:
        logs.logger.warning(f"warning: {file_path} is empty; no stations loaded.")
        return []

    # Remove trailing commas before a closing '}' or ']'
    raw = re.sub(r',(?=\s*[}\]])', '', raw)

    try:
        obj, _ = json.JSONDecoder().raw_decode(raw)
        return obj
    except json.JSONDecodeError as e:
        logs.logger.error(f"error loading stations JSON from {file_path}: {e}")
        return []


def get_custom_stations():
    # json_files lives at repo root: <repo>/json_files/stations.json
    base = Path(__file__).resolve().parents[2]
    file_path = (base / "json_files" / "stations.json").resolve()

    try:
        raw = file_path.read_text(encoding="utf-8")
        return _json_load_relaxed(raw, str(file_path))
    except FileNotFoundError as e:
        logs.logger.error(f"error loading stations JSON from {file_path}: {e}")
        return []


def get_station_metadata(teleporter_name: str):
    global custom_stations
    custom_stations = False
    stationdata = station_metadata()
    foundstation = False

    all_stations = get_custom_stations()

    if len(all_stations) > 0:
        custom_stations = True
        for entry_station in all_stations:
            if entry_station.get("name") == teleporter_name:
                stationdata.name = entry_station.get("name")
                stationdata.xpos = entry_station.get("xpos", 0)
                stationdata.ypos = entry_station.get("ypos", 0)
                stationdata.zpos = entry_station.get("zpos", 0)
                stationdata.yaw = entry_station.get("yaw", settings.station_yaw)
                # stationdata.pitch = entry_station.get("pitch", 0)
                foundstation = True
                break

    if not foundstation:  # default station metadata
        stationdata.name = teleporter_name
        stationdata.xpos = 0
        stationdata.ypos = 0
        stationdata.zpos = 0
        stationdata.yaw = settings.station_yaw
        stationdata.pitch = 0

    return stationdata
