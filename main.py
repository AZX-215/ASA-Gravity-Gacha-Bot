import discord
from discord.ext import commands
from typing import Callable
import asyncio
import logs.botoptions as botoptions
import pyautogui
import settings
import json
import time
import logs.discordbot as discordbot
import bot.stations as stations
import task_manager
import win32gui
import win32con
import sys
import pygetwindow as gw
from pathlib import Path
from collections import deque

intents = discord.Intents.default()
pyautogui.FAILSAFE = False
bot = commands.Bot(command_prefix=settings.command_prefix, intents=intents)

running_tasks = []
bot_started = False

# Stable log file path (matches logs.gachalogs)
LOG_FILE_PATH = (Path(__file__).resolve().parent / "logs" / "logs.txt").resolve()
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_json(json_file:str):
    try:
        with open(json_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []  

def save_json(json_file:str,data):
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=4)

async def send_new_logs():
    """Live log panel in Discord.

    - Uses message *edit* (one panel) instead of spamming.
    - Keeps a bounded tail so it never exceeds Discord's 2000 character limit.
    - Never dies on an exception (network hiccup / message too long / file rotate).
    """

    log_channel = bot.get_channel(settings.log_channel_gacha)
    if not log_channel:
        return

    tail_lines = deque(maxlen=200)
    last_position = 0
    panel_msg = None
    last_sent = ""

    # Alerts: keep history by posting separate messages for WARNING/ERROR/CRITICAL.
    alert_levels = (" - WARNING - ", " - ERROR - ", " - CRITICAL - ")
    alert_buffer = []

    def _toggle(v: bool) -> str:
        return "ON" if v else "OFF"

    def _status_block() -> str:
        # Settings toggles
        pego = bool(getattr(settings, "pego_enabled", True))
        gacha = bool(getattr(settings, "gacha_enabled", True))
        crafting = bool(getattr(settings, "crafting", False))
        spark = bool(getattr(settings, "sparkpowder_enabled", False))
        gun = bool(getattr(settings, "gunpowder_enabled", False))
        decay = bool(getattr(settings, "decay_prevention_enabled", False))

        enabled_line = (
            f"Enabled: pego={_toggle(pego)} | gacha={_toggle(gacha)} | "
            f"crafting={_toggle(crafting)} (spark={_toggle(spark)}, gun={_toggle(gun)}) | "
            f"decay={_toggle(decay)}"
        )

        # Scheduler stats (best-effort)
        try:
            if getattr(task_manager, "started", False) and getattr(task_manager, "scheduler", None):
                sch = task_manager.scheduler
                active_n = len(getattr(sch.active_queue, "queue", []))
                waiting_n = len(getattr(sch.waiting_queue, "queue", []))
                prev = getattr(sch, "prev_task_name", "")
                counts = getattr(sch, "loaded_counts", None)

                counts_line = ""
                if isinstance(counts, dict):
                    counts_line = (
                        f"Loaded: pego={counts.get('pego', 0)}, gacha={counts.get('gacha', 0)}, "
                        f"collect={counts.get('collect', 0)}, spark={counts.get('sparkpowder', 0)}, "
                        f"gun={counts.get('gunpowder', 0)}, decay={counts.get('decay_prevention', 0)}, "
                        f"render={counts.get('render', 0)}"
                    )

                queue_line = f"Queues: active={active_n} | waiting={waiting_n}"
                if prev:
                    queue_line += f" | last={prev}"
                if counts_line:
                    return enabled_line + "\n" + counts_line + "\n" + queue_line
                return enabled_line + "\n" + queue_line
        except Exception:
            pass

        return enabled_line

    def _build_panel_text() -> str:
        # Avoid including a constantly-changing timestamp in the content; Discord already shows
        # the message "edited" time, and we only want to edit when something actually changed.
        header = "**Live logs** (updates every 5s)\n" + _status_block()
        tail_text = "".join(tail_lines)

        # Hard cap to stay within Discord limits.
        max_total = 1950
        overhead = len(header) + len("\n```\n\n```")
        max_tail = max(0, max_total - overhead)
        if len(tail_text) > max_tail:
            tail_text = tail_text[-max_tail:]

        return header + "\n```\n" + tail_text + "\n```"

    while True:
        try:
            # Ensure file exists
            if not LOG_FILE_PATH.exists():
                LOG_FILE_PATH.write_text("", encoding="utf-8")

            # Handle truncation/rotation
            try:
                size = LOG_FILE_PATH.stat().st_size
                if size < last_position:
                    last_position = 0
                    tail_lines.clear()
            except Exception:
                pass

            new_text = ""
            try:
                with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(last_position)
                    new_text = f.read()
                    last_position = f.tell()
            except Exception:
                new_text = ""

            if new_text:
                for line in new_text.splitlines(True):
                    tail_lines.append(line)
                    if any(level in line for level in alert_levels):
                        alert_buffer.append(line)

            # Post alert history as separate messages (best-effort, rate-safe).
            if alert_buffer:
                alert_channel_id = getattr(settings, "log_channel_alerts", None) or settings.log_channel_gacha
                alert_channel = bot.get_channel(alert_channel_id) if alert_channel_id else None
                if alert_channel:
                    # Chunk alerts to respect Discord limits.
                    chunk = ""
                    while alert_buffer:
                        line = alert_buffer.pop(0)
                        if len(chunk) + len(line) > 1800:
                            try:
                                await alert_channel.send("**Alert**\n```\n" + chunk + "\n```")
                            except Exception:
                                pass
                            chunk = ""
                        chunk += line
                    if chunk:
                        try:
                            await alert_channel.send("**Alert**\n```\n" + chunk + "\n```")
                        except Exception:
                            pass

            panel_text = _build_panel_text()
            if panel_text != last_sent:
                if panel_msg is None:
                    panel_msg = await log_channel.send(panel_text)
                else:
                    try:
                        await panel_msg.edit(content=panel_text)
                    except Exception:
                        # If message was deleted or can't be edited, create a new one.
                        panel_msg = await log_channel.send(panel_text)

                last_sent = panel_text

        except Exception:
            # Never crash the log streamer.
            pass

        await asyncio.sleep(5)

