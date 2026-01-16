import heapq
import time
import json
import re
from pathlib import Path
import settings
import bot.stations as stations
import logs.gachalogs as logs
from threading import Lock, Thread

global scheduler
global started
started = False


class SingletonMeta(type):
    _instances = {}
    _lock: Lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class priority_queue_exc:
    """Execution-time ordered queue (soonest first)."""

    def __init__(self):
        self.queue = []

    def add(self, task, priority, execution_time):
        heapq.heappush(self.queue, (execution_time, len(self.queue), priority, task))

    def pop(self):
        if not self.is_empty():
            return heapq.heappop(self.queue)
        return None

    def peek(self):
        if not self.is_empty():
            return self.queue[0]
        return None

    def is_empty(self):
        return len(self.queue) == 0


class priority_queue_prio:
    """Priority ordered queue (lowest number = highest priority)."""

    def __init__(self):
        self.queue = []

    def add(self, task, priority, execution_time):
        heapq.heappush(self.queue, (priority, execution_time, len(self.queue), task))

    def pop(self):
        if not self.is_empty():
            return heapq.heappop(self.queue)
        return None

    def peek(self):
        if not self.is_empty():
            return self.queue[0]
        return None

    def is_empty(self):
        return len(self.queue) == 0


class watchdog_render_task:
    """One-shot maintenance task.
    - Runs render_station.execute() at high priority so it can't be starved.
    - Optionally sets stations.berry_station=True AFTER render, so the next gacha run re-berries.
    """

    def __init__(self, reason="timeout", request_berry=False):
        self.name = f"watchdog_render:{reason}"
        self.reason = reason
        self.request_berry = request_berry
        self.one_shot = True
        self.has_run_before = False

    def execute(self):
        stations.render_station().execute()

        # IMPORTANT: set berry flag AFTER render
        if self.request_berry:
            stations.berry_station = True

    def get_priority_level(self):
        return 1

    def get_requeue_delay(self):
        return 0


