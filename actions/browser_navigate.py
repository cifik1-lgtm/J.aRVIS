# actions/browser_navigate.py
import time
import subprocess
import os
import platform
import pyautogui

def browser_navigate(parameters: dict, player=None) -> str:
    """
    Composite tool to open a browser and navigate to a URL.
    Handles browser launch, URL typing, and Enter key.
    """
    url = parameters.get("url") or parameters.get("text", "")
    browser = parameters.get("browser", "brave").lower()
    
    if not url:
        return "Error: No URL provided for navigation."

    # Normalize URL
    if not (url.startswith("http://") or url.startswith("https://")):
        if "." not in url:
            url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
        else:
            url = "https://" + url

    print(f"[BrowserNavigate] Goal: {url} on {browser}")
    if player:
        player.write_log(f"[Browser] Navigating to {url}")

    # Method 1: Try using the smart browser_control module first
    try:
        from actions.browser_control import browser_control
        result = browser_control({"action": "go_to", "url": url, "browser": browser})
        if "Launched" in result or "Opened" in result:
            return result
    except Exception as e:
        print(f"[BrowserNavigate] smart_control failed: {e}")

    # Method 2: Manual fallback if browser_control fails
    try:
        system = platform.system()
        if system == "Windows":
            # Just use start command which is very reliable for default/named browsers
            subprocess.Popen(f'start {browser} "{url}"', shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", browser, url])
        else:
            subprocess.Popen(["xdg-open", url])
            
        return f"Navigated to {url} using system launcher."
    except Exception as e:
        # Method 3: Last resort - type and enter (The user's requested logic)
        pyautogui.write(url)
        time.sleep(0.2)
        pyautogui.press("enter")
        return f"Typed URL and pressed Enter as fallback: {url}"
