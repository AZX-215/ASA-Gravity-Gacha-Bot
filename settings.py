screen_resolution: int = 1440 # No longer in use.
base_path: str = None # No longer in use.
# --- Display / scaling options (safe defaults) ---
# Controls how 2560x1440-authored coordinates/ROIs are mapped to your current ARK client resolution.
# True keeps the existing (current) multi-resolution behavior.
enable_resolution_mapping: bool = True

# How ARK UI is laid out on ultrawide.
# - "centered_16_9": treat UI as 16:9 canvas scaled by height and centered (recommended default)
# - "stretch": scale X independently to fill full width (only if your UI truly stretches)
ui_layout_mode: str = "centered_16_9"

# Template set selection: if True and icons{height}_hdr/ exists, prefer it over icons{height}/.
# Example: icons1440_hdr/ with the same filenames/crops as icons1440/.
use_hdr_templates: bool = False

lag_offset: float = 1.4
iguanadon: str = "GACHAIGUANADON"
open_crystals: str = "GACHACRYSOPEN" # 1st Resource Station.
drop_off: str = "GACHADEDI" # 2st Resource Station.
bed_spawn: str = "GACHARENDER" # set to (ARB-BOT_RENDER) for ARB bot. Return to (GACHARENDER) for every other task type.
berry_station: str = "GACHABERRYSTATION"
grindables: str = "GACHAGRINDABLES" # 3st Resource Station.
berry_type: str = "berry" # Can now use any berry or mix of berries.
station_yaw: float = -141.27 # Set to (-93.76) for ARB/Gunpowder Crafting. Return to (-141.27) for every other task type.
render_pushout: float = 170.54 # Set to (90.00) for ARB/Gunpowder Crafting. Return to (170.54) for every other task type.
height_ele: int = 3 
height_grind: int = 3
command_prefix: str = "%"
server_number: str = 9306
singleplayer: bool = False
seeds_230: bool = False
external_berry: bool = False

# Default Task toggles
pego_enabled: bool = True
gacha_enabled: bool = True

# Crafting task toggles (crafting must also be True)
crafting: bool = False # Toggle off for standalone gachabot.
sparkpowder_enabled: bool = False # Sparkpowder stations are configured in json_files/sparkpowder.json
gunpowder_enabled: bool = False # Gunpowder stations are configured in json_files/gunpowder.json

# Auto-decay prevention (teleport + open tribe log to keep areas rendered)
decay_prevention_enabled: bool = False
decay_prevention_open_seconds: float = 20.0
decay_prevention_post_tp_delay: float = 15.0  # multiplied by lag_offset
decay_prevention_requeue_delay: int = 21600  # 6 hours fallback if station delay is missing/0

#sparkpowder defaults
sparkpowder_look_degrees: float = 45.0 # Sparkpowder task tuning (safe defaults; adjust after in-game testing)
sparkpowder_turn_degrees: float = 180.0
sparkpowder_craft_seconds: float = 2
sparkpowder_requeue_delay: int = 1800  # fallback if sparkpowder.json delay is missing/0

# gunpowder defaults
gunpowder_look_degrees: float = -25.0 # Gunpowder task tuning (safe defaults; adjust after in-game testing)
gunpowder_turn_degrees: float = 180.0
gunpowder_craft_seconds: float = 2
gunpowder_requeue_delay: int = 1800 # fallback if gunpowder.json delay is missing/0

# YOUR discord channel IDs and bot API key. To find channel IDs enable developer mode in discord and right click the channel to copy ID.
log_channel_gacha: int = 1332520268895354911
log_channel_alerts: int = 1463991585665450035
log_active_queue: int = 1445620377177817149
log_wait_queue: int = 1332520069225512961
queue_preview_limit: int = 15
# Discord alert forwarding throttles (prevents API rate limits during bursts)
# - Max number of alert messages to post per send_new_logs tick (tick = 5 seconds)
# - Backlog is buffered and drained over time; oldest lines are dropped after alert_max_pending_lines
alert_send_spacing_sec: float = 1.2
alert_max_messages_per_tick: int = 1
alert_max_pending_lines: int = 600

discord_api_key: str = "API_KEY_GOES_HERE"



if __name__ =="__main__":

    pass