class task_scheduler(metaclass=SingletonMeta):
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.active_queue = priority_queue_prio()
            self.waiting_queue = priority_queue_exc()
            self.initialized = True
            self.prev_task_name = ""

            # watchdog / cycle tracking
            self.last_render_exec = time.time()
            self._maintenance_timeout_sec = 3 * 60 * 60  # force render at least once every 3 hours
            self._maintenance_enqueued = False
            self._maintenance_due_deferred = False
            self._defer_completion_ratio = 0.90  # if we're ~done, wait for cycle end instead of interrupting
            self._maintenance_counter = 0

            # cycle definition: "complete" means every pego + every gacha/collect has executed at least once
            self._pego_all = set()
            self._gacha_all = set()
            self._pego_done = set()
            self._gacha_done = set()

            # tracked but not used for cycle completion
            self._sparkpowder_all = set()
            self._sparkpowder_done = set()
            self._gunpowder_all = set()
            self._gunpowder_done = set()

    def _is_task_enabled(self, task):
        """Return True if the task should run given current settings toggles."""
        # Render tasks must always run
        if isinstance(task, (stations.render_station, watchdog_render_task)):
            return True

        # Pegos
        if isinstance(task, stations.pego_station):
            return bool(getattr(settings, "pego_enabled", True))

        # Gachas + collect tasks
        if isinstance(task, (stations.gacha_station, stations.snail_pheonix)):
            return bool(getattr(settings, "gacha_enabled", True))

        # Crafting tasks
        if isinstance(task, stations.sparkpowder_station):
            return bool(getattr(settings, "crafting", False) and getattr(settings, "sparkpowder_enabled", False))

        if isinstance(task, stations.gunpowder_station):
            return bool(getattr(settings, "crafting", False) and getattr(settings, "gunpowder_enabled", False))

        return True

    def _discard_from_tracking(self, task):
        """If a task is disabled mid-run, remove it from tracking sets so it can't affect cycle logic."""
        try:
            if isinstance(task, stations.pego_station):
                self._pego_all.discard(task.name)
                self._pego_done.discard(task.name)
            elif isinstance(task, (stations.gacha_station, stations.snail_pheonix)):
                self._gacha_all.discard(task.name)
                self._gacha_done.discard(task.name)
            elif isinstance(task, stations.sparkpowder_station):
                self._sparkpowder_all.discard(task.name)
                self._sparkpowder_done.discard(task.name)
            elif isinstance(task, stations.gunpowder_station):
                self._gunpowder_all.discard(task.name)
                self._gunpowder_done.discard(task.name)
        except Exception:
            pass

    def add_task(self, task):
        # First run: allow a task-specific initial delay
        if not getattr(task, 'has_run_before', False):
            next_execution_time = time.time() + float(getattr(task, 'initial_delay', 0) or 0)
        else:
            next_execution_time = time.time() + float(task.get_requeue_delay() or 0)

        task.has_run_before = True

        # Track station lists for cycle completion logic
        try:
            if isinstance(task, stations.pego_station):
                self._pego_all.add(task.name)
            elif isinstance(task, (stations.gacha_station, stations.snail_pheonix)):
                self._gacha_all.add(task.name)
            elif isinstance(task, stations.sparkpowder_station):
                self._sparkpowder_all.add(task.name)
            elif isinstance(task, stations.gunpowder_station):
                self._gunpowder_all.add(task.name)
        except Exception:
            pass

        self.waiting_queue.add(task, task.get_priority_level(), next_execution_time)
        # logs.logger.info(f"Added task {task.name} to waiting queue")

    def run(self):
        while True:
            current_time = time.time()
            self.move_ready_tasks_to_active_queue(current_time)

            if not self.active_queue.is_empty():
                self.execute_task(current_time)
            else:
                time.sleep(5)

    def move_ready_tasks_to_active_queue(self, current_time):
        while not self.waiting_queue.is_empty():
            task_tuple = self.waiting_queue.peek()
            exec_time, _, priority, task = task_tuple

            if exec_time <= current_time:
                self.waiting_queue.pop()
                self.active_queue.add(task, priority, exec_time)
            else:
                break

    def execute_task(self, current_time):
        task_tuple = self.active_queue.pop()
        if not task_tuple:
            return

        # active_queue stores: (priority, exec_time, idx, task)
        priority, exec_time, _, task = task_tuple

        # Not ready yet (should be rare)
        if exec_time > current_time:
            self.active_queue.add(task, priority, exec_time)
            return

        # Toggle gate: skip tasks that are disabled (and do not re-queue them)
        if not self._is_task_enabled(task):
            logs.logger.info(f"Skipping disabled task: {getattr(task, 'name', '<unnamed>')}")
            self._discard_from_tracking(task)
            self.prev_task_name = getattr(task, 'name', '')
            return

        if getattr(task, 'name', '') != self.prev_task_name:
            logs.logger.info(f"Executing task: {getattr(task, 'name', '<unnamed>')}")

        try:
            task.execute()
        except Exception as e:
            logs.logger.exception(f"Task {getattr(task, 'name', '<unnamed>')} raised: {e}")

        now = time.time()

        # If a watchdog task just ran, reset tracking and DO NOT run cycle logic for this execution.
        if isinstance(task, watchdog_render_task):
            self.last_render_exec = now
            self._pego_done.clear()
            self._gacha_done.clear()
            self._sparkpowder_done.clear()
            self._gunpowder_done.clear()
            self._maintenance_enqueued = False
            self._maintenance_due_deferred = False

            self.prev_task_name = getattr(task, 'name', '')
            return

        # -------- watchdog + cycle tracking --------
        # Update last render time
        if isinstance(task, stations.render_station):
            self.last_render_exec = now

        # Mark progress toward a full cycle (pego + gacha/collect only)
        if isinstance(task, stations.pego_station):
            self._pego_done.add(task.name)
        elif isinstance(task, (stations.gacha_station, stations.snail_pheonix)):
            self._gacha_done.add(task.name)

        # Track crafting completion (not used for cycle completion)
        if isinstance(task, stations.sparkpowder_station):
            self._sparkpowder_done.add(task.name)
        elif isinstance(task, stations.gunpowder_station):
            self._gunpowder_done.add(task.name)

        total = len(self._pego_all) + len(self._gacha_all)
        cycle_complete = (
            total > 0 and
            (len(self._pego_all) == 0 or self._pego_done.issuperset(self._pego_all)) and
            (len(self._gacha_all) == 0 or self._gacha_done.issuperset(self._gacha_all))
        )

        # If maintenance was deferred and the cycle completed, run it now (once).
        if self._maintenance_due_deferred and cycle_complete and not self._maintenance_enqueued:
            self._maintenance_counter += 1
            self._maintenance_enqueued = True
            self._maintenance_due_deferred = False
            self.add_task(watchdog_render_task(
                reason=f"deferred_cycle_complete#{self._maintenance_counter}",
                request_berry=True
            ))

        # Otherwise, if a cycle completes, perform maintenance at end of the cycle (once).
        elif cycle_complete and not self._maintenance_enqueued:
            self._maintenance_counter += 1
            self._maintenance_enqueued = True
            self._maintenance_due_deferred = False
            self.add_task(watchdog_render_task(
                reason=f"cycle_complete#{self._maintenance_counter}",
                request_berry=True
            ))

        # If render hasn't happened in too long, enqueue a watchdog render.
        # If we're almost done with the current cycle, defer until cycle completes to avoid wasting time/berries.
        if not self._maintenance_enqueued:
            time_since_render = now - self.last_render_exec
            if time_since_render >= self._maintenance_timeout_sec:
                done = len(self._pego_done) + len(self._gacha_done)
                progress = (done / total) if total > 0 else 0.0

                if (not cycle_complete) and total > 0 and progress >= self._defer_completion_ratio:
                    self._maintenance_due_deferred = True
                else:
                    self._maintenance_counter += 1
                    self._maintenance_enqueued = True
                    self._maintenance_due_deferred = False
                    self.add_task(watchdog_render_task(
                        reason=f"timeout#{self._maintenance_counter}",
                        request_berry=False
                    ))

        self.prev_task_name = getattr(task, 'name', '')

        # Re-queue unless one-shot
        if getattr(task, 'name', '') != "pause" and not getattr(task, 'one_shot', False):
            self.move_to_waiting_queue(task)

    def move_to_waiting_queue(self, task):
        # For sparkpowder/gunpowder, prefer per-station delay from JSON (task.delay)
        delay = float(task.get_requeue_delay() or 0)
        if isinstance(task, (stations.sparkpowder_station, stations.gunpowder_station)):
            try:
                delay = float(getattr(task, "delay", delay) or delay)
            except Exception:
                pass

        next_execution_time = time.time() + delay
        priority_level = task.get_priority_level()
        self.waiting_queue.add(task, priority_level, next_execution_time)


