import json
import re
from pathlib import Path
import sys
from core.llm_provider import call_llm

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()

def decompose(goal: str, preferred_brain: str = None) -> list[dict]:
    """Decompose a goal into a list of structured steps (task queue)."""
    from core.tools import TOOL_DECLARATIONS
    
    # Format project directory with forward slashes
    base_dir_str = str(BASE_DIR).replace("\\", "/")
    
    # Gather tool declarations
    tools_list = []
    for tool in TOOL_DECLARATIONS:
        tools_list.append(
            f"- Tool Name: {tool.get('name')}\n"
            f"  Description: {tool.get('description')}\n"
            f"  Parameters Schema: {json.dumps(tool.get('parameters', {}))}"
        )
    tools_str = "\n".join(tools_list)

    prompt = f"""You are the Master Planner for JARVIS. Your job is to break the following goal into a sequence of structured steps (subtasks).

GOAL: "{goal}"

PROJECT BASE DIRECTORY: "{base_dir_str}"
You MUST perform all operations, file writes, reads, checks, and cleanups within this directory. Never use default placeholder paths like C:/JARVIS.

AVAILABLE SYSTEM TOOLS:
{tools_str}

Output MUST be a JSON list of objects. Each step in the list must match this schema:
{{
  "step": 1,
  "tool": "tool_name",
  "command": "The shell command to run if using shell_runner, otherwise empty string",
  "description": "Short explanation of what this step does",
  "file_path": "Absolute path to execute/write if code",
  "required_tool": "Optional external CLI tool name, e.g. npm, black",
  "install_cmd": "Optional installation command if the tool is missing, e.g. npm install -g create-react-app",
  "test_command": "Command to verify if this step succeeded, e.g. python -m py_compile main.py",
  "prompt": "Generative prompt/instruction for the subtask"
}}

IMPORTANT: If a tool requires additional parameters, you MUST add them as top-level keys directly in the step object.
For example:
- For `self_improvement`, you MUST include "action": "run_audit" or "action": "optimize_tool", "tool_name": "name".
- For `preference_manager`, you MUST include "action": "set", "preference_key": "Proactive Tasks", "value": "disabled".

Rules:
- Return ONLY a JSON list of objects, no markdown fences, no explanations.
- Limit steps to 1-5.
- CRITICAL: Prioritize using native tools (e.g. `self_improvement`, `preference_manager`, `file_controller`) instead of running shell scripts with `shell_runner` when a specific native tool exists for the goal.
- CRITICAL: You are running on Windows. DO NOT use Linux paths like /usr/local/bin. Use Windows paths with forward slashes starting with "{base_dir_str}" to prevent JSON escape errors.
- CRITICAL: DO NOT invent tools. If no specific native tool exists, use `shell_runner` for shell/command-line operations, or `generated_code` to execute Python code.
- CRITICAL: The default shell is PowerShell. ALWAYS use standard PowerShell cmdlets (e.g., Get-ChildItem, Remove-Item). DO NOT use cmd.exe aliases or flags (like dir /s /b).
"""
    try:
        raw = call_llm(prompt, system_prompt="You are a brilliant master planner.", brain=preferred_brain)
        # Extract the JSON array block safely
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"[MasterPlanner] Error decomposing goal: {e}")
        # Return a single fallback step
        return [{
            "step": 1,
            "tool": "generated_code",
            "description": goal,
            "file_path": "",
            "test_command": "",
            "prompt": goal
        }]
