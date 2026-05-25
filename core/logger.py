import time
from datetime import datetime
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "memory" / "chronos_execution_log.json"

def log_success(task: dict, duration: float = 0.0):
    """Write a timestamped success log to execution history."""
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "step": task.get("step", 1),
        "tool": task.get("tool", "unknown"),
        "description": task.get("description", ""),
        "file_path": task.get("file_path", ""),
        "duration": duration,
        "status": "SUCCESS"
    }
    
    print(f"📝 [LOGGER] Success log: {log_entry['description']}")
    
    try:
        logs = []
        if LOG_FILE.exists():
            try:
                logs = json.loads(LOG_FILE.read_text(encoding="utf-8"))
                if not isinstance(logs, list):
                    logs = []
            except Exception:
                logs = []
        logs.append(log_entry)
        LOG_FILE.write_text(json.dumps(logs[-500:], indent=2), encoding="utf-8")
    except Exception as e:
        print(f"❌ [LOGGER] Failed to write success log: {e}")
