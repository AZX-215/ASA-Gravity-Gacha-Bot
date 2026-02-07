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
from collections import OrderedDict, deque

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

    # Alerts: WARNING/ERROR/CRITICAL are forwarded to the alerts channel.
    # Rate-limit safe strategy:
    #   - Deduplicate repeating alert lines into counters (xN).
    #   - Maintain a single "Alert panel" message in the alerts channel (edit-in-place).
    #   - Optionally send immediate one-off messages for CRITICAL with cooldown.
    alert_levels = (" - WARNING - ", " - ERROR - ", " - CRITICAL - ")

    alert_channel_id = getattr(settings, "log_channel_alerts", None) or getattr(settings, "log_channel_gacha", None)
    alert_flush_interval_sec = float(getattr(settings, "alert_flush_interval_sec", 10.0))
    alert_dedup_window_sec = float(getattr(settings, "alert_dedup_window_sec", 120.0))
    alert_panel_max_entries = int(getattr(settings, "alert_panel_max_entries", 20))
    alert_panel_max_chars = int(getattr(settings, "alert_panel_max_chars", 1800))
    alert_critical_immediate = bool(getattr(settings, "alert_critical_immediate", True))
    alert_critical_cooldown_sec = float(getattr(settings, "alert_critical_cooldown_sec", 60.0))

    alert_panel_msg = None
    last_alert_flush = 0.0

    # key -> dict(count, first_ts, last_ts, line, task, level)
    alert_store = OrderedDict()
    critical_last_sent = {}  # key -> monotonic ts

    def _alert_level(line: str) -> str:
        if " - CRITICAL - " in line:
            return "CRITICAL"
        if " - ERROR - " in line:
            return "ERROR"
        if " - WARNING - " in line:
            return "WARNING"
        return "INFO"

    def _normalize_alert_key(line: str) -> str:
        # Remove leading timestamp if present; keep the semantic portion to dedupe repeats.
        # Works for both "YYYY-MM-DD HH:MM:SS ..." and "HH:MM:SS - LEVEL - ..." formats.
        s = line.strip()
        # strip leading date/time chunk up to first ' - '
        if " - " in s:
            parts = s.split(" - ", 1)
            # If the first part looks like a time/date, drop it.
            head = parts[0]
            if any(ch.isdigit() for ch in head) and (":" in head or "-" in head):
                s = parts[1].strip()
        return s

    def _add_alert(line: str):
        nonlocal alert_store
        now = time.monotonic()
        key = _normalize_alert_key(line)
        lvl = _alert_level(line)
        task_ctx = _extract_task_ctx(line)

        # Expire old keys outside the window so store doesn't grow unbounded.
        if alert_store:
            cutoff = now - max(30.0, alert_dedup_window_sec * 4)
            drop = []
            for k, v in alert_store.items():
                if v["last_ts"] < cutoff:
                    drop.append(k)
            for k in drop:
                alert_store.pop(k, None)

        # Dedup / bump
        if key in alert_store and (now - alert_store[key]["last_ts"]) <= alert_dedup_window_sec:
            v = alert_store[key]
            v["count"] += 1
            v["last_ts"] = now
            # keep most recent line (in case message differs slightly but normalized same)
            v["line"] = line
            v["task"] = task_ctx
            v["level"] = lvl
            # move to front (most recent)
            alert_store.move_to_end(key, last=False)
        else:
            alert_store[key] = {
                "count": 1,
                "first_ts": now,
                "last_ts": now,
                "line": line,
                "task": task_ctx,
                "level": lvl,
            }
            alert_store.move_to_end(key, last=False)

        # Optional immediate CRITICAL
        if lvl == "CRITICAL" and alert_critical_immediate:
            last = critical_last_sent.get(key, 0.0)
            if (now - last) >= alert_critical_cooldown_sec:
                critical_last_sent[key] = now
                return ("CRITICAL", key, task_ctx, line)
        return None

    def _build_alert_panel_text() -> str:
        if not alert_store:
            return "**Alerts**\n(No recent WARNING/ERROR/CRITICAL lines)\n"

        lines_out = []
        now = time.monotonic()
        n = 0
        for k, v in alert_store.items():
            if n >= alert_panel_max_entries:
                break
            age = int(now - v["last_ts"])
            cnt = v["count"]
            lvl = v["level"]
            task = v["task"]
            # Keep line readable; show count/age/task prefix.
            base = v["line"].strip()
            prefix = f"[{lvl}]"
            if task and task != "-":
                prefix += f"[{task}]"
            prefix += f" x{cnt} (last {age}s)"
            lines_out.append(prefix + " :: " + base)
            n += 1

        body = "\n".join(lines_out)
        # Ensure we stay under Discord limit.
        if len(body) > alert_panel_max_chars:
            body = body[:alert_panel_max_chars] + "\n...(truncated)"
        return "**Alerts** (deduped)\n```\n" + body + "\n```"
