import subprocess
import os
from pathlib import Path

def git_manager(parameters: dict, player=None) -> str:
    """
    Manages Git repositories: clone, pull, push, commit, status.
    parameters:
        action : clone | pull | push | commit | status | init
        url    : Repository URL (for clone)
        path   : Local repository path
        message: Commit message
    """
    p = parameters or {}
    action = p.get("action", "status").lower().strip()
    url = p.get("url", "").strip()
    repo_path = p.get("path", "").strip()
    message = p.get("message", "Auto-commit by JARVIS").strip()

    if not repo_path:
        repo_path = str(Path.home() / "Desktop" / "JarvisProjects")
    
    if action == "clone":
        if not url: return "Please provide a repository URL, sir."
        try:
            result = subprocess.run(["git", "clone", url], capture_output=True, text=True, cwd=repo_path)
            if result.returncode == 0: return f"Repository cloned successfully to {repo_path}."
            return f"Clone failed: {result.stderr}"
        except Exception as e: return f"Git error: {e}"

    if action == "status":
        try:
            result = subprocess.run(["git", "status"], capture_output=True, text=True, cwd=repo_path)
            return result.stdout or result.stderr
        except Exception as e: return f"Git error: {e}"

    if action == "commit":
        try:
            subprocess.run(["git", "add", "."], cwd=repo_path)
            result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True, cwd=repo_path)
            return result.stdout or result.stderr
        except Exception as e: return f"Git error: {e}"

    return f"Action '{action}' not fully implemented, but I can add it if you need, sir!"
