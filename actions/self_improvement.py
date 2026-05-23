import json
from pathlib import Path
from datetime import datetime
from actions.self_healing import self_healing

BASE_DIR = Path(__file__).resolve().parent.parent
IMPROVEMENT_LOG = BASE_DIR / "memory" / "self_improvement_log.json"

def _log_improvement(action: str, details: str, status: str):
    IMPROVEMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    logs = []
    if IMPROVEMENT_LOG.exists():
        try:
            logs = json.loads(IMPROVEMENT_LOG.read_text(encoding="utf-8"))
        except Exception:
            logs = []
            
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
        "status": status
    })
    
    try:
        IMPROVEMENT_LOG.write_text(json.dumps(logs[-100:], indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[SelfImprovement] [ERROR] Failed to write improvement log: {e}")

def self_improvement(parameters: dict, player=None) -> str:
    action = parameters.get("action", "run_audit").lower()
    
    if action == "run_audit":
        if player:
            try:
                player.write_log("SelfImprovement: [INFO] Scanning error ledger for recurring issues...")
            except Exception:
                pass
            
        print("[SelfImprovement] [INFO] Auditing error logs...")
        
        # Trigger self-healing audit mode
        audit_params = {"mode": "audit"}
        result = self_healing(audit_params, player=player)
        
        # Log success/failure
        status = "success" if "❌" not in result else "failed"
        _log_improvement("error_audit", result, status)
        
        # Also clean up cached modules in ToolDispatcher if they were healed
        # The hot_reload tool or dispatch reloading handles actual module refresh.
        if "Auto-patched" in result:
            if player and hasattr(player, "tools") and hasattr(player.tools, "_tool_cache"):
                player.tools._tool_cache.clear()
                print("[SelfImprovement] [INFO] Cleared tool dispatcher cache to load patched modules.")
                
        return f"Self-Improvement Audit Result:\n{result}"
        
    elif action == "status":
        if not IMPROVEMENT_LOG.exists():
            return "No self-improvement logs recorded yet."
        try:
            logs = json.loads(IMPROVEMENT_LOG.read_text(encoding="utf-8"))
            lines = ["📈 JARVIS Self-Improvement Ledger:"]
            for log in logs[-10:]:
                lines.append(f"  • [{log.get('timestamp','?')[:16]}] action='{log.get('action')}' | status='{log.get('status')}'")
                lines.append(f"    Details: {log.get('details')[:120]}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error reading ledger: {e}"
            
    elif action == "optimize_tool":
        tool_name = parameters.get("tool_name", "")
        if not tool_name:
            return "❌ optimize_tool requires 'tool_name' parameter."
            
        if player:
            player.write_log(f"SelfImprovement: 🛠️ Optimizing {tool_name}...")
            
        from actions.self_healing import _resolve_source_file
        path = _resolve_source_file(tool_name)
        if not path or not path.exists():
            return f"❌ Source file not found for: {tool_name}"
            
        try:
            current_code = path.read_text(encoding="utf-8")
            from core.llm_provider import call_llm
            prompt = (
                f"You are the JARVIS Self-Improvement System.\n"
                f"Optimize and enhance this Python tool for speed, clarity, and robust error handling.\n"
                f"File: {path.name}\n\n"
                f"Current Code:\n{current_code}\n\n"
                f"Task: Improve the code while keeping its external function signature and behavior unchanged. "
                f"Return ONLY the complete corrected Python code. No markdown. No explanation."
            )
            optimized_code = call_llm(prompt)
            # Remove markdown formatting if any
            import re
            optimized_code = re.sub(r"```[a-zA-Z]*\n?", "", optimized_code).replace("```", "").strip()
            
            if len(optimized_code) > 100:
                path.write_text(optimized_code, encoding="utf-8")
                _log_improvement("optimize_tool", f"Optimized {path.name}", "success")
                return f"✅ Successfully optimized {path.name}."
            else:
                return "❌ Optimization failed (empty or invalid output from model)."
        except Exception as e:
            _log_improvement("optimize_tool", f"Failed to optimize {tool_name}: {e}", "failed")
            return f"❌ Optimization failed: {e}"
            
    else:
        return f"❌ Unknown self-improvement action: {action}. Supported: run_audit | status | optimize_tool"
