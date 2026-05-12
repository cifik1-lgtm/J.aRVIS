"""
Browser Control - Smart tab reuse for ALL URLs
Detects if browser is already running and opens new tab instead of new window
"""

import asyncio
import subprocess
import shutil
import sys
import os
import time
import psutil
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("[Browser] ⚠️ Playwright not installed. Install with: pip install playwright && playwright install")

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
JARVIS_PROFILES = Path.home() / ".jarvis_profiles"
JARVIS_PROFILES.mkdir(exist_ok=True)

# Browser paths
BROWSER_PATHS = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
}


def is_browser_running(browser_name: str) -> bool:
    """Check if browser is already running"""
    browser_processes = {
        "chrome": ["chrome.exe"],
        "brave": ["brave.exe"],
        "edge": ["msedge.exe"],
        "firefox": ["firefox.exe"],
    }
    
    process_names = browser_processes.get(browser_name, [f"{browser_name}.exe"])
    
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() in [p.lower() for p in process_names]:
                return True
        except:
            pass
    return False


def open_url_in_existing_browser(browser_name: str, url: str) -> bool:
    """
    Open URL in existing browser window as a new tab.
    Works for Chrome, Brave, Edge, Firefox
    """
    browser_config = {
        "chrome": {
            "path": BROWSER_PATHS.get("chrome"),
            "args": ["--new-tab", url],
            "fallback": f'start chrome "{url}"'
        },
        "brave": {
            "path": BROWSER_PATHS.get("brave"),
            "args": ["--new-tab", url],
            "fallback": f'start brave "{url}"'
        },
        "edge": {
            "path": BROWSER_PATHS.get("edge"),
            "args": ["--new-tab", url],
            "fallback": f'start msedge "{url}"'
        },
        "firefox": {
            "path": BROWSER_PATHS.get("firefox"),
            "args": ["-new-tab", url],
            "fallback": f'start firefox "{url}"'
        }
    }
    
    config = browser_config.get(browser_name)
    if not config:
        return False
    
    try:
        # Method 1: Use browser executable with new-tab argument
        if config["path"] and os.path.exists(config["path"]):
            subprocess.Popen([config["path"]] + config["args"], shell=False)
            return True
        
        # Method 2: Use start command
        subprocess.Popen(config["fallback"], shell=True)
        return True
    except Exception as e:
        print(f"[Browser] Failed to open in existing {browser_name}: {e}")
        return False


