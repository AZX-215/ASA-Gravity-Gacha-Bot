import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading

"""Central logging for the bot.

Key points:
- Logs are tailed to Discord from a fixed file location.
- A per-thread task context is injected into each log line so warnings/errors
  can be attributed to the task/station that was running when they occurred.
"""


# ---------------- Custom TEMPLATE level ----------------
TEMPLATE_LEVEL = 5
logging.addLevelName(TEMPLATE_LEVEL, "TEMPLATE")


def template(self, message, *args, **kwargs):
    if self.isEnabledFor(TEMPLATE_LEVEL):
        self._log(TEMPLATE_LEVEL, message, args, **kwargs)


logging.Logger.template = template


# ---------------- Per-thread task context ----------------
_task_ctx = threading.local()


def set_task_context(name: str):
    """Set the current task/station context for logs emitted on this thread."""
    try:
        _task_ctx.name = str(name) if name else "-"
    except Exception:
        _task_ctx.name = "-"


def clear_task_context():
    """Clear the current task context for this thread."""
    try:
        _task_ctx.name = "-"
    except Exception:
        pass


def _get_task_context() -> str:
    return getattr(_task_ctx, "name", "-") or "-"


class _TaskContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Inject attribute used by the formatter
        record.task_ctx = _get_task_context()
        return True


# ---------------- File location (stable) ----------------
LOG_DIR = Path(__file__).resolve().parent
LOG_FILE = (LOG_DIR / "logs.txt").resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)


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

    fh.addFilter(_TaskContextFilter())

    fmt = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(task_ctx)s - %(funcName)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)


_ensure_file_handler()
