"""
JARVIS Self-Healing Engine v2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Modes:
  • heal_file   — Fix a specific file given an error message (original behavior)
  • audit       — Scan the error ledger, find recurring patterns, auto-patch source
  • report      — Return a human-readable summary of all logged errors
  • clear       — Wipe the error ledger after a clean run
"""

import json
import re
from pathlib import Path
from collections import Counter
from core.llm_provider import call_llm

BASE_DIR     = Path(__file__).resolve().parent.parent
LEDGER_PATH  = BASE_DIR / "memory" / "file_errors.json"
REPORT_PATH  = BASE_DIR / "memory" / "self_healing_report.json"


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _read_ledger() -> list:
    if not LEDGER_PATH.exists():
        return []
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_ledger(ledger: list):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def _clean_code(code: str) -> str:
    """Strip markdown fences if the model added them."""
    if "```" in code:
        code = re.sub(r"```[a-zA-Z]*\n?", "", code).replace("```", "")
    return code.strip()


def _resolve_source_file(name: str) -> Path | None:
    """Try to locate a JARVIS source file by partial name."""
    try:
        p = Path(name)
        if p.exists() and p.is_file():
            return p
    except Exception:
        pass

    # Check last project location memory fallback
    try:
        from memory.memory_manager import retrieve_memory
        last_loc = retrieve_memory("last_project_location", "notes")
        if last_loc and isinstance(last_loc, dict) and "value" in last_loc:
            loc_path = Path(last_loc["value"]) / name
            if loc_path.exists() and loc_path.is_file():
                return loc_path
    except Exception:
        pass

    candidates = [
        BASE_DIR / name,
        BASE_DIR / "actions" / name,
        BASE_DIR / "agent"   / name,
        BASE_DIR / "core"    / name,
    ]
    for c in candidates:
        if c.exists():
            return c
    # fuzzy: walk actions/ and core/
    for folder in [BASE_DIR / "actions", BASE_DIR / "core", BASE_DIR / "agent"]:
        for f in folder.glob("*.py"):
            if name.lower() in f.name.lower():
                return f
    return None


# ─────────────────────────────────────────────────────────────
#  Web Search — look up an error online before patching
# ─────────────────────────────────────────────────────────────

def _web_search_error(error_message: str, context: str = "") -> str:
    """Search the web for the error and return a summary of solutions."""
    try:
        from actions.ghost_browser import ghost_browser
        # Trim to the most informative part of the error
        short_err = error_message[:150].strip()
        query = f"python fix: {short_err}"
        if context:
            query = f"python {context} fix: {short_err}"
        result = ghost_browser(parameters={"action": "search", "query": query})
        if result and len(str(result)) > 20:
            return f"[Web Research]\n{str(result)[:1500]}"
    except Exception as e:
        pass  # Web search is optional — never crash the healer
    return ""

# ─────────────────────────────────────────────────────────────

def _heal_file(target_file: str, error_message: str, player=None) -> str:
    path = _resolve_source_file(target_file)
    if not path:
        return f"❌ File not found: {target_file}"

    try:
        current_code = path.read_text(encoding="utf-8")

        # Step 1: Search the web for a solution first
        if player:
            player.write_log(f"🌐 Searching web for fix: {error_message[:60]}...")
        web_context = _web_search_error(error_message, context=path.name)

        prompt = (
            f"You are an advanced AI self-healing agent inside the JARVIS system.\n"
            f"A python file crashed with an error. Fix the bug.\n\n"
            f"File: {path.name}\n"
            f"Error: {error_message}\n\n"
            + (f"{web_context}\n\n" if web_context else "")
            + f"Current Code:\n{current_code}\n\n"
            f"Rules: Return ONLY the full corrected python code. No markdown. No explanations."
        )
        if player:
            player.write_log(f"🛠️ Self-healing: {path.name}")

        fixed_code = _clean_code(call_llm(prompt))
        path.write_text(fixed_code, encoding="utf-8")

        # Log the heal to the report
        _append_report({
            "mode": "heal_file",
            "file": path.name,
            "error": error_message,
            "status": "healed"
        })

        if player:
            player.write_log(f"✅ Healed: {path.name}")
        return f"✅ Successfully healed {path.name}."

    except Exception as e:
        return f"❌ Self-healing failed: {e}"


# ─────────────────────────────────────────────────────────────
#  Mode 2 — Audit the error ledger and auto-patch
# ─────────────────────────────────────────────────────────────

