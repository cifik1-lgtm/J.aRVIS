"""
Unified YouTube Player for JARVIS
Handles: Playback, volume, playlists, tab management
"""

import webbrowser
import psutil
import subprocess
import time
import re
from typing import List, Dict, Optional

class YouTubePlayer:
    def __init__(self, ui):
        self.ui = ui
        self.current_playlist = []
        self.playlist_index = 0
        self.volume_level = 50  # Default 50%
        self.brave_path = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"
        self.vlc_path = "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
        
        # State Management
        self.playback_proc = None
        self.current_song = None
        self.is_direct_mode = True  # Default to direct audio playback
        
    def ensure_single_brave(self) -> bool:
        """Make sure only one Brave instance runs"""
        brave_count = 0
        brave_pids = []
        
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] and 'brave' in proc.info['name'].lower():
                brave_count += 1
                brave_pids.append(proc.info['pid'])
        
        # If more than one Brave process, kill extras except the first
        if brave_count > 1:
            for pid in brave_pids[1:]:
                try:
                    psutil.Process(pid).terminate()
                    self.ui.write_log(f"🔪 Killed duplicate Brave process: {pid}")
                except:
                    pass
            time.sleep(1)
            return True
        return False
    
    def is_brave_running(self) -> bool:
        """Check if Brave is already running"""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and 'brave' in proc.info['name'].lower():
                return True
        return False
    
    def open_brave_tab(self, url: str) -> bool:
        """Open URL in Brave with full diagnostic logging."""
        from pathlib import Path

        self.ui.write_log(f"[YouTubePlayer] 📂 Opening URL: {url[:80]}")
        print(f"[YouTubePlayer] 📂 Opening URL: {url[:80]}")

        # Find Brave executable
        brave_paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ]
        brave_exe = None
        for p in brave_paths:
            if Path(p).exists():
                brave_exe = p
                self.ui.write_log(f"[YouTubePlayer] ✅ Found Brave: {p}")
                print(f"[YouTubePlayer] ✅ Found Brave: {p}")
                break

        if not brave_exe:
            self.ui.write_log("[YouTubePlayer] ❌ Brave NOT found — falling back to default browser")
            print("[YouTubePlayer] ❌ Brave not found")
            import webbrowser
            webbrowser.open(url)
            return True

        # Check if Brave is already running
        brave_running = False
        brave_pids = []
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] and 'brave' in proc.info['name'].lower():
                    brave_running = True
                    brave_pids.append(proc.info['pid'])
            except Exception:
                pass

        if brave_running:
            self.ui.write_log(f"[YouTubePlayer] 🔄 Brave is running, opening new tab...")
            try:
                # Direct Popen with list is more robust than shell 'start'
                subprocess.Popen([brave_exe, "--new-tab", url])
                
                # Still ensure the window is focused after the new tab opens
                time.sleep(1.5)
                import pygetwindow as gw
                wins = [w for w in gw.getWindowsWithTitle('Brave') if w.visible]
                if wins:
                    win = wins[0]
                    if win.isMinimized: win.restore()
                    win.activate()
                    self.ui.write_log("[YouTubePlayer] ✨ Focused existing Brave instance")
                return True
            except Exception as e:
                self.ui.write_log(f"[YouTubePlayer] ⚠️ Failed to open tab in running Brave: {e}")

        # Default / Fallback: Launch browser
        try:
            # Direct Popen with list
            subprocess.Popen([brave_exe, url])
            self.ui.write_log(f"[YouTubePlayer] 🚀 Launched Brave with URL: {url[:40]}...")
            
            # Ensure focus after launch
            time.sleep(2.5)
            try:
                import pygetwindow as gw
                wins = [w for w in gw.getWindowsWithTitle('Brave') if w.visible]
                if wins:
                    win = wins[0]
                    if win.isMinimized: win.restore()
                    win.activate()
            except: pass
            
            return True
        except Exception as e:
            self.ui.write_log(f"[YouTubePlayer] ❌ Command failed: {e}")
            import webbrowser
            webbrowser.open(url)
            return True

    def stop_playback(self) -> str:
        """Stop any active playback (Direct mode or Browser mode)"""
        stopped = False
        
        # 1. Kill direct VLC process
        if self.playback_proc:
            try:
                self.playback_proc.terminate()
                self.playback_proc = None
                self.ui.write_log("[YouTubePlayer] ⏹️ Stopped direct audio playback")
                stopped = True
            except:
                pass
        
        # 2. Cleanup current state
        self.current_song = None
        
        if stopped:
            return "Stopped playback, sir."
        return "Nothing is currently playing in direct mode, sir."

    def play_audio_direct(self, video_url: str, title: str = "Unknown Track") -> bool:
        """Play YouTube audio directly via yt-dlp and VLC (No browser needed)"""
        self.stop_playback()
        self.ui.write_log(f"[YouTubePlayer] 🎧 Preparing direct audio: {title}")
        
        try:
            import subprocess
            import sys
            import os
            
            # 1. Get the best audio URL using yt-dlp
            self.ui.write_log("[YouTubePlayer] 🔍 Extracting audio stream URL...")
            cmd_dlp = [
                sys.executable, "-m", "yt_dlp",
                "-f", "bestaudio",
                "--get-url",
                video_url
            ]
            result = subprocess.run(cmd_dlp, capture_output=True, text=True, timeout=15)
            
            if result.returncode != 0:
                self.ui.write_log(f"[YouTubePlayer] ❌ yt-dlp extraction failed: {result.stderr}")
                return False
                
            audio_url = result.stdout.strip()
            if not audio_url:
                return False

            # 2. Launch VLC in background (no interface, no video)
            self.ui.write_log(f"[YouTubePlayer] 🚀 Launching VLC for {title}")
            vlc_cmd = [
                self.vlc_path,
                "--intf", "dummy",
                "--no-video",
                "--play-and-exit",
                audio_url
            ]
            
            # Start VLC in its own process group
            self.playback_proc = subprocess.Popen(
                vlc_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            self.current_song = title
            self.ui.write_log(f"[YouTubePlayer] ✅ Direct playback started: {title}")
            return True
            
        except Exception as e:
            self.ui.write_log(f"[YouTubePlayer] ❌ Direct playback failed: {e}")
            return False

    
    def play_song(self, query: str) -> str:
        """Play a song on YouTube"""
        # Clean query
        query = self._clean_query(query)
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        
        self.open_brave_tab(search_url)
        return f"Playing {query} on YouTube, sir."
    
    def play_playlist(self, songs: List[str]) -> str:
        """Create and play a playlist"""
        self.current_playlist = songs
        self.playlist_index = 0
        return self.play_next_in_playlist()
    
    def play_next_in_playlist(self) -> str:
        """Play next song in current playlist"""
        if self.current_playlist and self.playlist_index < len(self.current_playlist):
            song = self.current_playlist[self.playlist_index]
            self.playlist_index += 1
            return self.play_song(song)
        else:
            self.current_playlist = []
            return "Playlist finished, sir."
    
    def play_previous_in_playlist(self) -> str:
        """Play previous song in current playlist"""
        if self.current_playlist and self.playlist_index > 1:
            self.playlist_index -= 2
            return self.play_next_in_playlist()
        return "At start of playlist, sir."
    
    def set_volume(self, level: int) -> str:
        """Set system volume (0-100)"""
        self.volume_level = max(0, min(100, level))
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(self.volume_level / 100.0, None)
            return f"Volume set to {self.volume_level}%, sir."
        except:
            # Fallback: Use keyboard shortcuts
            for _ in range(10):  # Press volume down 10 times to reset
                self._press_volume_down()
            for _ in range(self.volume_level // 10):
                self._press_volume_up()
            return f"Volume set to approximately {self.volume_level}%, sir."
    
    def volume_up(self, amount: int = 10) -> str:
        """Increase volume"""
        return self.set_volume(self.volume_level + amount)
    
    def volume_down(self, amount: int = 10) -> str:
        """Decrease volume"""
        return self.set_volume(self.volume_level - amount)
    
    def pause_playback(self) -> str:
        """Pause current YouTube video"""
        try:
            import pyautogui
            pyautogui.press('space')
            return "Paused playback, sir."
        except:
            return "Could not pause, sir."
    
    def resume_playback(self) -> str:
        """Resume playback"""
        try:
            import pyautogui
            pyautogui.press('space')
            return "Resumed playback, sir."
        except:
            return "Could not resume, sir."
    
    def skip_ad(self) -> str:
        """Try to skip YouTube ad"""
        try:
            import pyautogui
            import time
            # Look for "Skip Ad" button area (bottom right)
            pyautogui.click(x=1800, y=950)  # Adjust based on screen resolution
            time.sleep(0.5)
            pyautogui.press('space')
            return "Attempted to skip ad, sir."
        except:
            return "Could not skip ad, sir."
    
    def fullscreen(self) -> str:
        """Toggle fullscreen"""
        try:
            import pyautogui
            pyautogui.press('f')
            return "Toggled fullscreen, sir."
        except:
            return "Could not toggle fullscreen, sir."
    
    def _clean_query(self, query: str) -> str:
        """Clean up search query"""
        # Remove common words
        remove_words = ["play", "on youtube", "song", "music", "video", "please", "can you", "could you", "youtube"]
        for word in remove_words:
            query = query.lower().replace(word, "")
        
        # Remove extra spaces
        query = " ".join(query.split())
        
        # If empty, use default
        if not query:
            query = "relaxing music"
        
        return query
    
    def _press_volume_up(self):
        """Press volume up key"""
        try:
            import pyautogui
            pyautogui.press('volumeup')
        except:
            pass
    
    def _press_volume_down(self):
        """Press volume down key"""
        try:
            import pyautogui
            pyautogui.press('volumedown')
        except:
            pass

# Global instance
_youtube_player = None

def get_youtube_player(ui):
    global _youtube_player
    if _youtube_player is None:
        _youtube_player = YouTubePlayer(ui)
    return _youtube_player
