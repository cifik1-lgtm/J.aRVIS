"""
YouTube Controller - Uses direct video URL and keyboard shortcuts
"""

import subprocess
import pyautogui
import time
import re
import urllib.parse
from pathlib import Path

# YouTube keyboard shortcuts
YOUTUBE_SHORTCUTS = {
    "play_pause": "k",
    "next": "shift+n",
    "previous": "shift+p",
    "fullscreen": "f",
    "mute": "m",
    "volume_up": "up",
    "volume_down": "down",
    "seek_forward": "shift+period",
    "seek_backward": "shift+comma",
    "like": "shift+l",
    "dislike": "shift+d",
    "theater_mode": "t",
    "captions": "c",
}

def focus_youtube_window() -> bool:
    """Find and focus the YouTube window (or Brave browser)"""
    try:
        import pygetwindow
        import sys
        
        windows = pygetwindow.getWindowsWithTitle("YouTube")
        if not windows:
            windows = pygetwindow.getWindowsWithTitle("Brave")
        
        if windows:
            win = windows[0]
            if win.isMinimized:
                try:
                    win.restore()
                except Exception:
                    pass
            
            if sys.platform == "win32":
                try:
                    import win32com.client
                    shell = win32com.client.Dispatch("WScript.Shell")
                    if shell.AppActivate("YouTube"):
                        time.sleep(0.2)
                        return True
                    if shell.AppActivate("Brave"):
                        time.sleep(0.2)
                        return True
                except Exception:
                    pass
            
            try:
                win.activate()
                time.sleep(0.2)
                return True
            except Exception:
                pass
    except Exception as e:
        print(f"[YouTube] Focus window failed: {e}")
    return False

def send_shortcut(shortcut: str):
    """Send keyboard shortcut to active window"""
    try:
        # Focus the YouTube window first to ensure it receives the shortcut
        focus_youtube_window()
        
        time.sleep(0.1)
        
        keys = shortcut.split('+')
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        return True
    except Exception as e:
        print(f"[YouTube] Shortcut failed: {e}")
        return False

def get_youtube_video_url(query: str) -> str:
    """Get direct YouTube video URL using yt-dlp or fallback"""
    import urllib.request
    import json
    
    encoded_query = urllib.parse.quote(query)
    
    # Try to get first video result using YouTube's API (no key needed)
    try:
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        
        # Use yt-dlp if available (best option)
        try:
            import yt_dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'playlist_items': '1',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if info and 'entries' in info and info['entries']:
                    video_url = f"https://www.youtube.com/watch?v={info['entries'][0]['id']}"
                    return video_url
        except:
            pass
        
        # Fallback: Use direct search and pattern match
        import re
        with urllib.request.urlopen(search_url, timeout=10) as response:
            html = response.read().decode('utf-8')
            
            # Find video ID in page
            patterns = [
                r'"videoId":"([^"]+)"',
                r'/watch\?v=([a-zA-Z0-9_-]{11})',
                r'watch\?v=([a-zA-Z0-9_-]{11})',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, html)
                if matches:
                    video_id = matches[0]
                    return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        print(f"[YouTube] Error getting video URL: {e}")
    
    # Ultimate fallback - just go to search page
    return f"https://www.youtube.com/results?search_query={encoded_query}"

def open_browser(url: str, browser: str = "brave"):
    """Open URL in specified browser"""
    if browser.lower() == "brave":
        brave_paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ]
        for path in brave_paths:
            if Path(path).exists():
                subprocess.Popen([path, url])
                return True
    elif browser.lower() == "chrome":
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for path in chrome_paths:
            if Path(path).exists():
                subprocess.Popen([path, url])
                return True
    
    # Fallback to default browser
    import webbrowser
    webbrowser.open(url)
    return True

def play_youtube_search(query: str, browser: str = "brave") -> str:
    """Open YouTube and automatically play the first video"""
    if not query:
        return "Please specify a song or video to play."
    
    # Get direct video URL
    video_url = get_youtube_video_url(query)
    
    # Open browser directly to video
    open_browser(video_url, browser)
    time.sleep(2)
    
    # Ensure video is playing (autoplay=1 usually handles this, so we just wait)
    time.sleep(1.0)
    
    return f"Playing {query} on YouTube"

def youtube_control(parameters: dict, player=None) -> str:
    """Control YouTube playback using keyboard shortcuts"""
    action = parameters.get("action", "")
    query = parameters.get("query", "")
    browser = parameters.get("browser", "brave")
    
    result = ""
    
    if action == "play":
        result = play_youtube_search(query, browser)
    
    elif action == "pause":
        if send_shortcut(YOUTUBE_SHORTCUTS["play_pause"]):
            result = "Paused playback."
        else:
            result = "Failed to pause playback."
    
    elif action == "resume":
        if send_shortcut(YOUTUBE_SHORTCUTS["play_pause"]):
            result = "Resumed playback."
        else:
            result = "Failed to resume playback."
    
    elif action == "next":
        if send_shortcut(YOUTUBE_SHORTCUTS["next"]):
            result = "Playing next song."
        else:
            result = "Failed to play next song. Make sure you have a playlist or queue."
    
    elif action == "previous":
        if send_shortcut(YOUTUBE_SHORTCUTS["previous"]):
            result = "Playing previous song."
        else:
            result = "Failed to play previous song."
    
    elif action == "fullscreen":
        if send_shortcut(YOUTUBE_SHORTCUTS["fullscreen"]):
            result = "Toggled fullscreen mode."
        else:
            result = "Failed to toggle fullscreen."
    
    elif action == "mute":
        if send_shortcut(YOUTUBE_SHORTCUTS["mute"]):
            result = "Muted/unmuted."
        else:
            result = "Failed to mute."
    
    elif action == "volume_up":
        for _ in range(3):  # Press multiple times for noticeable change
            send_shortcut(YOUTUBE_SHORTCUTS["volume_up"])
        result = "Volume increased."
    
    elif action == "volume_down":
        for _ in range(3):
            send_shortcut(YOUTUBE_SHORTCUTS["volume_down"])
        result = "Volume decreased."
    
    elif action == "like":
        if send_shortcut(YOUTUBE_SHORTCUTS["like"]):
            result = "Liked the video."
        else:
            result = "Failed to like video."
    
    elif action == "theater":
        if send_shortcut(YOUTUBE_SHORTCUTS["theater_mode"]):
            result = "Toggled theater mode."
        else:
            result = "Failed to toggle theater mode."
    
    else:
        result = f"Unknown action: {action}. Available: play, pause, resume, next, previous, fullscreen, mute, volume_up, volume_down, like, theater"
    
    if player:
        player.write_log(f"[YouTube] {result}")
    
    return result
