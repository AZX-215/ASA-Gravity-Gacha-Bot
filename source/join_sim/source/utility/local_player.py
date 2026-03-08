import os
import re
import time
from pathlib import Path

import psutil


def path(process_name):
    print("finding path now ")
    for proc in psutil.process_iter(attrs=["name", "exe"]):
        try:
            if proc.info["name"] == process_name and proc.info.get("exe"):
                return Path(proc.info["exe"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _resolve_base_path():
    # Settings override wins if explicitly set.
    try:
        import settings  # type: ignore
        configured = getattr(settings, "base_path", None)
        if configured:
            candidate = Path(configured)
            if candidate.exists():
                return candidate
    except Exception:
        pass

    exe_path = path("ArkAscended.exe")
    if exe_path is not None:
        return exe_path.parents[3]

    raise RuntimeError("ArkAscended.exe was not found and no valid settings.base_path override is configured")


try:
    base_path = _resolve_base_path()
except Exception as e:
    print(f"{e} PLEASE OPEN UP ARK OR SET settings.base_path, THEN RESTART THE SCRIPT")
    time.sleep(10)
    raise SystemExit(1)


def get_user_settings(setting_name):
    settings_path = os.path.join(base_path, "ShooterGame", "Saved", "Config", "Windows", "GameUserSettings.ini")
    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    with open(settings_path, "r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            if setting_name in line and "=" in line:
                _, value = line.strip().split("=", 1)
                return value


def get_look_lr_sens():
    return float(get_user_settings("LookLeftRightSensitivity"))


def get_look_ud_sens():
    return float(get_user_settings("LookUpDownSensitivity"))


def get_fov():
    return float(get_user_settings("FOVMultiplier"))


def get_input_settings(input_name):
    input_path = os.path.join(base_path, "ShooterGame", "Saved", "Config", "Windows", "input.ini")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input settings file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8", errors="ignore") as file:
        lines = list(file)

    if input_name == "ConsoleKeys":
        for line in lines:
            if input_name in line and "=" in line:
                _, value = line.strip().split("=", 1)
                return value

    for line in lines:
        match = re.match(r'ActionMappings=\(ActionName="([^"]+)",.*Key=([A-Za-z0-9_]+)\)', line.strip())
        if match:
            action_name = match.group(1)
            key = match.group(2)
            if action_name == input_name:
                return key

    return input_name


console_key = str(get_input_settings("ConsoleKeys") or "").lower()
if console_key == "tilde":
    print("ERROR :: CHANGE YOUR CONSOLE KEYBIND FROM TILDE")
