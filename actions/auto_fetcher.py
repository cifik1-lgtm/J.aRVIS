# auto_fetcher.py
import os
import sys
import json
import time
import shutil
import threading
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
WIKI_DIR = BASE_DIR / "memory" / "wiki"
WIKI_DIR.mkdir(parents=True, exist_ok=True)

def _load_config() -> dict:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def sync_system_info():
    """Fetches general system state and writes it to the Wiki."""
    try:
        import platform
        import psutil
        
        cpu_usage = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        
        md_content = f"""# System Performance Status

Last Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}
Operating System: {platform.system()} {platform.release()}
Machine: {platform.machine()}

## Resources
- **CPU Usage**: {cpu_usage}%
- **RAM Usage**: {ram.percent}% ({ram.used // (1024**2)} MB used / {ram.total // (1024**2)} MB total)
- **Disk Free**: {disk.free // (1024**3)} GB free / {disk.total // (1024**3)} GB total
"""
        with open(WIKI_DIR / "system_info.md", "w", encoding="utf-8") as f:
            f.write(md_content)
        print("[AutoFetcher] [SUCCESS] Synced system_info.md")
    except Exception as e:
        print(f"[AutoFetcher] [ERROR] Failed to sync system info: {e}")

def sync_github():
    """Mock/Skeleton for GitHub issues sync."""
    cfg = _load_config()
    token = cfg.get("github_token", "")
    repo = cfg.get("github_repo", "")
    
    if not token or not repo:
        # Generate placeholder instruction on how to configure
        md_content = """# GitHub Issues Sync

GitHub Sync is currently **Not Configured**. 
To configure GitHub sync, please add `"github_token": "YOUR_PERSONAL_ACCESS_TOKEN"` and `"github_repo": "owner/repo"` inside your `config/api_keys.json` file.
"""
        with open(WIKI_DIR / "github_issues.md", "w", encoding="utf-8") as f:
            f.write(md_content)
        return

    try:
        import requests
        headers = {"Authorization": f"token {token}"}
        url = f"https://api.github.com/repos/{repo}/issues?state=open"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            issues = resp.json()
            lines = [f"# GitHub Open Issues ({repo})", f"Last Sync: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
            for issue in issues[:10]: # Limit to top 10 for context length
                title = issue.get("title", "No Title")
                number = issue.get("number", "0")
                user = issue.get("user", {}).get("login", "unknown")
                url = issue.get("html_url", "")
                lines.append(f"- **#{number}** [{title}]({url}) by @{user}")
            
            if not issues:
                lines.append("No open issues found.")
                
            with open(WIKI_DIR / "github_issues.md", "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print("[AutoFetcher] [SUCCESS] Synced github_issues.md")
        else:
            print(f"[AutoFetcher] [WARN] GitHub API returned status code {resp.status_code}")
    except Exception as e:
        print(f"[AutoFetcher] [ERROR] Failed to sync GitHub: {e}")

def sync_calendar():
    """Mock/Skeleton for Google Calendar sync."""
    cfg = _load_config()
    calendar_enabled = cfg.get("calendar_enabled", False)
    
    if not calendar_enabled:
        md_content = """# Calendar Events Sync

Google Calendar Sync is currently **Not Enabled**.
To configure, please set `"calendar_enabled": true` in your `config/api_keys.json` and ensure credentials are set up.
"""
        with open(WIKI_DIR / "calendar_events.md", "w", encoding="utf-8") as f:
            f.write(md_content)
        return

    # Add real calendar API call logic here if credentials exist
    pass

def sync_all():
    """Triggers all configured integrations."""
    print("[AutoFetcher] [INFO] Triggering memory auto-fetch...")
    sync_system_info()
    sync_github()
    sync_calendar()
    
    # After sync, notify RAG engine to re-index the Wiki directory
    try:
        from memory.rag_engine import get_rag_engine
        rag = get_rag_engine()
        if rag:
            rag.ingest_wiki()
            print("[AutoFetcher] [SUCCESS] Re-indexed Memory Tree successfully.")
    except Exception as e:
        print(f"[AutoFetcher] [WARN] Failed to trigger RAG indexing: {e}")

def start_auto_fetcher(interval_minutes: int = 15):
    """Starts the auto-fetcher daemon in a background thread."""
    def run_loop():
        # First sync happens after initialization delay to prevent startup blocking
        time.sleep(5)
        while True:
            try:
                sync_all()
            except Exception as e:
                print(f"[AutoFetcher] [ERROR] Error in auto-fetch loop: {e}")
            time.sleep(interval_minutes * 60)

    t = threading.Thread(target=run_loop, name="AutoFetcherDaemon", daemon=True)
    t.start()
    print(f"[AutoFetcher] [INFO] Daemon started (polling interval: {interval_minutes} mins)")
