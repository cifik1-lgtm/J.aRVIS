"""
JARVIS Opportunity Dashboard Server
====================================
A persistent local server running at http://localhost:8000
that displays all projects JARVIS has autonomously built,
live opportunities data, and the Chronos pipeline status.

Starts automatically when JARVIS boots. Always visible at localhost:8000.
"""

import json
import threading
import socketserver
import http.server
from pathlib import Path
from datetime import datetime
import urllib.parse

BASE_DIR  = Path(__file__).resolve().parent.parent
PORT      = 8000
PROJECTS_DIR      = Path.home() / "Desktop" / "JarvisProjects"
OPPORTUNITIES_PATH = BASE_DIR / "memory" / "validated_opportunities.json"
CHRONOS_LOG_PATH   = BASE_DIR / "memory" / "chronos_execution_log.json"

_server_instance = None
_server_thread   = None
PAIN_POINTS_PATH = BASE_DIR / "memory" / "pain_points.json"


def _sync_status(url: str, new_status: str):
    """Update an opportunity's status in BOTH json files to prevent desync."""
    for path in (OPPORTUNITIES_PATH, PAIN_POINTS_PATH):
        if not path.exists():
            continue
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for item in items:
                if item.get("url") == url and item.get("status") != new_status:
                    item["status"] = new_status
                    changed = True
            if changed:
                path.write_text(json.dumps(items, indent=2), encoding="utf-8")
        except Exception:
            pass

# ──────────────────────────────────────────────
#  HTML Generator
# ──────────────────────────────────────────────

