"""
JARVIS REST Bridge — Android App API
Exposes JARVIS to the Android companion app over LAN (and optionally internet).
Endpoints:
  POST /api/chat          → Chat with JARVIS (returns response text)
  POST /api/command       → Execute any tool by name
  GET  /api/memory        → Get all memory entries
  POST /api/memory        → Write a memory entry
  GET  /api/status        → System health + active tasks
  GET  /api/faces         → List known faces
  POST /api/speak         → Make PC JARVIS speak
  GET  /api/config        → Get safe config (no secrets)
"""

import json
import threading
import traceback
from pathlib import Path
from datetime import datetime
import sys

# --- Lazy Flask import ---
try:
    from flask import Flask, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
MEMORY_PATH = BASE_DIR / "memory" / "long_term.json"
FACES_DIR   = BASE_DIR / "memory" / "faces"

_bridge_thread = None
_app = None

# ──────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────
def _get_bridge_token() -> str:
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("android_bridge_token", "JARVIS_BRIDGE_SECRET")
    except Exception:
        return "JARVIS_BRIDGE_SECRET"

def _check_auth(req) -> bool:
    token = req.headers.get("X-JARVIS-Token") or req.args.get("token", "")
    return token == _get_bridge_token()

def _auth_error():
    return jsonify({"error": "Unauthorized. Set X-JARVIS-Token header."}), 401

