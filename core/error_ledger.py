"""
error_ledger.py — Central error logging for JARVIS self-healing.

Any module that catches a meaningful error should call log_error() so the
self_fix 'audit' mode can see it, count recurring patterns, and auto-patch.

Ledger file: memory/file_errors.json  (same file that actions/self_healing.py reads)
"""

import json
import traceback
import re
from pathlib import Path
from datetime import datetime

BASE_DIR     = Path(__file__).resolve().parent.parent
LEDGER_PATH  = BASE_DIR / "memory" / "file_errors.json"
MAX_ENTRIES  = 500  # keep ledger from growing forever


def _read() -> list:
    if not LEDGER_PATH.exists():
        return []
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write(ledger: list):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger[-MAX_ENTRIES:], indent=2), encoding="utf-8")


def _infer_source_file(error_msg: str, action: str = "") -> str:
    """Try to extract a JARVIS source filename from a traceback string."""
    # Look for File "...CifikAI/something.py" patterns
    matches = re.findall(
        r'File ["\']([^"\']+\.py)["\']',
        error_msg or ""
    )
    for m in reversed(matches):
        p = Path(m)
        # Only report our own files, not site-packages
        if "CifikAI" in str(p) or BASE_DIR.name in str(p):
            return p.name
    # Fallback: map action name to file
    _MAP = {
        "file_controller":  "file_controller.py",
        "code_helper":      "code_helper.py",
        "browser_control":  "browser_control.py",
        "shell_runner":     "shell_runner.py",
        "ghost_browser":    "ghost_browser.py",
        "delegate_task":    "task_queue.py",
        "self_fix":         "self_healing.py",
    }
    return _MAP.get(action, "unknown")


def log_error(
    error: str,
    action: str = "",
    source_file: str = "",
    goal: str = "",
    extra: dict | None = None,
):
    """Append one error entry to the shared ledger.

    Args:
        error:       The exception / error message string.
        action:      The tool or action name that failed (e.g. 'delegate_task').
        source_file: The Python file responsible (auto-detected if blank).
        goal:        The task goal string, for context.
        extra:       Any additional key/value pairs to store.
    """
    if not source_file:
        source_file = _infer_source_file(error, action)

    entry = {
        "timestamp":   datetime.now().isoformat(),
        "action":      action or "unknown",
        "source_file": source_file,
        "error":       str(error)[:500],   # cap length
        "goal":        str(goal)[:200],
    }
    if extra:
        entry.update(extra)

    ledger = _read()
    ledger.append(entry)
    _write(ledger)

    print(f"[ErrorLedger] 📝 Logged: [{action}] {str(error)[:80]}")
