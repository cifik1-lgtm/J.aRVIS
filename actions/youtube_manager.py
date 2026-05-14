"""
Unified YouTube Manager for JARVIS
Routes to the right sub-module based on user intent:
- youtube_controller  → keyboard shortcuts (pause, next, previous, mute, like, theater)
- youtube_player      → tab/browser management, system volume, playlists
- youtube_video       → play by search query, summarize, get_info, trending
"""

from actions.youtube_controller import youtube_control
from actions.youtube_player import get_youtube_player
from actions.youtube_video import youtube_video

import pyautogui
import re
from urllib.parse import quote_plus, urlparse, parse_qsl, urlencode, urlunparse
from typing import Optional


class YouTubeManager:
    def __init__(self, ui):
        self.ui = ui
        self.player = get_youtube_player(ui)

    def ensure_browser_focused(self, browser_name="Brave"):
        """Ensure browser window is visible and focused"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(browser_name)
            if windows:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                self.ui.write_log(f"[YouTubeManager] ✨ Verified focus for {browser_name}")
                return True
        except:
            # Fallback: try Alt+Tab to Brave
            import pyautogui
            pyautogui.hotkey('alt', 'tab')
        return False

    def _with_autoplay(self, url: str) -> str:
        """Add autoplay=1 without clobbering existing query params."""
        try:
            parsed = urlparse(url)
            q = dict(parse_qsl(parsed.query, keep_blank_values=True))
            q["autoplay"] = "1"
            new_query = urlencode(q)
            return urlunparse(parsed._replace(query=new_query))
        except Exception:
            # Worst case, just append
            return url + ("&" if "?" in url else "?") + "autoplay=1"

    def _resolve_direct_video_url(self, query: str) -> Optional[str]:
        """
        Resolve the first YouTube video URL for a query.
        Prefers yt-dlp if available; falls back to scraping /results HTML.
        """
        query = (query or "").strip()
        if not query:
            return None

        # 1) Best effort: yt-dlp library with Brave cookies
        try:
            import yt_dlp
            import browser_cookie3
            
            self.ui.write_log(f"[YouTube] 🔍 Searching via yt-dlp: {query}")
            
            # Load cookies from Brave to avoid 429/Bot detection
            try:
                cj = browser_cookie3.brave(domain_name='.youtube.com')
            except Exception as e:
                self.ui.write_log(f"[YouTube] ⚠️ Could not load Brave cookies: {e}")
                cj = None

            ydl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'cookiejar': cj,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if info and 'entries' in info and len(info['entries']) > 0:
                    video = info['entries'][0]
                    url = video.get('webpage_url')
                    if url:
                        self.ui.write_log(f"[YouTube] ✅ yt-dlp resolved: {url}")
                        return url
        except Exception as e:
            self.ui.write_log(f"[YouTube] ⚠️ yt-dlp resolver failed: {e}")

        # 2) Fallback: scrape the search results page for a videoId/watch URL
        search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        self.ui.write_log(f"[YouTube] 🔍 Scrape search: {query}")
        html = ""

        # Prefer requests if installed, otherwise urllib
        try:
            try:
                import requests  # type: ignore

                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                }
                resp = requests.get(search_url, headers=headers, timeout=10)
                html = resp.text or ""
            except Exception:
                import urllib.request

                req = urllib.request.Request(
                    search_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    },
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    html = r.read().decode("utf-8", errors="ignore")
        except Exception as e:
            self.ui.write_log(f"[YouTube] ⚠️ Search scrape failed: {e}")
            return None

        if not html:
            return None

        # Pattern 1: "videoId":"XXXXXXXXXXX"
        m = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        if m:
            video_id = m.group(1)
            self.ui.write_log(f"[YouTube] ✅ Found videoId: {video_id}")
            return f"https://www.youtube.com/watch?v={video_id}"

        # Pattern 2: /watch?v=XXXXXXXXXXX
        m = re.search(r"/watch\?v=([a-zA-Z0-9_-]{11})", html)
        if m:
            video_id = m.group(1)
            self.ui.write_log(f"[YouTube] ✅ Found watch pattern: {video_id}")
            return f"https://www.youtube.com/watch?v={video_id}"

        return None

    def handle_command(self, parameters: dict, speak=None) -> str:
        """
        Main entry point for all YouTube commands.
        Routes to the appropriate sub-module based on action.
        """
        action = parameters.get("action", "play_song").lower()

        # ── KEYBOARD SHORTCUT ACTIONS (youtube_controller) ──────────────────
        # These send hotkeys directly to the active browser window
        if action in ("pause", "resume", "next", "previous",
                      "fullscreen", "mute", "volume_up", "volume_down",
                      "like", "theater"):
            return youtube_control({"action": action}, self.ui)

        if action == "stop":
            # Aggressively stop all YouTube playback (VLC and Browser)
            return self.player.stop_playback()

        # ── BROWSER / TAB MANAGEMENT (youtube_player) ────────────────────────
        if action == "open_tab":
            url = parameters.get("url", "https://www.youtube.com")
            self.player.open_brave_tab(url)
            self.ensure_browser_focused("Brave")
            return f"Opened new tab: {url}, sir."

        if action == "close_tab":
            try:
                pyautogui.hotkey("ctrl", "w")
                return "Closed current tab, sir."
            except Exception as e:
                return f"Could not close tab, sir: {e}"

        if action == "switch_tab":
            try:
                pyautogui.hotkey("ctrl", "tab")
                return "Switched to next tab, sir."
            except Exception as e:
                return f"Could not switch tab, sir: {e}"

        # ── SYSTEM-WIDE VOLUME (youtube_player / pycaw) ──────────────────────
        if action == "set_volume":
            level = int(parameters.get("level", 50))
            return self.player.set_volume(level)

        if action == "volume_up_system":
            amount = int(parameters.get("amount", 10))
            return self.player.volume_up(amount)

        if action == "volume_down_system":
            amount = int(parameters.get("amount", 10))
            return self.player.volume_down(amount)

        # ── PLAYLIST MANAGEMENT (youtube_player) ─────────────────────────────
        if action == "create_playlist":
            songs = parameters.get("songs", [])
            if not songs:
                return "Please provide a list of songs for the playlist, sir."
            return self.player.play_playlist(songs)

        if action == "next_song":
            return self.player.play_next_in_playlist()

        if action == "previous_song":
            return self.player.play_previous_in_playlist()

        # ── PLAY BY QUERY — open YouTube search directly in Brave ────────────
        if action in ("play_song", "play", "play_song_background", "play_song_foreground"):
            query = parameters.get("query", "").strip()
            if not query:
                return "What would you like me to play, sir?"
                
            # Default to foreground if no specific mode is requested
            mode = "foreground"
            if action == "play_song_background":
                mode = "background"
            elif action == "play_song_foreground":
                mode = "foreground"
            
            direct_url = self._resolve_direct_video_url(query)
            if direct_url:
                # Background Audio Mode
                if mode == "background":
                    success = self.player.play_audio_direct(direct_url, title=query)
                    if success:
                        return f"Playing {query} in the background, sir."
                
                # Foreground Video Mode (Default) - Using PWA App Mode
                direct_url = self._with_autoplay(direct_url)
                self.ui.write_log(f"[YouTube] 📺 Opening foreground PWA: {direct_url}")
                success = self.player.open_brave_app(direct_url)
                return f"Playing {query} on YouTube, sir." if success else f"Failed to open Brave for {query}, sir."

            # Fallback to search results if direct URL resolution fails
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            self.ui.write_log("[YouTube] ⚠️ Could not resolve direct video URL; opening search page in App mode")
            success = self.player.open_brave_app(search_url)
            return (
                f"Opening YouTube search for {query}, sir. Please click the first video to play."
                if success
                else f"Failed to open Brave for {query}, sir."
            )

        # ── SEARCH / INFO / TRANSCRIPT / TRENDING (youtube_video) ───────────
        if action in ("summarize", "get_info", "trending"):
            return youtube_video(parameters, player=self.ui, speak=speak)

        if action == "search":
            # Gemini sometimes uses 'search' when user says 'play' — treat it identically
            query = parameters.get("query", "")
            if not query:
                return "What should I search for on YouTube, sir?"
            # Delegate to play_song logic (scrape direct URL → open in Brave)
            return self.handle_command({"action": "play_song", "query": query}, speak=speak)

        return f"Unknown YouTube action: '{action}', sir."


# ─── Singleton ────────────────────────────────────────────────────────────────
_youtube_manager = None


def get_youtube_manager(ui):
    global _youtube_manager
    if _youtube_manager is None:
        _youtube_manager = YouTubeManager(ui)
    return _youtube_manager


def youtube_manager(parameters: dict, player=None, speak=None) -> str:
    """Module-level entry point used by ToolDispatcher._get_tool() fallback."""
    mgr = get_youtube_manager(player)
    return mgr.handle_command(parameters, speak=speak)
