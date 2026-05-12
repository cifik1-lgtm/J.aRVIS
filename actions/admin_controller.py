"""
Admin Controller - Full system command execution with admin rights
"""

import subprocess
import os
import sys
import ctypes
import time
from pathlib import Path

def is_admin() -> bool:
    """Check if running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def run_as_admin(command: str, args: str = "") -> bool:
    """Relaunch a command with admin rights"""
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", command, args, None, 1
        )
        return True
    except:
        return False

def execute_admin_command(command: str, timeout: int = 60, use_powershell: bool = False) -> dict:
    """Execute a system command with admin privileges"""
    result = {
        "success": False,
        "stdout": "",
        "stderr": "",
        "exit_code": -1
    }
    
    try:
        if use_powershell:
            cmd = ["powershell", "-Command", command]
        else:
            cmd = ["cmd", "/c", command]
        
        # Run with admin flag
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False
        )
        
        result["success"] = process.returncode == 0
        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
        result["exit_code"] = process.returncode
        
    except subprocess.TimeoutExpired:
        result["stderr"] = f"Command timed out after {timeout} seconds"
    except Exception as e:
        result["stderr"] = str(e)
    
    return result

def execute_python(code: str, timeout: int = 30) -> dict:
    """Execute Python code with full permissions"""
    result = {
        "success": False,
        "output": "",
        "error": "",
        "executed": False
    }
    
    try:
        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        # Execute the Python file
        process = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        result["success"] = process.returncode == 0
        result["output"] = process.stdout
        result["error"] = process.stderr
        result["executed"] = True
        
        # Clean up temp file
        os.unlink(temp_file)
        
    except subprocess.TimeoutExpired:
        result["error"] = f"Python code timed out after {timeout} seconds"
    except Exception as e:
        result["error"] = str(e)
    
    return result

def get_system_commands() -> dict:
    """Get available system commands"""
    return {
        "network": ["ipconfig", "ping", "netstat", "tracert", "nslookup"],
        "system": ["systeminfo", "tasklist", "taskkill", "shutdown", "powershell"],
        "disk": ["chkdsk", "diskpart", "wmic diskdrive", "fsutil"],
        "user": ["whoami", "net user", "net localgroup", "query user"],
        "process": ["tasklist", "taskkill /F /IM", "wmic process"]
    }

def admin_controller(parameters: dict, player=None) -> str:
    """Main handler for admin commands"""
    action = parameters.get("action", "")
    command = parameters.get("command", "")
    python_code = parameters.get("code", "")
    timeout = parameters.get("timeout", 60)
    use_powershell = parameters.get("use_powershell", False)
    
    result = ""
    
    if action == "run_command":
        # Check admin status
        if not is_admin():
            result = "⚠️ Command requires administrator privileges. Attempting to elevate..."
            run_as_admin("cmd.exe", f"/c {command}")
            return "Elevation requested. Please approve the UAC prompt."
        
        # Execute command
        output = execute_admin_command(command, timeout, use_powershell)
        if output["success"]:
            result = f"✅ Command executed successfully:\n{output['stdout'][:500]}"
            if output["stderr"]:
                result += f"\n⚠️ Warnings:\n{output['stderr'][:200]}"
        else:
            result = f"❌ Command failed:\n{output['stderr'][:300]}"
    
    elif action == "run_python":
        # Execute Python code
        output = execute_python(python_code, timeout)
        if output["success"]:
            result = f"✅ Python code executed:\n{output['output'][:500]}"
        else:
            result = f"❌ Python execution failed:\n{output['error'][:300]}"
    
    elif action == "elevate_jarvis":
        # Elevate the entire JARVIS process
        if not is_admin():
            run_as_admin(sys.executable, " ".join(sys.argv))
            result = "🔄 Restarting JARVIS with administrator privileges..."
            import time
            time.sleep(2)
            os._exit(0)
        else:
            result = "✅ JARVIS is already running with administrator privileges."
    
    elif action == "check_admin":
        if is_admin():
            result = "✅ JARVIS has administrator privileges."
        else:
            result = "⚠️ JARVIS is running without administrator privileges. Use 'elevate_jarvis' to restart as admin."
    
    elif action == "list_commands":
        commands = get_system_commands()
        result = "📋 Available system commands:\n"
        for category, cmds in commands.items():
            result += f"\n{category.upper()}: {', '.join(cmds[:5])}"
    
    else:
        result = f"Unknown action: {action}. Available: run_command, run_python, elevate_jarvis, check_admin, list_commands"
    
    if player:
        player.write_log(f"[Admin] {result[:200]}")
    
    return result
