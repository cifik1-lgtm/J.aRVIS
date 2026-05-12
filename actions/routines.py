import threading
import time
import datetime

try:
    import schedule
    HAS_SCHEDULE = True
except ImportError:
    HAS_SCHEDULE = False

_routines_thread = None
_running = False
_queue_ref = None

def run_pending():
    while _running:
        try:
            schedule.run_pending()
        except Exception:
            pass
        time.sleep(1)

def start_routines(queue):
    global _routines_thread, _running, _queue_ref
    if not HAS_SCHEDULE: return
    _queue_ref = queue
    if _routines_thread is None:
        _running = True
        _routines_thread = threading.Thread(target=run_pending, daemon=True)
        _routines_thread.start()

def routine_manager(parameters: dict, player=None) -> str:
    if not HAS_SCHEDULE:
        return "Schedule library is missing. Run: python -m pip install schedule"
        
    action = parameters.get("action", "list")
    
    if action == "add":
        time_str = parameters.get("time", "08:00")
        task = parameters.get("task", "")
        if not task: return "No task provided."
        
        from agent.task_queue import TaskPriority
        
        def job_func():
            if _queue_ref:
                _queue_ref.submit(goal=f"Scheduled Routine: {task}", priority=TaskPriority.NORMAL)
                if player:
                    player.write_log(f"SYS: Running scheduled routine: {task}")
            
        schedule.every().day.at(time_str).do(job_func).tag(task)
        return f"Scheduled background routine '{task}' every day at {time_str}."
        
    elif action == "list":
        jobs = schedule.get_jobs()
        if not jobs: return "No active routines."
        res = "Active Background Routines:\n"
        for j in jobs:
            res += f"- '{j.tags[0]}' at {j.next_run}\n"
        return res
        
    elif action == "clear":
        schedule.clear()
        return "All background routines have been cleared."
        
    return "Unknown action."
