"""
JARVIS Self-Healing Protocol - Automated error detection and code repair
"""

import os
import sys
import json
import traceback
import re
import shutil
from pathlib import Path
from datetime import datetime
from core.llm_provider import call_llm

class SelfHealingProtocol:
    def __init__(self, ui=None, self_audit=None):
        self.ui = ui
        self.self_audit = self_audit
        self.base_dir = Path(__file__).resolve().parent.parent
        self.backups_dir = self.base_dir / "memory" / "backups"
        self.backups_dir.mkdir(exist_ok=True)
        # Files the self-healer must NEVER overwrite (manually verified fixes or too large for LLM)
        self.EXEMPT_FILES = {
            "audio_master.py",  # Uses EndpointVolume - LLM keeps breaking with Activate()
            "main.py",          # Too large (1800+ lines) - LLM will timeout or corrupt it
            "tools.py",         # Critical routing file - too large for safe LLM repair
            "brain_router.py",  # Core routing logic - manual fixes only
        }

    def log(self, message):
        print(f"[SelfHealing] {message}")
        if self.ui:
            self.ui.write_log(f"🛠️ {message}")
        
        # Dashboard Telemetry
        try:
            log_file = self.base_dir / "memory" / "self_healing_logs.json"
            logs = []
            if log_file.exists():
                logs = json.loads(log_file.read_text(encoding="utf-8"))
            logs.append({"timestamp": datetime.now().isoformat(), "message": message})
            log_file.write_text(json.dumps(logs[-100:], indent=2), encoding="utf-8")
        except:
            pass

    def create_backup(self, file_path: Path):
        """
        Create a safety backup before editing.
        Uses a sanitized relative path in the backup name to avoid collisions
        if files with the same name exist in different subdirectories.
        """
        try:
            rel_path = file_path.relative_to(self.base_dir)
            # e.g., 'core/llm_provider.py' -> 'core__llm_provider.py'
            sanitized_name = str(rel_path).replace(os.sep, '__')
            backup_path = self.backups_dir / f"{sanitized_name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception as e:
            self.log(f"Error creating backup for {file_path}: {e}")
            return None

    def _find_file(self, filename: str) -> Path:
        """Search the entire workspace for a filename if the path is unknown"""
        filename = filename.replace("\\", "/").split("/")[-1] # Extract just the name
        for root, dirs, files in os.walk(self.base_dir):
            if filename in files:
                return Path(root) / filename
        return None

    def attempt_repair(self, file_path_str: str, error_msg: str):
        """Use AI to repair the file (with smart path finding)"""
        try:
            file_path = Path(file_path_str)
            # Check exemption list first
            if file_path.name in self.EXEMPT_FILES:
                self.log(f"[EXEMPT] Skipping {file_path.name} - manually verified fix in place.")
                return False, "File is exempt from self-healing."

            if not file_path.exists() or not file_path.is_file():
                # Try to find it in the workspace
                self.log(f"Path '{file_path_str}' not found. Searching workspace for '{file_path_str}'...")
                found_path = self._find_file(file_path_str)
                if found_path:
                    file_path = found_path
                    self.log(f"Located file at: {file_path}")
                else:
                    return False, f"File '{file_path_str}' could not be located anywhere in the workspace."

            code = file_path.read_text(encoding="utf-8")
            
            prompt = f"""
            You are the JARVIS Self-Healing Protocol. 
            A core file in your system has crashed. You MUST fix it.
            
            FILE: {file_path.name}
            ERROR: {error_msg}
            
            CURRENT CODE:
            {code}
            
            TASK: 
            Analyze the error and the code. Provide the FULL corrected code for the file.
            Do not provide explanations. Return ONLY the code block.
            Ensure imports are preserved and the fix is robust.
            """
            
            self.log(f"Diagnosing {file_path.name}...")
            
            # Use a powerful model for coding
            fixed_code = call_llm(prompt, system_prompt="You are an expert Python developer and system architect.")
            
            # Refined LLM output cleaning to reliably extract code block
            if "" in fixed_code:
                # This regex captures content between the first and last , optionally skipping a language specifier
                match = re.search(r"(?:[a-zA-Z]+\n)?(.*)", fixed_code, re.DOTALL)
                if match:
                    fixed_code = match.group(1).strip()
                else:
                    # Fallback for cases where the regex might not perfectly match (e.g., only one )
                    # or if it's a non-standard markdown block.
                    # This will strip common variations like "", "", and extra whitespace.
                    fixed_code = fixed_code.replace("", "").replace("", "").strip()
            
            if not fixed_code or len(fixed_code) < 10:
                return False, "AI returned empty or invalid code."

            # Create backup
            backup = self.create_backup(file_path)
            if backup:
                self.log(f"Backup created: {backup.name}")

            # Write fix
            file_path.write_text(fixed_code, encoding="utf-8")
            self.log(f"Applied patch to {file_path.name}")
            return True, "Repair applied successfully."

        except Exception as e:
            return False, f"Repair failed: {e}"

    def handle_startup_failure(self, error_traceback: str):
        """Emergency handler for startup crashes"""
        self.log("EMERGENCY: Startup failure detected. Analyzing traceback...")
        
        # 1. Identify culprit file from traceback
        lines = error_traceback.splitlines()
        culprit_file = None
        for line in reversed(lines):
            if "File \"" in line and ".py\", line" in line:
                match = re.search(r"File \"(.*?)\", line", line)
                if match:
                    potential_path = Path(match.group(1))
                    # Only heal our own files, not site-packages
                    if str(self.base_dir).lower() in str(potential_path).lower():
                        culprit_file = potential_path
                        break
        
        if not culprit_file:
            self.log("Could not identify internal culprit in traceback.")
            return False

        self.log(f"Culprit identified: {culprit_file.name}")
        
        # 2. Check if we have a baseline to revert to
        if self.self_audit:
            # We could revert, but let's try AI repair first
            pass

        # 3. Attempt AI Repair
        success, msg = self.attempt_repair(culprit_file, error_traceback)
        if success:
            self.log("System healed. A restart is required.")
            return True
        else:
            self.log(f"Self-healing failed: {msg}")
            return False