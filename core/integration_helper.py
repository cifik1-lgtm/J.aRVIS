"""
JARVIS Core Integration Helper - Configuration and logging utilities
"""

import os
import json
import threading
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "integration_config.json"
LOG_PATH = BASE_DIR / "memory" / "integration_log.json"

_lock = threading.Lock()

def load_integration_config() -> dict:
    """Load integration configuration settings with safe fallbacks."""
    default_config = {
        "rag_memory_injection": True,
        "dynamic_tool_registration": True,
        "rag_expert_skills": True
    }
    
    if not CONFIG_PATH.exists():
        return default_config
        
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            # Merge to ensure all keys exist
            return {**default_config, **user_config}
    except Exception as e:
        print(f"[IntegrationHelper] ⚠️ Error loading config: {e}. Using defaults.")
        return default_config

def log_integration_event(event_type: str, details: dict):
    """Safely log integration events with a thread lock to prevent file corruption."""
    config = load_integration_config()
    # Respect config toggle
    if not config.get("dynamic_tool_registration", True) and event_type == "tool_registration":
        return
    if not config.get("rag_memory_injection", True) and event_type == "rag_query":
        return
    if not config.get("rag_expert_skills", True) and event_type == "expert_skills_exec":
        return

    with _lock:
        try:
            logs = []
            if LOG_PATH.exists():
                try:
                    with open(LOG_PATH, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                except Exception:
                    pass
            
            entry = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "details": details
            }
            logs.append(entry)
            
            # Prevent log bloat by keeping last 500 entries
            logs = logs[-500:]
            
            # Ensure parent directory exists
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[IntegrationHelper] ❌ Failed to log integration event: {e}")
