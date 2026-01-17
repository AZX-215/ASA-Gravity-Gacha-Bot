screen_resolution: int = 0 # No longer in use.
base_path: str = None # No longer in use.
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
crafting: bool = True # Toggle off for standalone gachabot.
sparkpowder_enabled: bool = False # Sparkpowder stations are configured in json_files/sparkpowder.json
gunpowder_enabled: bool = False # Gunpowder stations are configured in json_files/gunpowder.json

# Auto-decay prevention (teleport + open tribe log to keep areas rendered)
decay_prevention_enabled: bool = False
decay_prevention_open_seconds: float = 20.0
decay_prevention_post_tp_delay: float = 10.0  # multiplied by lag_offset
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
log_channel_gacha: int = 111111111111111
log_active_queue: int = 111111111111111
log_wait_queue: int = 111111111111111
discord_api_key: str = "111111111111111"


if __name__ =="__main__":

    pass






