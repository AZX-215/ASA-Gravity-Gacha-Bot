"""JSON-backed dedi profile execution helpers.

This module lets deposit / withdrawal station layouts live in json_files/dedis.json
while keeping the Python call sites stable. Existing public functions in bot.deposit
and bot.withdrawal remain the live API, but they can now execute named profiles from JSON
before falling back to the hard-coded routines.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import settings
import utils
import logs.gachalogs as logs


DEDIS_JSON = Path("json_files/dedis.json")


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", value).strip("_")


def load_dedi_config(file_path: Path = DEDIS_JSON) -> Any:
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_profiles(file_path: Path = DEDIS_JSON) -> Dict[str, Dict[str, Any]]:
    data = load_dedi_config(file_path)
    profiles: Dict[str, Dict[str, Any]] = {}

    if isinstance(data, dict):
        for name, profile in (data.get("profiles") or {}).items():
            if isinstance(profile, dict):
                profiles[name] = profile
        return profiles

    if not isinstance(data, list):
        return profiles

    for entry in data:
        if not isinstance(entry, dict):
            continue

        if "profiles" in entry and isinstance(entry["profiles"], dict):
            for name, profile in entry["profiles"].items():
                if isinstance(profile, dict):
                    profiles[name] = profile

        profile_id = entry.get("profileID")
        if profile_id and isinstance(profile_id, str):
            profiles[profile_id] = entry

    return profiles


def get_profile(name: str) -> Optional[Dict[str, Any]]:
    return load_profiles().get(name)


def _sleep(seconds: float, *, lag_scaled: bool = True) -> None:
    duration = float(seconds)
    if lag_scaled:
        duration *= settings.lag_offset
    time.sleep(duration)


def _execute_step(step: Dict[str, Any]) -> None:
    action = step.get("action")
    if not action:
        raise ValueError(f"Profile step is missing an action: {step!r}")

    if action == "sleep":
        _sleep(step.get("seconds", 0), lag_scaled=step.get("lag_scaled", True))
        return

    if action == "turn_up":
        utils.turn_up(step["value"])
    elif action == "turn_down":
        utils.turn_down(step["value"])
    elif action == "turn_left":
        utils.turn_left(step["value"])
    elif action == "turn_right":
        utils.turn_right(step["value"])
    elif action == "press_key":
        utils.press_key(step["key"])
    elif action == "set_yaw":
        utils.set_yaw(step["value"])
    elif action == "set_pitch":
        utils.set_pitch(step["value"])
    elif action == "pitch_zero":
        utils.pitch_zero()
    elif action == "zero":
        utils.zero()
    elif action == "turn_to":
        utils.turn_to(step["yaw"], step["pitch"])
    else:
        raise ValueError(f"Unsupported dedi profile action: {action!r}")

    sleep_after = step.get("sleep_after")
    if sleep_after is not None:
        _sleep(float(sleep_after), lag_scaled=step.get("lag_scaled", True))


def execute_profile(
    profile_name: str,
    *,
    expected_height: Optional[int] = None,
    context: str = "",
) -> bool:
    profile = get_profile(profile_name)
    if not profile:
        return False

    if not profile.get("active", False):
        return False

    configured_height = profile.get("height")
    if expected_height is not None and configured_height is not None and configured_height != expected_height:
        logs.logger.warning(
            f"{context or profile_name}: profile height={configured_height} does not match requested height={expected_height}; using fallback"
        )
        return False

    steps = profile.get("steps")
    if not isinstance(steps, list) or not steps:
        logs.logger.warning(f"{context or profile_name}: profile has no executable steps; using fallback")
        return False

    try:
        for step in steps:
            _execute_step(step)
    except Exception as exc:
        logs.logger.exception(f"{context or profile_name}: failed while executing JSON profile {profile_name!r}: {exc}")
        return False

    return True


def execute_first_available(
    profile_names: Iterable[str],
    *,
    expected_height: Optional[int] = None,
    context: str = "",
) -> Optional[str]:
    for profile_name in profile_names:
        if execute_profile(profile_name, expected_height=expected_height, context=context or profile_name):
            return profile_name
    return None
