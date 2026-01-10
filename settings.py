screen_resolution: int = 0 # No longer in use.
base_path: str = None # No longer in use.
lag_offset: float = 1.3
iguanadon: str = "GACHAIGUANADON"
open_crystals: str = "GACHACRYSOPEN" # 1st Resource Station.
drop_off: str = "GACHADEDI" # 2st Resource Station.
bed_spawn: str = "GACHARENDER" # set to (ARB-BOT_RENDER) for ARB bot
berry_station: str = "GACHABERRYSTATION"
grindables: str = "GACHAGRINDABLES" # 3st Resource Station.
berry_type: str = "berry" # Can now use any berry or mix of berries.
station_yaw: float = 0.0
render_pushout: float = 0.0
height_ele: int = 3 
height_grind: int = 3
command_prefix: str = "%"
server_number: str = 0
singleplayer: bool = False
seeds_230: bool = False
external_berry: bool = False

# Crafting task toggles (crafting must also be True)
crafting: bool = True # Toggle off for standalone gachabot.
sparkpowder_enabled: bool = False # Sparkpowder stations are configured in json_files/sparkpowder.json
gunpowder_enabled: bool = False # Gunpowder stations are configured in json_files/gunpowder.json

# Task toggles
pego_enabled: bool = True
gacha_enabled: bool = True

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
discord_api_key: str = ""


if __name__ =="__main__":

    pass






