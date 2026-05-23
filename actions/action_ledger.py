import json
from pathlib import Path
from datetime import datetime
import threading

BASE_DIR = Path(__file__).resolve().parent.parent
LEDGER_PATH = BASE_DIR / "memory" / "action_ledger.json"
MAX_ACTIONS = 100

_ledger_lock = threading.Lock()

def _load_ledger() -> list:
    if not LEDGER_PATH.exists():
        return []
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_ledger(data: list):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

def log_action(source: str, action_details: str):
    """
    Logs an action to the rolling ledger.
    Args:
        source: e.g. "shell_runner", "file_controller"
        action_details: What actually happened (e.g. "Executed: start /b python web.py")
    """
    with _ledger_lock:
        ledger = _load_ledger()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{source}] {action_details}"
        
        ledger.append(entry)
        if len(ledger) > MAX_ACTIONS:
            ledger = ledger[-MAX_ACTIONS:]
            
        _save_ledger(ledger)
        print(f"[Ledger] Logged: {entry}")

def get_recent_actions() -> str:
    """
    Returns a formatted string of the most recent actions for context injection.
    """
    with _ledger_lock:
        ledger = _load_ledger()
        
    if not ledger:
        return "No recent background actions."
        
    return "Recent JARVIS Actions (Use this context to understand what was just created or executed):\n" + "\n".join(ledger)