def _toggle(v: bool) -> str:
        return "ON" if v else "OFF"

    def _status_block() -> str:
        # Settings toggles
        pego = bool(getattr(settings, "pego_enabled", True))
        gacha = bool(getattr(settings, "gacha_enabled", True))
        crafting = bool(getattr(settings, "crafting", False))            # Flush alert panel (edit-in-place) on interval.
            if alert_channel_id:
                now = time.monotonic()
                if (now - last_alert_flush) >= alert_flush_interval_sec:
                    alert_channel = bot.get_channel(alert_channel_id)
                    if alert_channel:
                        alert_text = _build_alert_panel_text()
                        try:
                            if alert_panel_msg is None:
                                alert_panel_msg = await alert_channel.send(alert_text)
                            else:
                                await alert_panel_msg.edit(content=alert_text)
                        except Exception:
                            try:
                                alert_panel_msg = await alert_channel.send(alert_text)
                            except Exception:
                                pass
                    last_alert_flush = now

ail_text) > max_tail:
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
                        crit = _add_alert(line)
                        if crit:
                            # send CRITICAL immediate best-effort; panel still handles dedup.
                            try:
                                _lvl, _key, _task, _line = crit
                                _ch = bot.get_channel(alert_channel_id) if alert_channel_id else None
                                if _ch:
                                    await _ch.send(f"**CRITICAL** (task: {_task})\n```\n{_line.strip()}\n```")
                            except Exception:
                                pass
s:
                            drop_n = len(alert_buffer) - alert_max_pending_lines
                            suppressed_alerts += drop_n
                            del alert_buffer[:drop_n]

            # Post alert history as separate messages (best-effort, rate-safe).
            if alert_buffer:
                alert_channel_id = getattr(settings, "log_channel_alerts", None) or settings.log_channel_gacha
                alert_channel = bot.get_channel(alert_channel_id) if alert_channel_id else None
                if alert_channel:
                    sent_messages = 0
                    while alert_buffer and sent_messages < alert_max_messages_per_tick:
                        chunk_lines = []
                        chunk_len = 0
                        chunk_tasks = set()

                        # Build one message worth of alert lines.
                        while alert_buffer:
                            task_ctx, line = alert_buffer[0]

                            # If a single line is huge, truncate it so we never exceed Discord limits.
                            if (not chunk_lines) and len(line) > 1800:
                                alert_buffer.pop(0)
                                truncated = (line[:1800] + "\n") if not line.endswith("\n") else line[:1800]
                                chunk_lines.append(truncated)
                                chunk_len += len(truncated)
                                if task_ctx:
                                    chunk_tasks.add(task_ctx)
                                break

                            if chunk_len + len(line) > 1800 and chunk_lines:
                                break
                            alert_buffer.pop(0)
                            chunk_lines.append(line)
                            chunk_len += len(line)
                            if task_ctx:
                                chunk_tasks.add(task_ctx)

                        if not chunk_lines:
                            break

                        header = "**Alert**"
                        if len(chunk_tasks) == 1:
                            only = next(iter(chunk_tasks))
                            if only and only != "-":
                                header = f"**Alert** (task: {only})"

                        # Include suppression note once (oldest dropped lines).
                        if suppressed_alerts:
                            header += f" (suppressed {suppressed_alerts} older lines)"
                            suppressed_alerts = 0

                        body = "".join(chunk_lines)
                        try:
                            await alert_channel.send(header + "\n```\n" + body + "\n```")
                        except Exception:
                            pass

                        sent_messages += 1
                        if alert_buffer and alert_send_spacing_sec > 0:
                            await asyncio.sleep(alert_send_spacing_sec)

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

    Single-message panel that updates by editing.
    Shows first N tasks (default 15) plus an "...and X more" footer.
    """
    if queue_type == "active_queue":
        log_channel = bot.get_channel(settings.log_active_queue)
    else:
        log_channel = bot.get_channel(settings.log_wait_queue)

    if not log_channel:
        return

    panel_msg = None

    # How many tasks to display in the queue panels.
    max_tasks = int(getattr(settings, "queue_preview_limit", 15) or 15)

    while True:
        try:
            embed = await discordbot.embed_create(queue_type, limit=max_tasks)

            if panel_msg is None:
                panel_msg = await log_channel.send(embed=embed)
            else:
                try:
                    await panel_msg.edit(embed=embed)
                except Exception:
                    panel_msg = await log_channel.send(embed=embed)

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