@bot.tree.command(name="add_gacha", description="add a new gacha station to the data")
async def add_gacha(interaction: discord.Interaction, name: str, teleporter: str, resource_type: str ,direction: str):
    data = load_json("json_files/gacha.json")

    for entry in data:
        if entry["name"] == name:
            await interaction.response.send_message(f"a gacha station with the name '{name}' already exists", ephemeral=True)
            return
        
    new_entry = {
        "name": name,
        "teleporter": teleporter,
        "resource_type": resource_type,
        "side" : direction
    }
    data.append(new_entry)

    save_json("json_files/gacha.json",data)

    await interaction.response.send_message(f"added new gacha station: {name}")

@bot.tree.command(name="list_gacha", description="list all gacha stations")
async def list_gacha(interaction: discord.Interaction):

    data = load_json("json_files/gacha.json")
    if not data:
        await interaction.response.send_message("no gacha stations found", ephemeral=True)
        return


    response = "gacha Stations:\n"
    for entry in data:
        response += f"- **{entry['name']}**: teleporter `{entry['teleporter']}`, resource `{entry['resource_type']} gacha on the `{entry['side']}` side `\n"

    await interaction.response.send_message(response)


@bot.tree.command(name="add_pego", description="add a new pego station to the data")

async def add_pego(interaction: discord.Interaction, name: str, teleporter: str, delay: int):
    data = load_json("json_files/pego.json")

    for entry in data:
        if entry["name"] == name:
            await interaction.response.send_message(f"a pego station with the name '{name}' already exists", ephemeral=True)
            return
        
    new_entry = {
        "name": name,
        "teleporter": teleporter,
        "delay": delay
    }
    data.append(new_entry)

    save_json("json_files/pego.json",data)

    await interaction.response.send_message(f"added new pego station: {name}")

@bot.tree.command(name="list_pego", description="list all pego stations")
async def list_pego(interaction: discord.Interaction):

    data = load_json("json_files/pego.json")
    if not data:
        await interaction.response.send_message("no pego stations found", ephemeral=True)
        return


    response = "pego Stations:\n"
    for entry in data:
        response += f"- **{entry['name']}**: teleporter `{entry['teleporter']}`, delay `{entry['delay']}`\n"

    await interaction.response.send_message(response)

