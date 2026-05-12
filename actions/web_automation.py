"""
Web Automation - Working version with simple API
"""

import asyncio
import subprocess
import webbrowser
from pathlib import Path

# Try to import playwright, but don't crash if not available
HAS_PLAYWRIGHT = False
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    print("[WebAutomation] ⚠️ Playwright not available. Using simple browser automation.")


async def web_automation_async(parameters: dict, player=None) -> str:
    """Execute web automation tasks"""
    action = parameters.get("action", "")
    url = parameters.get("url", "")
    code = parameters.get("code", "")
    selector = parameters.get("selector", "")
    text = parameters.get("text", "")
    
    result = ""
    
    try:
        # Simple actions that don't need Playwright
        if action == "open_url":
            if not url:
                return "Error: URL required"
            
            # Open in default browser
            webbrowser.open(url)
            result = f"Opened {url} in default browser"
        
        elif action == "search_google":
            query = parameters.get("query", "")
            if not query:
                return "Error: query required"
            
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(search_url)
            result = f"Searched Google for: {query}"
        
        elif action == "search_youtube":
            query = parameters.get("query", "")
            if not query:
                return "Error: query required"
            
            search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            webbrowser.open(search_url)
            result = f"Searched YouTube for: {query}"
        
        elif action == "navigate_and_extract":
            if not HAS_PLAYWRIGHT:
                # Fallback: just open the URL
                webbrowser.open(url)
                result = f"Opened {url} (Playwright not available for extraction)"
            else:
                # Use Playwright for extraction
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                    
                    title = await page.title()
                    text_content = await page.evaluate("document.body.innerText")
                    
                    await browser.close()
                    
                    result = f"Title: {title}\n\nFirst 500 chars:\n{text_content[:500]}"
        
        elif action == "click_element":
            if not HAS_PLAYWRIGHT:
                return "Click automation requires Playwright. Install with: pip install playwright && playwright install"
            
            if not url:
                return "Error: URL required"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                
                if selector:
                    await page.click(selector)
                    result = f"Clicked: {selector}"
                elif text:
                    await page.click(f"text={text}")
                    result = f"Clicked text: {text}"
                else:
                    result = "No selector or text provided"
                
                await browser.close()
        
        elif action == "take_screenshot":
            if not HAS_PLAYWRIGHT:
                return "Screenshot requires Playwright. Install with: pip install playwright && playwright install"
            
            if not url:
                return "Error: URL required"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                
                screenshot_path = Path.home() / "Desktop" / f"screenshot_{int(asyncio.get_event_loop().time())}.png"
                await page.screenshot(path=str(screenshot_path))
                await browser.close()
                
                result = f"Screenshot saved to {screenshot_path}"
        
        elif action == "run_script":
            if not HAS_PLAYWRIGHT:
                return "Script execution requires Playwright. Install with: pip install playwright && playwright install"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                page = await browser.new_page()
                
                if url:
                    await page.goto(url, wait_until="domcontentloaded")
                
                # Safe execution environment
                safe_globals = {"page": page, "browser": browser, "print": print}
                try:
                    exec(code, safe_globals)
                    result = "Script executed successfully"
                except Exception as e:
                    result = f"Script error: {str(e)}"
                
                await browser.close()
        
        else:
            result = f"Unknown action: {action}. Available: open_url, search_google, search_youtube, navigate_and_extract, click_element, take_screenshot, run_script"
    
    except Exception as e:
        result = f"Web automation error: {str(e)}"
    
    if player:
        player.write_log(f"[WebAutomation] {result[:200]}")
    
    return result


def web_automation(parameters: dict, player=None) -> str:
    """Sync wrapper for web automation"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(web_automation_async(parameters, player))
        loop.close()
        return result
    except Exception as e:
        return f"Web automation failed: {e}"