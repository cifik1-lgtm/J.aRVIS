import threading
import json
import time
import os
from pathlib import Path
import sys

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

API_CONFIG_PATH = get_base_dir() / "config" / "api_keys.json"

def get_config():
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def get_relay_path():
    cfg = get_config()
    my_name = cfg.get("device_name", "").upper().strip()
    paths = []
    
    # 1. Try local network share (Instant Speed) ONLY if we are NOT CIFIK
    # If CIFIK tries to access its own share via UNC, Windows SMB loopback will block os.listdir!
    if my_name != "CIFIK":
        paths.append(Path(r"\\DESKTOP-9JBLGJ6.local\share\Cifik_Intelegents\memory\relay"))
    
    # 2. Try the local memory folder relative to the project
    local_relay = get_base_dir() / "memory" / "relay"
    paths.append(local_relay)

    # 3. Try Cloud Folder (OneDrive)
    cloud_path = cfg.get("cloud_relay_path")
    if cloud_path:
        paths.append(Path(cloud_path))

    for p in paths:
        try:
            p.mkdir(parents=True, exist_ok=True)
            if p.exists(): return p
        except: pass
    return None

def publish_command(target_device, command_text):
    """Sends a command to the cloud relay (via File Sync)."""
    try:
        relay_dir = get_relay_path()
        if not relay_dir: return False
        
        # We create a unique file for this command
        # Format: TARGET_COMMAND_TIMESTAMP.json
        filename = f"{target_device.upper()}_{int(time.time()*1000)}.json"
        filepath = relay_dir / filename
        
        data = {
            "target": target_device.upper(),
            "command": command_text,
            "sender": get_config().get("device_name", "JARVIS")
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
        print(f"[Ghost] 📤 Signal synced to Cloud Folder: {target_device}: {command_text}")
        return True
    except Exception as e:
        print(f"[Ghost] ❌ Cloud sync failed: {e}")
        return False

def start_ghost_relay(queue, speak_ref=None):
    """Starts the background listener for cloud command files."""
    def listener():
        my_name = get_config().get("device_name", "JARVIS").upper().strip()
        print(f"[Ghost] 👻 Cloud Folder Relay active. My identity is: '{my_name}'")
        
        while True:
            try:
                relay_dir = get_relay_path()
                if not relay_dir:
                    time.sleep(10)
                    continue
                
                # Check for files in the relay folder
                for file in os.listdir(relay_dir):
                    if not file.endswith(".json"): continue
                    
                    filepath = relay_dir / file
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            
                        target = data.get("target", "").upper().strip()
                        cmd = data.get("command", "")
                        
                        # STRICT MATCHING ONLY
                        if target == my_name or target == "ALL":
                            print(f"[Ghost] 🎯 Match found! Cloud Signal Received: {cmd}")
                            from agent.task_queue import TaskPriority
                            queue.submit(goal=f"Cloud command: {cmd}", priority=TaskPriority.HIGH)
                            # ONLY delete if it was for us
                            try: os.remove(filepath)
                            except: pass
                        else:
                            # If it's NOT for us, only delete if it's older than 2 minutes (stale)
                            file_age = time.time() - os.path.getmtime(filepath)
                            if file_age > 120:
                                try: os.remove(filepath)
                                except: pass
                        
                    except Exception as fe:
                        # File might be in use by sync, ignore and retry
                        pass
                
                time.sleep(2) # Fast polling of local folder
                
            except Exception as e:
                time.sleep(5)
                
    t = threading.Thread(target=listener, daemon=True)
    t.start()
