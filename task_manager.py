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

    def __call__(cls,*args,**kwargs):

        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args,**kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]

class priority_queue_exc:
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
        # Run render maintenance (teleport -> tekpod -> drop all -> open tribe log, etc.)
        stations.render_station().execute()

        # IMPORTANT: set berry flag AFTER render, because render_station.execute() may also touch berry_station.
        if self.request_berry:
            stations.berry_station = True

    def get_priority_level(self):
        return 1  # higher than pegos/gachas so it can pre-empt

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

            # cycle definition: "complete" means every pego + every gacha has executed at least once
            self._pego_all = set()
            self._gacha_all = set()
            self._pego_done = set()
            self._gacha_done = set()



    def add_task(self, task):
        # First run: allow a task-specific initial delay (used by one-shot crafting tasks)
        if not getattr(task, 'has_run_before', False):
            next_execution_time = time.time() + float(getattr(task, 'initial_delay', 0) or 0)
        else:
            next_execution_time = time.time() + task.get_requeue_delay()

        task.has_run_before = True

        # Track station lists for cycle completion logic
        try:
            if isinstance(task, stations.pego_station):
                self._pego_all.add(task.name)
            elif isinstance(task, stations.gacha_station):
                self._gacha_all.add(task.name)
        except Exception:
            pass

        self.waiting_queue.add(task, task.get_priority_level(), next_execution_time)
        print(f"Added task {task.name} to waiting queue ") # might need to remove this if you have LOADS OF stations causing long messages

            
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
        exec_time,priority , _, task = task_tuple

        if exec_time <= current_time:
            
            if task.name != self.prev_task_name:
                logs.logger.info(f"Executing task: {task.name}")
            task.execute()  

            # -------- watchdog + cycle tracking --------
            # Update last render time
            if isinstance(task, stations.render_station) or isinstance(task, watchdog_render_task):
                self.last_render_exec = time.time()

            # Mark progress toward a full cycle
            if isinstance(task, stations.pego_station):
                self._pego_done.add(task.name)
            elif isinstance(task, stations.gacha_station):
                self._gacha_done.add(task.name)
            # Determine cycle completion (based on enabled task groups)
            pego_enabled = getattr(settings, "pego_enabled", True)
            gacha_enabled = getattr(settings, "gacha_enabled", True)

            pego_complete = (not pego_enabled) or (len(self._pego_all) > 0 and self._pego_done.issuperset(self._pego_all))
            gacha_complete = (not gacha_enabled) or (len(self._gacha_all) > 0 and self._gacha_done.issuperset(self._gacha_all))

            # If both groups are disabled, treat the cycle as complete.
            cycle_complete = pego_complete and gacha_complete and (
                (pego_enabled and len(self._pego_all) > 0) or
                (gacha_enabled and len(self._gacha_all) > 0) or
                ((not pego_enabled) and (not gacha_enabled))
            )

            # If render hasn't happened in too long, enqueue a watchdog render.
            # If we're almost done with the current cycle, defer until cycle completes to avoid wasting time/berries.
            if not self._maintenance_enqueued:
                time_since_render = time.time() - self.last_render_exec
                if time_since_render >= self._maintenance_timeout_sec:
                    total = (len(self._pego_all) if pego_enabled else 0) + (len(self._gacha_all) if gacha_enabled else 0)
                    done = (len(self._pego_done) if pego_enabled else 0) + (len(self._gacha_done) if gacha_enabled else 0)
                    progress = (done / total) if total > 0 else 1.0

                    if (not cycle_complete) and progress >= self._defer_completion_ratio:
                        self._maintenance_due_deferred = True
                    else:
                        self._maintenance_counter += 1
                        self._maintenance_enqueued = True
                        self._maintenance_due_deferred = False
                        self.add_task(watchdog_render_task(reason=f"timeout#{self._maintenance_counter}", request_berry=False))

            # Enqueue maintenance at the end of each full cycle, and request re-berry on the next gacha run.
            if cycle_complete and not self._maintenance_enqueued:
                self._maintenance_counter += 1
                self._maintenance_enqueued = True
                self._maintenance_due_deferred = False
                self.add_task(watchdog_render_task(reason=f"cycle_complete#{self._maintenance_counter}", request_berry=True))

            # If we deferred a watchdog because we were ~done, trigger it now that the cycle is complete.
            if cycle_complete and self._maintenance_due_deferred and not self._maintenance_enqueued:
                self._maintenance_counter += 1
                self._maintenance_enqueued = True
                self._maintenance_due_deferred = False
                self.add_task(watchdog_render_task(reason=f"deferred_cycle_complete#{self._maintenance_counter}", request_berry=True))

            # When maintenance runs, reset cycle tracking so the next cycle starts clean
            if isinstance(task, watchdog_render_task):
                self._pego_done.clear()
                self._gacha_done.clear()
                self._maintenance_enqueued = False
                self._maintenance_due_deferred = False

            # ------------------------------------------

            self.prev_task_name = task.name
            if task.name != "pause" and not getattr(task, 'one_shot', False):
                self.move_to_waiting_queue(task)
            elif getattr(task, 'one_shot', False):
                print("one-shot task complete, not re-queuing")
            else:
                print("pause task skipping adding back ")
        else:
            
            self.active_queue.add(task, priority, exec_time)

    def move_to_waiting_queue(self, task):
        logs.logger.debug(f"adding {task.name} to waiting queue" ) 
        next_execution_time = time.time() + task.get_requeue_delay()
        priority_level = task.get_priority_level()
        self.waiting_queue.add(task,priority_level , next_execution_time)



