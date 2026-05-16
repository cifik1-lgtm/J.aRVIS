# JARVIS Shadow Audit - Activity Tracker
import time
import json
import threading
from pathlib import Path
import psutil

# Windows specific window detection
try:
    import win32gui
    import win32process
except ImportError:
    win32gui = None

class ShadowAuditor:
    def __init__(self, base_dir):
        self.log_path = Path(base_dir) / "memory" / "shadow_audit.json"
        self.enabled = False
        self.current_app = None
        self.start_time = None
        self.stats = self._load_stats()

    def _load_stats(self):
        if self.log_path.exists():
            try: return json.loads(self.log_path.read_text(encoding="utf-8"))
            except: return {}
        return {}

    def _save_stats(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(json.dumps(self.stats, indent=4), encoding="utf-8")

    def get_active_window_name(self):
        if not win32gui: return "Unknown"
        try:
            window = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(window)
            # Get process name
            _, pid = win32process.GetWindowThreadProcessId(window)
            process = psutil.Process(pid)
            return process.name(), title
        except:
            return "Idle", "System"

    def start(self):
        if self.enabled: return "Shadow Audit is already active, sir."
        self.enabled = True
        self.thread = threading.Thread(target=self._audit_loop, daemon=True)
        self.thread.start()
        return "Shadow Audit initiated. I am now observing your workflow, sir."

    def stop(self):
        self.enabled = False
        return "Shadow Audit suspended, sir."

    def _audit_loop(self):
        while self.enabled:
            app_name, title = self.get_active_window_name()
            
            if app_name != self.current_app:
                # Log previous app time
                if self.current_app:
                    duration = time.time() - self.start_time
                    self.stats[self.current_app] = self.stats.get(self.current_app, 0) + duration
                    self._save_stats()
                
                self.current_app = app_name
                self.start_time = time.time()
            
            time.sleep(5) # Sample every 5 seconds

    def get_report(self):
        if not self.stats: return "I have no activity data yet, sir. We should start the audit first."
        
        # Sort by duration
        sorted_stats = sorted(self.stats.items(), key=lambda x: x[1], reverse=True)
        report = "### 🕵️ Shadow Productivity Report\n\n"
        for app, duration in sorted_stats[:5]:
            minutes = int(duration // 60)
            report += f"- **{app}**: {minutes} minutes\n"
        
        return report

# Global instance for JARVIS
_auditor = None

def get_auditor(base_dir):
    global _auditor
    if _auditor is None:
        _auditor = ShadowAuditor(base_dir)
    return _auditor

def shadow_audit(parameters, player=None, base_dir=None):
    action = parameters.get("action", "report").lower()
    auditor = get_auditor(base_dir)
    
    if action == "start":
        return auditor.start()
    elif action == "stop":
        return auditor.stop()
    else:
        return auditor.get_report()