def _render_dashboard() -> str:
    # --- Opportunities ---
    opps = []
    if OPPORTUNITIES_PATH.exists():
        try:
            opps = json.loads(OPPORTUNITIES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    opp_cards = ""
    pending_cards = ""
    for o in opps:
        score = o.get("score", 0)
        bar_w = min(100, score * 10)
        status = o.get("status", "new")
        monetization = o.get("monetization", "Unknown")
        url_enc = o.get('url', '')
        
        # Base card
        card_html = f"""
        <div class="card opp-card">
          <div class="card-source">{o.get('source','?')} &bull; <span style="color:var(--yellow)">{monetization}</span></div>
          <h3 class="card-title">{o.get('title','Untitled')}</h3>
          <p class="card-desc">{o.get('description','')[:120]}...</p>
          <div class="score-bar-wrap">
            <div class="score-bar" style="width:{bar_w}%"></div>
          </div>
          <span class="score-label">Score: {score}/10 &bull; Status: {status.upper()}</span>
          <br><a class="card-link" href="{o.get('url','#')}" target="_blank">View Source ↗</a>
        """
        
        if status in ("pending_approval", "new"):
            # Add buttons for pending and new
            card_html += f"""
          <div style="margin-top:1rem;display:flex;gap:0.5rem;">
            <button onclick="fetch('/api/action', {{method:'POST',body:JSON.stringify({{action:'approve',url:'{url_enc}'}})}}).then(()=>window.location.reload())" style="padding:0.4rem 0.8rem;background:rgba(34,197,94,0.2);color:var(--green);border:1px solid var(--green);border-radius:6px;cursor:pointer;font-weight:bold;flex:1">Approve</button>
            <button onclick="fetch('/api/action', {{method:'POST',body:JSON.stringify({{action:'reject',url:'{url_enc}'}})}}).then(()=>window.location.reload())" style="padding:0.4rem 0.8rem;background:rgba(239,68,68,0.2);color:#ef4444;border:1px solid #ef4444;border-radius:6px;cursor:pointer;font-weight:bold;flex:1">Reject</button>
          </div>
        </div>
            """
            pending_cards += card_html
        else:
            card_html += "</div>"
            opp_cards += card_html
            
    if not pending_cards:
        pending_cards = '<p class="empty">No opportunities awaiting approval right now.</p>'
    if not opp_cards:
        opp_cards = '<p class="empty">No active opportunities found. JARVIS will scan soon.</p>'

    # --- Projects ---
    proj_cards = ""
    if PROJECTS_DIR.exists():
        for p in sorted(PROJECTS_DIR.iterdir()):
            if p.is_dir() and not p.name.startswith('.'):
                files = list(p.rglob("*.py")) + list(p.rglob("*.html"))
                has_server = any(f.name in ("app.py", "main.py", "server.py") for f in p.rglob("*.py"))
                server_badge = '<span class="badge badge-green">▶ Runnable</span>' if has_server else '<span class="badge badge-muted">Static</span>'
                proj_cards += f"""
                <div class="card proj-card">
                  <div class="proj-icon">🚀</div>
                  <h3 class="card-title">{p.name.replace('_',' ').title()}</h3>
                  <p class="card-desc">{len(files)} source files</p>
                  {server_badge}
                  <p class="proj-path">{p}</p>
                </div>
                """
    if not proj_cards:
        proj_cards = '<p class="empty">No projects built yet. JARVIS will build one soon.</p>'

    # --- Research Reports ---
    research_cards = ""
    for md_file in BASE_DIR.glob("*.md"):
        if md_file.name.lower() in ("readme.md", "docs.md"): continue
        if "plan" in md_file.name.lower() or "report" in md_file.name.lower() or "insights" in md_file.name.lower() or "strategy" in md_file.name.lower() or "comparison" in md_file.name.lower():
            file_sz = md_file.stat().st_size
            title = md_file.stem.replace('_', ' ').title()
            research_cards += f"""
            <div class="card proj-card">
              <div class="proj-icon">📊</div>
              <h3 class="card-title">{title}</h3>
              <p class="card-desc">Markdown Report • {file_sz // 1024} KB</p>
              <br><a class="card-link" href="/view_doc?path={urllib.parse.quote(md_file.name)}" target="_blank">View Document ↗</a>
            </div>
            """
    if not research_cards:
        research_cards = '<p class="empty">No research reports generated yet.</p>'

    # --- Chronos Log ---
    timeline_rows = ""
    if CHRONOS_LOG_PATH.exists():
        try:
            logs = json.loads(CHRONOS_LOG_PATH.read_text(encoding="utf-8"))
            for entry in reversed(logs[-10:]):
                ts  = entry.get("timestamp","")[:16].replace("T"," ")
                gn  = entry.get("goal_name","?")
                st  = entry.get("status","?")
                dot = "dot-green" if st == "completed" else "dot-yellow" if st == "running" else "dot-red"
                timeline_rows += f"""
                <tr>
                  <td class="ttime">{ts}</td>
                  <td><span class="dot {dot}"></span> {gn}</td>
                  <td class="tstatus">{st}</td>
                </tr>"""
        except Exception:
            pass
    if not timeline_rows:
        timeline_rows = '<tr><td colspan="3" class="empty">No Chronos activity yet.</td></tr>'

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta http-equiv="refresh" content="30"/>
<title>JARVIS — Opportunity Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
:root{{
  --bg:#0b0f1a; --surface:rgba(255,255,255,0.06);
  --border:rgba(255,255,255,0.10); --text:#e8edf5;
  --muted:rgba(232,237,245,0.55); --accent:#7c3aed;
  --cyan:#06b6d4; --green:#22c55e; --yellow:#f59e0b;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{min-height:100%;background:var(--bg);font-family:'Inter',system-ui,sans-serif;color:var(--text);overflow-x:hidden}}
body{{
  background:
    radial-gradient(ellipse at 10% 0%,rgba(124,58,237,.25),transparent 40%),
    radial-gradient(ellipse at 90% 0%,rgba(6,182,212,.18),transparent 35%),
    var(--bg);
}}

/* ── Layout ── */
.wrap{{max-width:1200px;margin:0 auto;padding:2rem 1.25rem 3rem}}
.topbar{{display:flex;align-items:center;justify-content:space-between;margin-bottom:2rem;
  padding:1rem 1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:18px;backdrop-filter:blur(20px)}}
.logo{{display:flex;align-items:center;gap:.75rem;font-weight:800;font-size:1.05rem;letter-spacing:-.03em}}
.logo-mark{{width:2.2rem;height:2.2rem;display:grid;place-items:center;border-radius:10px;
  background:linear-gradient(135deg,var(--accent),var(--cyan));font-size:.8rem;font-weight:900;color:#fff}}
.live-dot{{width:.55rem;height:.55rem;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.updated{{color:var(--muted);font-size:.82rem}}

/* ── Section headers ── */
.section-label{{font-size:.78rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin-bottom:1rem;display:flex;align-items:center;gap:.5rem}}
.section-label::after{{content:'';flex:1;height:1px;background:var(--border)}}

/* ── Grid ── */
.grid{{display:grid;gap:1rem}}
.grid-3{{grid-template-columns:repeat(3,1fr)}}
.grid-2{{grid-template-columns:repeat(2,1fr)}}
@media(max-width:900px){{.grid-3,.grid-2{{grid-template-columns:1fr}}}}
.mb2{{margin-bottom:2rem}}

/* ── Cards ── */
.card{{background:var(--surface);border:1px solid var(--border);border-radius:20px;
  padding:1.25rem;backdrop-filter:blur(16px);transition:border-color .2s,transform .2s}}
.card:hover{{border-color:rgba(255,255,255,.2);transform:translateY(-2px)}}
.card-source{{font-size:.75rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.5rem}}
.card-title{{font-size:1.05rem;font-weight:700;margin-bottom:.5rem;letter-spacing:-.02em}}
.card-desc{{font-size:.88rem;color:var(--muted);line-height:1.6;margin-bottom:.9rem}}
.card-link{{display:inline-block;margin-top:.5rem;font-size:.82rem;color:var(--cyan);text-decoration:none;font-weight:600}}
.card-link:hover{{text-decoration:underline}}

/* ── Score bar ── */
.score-bar-wrap{{height:5px;background:rgba(255,255,255,.1);border-radius:99px;overflow:hidden;margin-bottom:.35rem}}
.score-bar{{height:100%;background:linear-gradient(90deg,var(--accent),var(--cyan));border-radius:99px;transition:width .5s}}
.score-label{{font-size:.78rem;color:var(--muted)}}

/* ── Projects ── */
.proj-icon{{font-size:1.6rem;margin-bottom:.6rem}}
.proj-path{{font-size:.73rem;color:var(--muted);margin-top:.5rem;word-break:break-all}}

/* ── Badges ── */
.badge{{display:inline-block;padding:.25rem .65rem;border-radius:99px;font-size:.75rem;font-weight:700;margin-top:.5rem}}
.badge-green{{background:rgba(34,197,94,.15);color:var(--green);border:1px solid rgba(34,197,94,.3)}}
.badge-muted{{background:rgba(255,255,255,.07);color:var(--muted);border:1px solid var(--border)}}

/* ── Timeline table ── */
.tbl{{width:100%;border-collapse:collapse;font-size:.88rem}}
.tbl th{{text-align:left;padding:.5rem .75rem;color:var(--muted);font-weight:600;border-bottom:1px solid var(--border)}}
.tbl td{{padding:.6rem .75rem;border-bottom:1px solid rgba(255,255,255,.05)}}
.ttime{{color:var(--muted);font-family:monospace;font-size:.8rem}}
.tstatus{{text-transform:capitalize;color:var(--muted)}}
.dot{{display:inline-block;width:.5rem;height:.5rem;border-radius:50%;margin-right:.4rem;vertical-align:middle}}
.dot-green{{background:var(--green)}}
.dot-yellow{{background:var(--yellow)}}
.dot-red{{background:#ef4444}}

/* ── Stat strip ── */
.stats{{display:flex;gap:1rem;margin-bottom:2rem;flex-wrap:wrap}}
.stat{{flex:1;min-width:140px;background:var(--surface);border:1px solid var(--border);
  border-radius:16px;padding:1rem 1.25rem;backdrop-filter:blur(12px)}}
.stat-num{{font-size:2rem;font-weight:800;letter-spacing:-.05em;
  background:linear-gradient(135deg,#fff,var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}}
.stat-name{{font-size:.8rem;color:var(--muted);font-weight:600;margin-top:.2rem}}

.empty{{color:var(--muted);font-size:.9rem;padding:.5rem 0;font-style:italic}}
</style>
</head>
<body>
<div class="wrap">

  <!-- Top bar -->
  <div class="topbar">
    <div class="logo">
      <div class="logo-mark">J</div>
      JARVIS Opportunity Dashboard
      <div class="live-dot" title="Auto-refreshes every 30s"></div>
    </div>
    <span class="updated">Last updated: {now}</span>
  </div>

  <!-- Stat strip -->
  <div class="stats">
    <div class="stat">
      <div class="stat-num">{len(opps)}</div>
      <div class="stat-name">Validated Ideas</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(list(PROJECTS_DIR.iterdir())) if PROJECTS_DIR.exists() else 0}</div>
      <div class="stat-name">MVPs Built</div>
    </div>
    <div class="stat">
      <div class="stat-num">8000</div>
      <div class="stat-name">Local Port</div>
    </div>
    <div class="stat">
      <div class="stat-num">🟢</div>
      <div class="stat-name">Engine Online</div>
    </div>
  </div>

  <!-- Awaiting Approval -->
  <div class="mb2">
    <div class="section-label" style="color:var(--yellow)">⚠️ Awaiting Your Approval</div>
    <div class="grid grid-3">
      {pending_cards}
    </div>
  </div>

  <!-- Top Opportunities -->
  <div class="mb2">
    <div class="section-label">🎯 Top Opportunities Found by JARVIS</div>
    <div class="grid grid-3">
      {opp_cards}
    </div>
  </div>

  <!-- Projects -->
  <div class="mb2">
    <div class="section-label">🚀 Autonomous MVPs Built</div>
    <div class="grid grid-3">
      {proj_cards}
    </div>
  </div>

  <!-- Research Reports -->
  <div class="mb2">
    <div class="section-label">📊 Autonomous Research & Plans</div>
    <div class="grid grid-3">
      {research_cards}
    </div>
  </div>

  <!-- Chronos Timeline -->
  <div class="mb2">
    <div class="section-label">⏱ Chronos Engine — Recent Activity</div>
    <div class="card">
      <table class="tbl">
        <thead><tr><th>Time</th><th>Task</th><th>Status</th></tr></thead>
        <tbody>{timeline_rows}</tbody>
      </table>
    </div>
  </div>

</div>
</body>
</html>"""


# ──────────────────────────────────────────────
#  HTTP Handler
# ──────────────────────────────────────────────

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/view_doc':
            qs = urllib.parse.parse_qs(parsed.query)
            if 'path' in qs:
                doc_path = BASE_DIR / qs['path'][0]
                if doc_path.exists() and doc_path.is_file():
                    content = doc_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found")
            return

        html = _render_dashboard().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_POST(self):
        if self.path == '/api/action':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                action = data.get('action')
                url = data.get('url')
                
                if OPPORTUNITIES_PATH.exists():
                    opps = json.loads(OPPORTUNITIES_PATH.read_text(encoding="utf-8"))
                    for o in opps:
                        if o.get('url') == url:
                            if action == 'approve':
                                o['status'] = 'approved'
                                # Queue the build task immediately!
                                try:
                                    from agent.task_queue import get_queue, TaskPriority
                                    title = o.get('title', 'Unknown Project')
                                    description = o.get('description', '')
                                    opp_url = o.get('url', '')

                                    def _mark_built(task_id, result, _url=opp_url):
                                        """Callback: mark opportunity as 'built' after build finishes."""
                                        try:
                                            _sync_status(_url, "built")
                                            print(f"[Dashboard] Marked opportunity as 'built': {_url[:60]}")
                                        except Exception as e:
                                            print(f"[Dashboard] Failed to mark built: {e}")

                                    goal_msg = f"Build a complete Python/HTML MVP codebase for the opportunity '{title}'. Description: {description}. Use the dev_agent tool to create this project."
                                    get_queue().submit(
                                        goal=goal_msg,
                                        priority=TaskPriority.HIGH,
                                        on_complete=_mark_built,
                                    )
                                    print(f"[Dashboard] Queued high-priority build task for: {title}")
                                except Exception as qe:
                                    print(f"[Dashboard] Failed to queue build task: {qe}")
                            elif action == 'reject':
                                o['status'] = 'rejected'
                            break
                    OPPORTUNITIES_PATH.write_text(json.dumps(opps, indent=2), encoding="utf-8")

                    # Sync status back to pain_points.json
                    _sync_status(url, o.get('status', 'rejected'))
                    
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # Silent — no console spam


# ──────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────

def start_dashboard(player=None):
    """Start the dashboard server in a daemon thread. Safe to call multiple times."""
    global _server_instance, _server_thread
    if _server_instance:
        return "Dashboard is already running at http://localhost:8000"

    try:
        socketserver.TCPServer.allow_reuse_address = True
        _server_instance = socketserver.TCPServer(("", PORT), DashboardHandler)
        _server_thread = threading.Thread(
            target=_server_instance.serve_forever,
            name="JarvisDashboard",
            daemon=True
        )
        _server_thread.start()
        msg = f"JARVIS Opportunity Dashboard is now live at http://localhost:{PORT}"
        print(f"[Dashboard] {msg}")
        if player:
            player.write_log(f"[Dashboard] {msg}")
        return msg
    except OSError as e:
        if "10048" in str(e) or "Address already in use" in str(e):
            msg = f"Port {PORT} is already in use. Dashboard may already be running."
            if player:
                player.write_log(f"[Dashboard] {msg}")
            return msg
        return f"[Dashboard] Failed to start: {e}"


def stop_dashboard():
    global _server_instance
    if _server_instance:
        _server_instance.shutdown()
        _server_instance = None
        return "Dashboard stopped."
    return "Dashboard was not running."


def opportunity_dashboard(parameters: dict, player=None) -> str:
    """Tool entry point for JARVIS ToolDispatcher."""
    action = parameters.get("action", "start").lower()
    if action == "stop":
        return stop_dashboard()
    return start_dashboard(player=player)
