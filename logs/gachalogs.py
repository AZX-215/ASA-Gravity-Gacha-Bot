import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

"""Central logging for the bot.

Why this exists:
- We tail logs to Discord. If logging writes to a relative path and the process
  working directory changes (common on hosted services), the Discord tailer and
  the logger can end up reading/writing different files.
- Discord has a 2000 character message limit. The Discord tailer is now a live
  panel (message edit) that shows a bounded tail.
"""


# ---------------- Custom TEMPLATE level ----------------
TEMPLATE_LEVEL = 5
logging.addLevelName(TEMPLATE_LEVEL, "TEMPLATE")


def template(self, message, *args, **kwargs):
    if self.isEnabledFor(TEMPLATE_LEVEL):
        self._log(TEMPLATE_LEVEL, message, args, **kwargs)


logging.Logger.template = template


# ---------------- File location (stable) ----------------
LOG_DIR = Path(__file__).resolve().parent
LOG_FILE = (LOG_DIR / "logs.txt").resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------- Task context injection ----------------
# The scheduler sets this before executing a task so every log line can include
# the task / station that produced it (useful for Discord alerts).
_TASK_CONTEXT = ""


def set_task_context(task: Optional[str]) -> None:
    global _TASK_CONTEXT
    _TASK_CONTEXT = (task or "").strip()


def clear_task_context() -> None:
    global _TASK_CONTEXT
    _TASK_CONTEXT = ""


class _TaskContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.task = _TASK_CONTEXT if _TASK_CONTEXT else "-"
        return True


# ---------------- Logger config ----------------
logger = logging.getLogger("Gacha")
logger.setLevel(logging.DEBUG)
logger.propagate = False


def _ensure_file_handler():
    """Attach a single FileHandler to this logger, avoiding duplicates."""
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")).resolve() == LOG_FILE:
            return

    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(task)s - %(funcName)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    fh.setFormatter(fmt)
    fh.addFilter(_TaskContextFilter())
    logger.addHandler(fh)


_ensure_file_handler()