def _audit(player=None) -> str:
    ledger = _read_ledger()
    if not ledger:
        return "✅ Error ledger is empty — no recurring issues found."

    # Count errors by (action, error_type)
    counter = Counter()
    error_groups: dict[str, list] = {}
    for entry in ledger:
        key = f"{entry.get('action','?')}::{entry.get('error','?')[:80]}"
        counter[key] += 1
        error_groups.setdefault(key, []).append(entry)

    # Focus on errors that happened more than once
    recurring = {k: v for k, v in counter.items() if v >= 2}

    if not recurring:
        return (
            f"📋 Ledger has {len(ledger)} error(s), none recurring yet. "
            f"Most recent: {ledger[-1].get('error','?')}"
        )

    lines = [f"🔍 Found {len(recurring)} recurring error pattern(s):"]
    healed = []

    for key, count in sorted(recurring.items(), key=lambda x: -x[1]):
        action, err = key.split("::", 1)
        sample = error_groups[key][0]
        lines.append(f"\n  • [{count}x] action='{action}' | error='{err[:60]}'")

        # Try to infer which source file to patch
        # Map known actions to their source files
        action_to_file = {
            "file_controller": "file_controller.py",
            "write":           "file_controller.py",
            "read":            "file_controller.py",
            "code_helper":     "code_helper.py",
            "code_agent":      "code_agent.py",
            "browser_control": "browser_control.py",
            "shell_runner":    "shell_runner.py",
        }
        source_file = action_to_file.get(action, "file_controller.py")
        path = _resolve_source_file(source_file)

        if path and path.exists():
            try:
                current_code = path.read_text(encoding="utf-8")
                prompt = (
                    f"You are the JARVIS self-healing AI.\n"
                    f"The following error has occurred {count} times in '{source_file}':\n\n"
                    f"Action: {action}\n"
                    f"Error: {err}\n"
                    f"Example path: {sample.get('path','')}\n"
                    f"Example name: {sample.get('name','')}\n\n"
                    f"Current source code:\n{current_code}\n\n"
                    f"Task: Patch the bug so this error never happens again. "
                    f"Return ONLY the complete corrected Python code. No markdown. No explanation."
                )
                if player:
                    player.write_log(f"🛠️ Auto-patching {source_file} for '{action}' error...")

                fixed = _clean_code(call_llm(prompt))
                if len(fixed) > 200:  # sanity check — don't write empty responses
                    path.write_text(fixed, encoding="utf-8")
                    healed.append(source_file)
                    lines.append(f"    → ✅ Auto-patched {source_file}")
                    _append_report({
                        "mode": "audit_patch",
                        "file": source_file,
                        "action": action,
                        "error": err,
                        "occurrences": count,
                        "status": "auto-patched"
                    })
            except Exception as e:
                lines.append(f"    → ❌ Patch failed: {e}")

    # Clear healed errors from ledger
    if healed:
        remaining = [e for e in ledger if e.get("action") not in
                     [k.split("::")[0] for k in recurring]]
        _save_ledger(remaining)
        lines.append(f"\n🧹 Cleared {len(ledger)-len(remaining)} resolved error(s) from ledger.")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  Mode 3 — Report
# ─────────────────────────────────────────────────────────────

def _report() -> str:
    ledger = _read_ledger()
    if not ledger:
        return "✅ No errors logged. JARVIS is running cleanly."

    counter = Counter(e.get("action", "?") for e in ledger)
    lines = [f"📊 JARVIS Error Report — {len(ledger)} total error(s):"]
    for action, count in counter.most_common(10):
        lines.append(f"  • {action}: {count}x")
    last = ledger[-1]
    lines.append(f"\n🕐 Last error: [{last.get('timestamp','')}] {last.get('action')} — {last.get('error','')[:80]}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  Mode 4 — Clear ledger
# ─────────────────────────────────────────────────────────────

def _clear() -> str:
    if LEDGER_PATH.exists():
        _save_ledger([])
        return "🧹 Error ledger cleared."
    return "Ledger was already empty."


# ─────────────────────────────────────────────────────────────
#  Report helper
# ─────────────────────────────────────────────────────────────

def _append_report(entry: dict):
    import datetime
    entry["timestamp"] = datetime.datetime.now().isoformat()
    report = []
    if REPORT_PATH.exists():
        try:
            report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        except Exception:
            report = []
    report.append(entry)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report[-500:], indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
#  Public entry point
# ─────────────────────────────────────────────────────────────

def self_healing(parameters: dict, player=None) -> str:
    mode         = parameters.get("mode", "heal_file").lower()
    target_file  = parameters.get("target_file", parameters.get("file_name", ""))
    error_message = parameters.get("error_message", "")

    if mode == "heal_file":
        if not target_file or not error_message:
            return "❌ heal_file mode requires 'target_file' and 'error_message'."
        return _heal_file(target_file, error_message, player)

    elif mode == "audit":
        return _audit(player)

    elif mode == "report":
        return _report()

    elif mode == "clear":
        return _clear()

    else:
        # Legacy support: if old code passes target_file + error_message without mode
        if target_file and error_message:
            return _heal_file(target_file, error_message, player)
        return "❌ Unknown mode. Use: heal_file | audit | report | clear"
