import discord
import task_manager
import logs.gachalogs


def _get_queue(queue_type: str):
    return getattr(task_manager.scheduler, queue_type, None)


def _format_entry(queue, entry, idx: int) -> str:
    """Return a single-line, human readable queue entry."""
    if isinstance(queue, task_manager.priority_queue_prio):
        # (priority, exec_time, counter, task)
        priority, _, __, task = entry
        return f"{idx:>3}. [P{priority}] {task.name} | READY"

    # waiting_queue: (execution_time, counter, priority, task)
    exec_time, _, priority, task = entry
    return f"{idx:>3}. [P{priority}] {task.name} | <t:{int(exec_time)}:R>"


def build_queue_embeds(queue_type: str, max_desc_chars: int = 3900):
    """Build one-or-more embeds to display the full queue without truncation.

    Discord limits:
      - Embed description max ~4096 chars.
      - Message rate-limits: keep pages minimal and update by editing.
    """
    try:
        queue = _get_queue(queue_type)

        if queue is None:
            return [discord.Embed(title=f"{queue_type}", description="queue unavailable")]

        entries = queue.snapshot() if hasattr(queue, "snapshot") else list(getattr(queue, "queue", []))
        total = len(entries)

        if total == 0:
            return [discord.Embed(title=f"{queue_type}", description="empty")]

        # Build all lines first.
        lines = []
        for i, entry in enumerate(entries, start=1):
            lines.append(_format_entry(queue, entry, i))

        # Split into pages based on embed description size.
        pages = []
        current = []

        # Fixed overhead per embed description.
        # "Total: N" + code fence wrappers.
        def _desc_len(task_lines):
            return len(f"Total: {total}\n```text\n" + "\n".join(task_lines) + "\n```")

        for line in lines:
            if current and _desc_len(current + [line]) > max_desc_chars:
                pages.append(current)
                current = [line]
            else:
                current.append(line)

        if current:
            pages.append(current)

        embeds = []
        page_count = len(pages)
        for page_idx, page_lines in enumerate(pages, start=1):
            title = f"{queue_type} ({page_idx}/{page_count})"
            desc = f"Total: {total}\n```text\n" + "\n".join(page_lines) + "\n```"
            embeds.append(discord.Embed(title=title, description=desc))

        return embeds

    except Exception as e:
        logs.gachalogs.logger.error(f"error in build_queue_embeds: {e}")
        return [discord.Embed(title="error", description=str(e))]


# Backwards-compatible helper (single embed). Prefer build_queue_embeds.
async def embed_create(queue_type: str):
    embeds = build_queue_embeds(queue_type)
    return embeds[0] if embeds else discord.Embed(title=f"{queue_type}")


if __name__ == "__main__":
    pass