def _loads_relaxed_json(text):
    # Strip UTF-8 BOM if present
    text = text.lstrip('\ufeff').strip()
    if not text:
        return []
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return json.loads(text)


def load_resolution_data(file_path):
    # Resolve relative paths from the project root (works regardless of current working directory).
    base_dir = Path(__file__).resolve().parent
    resolved = (base_dir / file_path).resolve() if not Path(file_path).is_absolute() else Path(file_path)

    try:
        with open(resolved, 'r', encoding='utf-8') as file:
            raw = file.read()
        return _loads_relaxed_json(raw)
    except FileNotFoundError as e:
        logs.logger.error(f"error loading JSON (not found) from {resolved}: {e}")
        return []
    except json.JSONDecodeError as e:
        logs.logger.error(f"error loading JSON (decode) from {resolved}: {e}")
        return []
    except Exception as e:
        logs.logger.error(f"error loading JSON from {resolved}: {e}")
        return []


def main():
    global scheduler
    global started
    scheduler = task_scheduler()

    # ---------------- Pegos ----------------
    if getattr(settings, "pego_enabled", True):
        pego_data = load_resolution_data("json_files/pego.json")
        for entry_pego in pego_data:
            name = entry_pego["name"]
            teleporter = entry_pego["teleporter"]
            delay = entry_pego["delay"]
            scheduler.add_task(stations.pego_station(name, teleporter, delay))
    else:
        logs.logger.info("Pego tasks disabled (settings.pego_enabled=False)")

    # ---------------- Gachas / Collects ----------------
    if getattr(settings, "gacha_enabled", True):
        gacha_data = load_resolution_data("json_files/gacha.json")
        for entry_gacha in gacha_data:
            name = entry_gacha["name"]
            teleporter = entry_gacha["teleporter"]
            direction = entry_gacha["side"]
            resource = entry_gacha["resource_type"]
            if resource == "collect":
                depo = entry_gacha["depo_tp"]
                task = stations.snail_pheonix(name, teleporter, direction, depo)
            else:
                task = stations.gacha_station(name, teleporter, direction)
            scheduler.add_task(task)
    else:
        logs.logger.info("Gacha tasks disabled (settings.gacha_enabled=False)")

    # ---------------- Crafting: Sparkpowder ----------------
    if getattr(settings, "crafting", False) and getattr(settings, "sparkpowder_enabled", False):
        sparkpowder_data = load_resolution_data("json_files/sparkpowder.json")
        for entry in sparkpowder_data:
            sp_name = entry.get("name") or entry.get("station_name") or entry.get("teleporter")
            sp_tp = entry.get("teleporter") or entry.get("station_name") or entry.get("name")
            sp_delay = entry.get("delay", 0)
            sp_initial = entry.get("initial_delay", 0)  # optional one-time startup offset
            sp_height = entry.get("deposit_height", 3)

            if not sp_name or not sp_tp:
                logs.logger.warning(f"[Sparkpowder] Invalid entry in sparkpowder.json: {entry}")
                continue

            t = stations.sparkpowder_station(sp_name, sp_tp, sp_delay, sp_height)
            # Ensure it queues immediately on startup unless explicitly overridden
            t.initial_delay = float(sp_initial or 0)
            t.delay = float(sp_delay or 0)
            scheduler.add_task(t)

    # ---------------- Crafting: Gunpowder ----------------
    if getattr(settings, "crafting", False) and getattr(settings, "gunpowder_enabled", False):
        gunpowder_data = load_resolution_data("json_files/gunpowder.json")
        for entry in gunpowder_data:
            gp_name = entry.get("name") or entry.get("station_name") or entry.get("teleporter")
            gp_tp = entry.get("teleporter") or entry.get("station_name") or entry.get("name")
            gp_delay = entry.get("delay", 0)
            gp_initial = entry.get("initial_delay", 0)  # optional one-time startup offset
            gp_height = entry.get("deposit_height", 3)

            if not gp_name or not gp_tp:
                logs.logger.warning(f"[Gunpowder] Invalid entry in gunpowder.json: {entry}")
                continue

            t = stations.gunpowder_station(gp_name, gp_tp, gp_delay, gp_height)
            t.initial_delay = float(gp_initial or 0)
            t.delay = float(gp_delay or 0)
            scheduler.add_task(t)

    # Render should always be active (no toggle); bot logic depends on it.
    scheduler.add_task(stations.render_station())
    logs.logger.info("scheduler now running")
    started = True
    scheduler.run()


if __name__ == "__main__":
    time.sleep(2)
    main()
