import asyncio
from playwright.async_api import async_playwright
import os
from pathlib import Path

class GhostBrowser:
    def __init__(self, ui=None):
        self.ui = ui
        self.browser = None
        self.context = None
        self.page = None
        self.screenshot_dir = Path("memory/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def start(self, headless=True):
        """Initialize the Ghost Browser instance."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        return self

    async def navigate(self, url):
        """Navigate to a specific URL."""
        if not self.page: await self.start()
        await self.page.goto(url, wait_until="networkidle")
        return f"Successfully navigated to {url}"

    async def search_and_extract(self, query):
        """Perform a search and extract the main content."""
        if not self.page: await self.start()
        search_url = f"https://www.google.com/search?q={query}"
        await self.page.goto(search_url, wait_until="networkidle")
        
        # Extract snippets
        content = await self.page.evaluate('''() => {
            const results = Array.from(document.querySelectorAll('.g'));
            return results.map(r => {
                const title = r.querySelector('h3')?.innerText;
                const link = r.querySelector('a')?.href;
                const snippet = r.querySelector('.VwiC3b')?.innerText;
                return { title, link, snippet };
            }).filter(r => r.title);
        }''')
        
        return content

    async def take_screenshot(self, name="ghost_capture"):
        """Capture the current page for vision analysis."""
        if not self.page: return "No page open to capture."
        path = self.screenshot_dir / f"{name}.png"
        await self.page.screenshot(path=str(path))
        return str(path)

    async def close(self):
        """Shutdown the browser."""
        if self.browser:
            await self.browser.close()
            self.browser = None

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
            result = f"Ghost Browser found {len(results)} results for '{query}'."
        elif action == "capture":
            path = await gb.take_screenshot()
            result = f"Screenshot saved to {path}."
        else:
            result = "Unknown ghost_browser action."
        
        await gb.close()
        if player:
            player.write_log(f"🌐 Ghost Browser: {result}")
        return result
    except Exception as e:
        if gb: await gb.close()
        return f"Ghost Browser error: {e}"

def ghost_browser(parameters: dict = None, player=None):
    """Synchronous wrapper for JARVIS dispatcher."""
    return asyncio.run(ghost_browser_action(parameters, player))
