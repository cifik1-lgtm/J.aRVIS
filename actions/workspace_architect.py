import pygetwindow as gw
import pyautogui
from screeninfo import get_monitors
import time
import subprocess
import os

# App mapping for launching
APP_PATHS = {
    "visual studio code": "code",
    "brave": "brave",
    "chrome": "chrome",
    "terminal": "wt", # Windows Terminal
    "telegram": os.path.expanduser("~\\AppData\\Roaming\\Telegram Desktop\\Telegram.exe"),
    "vlc": "vlc",
    "spotify": "spotify"
}

def setup_workspace(layout_name="coding", launch_missing=True):
    """
    The Architect Protocol 2.0: Organizes windows and LAUNCHES missing apps.
    """
    monitors = get_monitors()
    if not monitors:
        return {"status": "error", "message": "No monitors detected."}

    m = monitors[0]
    mw, mh = m.width, m.height
    mx, my = m.x, m.y

    layouts = {
        "coding": [
            {"title": "Visual Studio Code", "x": mx, "y": my, "w": int(mw * 0.6), "h": mh, "cmd": "code"},
            {"title": "Brave", "x": mx + int(mw * 0.6), "y": my, "w": int(mw * 0.4), "h": int(mh * 0.7), "cmd": "brave"},
            {"title": "Terminal", "x": mx + int(mw * 0.6), "y": my + int(mh * 0.7), "w": int(mw * 0.4), "h": int(mh * 0.3), "cmd": "wt"},
        ],
        "social": [
            {"title": "Telegram", "x": mx, "y": my, "w": int(mw * 0.3), "h": mh, "cmd": "telegram"},
            {"title": "Brave", "x": mx + int(mw * 0.3), "y": my, "w": int(mw * 0.7), "h": mh, "cmd": "brave"},
        ],
        "cinema": [
            {"title": "VLC", "x": mx, "y": my, "w": mw, "h": mh, "cmd": "vlc"},
        ],
        "gaming": [
            {"title": "Steam", "x": mx, "y": my, "w": mw, "h": mh, "cmd": "steam"},
            {"title": "Discord", "x": mx + int(mw * 0.7), "y": my, "w": int(mw * 0.3), "h": int(mh * 0.5), "cmd": "discord"},
        ]
    }

    if layout_name not in layouts:
        return {"status": "error", "message": f"Layout '{layout_name}' not found."}

    plan = layouts[layout_name]
    windows_found = 0

    for item in plan:
        targets = [w for w in gw.getAllWindows() if item["title"].lower() in w.title.lower()]
        
        if not targets and launch_missing:
            cmd = item.get("cmd") or APP_PATHS.get(item["title"].lower())
            if cmd:
                print(f"[Architect] Launching missing app: {item['title']}...")
                subprocess.Popen(cmd, shell=True)
                time.sleep(2) # Give it time to spawn
                targets = [w for w in gw.getAllWindows() if item["title"].lower() in w.title.lower()]

        if targets:
            win = targets[0]
            try:
                if win.isMinimized: win.restore()
                win.activate()
                win.moveTo(item["x"], item["y"])
                win.resizeTo(item["w"], item["h"])
                windows_found += 1
            except Exception as e:
                print(f"[Architect] Failed to move {item['title']}: {e}")

    return {"status": "success", "message": f"Architect 2.0: Applied '{layout_name}'. {windows_found} windows configured."}

def workspace_architect(parameters: dict = None, player=None):
    """Tool entry point."""
    params = parameters or {}
    layout = params.get("layout", "coding")
    launch = params.get("launch_missing", True)
    
    result = setup_workspace(layout, launch)
    if player:
        player.write_log(f"🏗️ Architect 2.0: {result['message']}")
    return result["message"]