class BrowserSession:
    """Manages browser sessions with smart tab reuse for ALL URLs"""
    
    _instances = {}
    
    def __init__(self, browser_name: str):
        self.browser_name = browser_name
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None
        self._is_running = False
    
    @classmethod
    def get_session(cls, browser_name: str):
        if browser_name not in cls._instances:
            cls._instances[browser_name] = cls(browser_name)
        return cls._instances[browser_name]
    
    def is_already_running(self) -> bool:
        """Check if browser is already running"""
        return is_browser_running(self.browser_name)
    
    async def ensure_browser_and_open_url(self, url: str) -> bool:
        """
        Smart method: 
        - If browser is running -> open URL in NEW TAB
        - If browser is NOT running -> launch browser and open URL
        """
        if self.is_already_running():
            print(f"[Browser] {self.browser_name} is already running, opening '{url}' in new tab")
            return open_url_in_existing_browser(self.browser_name, url)
        else:
            print(f"[Browser] {self.browser_name} is not running, launching and opening '{url}'")
            await self.launch()
            return await self.goto(url)
    
    async def launch(self) -> bool:
        """Launch browser with working profile"""
        if not HAS_PLAYWRIGHT:
            return await self._launch_legacy()
        
        try:
            # Create fresh profile for JARVIS
            profile_path = JARVIS_PROFILES / self.browser_name
            profile_path.mkdir(exist_ok=True)
            
            # Clean old lock files
            for lock_file in profile_path.glob("*.lock"):
                try:
                    lock_file.unlink()
                except:
                    pass
            
            self._playwright = await async_playwright().start()
            
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--start-maximized",
                "--disable-dev-shm-usage",
            ]
            
            if self.browser_name == "chrome":
                executable = BROWSER_PATHS.get("chrome")
                if executable and os.path.exists(executable):
                    self.context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(profile_path),
                        executable_path=executable,
                        headless=False,
                        args=launch_args,
                        viewport=None
                    )
                else:
                    self.context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(profile_path),
                        headless=False,
                        args=launch_args,
                        viewport=None
                    )
            elif self.browser_name == "brave":
                executable = BROWSER_PATHS.get("brave")
                if executable and os.path.exists(executable):
                    self.context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(profile_path),
                        executable_path=executable,
                        headless=False,
                        args=launch_args,
                        viewport=None
                    )
                else:
                    return await self._launch_legacy()
            elif self.browser_name == "edge":
                executable = BROWSER_PATHS.get("edge")
                if executable and os.path.exists(executable):
                    self.context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(profile_path),
                        executable_path=executable,
                        headless=False,
                        args=launch_args,
                        viewport=None
                    )
                else:
                    return await self._launch_legacy()
            else:
                return await self._launch_legacy()
            
            self.pages = self.context.pages
            if self.pages:
                self.page = self.pages[0]
            else:
                self.page = await self.context.new_page()
            
            self._is_running = True
            print(f"[Browser] ✅ Launched {self.browser_name}")
            return True
            
        except Exception as e:
            print(f"[Browser] ⚠️ Playwright failed: {e}")
            return await self._launch_legacy()
    
    async def _launch_legacy(self) -> bool:
        """Fallback to subprocess launch"""
        try:
            browser_path = BROWSER_PATHS.get(self.browser_name)
            if not browser_path or not os.path.exists(browser_path):
                # Try to find in PATH
                result = subprocess.run(['where', self.browser_name], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    browser_path = result.stdout.strip().split('\n')[0]
                else:
                    return False
            
            subprocess.Popen(
                [browser_path, "--new-window"],
                shell=False
            )
            print(f"[Browser] ✅ Launched {self.browser_name} (legacy mode)")
            self._is_running = True
            return True
        except Exception as e:
            print(f"[Browser] ❌ Failed to launch {self.browser_name}: {e}")
            return False
    
    async def goto(self, url: str) -> bool:
        """Navigate to URL"""
        if not HAS_PLAYWRIGHT or not self.page:
            # Legacy mode - just open in default browser
            try:
                os.startfile(url)
            except:
                subprocess.Popen(f'start {url}', shell=True)
            return True
        
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            print(f"[Browser] ⚠️ Navigation failed: {e}")
            try:
                os.startfile(url)
            except:
                subprocess.Popen(f'start {url}', shell=True)
            return True
    
    async def open_url_smart(self, url: str) -> bool:
        """
        SMART URL OPENING:
        - If browser running -> open in new tab
        - If browser not running -> launch and open
        """
        return await self.ensure_browser_and_open_url(url)
    
    async def click(self, selector: str = None, text: str = None) -> bool:
        """Click on element"""
        if not HAS_PLAYWRIGHT or not self.page:
            return False
        
        try:
            if selector:
                await self.page.click(selector, timeout=5000)
            elif text:
                await self.page.click(f"text={text}", timeout=5000)
            return True
        except Exception as e:
            print(f"[Browser] ⚠️ Click failed: {e}")
            return False
    
    async def type_text(self, text: str, selector: str = None) -> bool:
        """Type text into input"""
        if not HAS_PLAYWRIGHT or not self.page:
            return False
        
        try:
            if selector:
                await self.page.fill(selector, text, timeout=5000)
            else:
                await self.page.keyboard.type(text)
            return True
        except Exception as e:
            print(f"[Browser] ⚠️ Type failed: {e}")
            return False
    
    async def screenshot(self, path: str = None) -> Optional[bytes]:
        """Take screenshot"""
        if not HAS_PLAYWRIGHT or not self.page:
            return None
        
        try:
            if path:
                await self.page.screenshot(path=path)
                return None
            else:
                return await self.page.screenshot()
        except Exception as e:
            print(f"[Browser] ⚠️ Screenshot failed: {e}")
            return None
    
    async def close(self):
        """Close browser"""
        if self.context:
            await self.context.close()
        if self._playwright:
            await self._playwright.stop()
        BrowserSession._instances.pop(self.browser_name, None)
        self._is_running = False


async def browser_control_async(parameters: dict, player=None) -> str:
    """Async browser control handler - SMART TAB REUSE FOR ALL URLS"""
    action = parameters.get("action", "go_to")
    browser_name = parameters.get("browser", "brave").lower()
    url = parameters.get("url", "https://www.google.com")
    query = parameters.get("query", "")
    selector = parameters.get("selector", "")
    text = parameters.get("text", "")
    description = parameters.get("description", "")
    
    # Normalize action names
    action_map = {
        "open": "go_to",
        "open_url": "go_to",
        "navigate": "go_to",
        "goto": "go_to",
        "open_new_tab": "new_tab",
        "new_tab": "new_tab",
        "search": "search",
        "find": "search",
        "press": "click",
        "click_on": "click",
        "enter": "type",
        "write": "type",
        "capture": "screenshot",
        "exit": "close",
        "quit": "close",
    }
    
    if action in action_map:
        action = action_map[action]
    
    # Handle search action
    if action == "search":
        engine = parameters.get("engine", "google")
        search_urls = {
            "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
            "youtube": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
            "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
            "duckduckgo": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
        }
        url = search_urls.get(engine, search_urls["google"])
        action = "go_to"
    
    # Handle YouTube special case
    if "youtube.com" in url or (query and "youtube" in query.lower()):
        browser_name = "brave"
        if query and "youtube.com" not in url:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    
    session = BrowserSession.get_session(browser_name)
    
    result = ""
    
    try:
        if action == "go_to":
            # SMART: Check if browser is already running
            if session.is_already_running():
                print(f"[Browser] {browser_name} already running, opening '{url}' in new tab")
                success = open_url_in_existing_browser(browser_name, url)
                result = f"Opened in new tab: {url}" if success else f"Failed to open: {url}"
            else:
                print(f"[Browser] {browser_name} not running, launching and opening '{url}'")
                await session.launch()
                await session.goto(url)
                result = f"Launched {browser_name} and opened: {url}"
        
        elif action == "new_tab":
            # Force open in new tab (will launch browser if not running)
            await session.ensure_browser_and_open_url(url)
            result = f"Opened in new tab: {url}"
        
        elif action == "click":
            await session.launch()
            await asyncio.sleep(1)
            if description:
                success = await session.click(text=description)
            elif selector:
                success = await session.click(selector=selector)
            elif text:
                success = await session.click(text=text)
            else:
                success = False
            result = "Clicked on element" if success else "Click failed"
        
        elif action == "type":
            await session.launch()
            await asyncio.sleep(0.5)
            await session.type_text(text, selector if selector else None)
            result = f"Typed: {text[:50]}"
        
        elif action == "screenshot":
            await session.launch()
            screenshot_path = Path.home() / "Desktop" / f"screenshot_{int(time.time())}.png"
            await session.screenshot(str(screenshot_path))
            result = f"Screenshot saved to {screenshot_path}"
        
        elif action == "close":
            await session.close()
            result = f"Closed {browser_name}"
        
        else:
            result = f"Unknown action: {action}"
    
    except Exception as e:
        result = f"Browser error: {str(e)}"
    
    if player:
        player.write_log(f"[Browser] {result}")
    
    return result


def browser_control(parameters: dict, player=None) -> str:
    """Sync wrapper"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(browser_control_async(parameters, player))
        loop.close()
        return result
    except Exception as e:
        return f"Browser control failed: {e}"