import json
from pathlib import Path
from typing import Any

SETTINGS_FILE = Path(__file__).resolve().parent / "json_files" / "settings.json"

DEFAULT_SETTINGS = {'screen_resolution': 1440, 'base_path': None, 'enable_resolution_mapping': True, 'lag_offset': 1.4, 'ui_layout_mode': 'centered_16_9', 'use_hdr_templates': False, 'iguanadon': 'GACHAIGUANADON', 'open_crystals': 'GACHACRYSOPEN', 'drop_off': 'GACHADEDI', 'bed_spawn': 'GACHARENDER', 'berry_station': 'GACHABERRYSTATION', 'grindables': 'GACHAGRINDABLES', 'berry_type': 'berry', 'station_yaw': -141.27, 'render_pushout': 170.54, 'height_ele': 3, 'height_grind': 3, 'command_prefix': '%', 'server_number': 9306, 'singleplayer': False, 'seeds_230': False, 'external_berry': False, 'pego_enabled': True, 'gacha_enabled': True, 'crafting': True, 'sparkpowder_enabled': True, 'charcoal_enabled': False, 'gunpowder_enabled': False, 'decay_prevention_enabled': False, 'decay_prevention_open_seconds': 10.0, 'decay_prevention_post_tp_delay': 20.0, 'decay_prevention_requeue_delay': 21600, 'decay_prevention_beds_enabled': False, 'decay_prevention_beds_requeue_delay': 21600, 'decay_beds_post_spawn_delay': 20.0, 'decay_beds_open_seconds': 10.0, 'decay_beds_pitch_down_degrees': 15.0, 'decay_beds_fast_travel_attempts': 4, 'decay_beds_start_at_first': True, 'decay_beds_loop_back_to_first': False, 'decay_beds_inter_station_delay': 0.0, 'bed_travel_only_mode': False, 'sparkpowder_look_degrees': 45.0, 'sparkpowder_turn_degrees': 180.0, 'sparkpowder_craft_seconds': 2, 'sparkpowder_requeue_delay': 1800, 'gunpowder_look_degrees': -25.0, 'gunpowder_turn_degrees': 180.0, 'gunpowder_craft_seconds': 2, 'gunpowder_requeue_delay': 1800, 'log_channel_gacha': 1332520268895354911, 'log_channel_alerts': 1463991585665450035, 'log_active_queue': 1445620377177817149, 'log_wait_queue': 1332520069225512961, 'queue_preview_limit': 10, 'alert_send_spacing_sec': 1.5, 'alert_max_messages_per_tick': 1, 'alert_max_pending_lines': 600, 'alert_flush_interval_sec': 10.0, 'alert_dedup_window_sec': 120.0, 'alert_panel_max_entries': 25, 'alert_panel_max_chars': 1800, 'alert_send_cooldown_sec': 2.0, 'discord_api_key': 'key_goes_here', 'use_join_sim_reconnect': False, 'load_source_cogs': False}


def _coerce_value(default: Any, value: Any) -> Any:
    """Best-effort type preservation when loading from JSON/UI edits."""
    if default is None:
        return value
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(value)
        except Exception:
            return default
    if isinstance(default, float):
        try:
            return float(value)
        except Exception:
            return default
    return value


def _merge_settings(data: dict | None) -> dict:
    merged = dict(DEFAULT_SETTINGS)
    data = data or {}
    for key, default in DEFAULT_SETTINGS.items():
        if key in data:
            merged[key] = _coerce_value(default, data[key])
    # Preserve unknown keys so future additions are not lost by save/rewrite.
    for key, value in data.items():
        if key not in merged:
            merged[key] = value
    return merged


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)

    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    merged = _merge_settings(data)
    if merged != data:
        save_settings(merged)
    return merged


def save_settings(data: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged = _merge_settings(data)
    SETTINGS_FILE.write_text(json.dumps(merged, indent=4), encoding="utf-8")


def reload_settings() -> dict:
    data = load_settings()
    globals().update(data)
    return data


data = reload_settings()


if __name__ == "__main__":
    print(json.dumps(data, indent=4))