@bot.tree.command(name="pause", description="sends the bot back to render bed for X amount of seconds")
async def reset(interaction: discord.Interaction,time:int):
    task = task_manager.scheduler
    pause_task = stations.pause(time)
    task.add_task(pause_task)
    await interaction.response.send_message(f"pause task added will now pause for {time} seconds once the next task finishes")
    
async def embed_send(queue_type):
    """Continuously update queue panels.

    We may need multiple messages (pages) to show the full queue while respecting
    Discord embed limits. We edit existing messages instead of spamming.
    """
    if queue_type == "active_queue":
        log_channel = bot.get_channel(settings.log_active_queue)
    else:
        log_channel = bot.get_channel(settings.log_wait_queue)

    if not log_channel:
        return

    panel_msgs = []  # list[discord.Message]

    while True:
        try:
            embeds = discordbot.build_queue_embeds(queue_type)

            # Ensure we have enough messages.
            for i, embed in enumerate(embeds):
                if i >= len(panel_msgs) or panel_msgs[i] is None:
                    panel_msgs.append(await log_channel.send(embed=embed))
                else:
                    try:
                        await panel_msgs[i].edit(embed=embed)
                    except Exception:
                        # Message deleted or can't be edited; recreate.
                        panel_msgs[i] = await log_channel.send(embed=embed)

            # Remove extra messages if page count shrank.
            extra = panel_msgs[len(embeds):]
            if extra:
                for msg in extra:
                    if msg is None:
                        continue
                    try:
                        await msg.delete()
                    except Exception:
                        # If deletion isn't allowed, overwrite with a minimal placeholder.
                        try:
                            await msg.edit(embed=discord.Embed(title=f"{queue_type}", description="(page removed)"))
                        except Exception:
                            pass
                panel_msgs = panel_msgs[:len(embeds)]

        except Exception:
            # Best effort; try again next tick.
            pass

        await asyncio.sleep(30)

@bot.tree.command()
async def start(interaction: discord.Interaction):
    global running_tasks
    global bot_started
    if bot_started:
        await interaction.response.send_message("bot already started")
        return
    bot_started = True
    logchn = bot.get_channel(settings.log_channel_gacha) 
    if logchn:
        await logchn.send(f'bot starting up now')
    
    # resetting log files
    with open(LOG_FILE_PATH, 'w', encoding="utf-8") as file:
        file.write("")
    running_tasks.append(bot.loop.create_task(send_new_logs()))
    
    
    await interaction.response.send_message(f"starting up bot now you have 5 seconds before start")
    await asyncio.sleep(5)
    running_tasks.append(asyncio.create_task(botoptions.task_manager_start()))
    while task_manager.started == False:
        await asyncio.sleep(1)
    running_tasks.append(bot.loop.create_task(embed_send("active_queue")))
    running_tasks.append(bot.loop.create_task(embed_send("waiting_queue")))
    
@bot.tree.command()
async def shutdown(interaction: discord.Interaction):
    await interaction.response.send_message("Shutting down script...")
    print("Shutting down script...")
    cmd_windows = [win for win in gw.getAllWindows() if "cmd" in win.title.lower() or "system32" in win.title.lower()]

    if cmd_windows:
        cmd_window = cmd_windows[0]  
        hwnd = cmd_window._hWnd  

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE) 
        win32gui.SetForegroundWindow(hwnd)  
        time.sleep(1)         
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        print("Shutting down...")
        sys.exit() 
    else:
        print("No CMD window found.")


@bot.event
async def on_ready():
    await bot.tree.sync()
    
    logchn = bot.get_channel(settings.log_channel_gacha) 
    if logchn:
        await logchn.send(f'bot ready to start')
    print (f'logged in as {bot.user}')

api_key = settings.discord_api_key

if __name__ =="__main__":
    if len(settings.discord_api_key) < 4:
        print("you need to have a valid discord API key for the bot to run")
        print("please follow the instructions in the discord server to get your api key")
        exit()
    bot.run(api_key)
