# shell_runner.py
"""
Shell Runner — Execute PowerShell/CMD/bash commands silently.
This is the right tool for: creating files, folders, editing content,
running scripts, installing packages, git ops, npm, etc.
No GUI windows ever open. Everything runs in the background.
"""

import os
import platform
import subprocess
import threading
from pathlib import Path
from actions.action_ledger import log_action

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

# Safety: block destructive system-level commands
_BLOCKED = [
    "rm -rf /", "format c:", "del /f /s /q c:\\",
    "rd /s /q c:\\", "mkfs", ":(){:|:&};:",  # fork bomb
    "shutdown", "reboot", "halt", "poweroff",
]

# Path shortcuts (same as file_controller)
def _resolve_path(raw: str) -> str:
    shortcuts = {
        "desktop":   str(Path.home() / "Desktop"),
        "downloads": str(Path.home() / "Downloads"),
        "documents": str(Path.home() / "Documents"),
        "home":      str(Path.home()),
    }
    s = (raw or "").strip().lower()
    for key, val in shortcuts.items():
        if s == key or s.startswith(key + "/") or s.startswith(key + "\\"):
            return raw.replace(s[:len(key)], val, 1)
    return raw


def _is_blocked(cmd: str) -> bool:
    cl = cmd.lower()
    return any(b in cl for b in _BLOCKED)


def run_shell(
    command: str,
    cwd: str = None,
    timeout: int = 30,
    shell_type: str = "auto",
) -> dict:
    """
    Run a shell command and return its output.

    Args:
        command:    The command string to run.
        cwd:        Working directory (supports shortcuts: desktop, home, etc.)
        timeout:    Max seconds to wait (default 30).
        shell_type: 'powershell' | 'cmd' | 'bash' | 'auto' (auto-detects by OS)

    Returns:
        dict with keys: success, stdout, stderr, returncode
    """
    if _is_blocked(command):
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Blocked: command contains a dangerous pattern.",
            "returncode": -1,
        }

    # Resolve cwd shortcut
    work_dir = None
    if cwd:
        resolved = _resolve_path(cwd)
        p = Path(resolved)
        if p.exists() and p.is_dir():
            work_dir = str(p)

    # Build the actual shell invocation
    if shell_type == "auto":
        shell_type = "powershell" if _OS == "Windows" else "bash"

    if shell_type == "powershell":
        argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
        use_shell = False
    elif shell_type == "cmd":
        argv = ["cmd", "/c", command]
        use_shell = False
    else:
        # bash / sh
        argv = command
        use_shell = True

    # STARTUPINFO: hide any console window on Windows
    si = None
    cf = 0
    if _OS == "Windows":
        si = subprocess.STARTUPINFO()
        si.dwFlags = subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        cf = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
            shell=use_shell,
            startupinfo=si,
            creationflags=cf,
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s.",
            "returncode": -1,
        }
    except FileNotFoundError as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Executable not found: {e}",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
        }


def shell_runner(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    JARVIS tool entry point for shell_runner.

    Parameters:
        command     (str, required) : The shell command to execute.
        cwd         (str, optional) : Working directory. Supports 'desktop', 'home', 'downloads', or any absolute path.
        timeout     (int, optional) : Max seconds to wait (default 30).
        shell_type  (str, optional) : 'powershell' | 'cmd' | 'bash' | 'auto'

    Examples:
        Create a folder:    command="mkdir C:\\Users\\eva\\Desktop\\my-site"
        Create a file:      command="New-Item -Path 'C:\\Users\\eva\\Desktop\\my-site\\index.html' -ItemType File"
        Write content:      command="Set-Content -Path 'index.html' -Value '<h1>Hello</h1>'" cwd="desktop/my-site"
        Install package:    command="pip install requests" cwd="home"
        Run Python script:  command="python main.py" cwd="desktop/my-project"
        List directory:     command="dir" shell_type="cmd" cwd="desktop"
        Git clone:          command="git clone https://github.com/user/repo.git" cwd="desktop"
    """
    params  = parameters or {}
    command = (params.get("command") or params.get("cmd") or "").strip()
    cwd     = params.get("cwd", "")
    timeout = int(params.get("timeout", 30))
    stype   = params.get("shell_type", "auto")

    if not command:
        return "Error: 'command' parameter is required."

    print(f"[Shell] 🖥️  Running: {command[:120]}  (cwd={cwd or 'default'})")
    if player:
        player.write_log(f"[Shell] {command[:80]}")

    log_action("shell_runner", f"Executed: {command} (cwd: {cwd or 'default'})")

    result = run_shell(command, cwd=cwd, timeout=timeout, shell_type=stype)

    # Build a clean response
    lines = []
    if result["success"]:
        lines.append(f"✅ Done (exit 0)")
    else:
        lines.append(f"⚠️ Exit code: {result['returncode']}")

    if result["stdout"]:
        out = result["stdout"]
        if len(out) > 2000:
            out = out[:2000] + "\n... [truncated]"
        lines.append(f"Output:\n{out}")

    if result["stderr"]:
        err = result["stderr"]
        if len(err) > 1000:
            err = err[:1000] + "\n... [truncated]"
        lines.append(f"Stderr:\n{err}")

    return "\n".join(lines) if lines else "Done."
