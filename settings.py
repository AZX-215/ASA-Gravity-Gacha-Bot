screen_resolution: int = 0 # No longer in use. Just here cause people are thoughtless.
base_path: str = None # No longer in use. Just here cause people are thoughtless.
lag_offset: float = 1.0
iguanadon: str = "GACHAIGUANADON"
open_crystals: str = "GACHACRYSOPEN" # Additonal depo station for resources.
drop_off: str = "GACHADEDI"
bed_spawn: str = "GACHARENDER"
berry_station: str = "GACHABERRYSTATION"
grindables: str = "GACHAGRINDABLES"
berry_type: str = "berry" # Can now use any berry or mix of berries.
station_yaw: float = 0.0
render_pushout: float = 0.0
external_berry: bool = False
height_ele: int = 2 
height_grind: int = 3
command_prefix: str = "%"
singleplayer: bool = False
server_number: str = 0
pego_enabled: bool = True
gacha_enabled: bool = True
render_enabled: bool = True

crafting: bool = False
seeds_230: bool = False

# Sparkpowder stations are configured in json_files/sparkpowder.json
sparkpowder_enabled: bool = False

# Sparkpowder task tuning (safe defaults; adjust after in-game testing)
sparkpowder_look_degrees: float = 45.0
sparkpowder_turn_degrees: float = 180.0
sparkpowder_craft_seconds: float = 2
sparkpowder_requeue_delay: int = 1800  # fallback if sparkpowder.json delay is missing/0

# YOUR discord channel IDs and bot API key. To find channel IDs enable developer mode in discord and right click the channel to copy ID.
log_channel_gacha: int = 111111111111111
log_active_queue: int = 111111111111111
log_wait_queue: int = 111111111111111
discord_api_key: str = ""


if __name__ =="__main__":

    pass






