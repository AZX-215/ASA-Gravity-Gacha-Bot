# task_manager.py
from __future__ import annotations
import heapq, threading, time
from typing import Any, List, Optional, Tuple

try:
    from logs import gachalogs as logs
except Exception:
    import gachalogs as logs  # type: ignore

import settings
    started: bool = False
        _scheduler_thread = None


# -------- activity log that discordbot reads --------
class _RollingLog:
    def __init__(self, capacity: int = 400):
        self._buf: List[str] = []
        self._cap = capacity
        self._lock = threading.Lock()

    def add(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"{ts} {msg}"
        with self._lock:
            self._buf.append(line)
            if len(self._buf) > self._cap:
                del self._buf[: len(self._buf) - self._cap]

    def tail(self, n: int) -> List[str]:
        with self._lock:
            return self._buf[-n:] if n > 0 else []

EVENT_LOG = _RollingLog()

# -------- queues that discordbot renders --------
_SEQ = 0
_SEQ_LOCK = threading.Lock()
def _next_seq() -> int:
    global _SEQ
    with _SEQ_LOCK:
        _SEQ += 1
        return _SEQ

class _ActiveQueue:
    def __init__(self):
        # (priority, seq, enq_ts, task)
        self._heap: List[Tuple[int, int, float, Any]] = []
        self._lock = threading.Lock()

    @property
    def queue(self) -> List[Tuple[int, int, float, Any]]:
        with self._lock:
            return list(self._heap)

    def is_empty(self) -> bool:
        with self._lock:
            return not self._heap

    def push(self, priority: int, task: Any) -> None:
        with self._lock:
            heapq.heappush(self._heap, (priority, _next_seq(), time.time(), task))

    def pop(self) -> Tuple[int, int, float, Any]:
        with self._lock:
            return heapq.heappop(self._heap)

class _WaitingQueue:
    def __init__(self):
        # (exec_epoch, seq, priority, task)
        self._heap: List[Tuple[float, int, int, Any]] = []
        self._lock = threading.Lock()

    @property
    def queue(self) -> List[Tuple[float, int, int, Any]]:
        with self._lock:
            return list(self._heap)

    def is_empty(self) -> bool:
        with self._lock:
            return not self._heap

    def push(self, when_epoch: float, priority: int, task: Any) -> None:
        with self._lock:
            heapq.heappush(self._heap, (when_epoch, _next_seq(), priority, task))

    def peek_ready(self, now_epoch: float) -> Optional[Tuple[float, int, int, Any]]:
        with self._lock:
            if not self._heap:
                return None
            return self._heap[0] if self._heap[0][0] <= now_epoch else None

    def pop(self) -> Tuple[float, int, int, Any]:
        with self._lock:
            return heapq.heappop(self._heap)

# -------- scheduler --------
class TaskScheduler:
    def __init__(self):
        self.active_queue = _ActiveQueue()
        self.waiting_queue = _WaitingQueue()
        self._stop = threading.Event()

    def enqueue(self, task: Any, priority: Optional[int] = None) -> None:
        pri = int(getattr(task, "priority", 1000) if priority is None else priority)
        EVENT_LOG.add(f"enqueue -> {getattr(task, 'name', 'task')} p={pri}")
        self.active_queue.push(pri, task)

    def enqueue_delayed(self, task: Any, delay_seconds: int, priority: Optional[int] = None) -> None:
        run_at = time.time() + max(0, delay_seconds)
        pri = int(getattr(task, "priority", 1000) if priority is None else priority)
        EVENT_LOG.add(f"enqueue@{int(run_at)} -> {getattr(task, 'name', 'task')} p={pri}")
        self.waiting_queue.push(run_at, pri, task)

    def enqueue_at(self, task: Any, run_at, priority: Optional[int] = None) -> None:
        if isinstance(run_at, (int, float)):
            epoch = float(run_at)
        else:
            try:
                epoch = run_at.timestamp()
            except Exception:
                epoch = time.time()
        pri = int(getattr(task, "priority", 1000) if priority is None else priority)
        EVENT_LOG.add(f"enqueue@{int(epoch)} -> {getattr(task, 'name', 'task')} p={pri}")
        self.waiting_queue.push(epoch, pri, task)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        EVENT_LOG.add("scheduler: start")
        while not self._stop.is_set():
            now = time.time()

            # promote ready waiting tasks
            while True:
                ready = self.waiting_queue.peek_ready(now)
                if ready is None:
                    break
                self.waiting_queue.pop()
                _, _, pri, task = ready
                self.active_queue.push(pri, task)

            if self.active_queue.is_empty():
                time.sleep(0.1)
                continue

            pri, _, _, task = self.active_queue.pop()
            name = getattr(task, "name", "task")
            EVENT_LOG.add(f"run -> {name} p={pri}")
            try:
                task.run()
            except Exception as e:
                logs.logger.error(f"task {name} failed: {e}")
                EVENT_LOG.add(f"error -> {name}: {e}")
            finally:
                if hasattr(task, "on_complete"):
                    try:
                        task.on_complete(self)
                    except Exception as e:
                        logs.logger.error(f"on_complete {name} failed: {e}")
                EVENT_LOG.add(f"done -> {name}")
            time.sleep(0.05)

scheduler = TaskScheduler()

def main() -> None:
    EVENT_LOG.add("bootstrap")
    try:
        # keep gacha/pego gated by toggles; render at lowest priority
        if getattr(settings, "RENDER_ENABLED", True):
            from render_sweep import build_render_task
            t = build_render_task()
            if t:
                scheduler.enqueue(t, priority=int(getattr(settings, "RENDER_PRIORITY", 9999)))
        if getattr(settings, "GACHA_ENABLED", False):
            EVENT_LOG.add("gacha: enabled")
        if getattr(settings, "PEGO_ENABLED", False):
            EVENT_LOG.add("pego: enabled")
    except Exception as e:
        logs.logger.error(f"bootstrap failed: {e}")
    scheduler.run()





