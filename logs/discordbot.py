import discord
import task_manager
import logs.gachalogs


def _get_queue(queue_type: str):
    return getattr(task_manager.scheduler, queue_type, None)


def _to_ts(exec_time) -> str:
    """Return a Discord relative timestamp tag for an execution time."""
    try:
        return f"<t:{int(float(exec_time))}:R>"
    except Exception:
        return "unknown"


def _get_entries(queue):
    """Thread-safe best-effort snapshot of queue entries."""
    try:
        if hasattr(queue, "snapshot"):
            return queue.snapshot()
        return list(getattr(queue, "queue", []))
    except Exception:
        return []


def _entry_fields(queue, entry):
    """Return (priority, exec_time, task_name) for active/waiting tuples."""
    if isinstance(queue, task_manager.priority_queue_prio):
        # (priority, exec_time, counter, task)
        priority, exec_time, _, task = entry
        return priority, exec_time, getattr(task, "name", "<unnamed>")

    # waiting_queue: (execution_time, counter, priority, task)
    exec_time, _, priority, task = entry
    return priority, exec_time, getattr(task, "name", "<unnamed>")


def _format_entry(queue, entry, idx: int) -> str:
    """Return a single-line, human readable queue entry."""
    if isinstance(queue, task_manager.priority_queue_prio):
        # (priority, exec_time, counter, task)
        priority, _, __, task = entry
        return f"{idx:>3}. [P{priority}] {task.name} | READY"

    # waiting_queue: (execution_time, counter, priority, task)
    exec_time, _, priority, task = entry
    return f"{idx:>3}. [P{priority}] {task.name} | <t:{int(exec_time)}:R>"


def build_queue_embed(queue_type: str, limit: int = 15) -> discord.Embed:
    """Build a single embed with a limited number of tasks (default 15).

    This keeps the queue panels compact, preserves Discord-rendered timestamps,
    and avoids hitting embed/message size limits.
    """
    try:
        embed = discord.Embed(title=f"{queue_type}")

        queue = _get_queue(queue_type)
        if queue is None:
            embed.add_field(name=queue_type, value="queue unavailable", inline=False)
            return embed

        entries = _get_entries(queue)
        total = len(entries)

        if total == 0:
            embed.add_field(name=queue_type, value="empty", inline=False)
            return embed

        shown = 0
        for i, entry in enumerate(entries[:limit], start=1):
            priority, exec_time, name = _entry_fields(queue, entry)
            embed.add_field(
                name=f"Task {i}",
                value=f"Name: {name} | Priority: {priority} | Execution: {_to_ts(exec_time)}",
                inline=False,
            )
            shown += 1

        if total > shown:
            embed.add_field(
                name=f"...and {total - shown} more tasks.",
                value="",
                inline=False,
            )

        return embed

    except Exception as e:
        logs.gachalogs.logger.error(f"error in build_queue_embed: {e}")
        return discord.Embed(title="error", description=str(e))


# Backwards-compatible helper.
async def embed_create(queue_type: str, limit: int = 15):
    return build_queue_embed(queue_type, limit=limit)


if __name__ == "__main__":
    pass