# ──────────────────────────────────────────────
# Build Flask app
# ──────────────────────────────────────────────
def _build_app(jarvis_instance=None):
    app = Flask("JarvisBridge")
    app.config["JSON_SORT_KEYS"] = False

    # ── /api/status ───────────────────────────
    @app.route("/api/status", methods=["GET"])
    def status():
        if not _check_auth(request): return _auth_error()
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
        except Exception:
            cpu, ram = -1, -1
        return jsonify({
            "status": "online",
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": cpu,
            "ram_percent": ram,
            "jarvis_alive": jarvis_instance is not None,
        })

    # ── /api/chat ─────────────────────────────
    @app.route("/api/chat", methods=["POST"])
    def chat():
        if not _check_auth(request): return _auth_error()
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"error": "No message provided"}), 400
        try:
            from core.llm_provider import call_llm
            from core.prompt import build_system_prompt
            try:
                system = build_system_prompt()
            except Exception:
                system = "You are JARVIS, an elite AI assistant."
            response = call_llm(message, system_prompt=system)
            return jsonify({"response": response, "source": "llm"})
        except Exception as e:
            return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

    # ── /api/command ──────────────────────────
    @app.route("/api/command", methods=["POST"])
    def command():
        if not _check_auth(request): return _auth_error()
        data = request.get_json(silent=True) or {}
        tool_name = data.get("tool", "").strip()
        params    = data.get("params", {})
        if not tool_name:
            return jsonify({"error": "No tool specified"}), 400
        try:
            from core.tools import get_dispatcher
            dispatcher = get_dispatcher()
            result = dispatcher.dispatch(tool_name, params)
            return jsonify({"result": str(result), "tool": tool_name})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── /api/memory GET ───────────────────────
    @app.route("/api/memory", methods=["GET"])
    def get_memory():
        if not _check_auth(request): return _auth_error()
        try:
            from memory.memory_manager import get_memory_manager
            mm = get_memory_manager()
            memories = mm.get_all()
            return jsonify({"memories": memories, "count": len(memories)})
        except Exception as e:
            # Fallback: read raw JSON
            try:
                raw = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
                return jsonify({"memories": raw, "count": len(raw), "source": "raw"})
            except Exception:
                return jsonify({"error": str(e)}), 500

    # ── /api/memory POST ──────────────────────
    @app.route("/api/memory", methods=["POST"])
    def write_memory():
        if not _check_auth(request): return _auth_error()
        data = request.get_json(silent=True) or {}
        key      = data.get("key", "")
        value    = data.get("value", "")
        category = data.get("category", "notes")
        if not key or not value:
            return jsonify({"error": "key and value required"}), 400
        try:
            from memory.memory_manager import remember
            remember(key, value, category)
            return jsonify({"ok": True, "key": key})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── /api/faces ────────────────────────────
    @app.route("/api/faces", methods=["GET"])
    def list_faces():
        if not _check_auth(request): return _auth_error()
        try:
            faces = []
            if FACES_DIR.exists():
                for f in FACES_DIR.iterdir():
                    if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".npy"}:
                        faces.append(f.stem)
            return jsonify({"faces": list(set(faces))})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── /api/speak ────────────────────────────
    @app.route("/api/speak", methods=["POST"])
    def speak():
        if not _check_auth(request): return _auth_error()
        data = request.get_json(silent=True) or {}
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "No text provided"}), 400
        try:
            if jarvis_instance and hasattr(jarvis_instance, "speak"):
                jarvis_instance.speak(text)
                return jsonify({"ok": True, "spoken": text})
            # Fallback: pyttsx3 or win32
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            return jsonify({"ok": True, "spoken": text, "source": "pyttsx3"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── /api/config ───────────────────────────
    @app.route("/api/config", methods=["GET"])
    def get_config():
        if not _check_auth(request): return _auth_error()
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            # Strip all secrets — only return safe display fields
            safe = {
                "device_name":       cfg.get("device_name", "JARVIS_NODE"),
                "ui_mark_version":   cfg.get("ui_mark_version", "CIFIK ELITE"),
                "ui_company_name":   cfg.get("ui_company_name", "CIFIK Intelegents"),
                "os_system":         cfg.get("os_system", "windows"),
                "deployment_mode":   cfg.get("force_brain", "hybrid"),
                "gemini_model":      cfg.get("gemini_model", "gemini-2.5-flash"),
            }
            return jsonify(safe)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── /api/screenshot ───────────────────────
    @app.route("/api/screenshot", methods=["GET"])
    def screenshot():
        if not _check_auth(request): return _auth_error()
        try:
            import mss, io, base64
            from PIL import Image
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                img = sct.grab(monitor)
                pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                pil.thumbnail((1280, 720))
                buf = io.BytesIO()
                pil.save(buf, format="JPEG", quality=75)
                b64 = base64.b64encode(buf.getvalue()).decode()
            return jsonify({"screenshot": b64, "format": "jpeg", "resolution": f"{pil.width}x{pil.height}"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────
def start_bridge(jarvis_instance=None, host="0.0.0.0", port=18789):
    """Start the REST bridge in a background daemon thread."""
    global _bridge_thread, _app
    if not FLASK_AVAILABLE:
        print("[Bridge] Flask not installed. Run: pip install flask")
        return None
    if _bridge_thread and _bridge_thread.is_alive():
        print(f"[Bridge] Already running on port {port}")
        return _bridge_thread

    _app = _build_app(jarvis_instance)

    def _run():
        import logging
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)  # Silence Flask access logs
        _app.run(host=host, port=port, use_reloader=False, threaded=True)

    _bridge_thread = threading.Thread(target=_run, name="JarvisBridge", daemon=True)
    _bridge_thread.start()
    print(f"[Bridge] REST API live at http://0.0.0.0:{port}  (Android: use PC LAN IP)")
    print(f"[Bridge] Token: {_get_bridge_token()}")
    return _bridge_thread


def rest_bridge(parameters: dict, **kwargs) -> str:
    """Tool entry point — start/stop/status the bridge."""
    action = (parameters or {}).get("action", "start").lower()
    port   = int((parameters or {}).get("port", 18789))
    if action == "start":
        t = start_bridge(port=port)
        return f"REST Bridge started on port {port}." if t else "Flask not available — pip install flask"
    elif action == "stop":
        return "Bridge runs as daemon thread — it stops when JARVIS exits."
    elif action == "status":
        alive = _bridge_thread and _bridge_thread.is_alive()
        return f"Bridge {'running' if alive else 'stopped'}."
    return f"Unknown action: {action}"
