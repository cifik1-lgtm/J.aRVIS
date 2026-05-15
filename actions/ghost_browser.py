import asyncio
from playwright.async_api import async_playwright
import os
import sys
from pathlib import Path

class GhostBrowser:
    def __init__(self, ui=None):
        self.ui = ui
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.screenshot_dir = Path("memory/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def start(self, headless=True):
        """Initialize the Ghost Browser instance."""
        if self.page: return self
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        self.page = await self.context.new_page()
        # Stealth: Remove the webdriver flag
        await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return self

    async def navigate(self, url):
        """Navigate to a specific URL."""
        if not self.page: await self.start()
        if not url.startswith("http"): url = f"https://{url}"
        
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await self.page.title()
        return f"Successfully navigated to '{title}' at {url}"

    async def search_and_extract(self, query):
        """Perform a search and extract the main content."""
        if not self.page: await self.start()
        search_url = f"https://www.google.com/search?q={query}"
        await self.page.goto(search_url, wait_until="networkidle")
        
        # Extract snippets using multiple possible selectors
        content = await self.page.evaluate('''() => {
            const results = [];
            // Common selectors for Google search results
            const elements = document.querySelectorAll('div.g, div.v7W49e > div, .tF2Cxc');
            
            elements.forEach(el => {
                const titleEl = el.querySelector('h3');
                const linkEl = el.querySelector('a');
                const snippetEl = el.querySelector('.VwiC3b, .MU_pbb, .s3uMBd');
                
                if (titleEl && linkEl) {
                    results.append({
                        title: titleEl.innerText,
                        link: linkEl.href,
                        snippet: snippetEl ? snippetEl.innerText : ""
                    });
                }
            });
            return results;
        }''')
        
        return content

    async def take_screenshot(self, name="ghost_capture"):
        """Capture the current page for vision analysis."""
        if not self.page: return "No page open to capture."
        path = self.screenshot_dir / f"{name}.png"
        await self.page.screenshot(path=str(path))
        return str(path)

    async def close(self):
        """Shutdown the browser cleanly."""
        try:
            if self.page: await self.page.close()
            if self.context: await self.context.close()
            if self.browser: await self.browser.close()
            if self.playwright: await self.playwright.stop()
        except:
            pass

async def ghost_browser_action(parameters: dict = None, player=None):
    """Tool entry point for JARVIS."""
    params = parameters or {}
    action = params.get("action", "navigate")
    url = params.get("url", "")
    query = params.get("query", "")
    
    gb = GhostBrowser(player)
    try:
        await gb.start(headless=True)
        if action == "navigate":
            result = await gb.navigate(url)
        elif action == "search":
            results = await gb.search_and_extract(query)
            if not results:
                # Fallback: maybe just get page text
                text = await gb.page.inner_text("body")
                result = f"Ghost Browser search for '{query}' returned no structured results. Page text preview: {text[:200]}"
            else:
                result = f"Ghost Browser found {len(results)} results for '{query}'."
        elif action == "capture":
            path = await gb.take_screenshot()
            result = f"Screenshot saved to {path}."
        else:
            result = f"Unknown ghost_browser action: {action}"
        
        await gb.close()
        return result
    except Exception as e:
        try: await gb.close()
        except: pass
        return f"Ghost Browser error: {str(e)}"

def ghost_browser(parameters: dict = None, player=None):
    """Synchronous wrapper for JARVIS dispatcher."""
    try:
        # Check if there is an existing loop in this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(ghost_browser_action(parameters, player))
    except Exception as e:
        return f"Async Bridge Error: {e}"
    finally:
        try: loop.close()
        except: pass
