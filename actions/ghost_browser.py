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

    async def navigate(self, url_or_query):
        """Navigate to a specific URL or perform a search if it's a query."""
        if not self.page: await self.start()
        
        # Smart-Routing: Detect if it's a query or a URL
        is_url = "." in url_or_query and " " not in url_or_query.strip()
        
        if not is_url:
            # It's a query! Reroute to Google
            target_url = f"https://www.google.com/search?q={url_or_query.replace(' ', '+')}"
        else:
            target_url = url_or_query
            if not target_url.startswith("http"): target_url = f"https://{target_url}"
        
        await self.page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        title = await self.page.title()
        return f"Successfully navigated to '{title}' at {target_url}"

    async def search_and_extract(self, query):
        """Perform a search and extract the main content."""
        if not self.page: await self.start()
        
        current_url = self.page.url
        if "google.com" in current_url:
            # Extract snippets using Google selectors
            content = await self.page.evaluate('''() => {
                const results = [];
                const elements = document.querySelectorAll('div.g, div.v7W49e > div, .tF2Cxc');
                elements.forEach(el => {
                    const titleEl = el.querySelector('h3');
                    const linkEl = el.querySelector('a');
                    const snippetEl = el.querySelector('.VwiC3b, .MU_pbb, .s3uMBd');
                    if (titleEl && linkEl) {
                        results.push({
                            title: titleEl.innerText,
                            link: linkEl.href,
                            snippet: snippetEl ? snippetEl.innerText : ""
                        });
                    }
                });
                return results;
            }''')
        else:
            # Generic Page Scan: Find all headlines and links
            content = await self.page.evaluate('''() => {
                const results = [];
                // Look for common headline tags
                const elements = document.querySelectorAll('h1, h2, h3, h4, .headline, .title');
                elements.forEach(el => {
                    const text = el.innerText.trim();
                    const linkEl = el.querySelector('a') || el.closest('a');
                    if (text && text.length > 10) {
                        results.push({
                            title: text,
                            link: linkEl ? linkEl.href : window.location.href,
                            snippet: ""
                        });
                    }
                });
                return results.slice(0, 15); // Limit to top 15 findings
            }''')
        
        if not content:
            # Neural Sweep Fallback: Extract all relevant text snippets
            text_content = await self.page.inner_text("body")
            # Return a cleaned up preview of the page text
            return [{"title": "Page Text Sweep", "link": self.page.url, "snippet": text_content[:1000]}]
            
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
            target = url or query # Use whichever was provided
            if not target: return "I need a URL or query to navigate, sir."
            result = await gb.navigate(target)
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
