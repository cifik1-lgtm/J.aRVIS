import subprocess
import os
import sys
import time

def start_skill_cockpit(log_callback=None):
    """
    Launch the Skill Management Framework Cockpit as a background process.
    """
    try:
        framework_path = os.path.join(os.getcwd(), "Skill_Management_Framework")
        main_script = os.path.join(framework_path, "main.py")
        
        if not os.path.exists(main_script):
            if log_callback:
                log_callback("[Cockpit] ⚠️ Framework not found in workspace.")
            return None

        if log_callback:
            log_callback("[Cockpit] 🚀 Initializing Neural Fusion Framework...")

        # Launch in background
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=framework_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if log_callback:
            log_callback("[Cockpit] ✅ Skill Cockpit Active on port 8080.")
            
        return process
    except Exception as e:
        if log_callback:
            log_callback(f"[Cockpit] ❌ Startup failed: {e}")
        return None
