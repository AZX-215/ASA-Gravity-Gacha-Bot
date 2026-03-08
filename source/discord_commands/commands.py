import asyncio
import sys
import time
from collections import deque
from pathlib import Path

import discord
import pygetwindow as gw
import settings
import task_manager
import win32con
import win32gui
from discord import app_commands
from discord.ext import commands

import bot.stations as stations
import logs.botoptions as botoptions
import logs.discordbot as discordbot
from logs.alert_panel import AlertPanel

try:
    import ASA.player.player_inventory as inventory
except Exception:
    inventory = None

try:
    from source.utility.colour_checks import console_output, output_oranage_tp_pixel
except Exception:
    console_output = None
    output_oranage_tp_pixel = None


class discord_commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.running_tasks = []
        self.bot_started = False
        self.start_time = 0.0
        self.log_file_path = (Path(__file__).resolve().parents[2] / "logs" / "logs.txt").resolve()
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)

    async def send_new_logs(self):
        log_channel = self.bot.get_channel(settings.log_channel_gacha)
        if not log_channel:
            return

        tail_lines = deque(maxlen=200)
        last_position = 0
        panel_msg = None
        last_sent = ""

        alert_levels = (" - WARNING - ", " - ERROR - ", " - CRITICAL - ")
        alert_buffer = []
        suppressed_alerts = 0

        alert_panel = AlertPanel(
            bot=self.bot,
            channel_id=(getattr(settings, "log_channel_alerts", None) or settings.log_channel_gacha),
            flush_interval_sec=float(getattr(settings, "alert_flush_interval_sec", 10.0)),
            dedup_window_sec=float(getattr(settings, "alert_dedup_window_sec", 120.0)),
            max_entries=int(getattr(settings, "alert_panel_max_entries", 25)),
            max_chars=int(getattr(settings, "alert_panel_max_chars", 1800)),
            send_cooldown_sec=float(getattr(settings, "alert_send_cooldown_sec", 2.0)),
        )

        alert_max_messages_per_tick = int(getattr(settings, "alert_max_messages_per_tick", 1))
        alert_max_pending_lines = int(getattr(settings, "alert_max_pending_lines", 600))

        def _toggle(v: bool) -> str:
            return "ON" if v else "OFF"

        def _status_block() -> str:
            pego = bool(getattr(settings, "pego_enabled", True))
            gacha = bool(getattr(settings, "gacha_enabled", True))
            crafting = bool(getattr(settings, "crafting", False))
            spark = bool(getattr(settings, "sparkpowder_enabled", False))
            gun = bool(getattr(settings, "gunpowder_enabled", False))
            decay = bool(getattr(settings, "decay_prevention_enabled", False))
            decay_beds = bool(getattr(settings, "decay_prevention_beds_enabled", False))

            enabled_line = (
                f"Enabled: pego={_toggle(pego)} | gacha={_toggle(gacha)} | "
                f"crafting={_toggle(crafting)} (spark={_toggle(spark)}, gun={_toggle(gun)}) | "
                f"decay={_toggle(decay)} | decay_beds={_toggle(decay_beds)}"
            )

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
                            f"decay_beds={counts.get('decay_prevention_beds', 0)}, render={counts.get('render', 0)}"
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

        def _extract_task_ctx(line: str) -> str:
            try:
                parts = line.split(" - ")
                if len(parts) >= 3:
                    ctx = parts[2].strip()
                    return ctx if ctx else "-"
            except Exception:
                pass
            return "-"

        def _build_panel_text() -> str:
            header = "**Live logs** (updates every 5s)\n" + _status_block()
            tail_text = "".join(tail_lines)
            max_total = 1950
            overhead = len(header) + len("\n```\n\n```")
            max_tail = max(0, max_total - overhead)
            if len(tail_text) > max_tail:
                tail_text = tail_text[-max_tail:]
            return header + "\n```\n" + tail_text + "\n```"

        while True:
            try:
                if not self.log_file_path.exists():
                    self.log_file_path.write_text("", encoding="utf-8")

                try:
                    size = self.log_file_path.stat().st_size
                    if size < last_position:
                        last_position = 0
                        tail_lines.clear()
                except Exception:
                    pass

                new_text = ""
                try:
                    with open(self.log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(last_position)
                        new_text = f.read()
                        last_position = f.tell()
                except Exception:
                    new_text = ""

                if new_text:
                    for line in new_text.splitlines(True):
                        tail_lines.append(line)
                        if any(level in line for level in alert_levels):
                            alert_buffer.append((_extract_task_ctx(line), line))
                            if len(alert_buffer) > alert_max_pending_lines:
                                drop_n = len(alert_buffer) - alert_max_pending_lines
                                suppressed_alerts += drop_n
                                del alert_buffer[:drop_n]

                if alert_buffer:
                    alert_channel_id = getattr(settings, "log_channel_alerts", None) or settings.log_channel_gacha
                    alert_channel = self.bot.get_channel(alert_channel_id) if alert_channel_id else None
                    if alert_channel:
                        sent_messages = 0
                        while alert_buffer and sent_messages < alert_max_messages_per_tick:
                            task_ctx, raw_line = alert_buffer.pop(0)
                            line = raw_line.strip()
                            if len(line) > 1800:
                                line = line[-1800:]
                            try:
                                await alert_panel.add_entry(task_ctx, line)
                            except Exception:
                                pass
                            sent_messages += 1

                        if suppressed_alerts:
                            try:
                                await alert_panel.add_entry(
                                    "alerts",
                                    f"suppressed {suppressed_alerts} older alert lines to stay under pending-buffer limit",
                                )
                            except Exception:
                                pass
                            suppressed_alerts = 0

                panel_text = _build_panel_text()
                if panel_text != last_sent:
                    if panel_msg is None:
                        panel_msg = await log_channel.send(panel_text)
                    else:
                        try:
                            await panel_msg.edit(content=panel_text)
                        except Exception:
                            panel_msg = await log_channel.send(panel_text)
                    last_sent = panel_text
            except Exception:
                pass

            await asyncio.sleep(5)

    async def embed_send(self, queue_type):
        if queue_type == "active_queue":
            log_channel = self.bot.get_channel(settings.log_active_queue)
        else:
            log_channel = self.bot.get_channel(settings.log_wait_queue)

        if not log_channel:
            return

        panel_msg = None
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
                pass

            await asyncio.sleep(30)

    async def get_time_difference(self, initial):
        if not initial:
            return "0 hours"
        time_difference = time.time() - initial
        days = time_difference / 86400
        hours = time_difference / 3600
        if days >= 1:
            return f"{round(days, 2)} days"
        return f"{round(hours, 2)} hours"

    @app_commands.command(name="pause", description="sends the bot back to render bed for X amount of seconds")
    async def reset(self, interaction: discord.Interaction, time: int):
        task = task_manager.scheduler
        pause_task = stations.pause(time)
        task.add_task(pause_task)
        await interaction.response.send_message(
            f"pause task added will now pause for {time} seconds once the next task finishes"
        )

    @app_commands.command()
    async def start(self, interaction: discord.Interaction):
        if self.bot_started:
            await interaction.response.send_message("bot already started")
            return

        self.bot_started = True
        self.start_time = time.time()
        logchn = self.bot.get_channel(settings.log_channel_gacha)
        if logchn:
            await logchn.send("bot starting up now")

        with open(self.log_file_path, "w", encoding="utf-8") as file:
            file.write("")

        self.running_tasks.append(self.bot.loop.create_task(self.send_new_logs()))
        await interaction.response.send_message("starting up bot now you have 5 seconds before start")
        await asyncio.sleep(5)
        self.running_tasks.append(asyncio.create_task(botoptions.task_manager_start()))
        while task_manager.started == False:
            await asyncio.sleep(1)
        self.running_tasks.append(self.bot.loop.create_task(self.embed_send("active_queue")))
        self.running_tasks.append(self.bot.loop.create_task(self.embed_send("waiting_queue")))

    @app_commands.command()
    async def shutdown(self, interaction: discord.Interaction):
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

    @app_commands.command(name="info", description="sends analytics for the bot")
    async def info(self, interaction: discord.Interaction):
        if self.start_time == 0:
            await interaction.response.send_message("bot hasnt started up yet")
            return

        resets = getattr(inventory, "resets", "n/a") if inventory is not None else "n/a"
        await interaction.response.send_message(
            f"time since start: {await self.get_time_difference(self.start_time)} resets : {resets}"
        )

    @app_commands.command(name="colour_checks", description="outputs pixel values")
    async def colour_checks(self, interaction: discord.Interaction):
        if console_output is None or output_oranage_tp_pixel is None:
            await interaction.response.send_message("colour check helpers are unavailable in this build")
            return
        await interaction.response.send_message(
            f"console mean output {console_output.output_mean_colour()} orange pixel {output_oranage_tp_pixel.get_orange_pixel()}"
        )


async def setup(bot):
    await bot.add_cog(discord_commands(bot))
