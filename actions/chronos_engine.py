import json
import time
import threading
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
GOALS_PATH = BASE_DIR / "memory" / "proactive_goals.json"
CHRONOS_LOG_PATH = BASE_DIR / "memory" / "chronos_execution_log.json"

_chronos_lock = threading.Lock()

def _load_goals() -> list:
    if not GOALS_PATH.exists():
        # Create default goals if file doesn't exist
        default_goals = [
            {
                "name": "system_health_check",
                "goal": "Verify system resources, CPU, memory usage, and log status.",
                "interval_minutes": 15,
                "last_run": 0
            },
            {
                "name": "self_improvement_audit",
                "goal": "Run Self-Improvement Engine to audit error ledger and auto-patch recurring bugs.",
                "interval_minutes": 15,
                "last_run": 0
            },
            {
                "name": "verify_web_server",
                "goal": "Verify if the background web server is running and clean up any orphan server actions.",
                "interval_minutes": 5,
                "last_run": 0
            }
        ]
        GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOALS_PATH.write_text(json.dumps(default_goals, indent=2), encoding="utf-8")
        return default_goals
        
    try:
        return json.loads(GOALS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_goals(goals: list):
    try:
        GOALS_PATH.write_text(json.dumps(goals, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Chronos] ❌ Failed to save goals config: {e}")

def _log_execution(goal_name: str, status: str, result: str = ""):
    with _chronos_lock:
        logs = []
        if CHRONOS_LOG_PATH.exists():
            try:
                logs = json.loads(CHRONOS_LOG_PATH.read_text(encoding="utf-8"))
            except Exception:
                logs = []
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "goal_name": goal_name,
            "status": status,
            "result": result
        }
        logs.append(entry)
        # Cap logs at 100 entries
        try:
            CHRONOS_LOG_PATH.write_text(json.dumps(logs[-100:], indent=2), encoding="utf-8")
        except Exception:
            pass

class ChronosEngine:
    def __init__(self, task_queue, write_log=None):
        self.queue = task_queue
        self.write_log = write_log
        self.running = False
        self.thread = None
        self._check_interval_seconds = 30

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, name="ChronosEngineDaemon", daemon=True)
        self.thread.start()
        print("[Chronos] ✅ Chronos Engine daemon started.")
        if self.write_log:
            self.write_log("SYS: ⏳ Chronos Engine (Proactive Goal Setting) initialized.")

    def stop(self):
        self.running = False
        print("[Chronos] 🔴 Chronos Engine daemon stopped.")

    def _run_loop(self):
        # Initial sleep to allow the system to settle before executing proactive goals
        time.sleep(10)
        
        while self.running:
            try:
                goals = _load_goals()
                now = time.time()
                updated = False
                
                for goal_entry in goals:
                    name = goal_entry.get("name", "unnamed_goal")
                    goal_text = goal_entry.get("goal", "")
                    interval_mins = goal_entry.get("interval_minutes", 15)
                    last_run = goal_entry.get("last_run", 0)
                    is_enabled = goal_entry.get("enabled", True)
                    
                    # Check if it's time to run and if the goal is enabled
                    if is_enabled and (now - last_run >= (interval_mins * 60)):
                        print(f"[Chronos] 🕒 Time to execute proactive goal: {name}")
                        if self.write_log:
                            self.write_log(f"Chronos: 🎯 Triggering proactive task: '{name}'")
                        
                        # Set up the callback to log the task completion
                        def make_callback(g_name):
                            return lambda task_id, res: self._task_completed_callback(g_name, task_id, res)
                            
                        # Submit task to the task queue
                        # Import TaskPriority dynamically to avoid circular references
                        from agent.task_queue import TaskPriority
                        self.queue.submit(
                            goal=goal_text,
                            priority=TaskPriority.LOW,
                            on_complete=make_callback(name)
                        )
                        
                        goal_entry["last_run"] = now
                        updated = True
                        _log_execution(name, "queued", f"Submitted to TaskQueue at {datetime.now().strftime('%H:%M:%S')}")
                        
                if updated:
                    _save_goals(goals)
                    
            except Exception as e:
                print(f"[Chronos] ❌ Error in Chronos loop: {e}")
                
            time.sleep(self._check_interval_seconds)

    def _task_completed_callback(self, goal_name: str, task_id: str, result: str):
        print(f"[Chronos] ✅ Proactive task completed: {goal_name} (ID: {task_id})")
        if self.write_log:
            self.write_log(f"Chronos: ✅ Completed proactive task: '{goal_name}'")
        _log_execution(goal_name, "completed", f"Task ID: {task_id}. Result summary: {str(result)[:200]}")

def start_chronos_engine(task_queue, write_log=None):
    engine = ChronosEngine(task_queue, write_log)
    engine.start()
    return engine
