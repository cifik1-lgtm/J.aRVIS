import pygetwindow as gw
import pyautogui
from screeninfo import get_monitors
import time

def setup_workspace(layout_name="coding"):
    """
    The Architect Protocol: Organizes windows into predefined layouts.
    """
    monitors = get_monitors()
    if not monitors:
        return {"status": "error", "message": "No monitors detected."}

    # Primary monitor geometry
    m = monitors[0]
    mw, mh = m.width, m.height
    mx, my = m.x, m.y

    layouts = {
        "coding": [
            {"title": "Visual Studio Code", "x": mx, "y": my, "w": int(mw * 0.6), "h": mh},
            {"title": "Brave", "x": mx + int(mw * 0.6), "y": my, "w": int(mw * 0.4), "h": int(mh * 0.7)},
            {"title": "Terminal", "x": mx + int(mw * 0.6), "y": my + int(mh * 0.7), "w": int(mw * 0.4), "h": int(mh * 0.3)},
        ],
        "social": [
            {"title": "Telegram", "x": mx, "y": my, "w": int(mw * 0.3), "h": mh},
            {"title": "Brave", "x": mx + int(mw * 0.3), "y": my, "w": int(mw * 0.7), "h": mh},
        ],
        "cinema": [
            {"title": "VLC", "x": mx, "y": my, "w": mw, "h": mh},
            {"title": "Netflix", "x": mx, "y": my, "w": mw, "h": mh},
        ]
    }

    if layout_name not in layouts:
        return {"status": "error", "message": f"Layout '{layout_name}' not found."}

    plan = layouts[layout_name]
    windows_found = 0

    for item in plan:
        # Search for window with title containing string
        targets = [w for w in gw.getAllWindows() if item["title"].lower() in w.title.lower()]
        if targets:
            win = targets[0]
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                win.moveTo(item["x"], item["y"])
                win.resizeTo(item["w"], item["h"])
                windows_found += 1
            except Exception as e:
                print(f"[Architect] Failed to move {item['title']}: {e}")

    if windows_found == 0:
        return {"status": "partial", "message": f"Architect protocol initiated for '{layout_name}', but no matching windows were found. Please open the required apps."}
    
    return {"status": "success", "message": f"Workspace reorganized into '{layout_name}' layout. {windows_found} windows repositioned."}

def workspace_architect(jarvis, layout="coding"):
    """Tool entry point for workspace organization."""
    result = setup_workspace(layout)
    if jarvis.ui:
        jarvis.ui.write_log(f"🏗️ Architect: Applied '{layout}' layout.")
    return result
