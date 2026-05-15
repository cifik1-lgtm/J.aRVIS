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

    def log(self, message):
        print(f"[SelfHealing] {message}")
        if self.ui:
            self.ui.write_log(f"🛠️ {message}")

    def create_backup(self, file_path: Path):
        """Create a safety backup before editing"""
        try:
            rel_path = file_path.relative_to(self.base_dir)
            backup_path = self.backups_dir / f"{rel_path.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            shutil.copy2(file_path, backup_path)
            return backup_path
        except:
            return None

    def attempt_repair(self, file_path: Path, error_msg: str):
        """Use AI to repair the file"""
        try:
            if not file_path.exists():
                return False, "File does not exist."

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
            
            # Clean output
            if "```" in fixed_code:
                fixed_code = re.sub(r"```[a-zA-Z]*\n?", "", fixed_code).replace("```", "").strip()
            
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
