"""
logs.alert_panel

Rate-limit-safe alert forwarding for Discord.

- Keeps ONE alert panel message per channel (edits in place).
- Deduplicates identical alert lines and tracks counts.
- Prunes stale entries so the panel stays relevant.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class AlertEntry:
    line: str
    count: int
    first_ts: float
    last_ts: float
    task_ctx: str


class AlertPanel:
    def __init__(
        self,
        *,
        bot,
        channel_id: int | None,
        flush_interval_sec: float = 10.0,
        dedup_window_sec: float = 120.0,
        max_entries: int = 25,
        max_chars: int = 1800,
        send_cooldown_sec: float = 2.0,
    ):
        self.bot = bot
        self.channel_id = channel_id
        self.flush_interval_sec = float(flush_interval_sec)
        self.dedup_window_sec = float(dedup_window_sec)
        self.max_entries = int(max_entries)
        self.max_chars = int(max_chars)
        self.send_cooldown_sec = float(send_cooldown_sec)

        self._entries: "OrderedDict[str, AlertEntry]" = OrderedDict()
        self._suppressed = 0
        self._panel_msg = None
        self._last_flush = 0.0
        self._last_send = 0.0

    def push(self, task_ctx: str, line: str):
        if not line:
            return
        now = time.time()
        key = line.strip()
        e = self._entries.get(key)
        if e:
            e.count += 1
            e.last_ts = now
            self._entries.move_to_end(key)
        else:
            self._entries[key] = AlertEntry(line=line, count=1, first_ts=now, last_ts=now, task_ctx=task_ctx or "-")

        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
            self._suppressed += 1

    def _format(self) -> str:
        now = time.time()
        header = "**Alerts (deduped)**"
        if self._suppressed:
            header += f" — suppressed {self._suppressed} older unique alerts"

        # prune stale
        if self.dedup_window_sec > 0:
            stale = [k for k, e in self._entries.items() if (now - e.last_ts) > self.dedup_window_sec]
            for k in stale:
                del self._entries[k]

        lines = []
        for e in list(self._entries.values())[-self.max_entries:]:
            suffix = f" x{e.count}" if e.count > 1 else ""
            ctx = e.task_ctx if e.task_ctx else "-"
            one = e.line.strip().replace("\n", " ")
            lines.append(f"[{ctx}]{suffix} {one}")

        body = "\n".join(lines)
        if len(body) > self.max_chars:
            body = body[-self.max_chars:]
        return header + "\n```\n" + body + "\n```"

    async def flush_if_due(self):
        if not self.channel_id:
            return
        now = time.time()
        if now - self._last_flush < self.flush_interval_sec:
            return
        await self.flush()

    async def flush(self):
        if not self.channel_id:
            return
        now = time.time()
        if now - self._last_send < self.send_cooldown_sec:
            return

        ch = self.bot.get_channel(self.channel_id)
        if not ch:
            return

        content = self._format()
        try:
            if self._panel_msg is None:
                self._panel_msg = await ch.send(content)
            else:
                await self._panel_msg.edit(content=content)
        except Exception:
            self._panel_msg = None
        finally:
            self._last_flush = now
            self._last_send = now
