import pymonctl
import threading
import time

class MonitorManager:
    def __init__(self, jarvis=None):
        self.monitors = []
        self.jarvis = jarvis
        self.monitoring_enabled = False
        self._thread = None
        # Start monitoring by default if pymonctl supports it well
        try:
            self.enable_real_time_monitoring()
        except Exception as e:
            print(f"[MonitorManager] Warning: Real-time monitoring failed to initialize: {e}")

    def get_monitors(self):
        """Get all connected monitors"""
        self.monitors = pymonctl.getAllMonitors()
        return self.monitors

    def get_monitor_count(self):
        return pymonctl.getMonitorsCount()

    def get_primary_monitor(self):
        return pymonctl.getPrimary()

    def get_monitor_at_position(self, x, y):
        """Find which monitor a window is on"""
        return pymonctl.findMonitorsAtPoint(x, y)

    def enable_real_time_monitoring(self):
        """Watch for monitor changes (plug/unplug, resolution changes)"""
        try:
            if hasattr(pymonctl, "enableUpdate"):
                pymonctl.enableUpdate()
                
                # Set up callbacks for changes
                pymonctl.monitorCountChange = self._on_monitor_count_change
                pymonctl.monitorPropsChange = self._on_monitor_props_change
                self.monitoring_enabled = True
            else:
                self.monitoring_enabled = False
        except Exception as e:
            print(f"[MonitorManager] Real-time update not supported: {e}")
            self.monitoring_enabled = False

    def _on_monitor_count_change(self, changed_monitors, all_monitors):
        """Called when monitors are plugged/unplugged"""
        count = len(all_monitors)
        msg = f"Monitor count changed to {count}, sir."
        print(f"[JARVIS] {msg}")
        if self.jarvis:
            self.jarvis.speak(msg)
            if self.jarvis.ui:
                self.jarvis.ui.write_log(f"SYS: \ud83d\udda5\ufe0f {msg}")

    def _on_monitor_props_change(self, changed_monitors, all_monitors):
        """Called when monitor properties change (resolution, position)"""
        for monitor_name in changed_monitors:
            msg = f"Monitor {monitor_name} settings have been updated, sir."
            print(f"[JARVIS] {msg}")
            # Optional: speak for resolution changes
            # if self.jarvis:
            #     self.jarvis.speak(msg)

def execute_monitor_detection(jarvis):
    """Tool function to detect and report monitors"""
    mm = MonitorManager(jarvis)
    count = mm.get_monitor_count()
    
    report = []
    if count > 1:
        jarvis.speak(f"You have {count} monitors connected, sir.")
        
        # Get detailed info
        for monitor in mm.get_monitors():
            name = monitor.name
            resolution = monitor.size
            position = monitor.position
            is_primary = monitor.isPrimary
            primary_str = " (Primary)" if is_primary else ""
            report.append(f"Monitor: {name}{primary_str}, Resolution: {resolution.width}x{resolution.height}, Position: {position}")
            if jarvis.ui:
                jarvis.ui.write_log(f"SYS: 🖥️ {name}{primary_str} | {resolution.width}x{resolution.height} @ {position}")
    else:
        jarvis.speak("Single monitor setup detected, sir.")
        primary = mm.get_primary_monitor()
        if primary:
            res = primary.size
            report.append(f"Single Monitor: {primary.name}, Resolution: {res.width}x{res.height}")
    
    return {"status": "success", "monitor_count": count, "details": report}