def _json_load_relaxed(raw: str, file_path: str):
    raw = (raw or "").lstrip("\ufeff").strip()
    if not raw:
        logs.logger.warning(f"warning: {file_path} is empty; no tasks added.")
        return []

    # Remove trailing commas before a closing '}' or ']'
    raw = re.sub(r',(?=\s*[}\]])', '', raw)

    try:
        obj, _ = json.JSONDecoder().raw_decode(raw)
        return obj
    except json.JSONDecodeError as e:
        logs.logger.error(f"error loading JSON from {file_path}: {e}")
        return []


def load_resolution_data(file_path):
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = (Path(__file__).resolve().parent / path).resolve()

        raw = path.read_text(encoding="utf-8")
        return _json_load_relaxed(raw, str(path))
    except FileNotFoundError as e:
        logs.logger.error(f"error loading JSON from {file_path}: {e}")
        return []
    except Exception as e:
        logs.logger.error(f"error loading JSON from {file_path}: {e}")
        return []

def main():
    global scheduler
    global started
    scheduler = task_scheduler()

    # Pego tasks
    if getattr(settings, "pego_enabled", True):
        pego_data = load_resolution_data("json_files/pego.json")
        for entry_pego in pego_data:
            name = entry_pego.get("name")
            teleporter = entry_pego.get("teleporter")
            delay = entry_pego.get("delay", 0)
            if not name or not teleporter:
                logs.logger.warning(f"[Startup:Pego] Invalid entry in pego.json: {entry_pego}")
                continue
            scheduler.add_task(stations.pego_station(name, teleporter, delay))
    else:
        logs.logger.info("[Startup] pego_enabled=False; pego tasks will not be scheduled.")

    # Gacha tasks (includes collect-type tasks)
    if getattr(settings, "gacha_enabled", True):
        gacha_data = load_resolution_data("json_files/gacha.json")
        for entry_gacha in gacha_data:
            name = entry_gacha.get("name")
            teleporter = entry_gacha.get("teleporter")
            direction = entry_gacha.get("side")
            resource = entry_gacha.get("resource_type")
            if not name or not teleporter:
                logs.logger.warning(f"[Startup:Gacha] Invalid entry in gacha.json: {entry_gacha}")
                continue

            if resource == "collect":
                depo = entry_gacha.get("depo_tp")
                if not depo:
                    logs.logger.warning(f"[Startup:Gacha] Missing depo_tp for collect task: {entry_gacha}")
                    continue
                task = stations.snail_pheonix(name, teleporter, direction, depo)
            else:
                task = stations.gacha_station(name, teleporter, direction)

            scheduler.add_task(task)
    else:
        logs.logger.info("[Startup] gacha_enabled=False; gacha tasks will not be scheduled.")

    # Crafting tasks (global crafting must be enabled, plus per-feature toggles)
    if getattr(settings, "crafting", False) and getattr(settings, "sparkpowder_enabled", False):
        sparkpowder_data = load_resolution_data("json_files/sparkpowder.json")
        for entry in sparkpowder_data:
            sp_name = entry.get("name") or entry.get("station_name") or entry.get("teleporter")
            sp_tp = entry.get("teleporter") or entry.get("station_name")
            sp_delay = entry.get("delay", 0)
            sp_height = entry.get("deposit_height", 2)
            sp_initial = entry.get("initial_delay", 0)
            if not sp_name or not sp_tp:
                logs.logger.warning(f"[Startup:Sparkpowder] Invalid entry in sparkpowder.json: {entry}")
                continue
            scheduler.add_task(stations.sparkpowder_station(sp_name, sp_tp, sp_delay, sp_height, initial_delay=sp_initial))
    else:
        if not getattr(settings, "crafting", False):
            logs.logger.info("[Startup] crafting=False; crafting tasks will not be scheduled.")
        elif not getattr(settings, "sparkpowder_enabled", False):
            logs.logger.info("[Startup] sparkpowder_enabled=False; sparkpowder tasks will not be scheduled.")

    if getattr(settings, "crafting", False) and getattr(settings, "gunpowder_enabled", False):
        gunpowder_data = load_resolution_data("json_files/gunpowder.json")
        for entry in gunpowder_data:
            gp_name = entry.get("name") or entry.get("station_name") or entry.get("teleporter")
            gp_tp = entry.get("teleporter") or entry.get("station_name")
            gp_delay = entry.get("delay", 0)
            gp_height = entry.get("deposit_height", 3)
            gp_initial = entry.get("initial_delay", 0)
            if not gp_name or not gp_tp:
                logs.logger.warning(f"[Startup:Gunpowder] Invalid entry in gunpowder.json: {entry}")
                continue
            scheduler.add_task(stations.gunpowder_station(gp_name, gp_tp, gp_delay, gp_height, initial_delay=gp_initial))
    else:
        if getattr(settings, "crafting", False) and not getattr(settings, "gunpowder_enabled", False):
            logs.logger.info("[Startup] gunpowder_enabled=False; gunpowder tasks will not be scheduled.")

    # Render must always be active
    scheduler.add_task(stations.render_station())

    logs.logger.info("scheduler now running")
    started = True
    scheduler.run()

if __name__ == "__main__":
    time.sleep(2)
    main()