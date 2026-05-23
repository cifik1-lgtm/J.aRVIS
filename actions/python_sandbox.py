import sys
import subprocess
import tempfile
import os
import shutil
import textwrap
from pathlib import Path

def is_docker_available() -> bool:
    """Checks if docker command is available and the daemon is responsive."""
    if not shutil.which("docker"):
        return False
    try:
        # Run docker ps to verify daemon is responsive
        res = subprocess.run(
            ["docker", "ps"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3
        )
        return res.returncode == 0
    except Exception:
        return False

def python_sandbox(parameters: dict, player=None) -> str:
    code = parameters.get("code", "")
    if not code:
        return "No code provided to execute."
        
    code = textwrap.dedent(code)
    timeout = parameters.get("timeout", 30)
    
    # Check if we should use docker or subprocess fallback
    use_docker = is_docker_available()
    
    if use_docker:
        if player:
            player.write_log("Sandbox: Running code inside secure Docker container (python:3.10-slim)...")
        print("[Sandbox] [DOCKER] Running inside secure Docker container...")
        try:
            # Run docker container passing code via stdin
            cmd = [
                "docker", "run", "--rm", "-i",
                "--memory=256m",
                "--cpus=0.5",
                "--network=none",  # disable network for maximum sandbox isolation
                "python:3.10-slim", "python"
            ]
            res = subprocess.run(
                cmd,
                input=code,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            
            output = []
            if stdout:
                output.append(f"Execution Output:\n{stdout}")
            if stderr:
                output.append(f"Execution Error/Stderr:\n{stderr}")
            if res.returncode != 0 and not stderr:
                output.append(f"Process exited with non-zero code: {res.returncode}")
                
            return "\n".join(output) if output else "Code executed successfully with no output."
            
        except subprocess.TimeoutExpired:
            return f"Execution Error: Code timed out after {timeout} seconds inside the container."
        except Exception as e:
            return f"Execution Error setting up Docker: {e}"
            
    else:
        # Fallback to local subprocess execution (safer than exec() in the main process)
        if player:
            try:
                player.write_log("Sandbox: [WARN] Docker unavailable. Falling back to isolated local Python subprocess...")
            except Exception:
                pass
        print("[Sandbox] [WARN] Docker not found/responsive. Running in local Python subprocess...")
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name
            
        try:
            # Run subprocess with timeout
            # We clean environment variables to prevent access to credentials
            env = os.environ.copy()
            # Remove sensitive variables
            for key in list(env.keys()):
                if any(k in key.lower() for k in ["key", "token", "secret", "passwd", "password", "api"]):
                    env.pop(key)
                    
            res = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            
            output = []
            if stdout:
                output.append(f"Execution Output:\n{stdout}")
            if stderr:
                output.append(f"Execution Error/Stderr:\n{stderr}")
            if res.returncode != 0 and not stderr:
                output.append(f"Process exited with non-zero code: {res.returncode}")
                
            return "\n".join(output) if output else "Code executed successfully with no output."
            
        except subprocess.TimeoutExpired:
            return f"Execution Error: Code timed out after {timeout} seconds."
        except Exception as e:
            return f"Execution Error: {e}"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
