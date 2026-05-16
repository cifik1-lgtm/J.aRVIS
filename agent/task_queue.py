import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Any


class TaskStatus(Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    CANCELLED  = "cancelled"


class TaskPriority(Enum):
    LOW    = 3
    NORMAL = 2
    HIGH   = 1   


@dataclass(order=True)
class Task:
    priority:    int                       
    created_at:  float = field(compare=False)
    task_id:     str   = field(compare=False)
    goal:        str   = field(compare=False)
    status:      TaskStatus = field(compare=False, default=TaskStatus.PENDING)
    result:      Any        = field(compare=False, default=None)
    error:       str        = field(compare=False, default="")
    speak:       Any        = field(compare=False, default=None)   
    on_complete: Any        = field(compare=False, default=None)  
    preferred_brain: str    = field(compare=False, default=None)
    cancel_flag: threading.Event = field(compare=False, default_factory=threading.Event)


class TaskQueue:
    def __init__(self, max_concurrent: int = 1):
        self._queue:        list[Task]       = []
        self._lock:         threading.Lock   = threading.Lock()
        self._condition:    threading.Condition = threading.Condition(self._lock)
        self._tasks:        dict[str, Task]  = {} 
        self._running:      bool             = False
        self._worker_thread: threading.Thread | None = None
        self._max_concurrent = max_concurrent
        self._active_count   = 0
        self._executor       = None
        self.dispatcher      = None  
        self.base_dir        = Path(__file__).resolve().parent.parent
        self.telemetry_file  = self.base_dir / "memory" / "task_queue_telemetry.json"

    def _save_telemetry(self):
        try:
            data = self.get_all_statuses()
            # Only keep the last 50 tasks in history
            self.telemetry_file.write_text(json.dumps(data[-50:], indent=2), encoding="utf-8")
        except:
            pass

    def _get_executor(self):
        if self._executor is None:
            from agent.executor import AgentExecutor
            self._executor = AgentExecutor()
        return self._executor

    def start(self) -> None:
        if self._running:
            return
        self._running      = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="AgentTaskQueue"
        )
        self._worker_thread.start()
        print("[TaskQueue] ✅ Started")

    def stop(self) -> None:
        self._running = False
        with self._condition:
            self._condition.notify_all()
        print("[TaskQueue] 🔴 Stopped")

    def submit(
        self,
        goal:        str,
        priority:    TaskPriority = TaskPriority.NORMAL,
        speak:       Callable | None = None,
        on_complete: Callable | None = None,
        preferred_brain: str | None = None,
    ) -> str:

        # ===== AUTO-ROUTING: Code tasks to Qwen =====
        goal_lower = goal.lower()
        if any(word in goal_lower for word in ["code", "python", "script", "file", "write", "create", "debug", "develop"]):
            preferred_brain = "ollama"  # Use Qwen for code
            print(f"[TaskQueue] 🧠 Auto-routed code task to Qwen coder")

        # ===== GATE KEEPER: Universal Cross-PC Routing =====
        # Check BEFORE queuing if this command is meant for another PC
        goal_lower = goal.lower()
        # Skip if it's already a cloud relay command (prevent loops)
        if not goal.startswith("Cloud command:"):
            try:
                import json, re
                from pathlib import Path
                import sys
                cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
                my_name = json.loads(cfg_path.read_text(encoding="utf-8")).get("device_name", "").upper()
                
                # Detect if the command targets another specific PC
                target_pc = None
                if re.search(r"\b(?:on|in|to|for)?\s*eva\b", goal_lower) and my_name != "EVA": target_pc = "EVA"
                elif re.search(r"\b(?:on|in|to|for)?\s*cifik\b", goal_lower) and my_name != "CIFIK": target_pc = "CIFIK"
                
                if target_pc:
                    # Clean the command
                    clean = re.sub(r"(?i)\s*(?:on|in|to|for)\s+(eva|cifik)(\s+pc)?", "", goal).strip()
                    print(f"[TaskQueue] 🔀 GATE KEEPER: Rerouting '{clean}' to {target_pc}. Stopping locally.")
                    from actions.ghost_relay import publish_command
                    publish_command(target_pc, clean)
                    return "relayed"  # Stop here — do NOT execute locally
            except Exception as ge:
                pass  # If routing check fails, fall through to normal execution
        # ===== END GATE KEEPER =====

        task_id = str(uuid.uuid4())[:8]
        task    = Task(
            priority    = priority.value,
            created_at  = time.time(),
            task_id     = task_id,
            goal        = goal,
            speak       = speak,
            on_complete = on_complete,
            preferred_brain = preferred_brain,
        )

        with self._condition:
            self._queue.append(task)
            self._queue.sort(key=lambda t: (t.priority, t.created_at))
            self._tasks[task_id] = task
            self._condition.notify()
        self._save_telemetry()

        print(f"[TaskQueue] 📥 Task queued: [{task_id}] {goal[:60]}")
        return task_id

    def cancel(self, task_id: str) -> bool:

        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False

            task.cancel_flag.set()
            task.status = TaskStatus.CANCELLED
            print(f"[TaskQueue] 🚫 Task cancelled: [{task_id}]")
            return True

    def get_status(self, task_id: str) -> dict | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return {
                "task_id": task.task_id,
                "goal":    task.goal,
                "status":  task.status.value,
                "result":  task.result,
                "error":   task.error,
            }

    def get_all_statuses(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "task_id": t.task_id,
                    "goal":    t.goal[:50],
                    "status":  t.status.value,
                }
                for t in self._tasks.values()
            ]

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._queue if t.status == TaskStatus.PENDING)

    def _worker_loop(self) -> None:
        while self._running:
            task = None

            with self._condition:
                while self._running and not self._next_task():
                    self._condition.wait(timeout=1.0)
                task = self._next_task()
                if task:
                    task.status = TaskStatus.RUNNING
                    self._active_count += 1
                    try:
                        self._queue.remove(task)
                    except ValueError:
                        pass

            if task:
                threading.Thread(
                    target=self._run_task,
                    args=(task,),
                    daemon=True,
                    name=f"AgentTask-{task.task_id}"
                ).start()

    def _next_task(self) -> Task | None:
        if self._active_count >= self._max_concurrent:
            return None
        for task in self._queue:
            if task.status == TaskStatus.PENDING and not task.cancel_flag.is_set():
                return task
        return None

    def _run_task(self, task: Task) -> None:
        print(f"[TaskQueue] ▶️ Running: [{task.task_id}] {task.goal[:60]}")
        try:
            executor = self._get_executor()
            result   = executor.execute(
                goal            = task.goal,
                speak           = task.speak,
                cancel_flag     = task.cancel_flag,
                dispatcher      = self.dispatcher,
                preferred_brain = task.preferred_brain,
            )

            with self._lock:
                if task.cancel_flag.is_set():
                    task.status = TaskStatus.CANCELLED
                else:
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                self._active_count -= 1

            if task.on_complete and not task.cancel_flag.is_set():
                try:
                    task.on_complete(task.task_id, result)
                except Exception as e:
                    print(f"[TaskQueue] ⚠️ on_complete callback error: {e}")

            print(f"[TaskQueue] ✅ Completed: [{task.task_id}]")

        except Exception as e:
            with self._lock:
                task.status = TaskStatus.FAILED
                task.error  = str(e)
                self._active_count -= 1
            print(f"[TaskQueue] ❌ Failed: [{task.task_id}] {e}")

        self._save_telemetry()
        with self._condition:
            self._condition.notify()

_queue        = TaskQueue()
_queue_started = False
_queue_lock    = threading.Lock()


def get_queue() -> TaskQueue:
    global _queue_started
    with _queue_lock:
        if not _queue_started:
            _queue.start()
            _queue_started = True
    return _queue