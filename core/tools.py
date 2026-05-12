import asyncio
import importlib
import traceback
import threading
import json
from datetime import datetime
from google.genai import types

# ============================================================================
# TOOL DECLARATIONS (Lazy-Loaded Registry)
# ============================================================================

TOOL_DECLARATIONS = [
    {
        "name": "system_control",
        "description": "Control core systems",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "switch_brain | toggle_silence | set_autonomous_mode"},
                "brain": {"type": "STRING"},
                "state": {"type": "BOOLEAN"},
                "autonomous": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "preference_manager",
        "description": "Manage user-specific style, UI, and behavioral preferences.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "set | get | list"},
                "preference_key": {"type": "STRING"},
                "value": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "open_app",
        "description": "Opens any desktop application by name (e.g. spotify, notepad, calculator, steam, discord).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Returns TEXT search results without opening a browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gets weather report",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a message",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver": {"type": "STRING"},
                "message_text": {"type": "STRING"},
                "platform": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a reminder",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date": {"type": "STRING"},
                "time": {"type": "STRING"},
                "message": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_control",
        "description": "Controls YouTube PLAYBACK in the browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "query": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "screen_process",
        "description": "Captures and analyzes screen",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING"},
                "text": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "neural_inspector",
        "description": "Advanced neural object detection (uses TensorFlow deep learning).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {"type": "STRING", "description": "screen | webcam"},
                "image_path": {"type": "STRING", "description": "Optional: Specific image file to analyze"}
            }
        }
    },
    {
        "name": "computer_settings",
        "description": "OS-level keyboard shortcuts and system tweaks.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "description": {"type": "STRING"},
                "value": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "delegate_task",
        "description": "DELEGATE complex tasks (web searching, coding, file operations, browser control, detailed research) to the Expert Brains. Use this for ANY task that requires more than simple conversation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal": {"type": "STRING", "description": "The specific task or question to solve."},
                "priority": {"type": "STRING", "enum": ["HIGH", "NORMAL", "LOW"]},
                "context": {"type": "STRING", "description": "Any additional context needed for the task."}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "system_control",
        "description": "Controls JARVIS system states like silencing, autonomous mode, and brain switching.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["toggle_silence", "set_autonomous_mode", "switch_brain", "system_diagnostic"]},
                "state": {"type": "BOOLEAN"},
                "autonomous": {"type": "BOOLEAN"},
                "brain": {"type": "STRING"},
                "confirmed": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "browser_control",
        "description": "Opens a BROWSER WINDOW and navigates to a URL.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "go_to | new_tab | search | click | type | screenshot | close"},
                "url": {"type": "STRING"},
                "query": {"type": "STRING"},
                "browser": {"type": "STRING", "description": "chrome | brave | edge | firefox"},
                "selector": {"type": "STRING"},
                "text": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "File and folder operations.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "path": {"type": "STRING"},
                "name": {"type": "STRING"},
                "content": {"type": "STRING"},
                "destination": {"type": "STRING"},
                "target": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct mouse/keyboard control and OS tasks.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "text": {"type": "STRING"},
                "keys": {"type": "STRING"},
                "x": {"type": "NUMBER"}, "y": {"type": "NUMBER"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "save_memory",
        "description": "Save important facts to JARVIS memory.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING"},
                "key": {"type": "STRING"},
                "value": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "shutdown_jarvis",
        "description": "Closes the JARVIS application.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "confirmed": {"type": "BOOLEAN"}
            },
            "required": []
        }
    },
    {
        "name": "reboot_jarvis",
        "description": "Restarts the JARVIS application.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "confirmed": {"type": "BOOLEAN"}
            },
            "required": []
        }
    },
    {
        "name": "code_helper",
        "description": "Coding assistance.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "description": {"type": "STRING"},
                "language": {"type": "STRING"},
                "file_path": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "vision_inspector",
        "description": "Analyzes the environment using webcam or screen capture.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {"type": "STRING", "description": "webcam | screen | auto"},
                "focus": {"type": "STRING", "description": "text | object | face | ui"}
            },
            "required": ["source"]
        }
    },
    {
        "name": "face_manager",
        "description": "Learn, recognize, list, or forget faces.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "learn | recognize | list | forget"},
                "name": {"type": "STRING"},
                "relationship": {"type": "STRING"},
                "image_path": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "camera_feed",
        "description": "Control built-in camera feed.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "state": {"type": "BOOLEAN"},
                "camera_index": {"type": "INTEGER"},
                "list_cameras": {"type": "BOOLEAN"}
            },
            "required": ["state"]
        }
    },
    {
        "name": "youtube_video",
        "description": "Advanced YouTube actions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "query": {"type": "STRING"},
                "url": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_processor",
        "description": "AI-powered file analysis (OCR, summarization).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "file_path": {"type": "STRING"},
                "prompt": {"type": "STRING"}
            },
            "required": ["action", "file_path"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Manage the desktop wallpaper and organization.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "path": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "ip_checker",
        "description": "Check the local and public IP addresses of this machine.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING", "description": "local | public | both"}
            },
            "required": []
        }
    },
    {
        "name": "git_manager",
        "description": "Git repository operations.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "url": {"type": "STRING"},
                "path": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "media_downloader",
        "description": "Download video/audio from URLs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING"},
                "format": {"type": "STRING"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "python_sandbox",
        "description": "Execute Python code safely.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "code": {"type": "STRING"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "webcam_vision",
        "description": "Capture and analyze webcam photo.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING"}
            },
            "required": []
        }
    },
    {
        "name": "notification_manager",
        "description": "Show Windows desktop notifications.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "message": {"type": "STRING"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "email_manager",
        "description": "Send or read emails.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "to": {"type": "STRING"},
                "subject": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "sql_interactor",
        "description": "Execute SQL queries.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "db_path": {"type": "STRING"}
            },
            "required": ["action", "db_path"]
        }
    },
    {
        "name": "web_automation",
        "description": "Automate web tasks using Playwright.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "url": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_organizer",
        "description": "Organize files by type.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "directory": {"type": "STRING"}
            },
            "required": []
        }
    },
    {
        "name": "semantic_search",
        "description": "AI semantic search through documents.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "query": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "self_healing",
        "description": "AI self-repair for broken modules.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target_file": {"type": "STRING"},
                "error_message": {"type": "STRING"}
            },
            "required": ["target_file", "error_message"]
        }
    },
    {
        "name": "admin_controller",
        "description": "Admin level system controls.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "command": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_agent",
        "description": "Advanced code file operations.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"},
                "file_path": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "flight_finder",
        "description": "Search for flight information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin": {"type": "STRING"},
                "destination": {"type": "STRING"}
            },
            "required": ["origin", "destination"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Autonomous developer agent.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {"type": "STRING"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "game_updater",
        "description": "Update/Install games on Steam/Epic.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "relay_command",
        "description": "Send command to another device (EVA/CIFIK).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {"type": "STRING"},
                "command": {"type": "STRING"}
            },
            "required": ["target", "command"]
        }
    }
]

# ============================================================================
# TOOL DISPATCHER (The Manager)
# ============================================================================

class ToolDispatcher:
    def __init__(self, orchestrator):
        self.orch = orchestrator
        self.ui = orchestrator.ui
        self._tool_cache = {}
        self._loop_count = 0
        self._last_call = None
        
        # Classify tool risk level
        self._Tiers = {
            "harmless": ["web_search", "weather_report", "ip_checker", "save_memory", "vision_inspector", "preference_manager"],
            "state_changing": ["file_controller", "open_app", "browser_control", "face_manager", "desktop_control", "youtube_control"],
            "privileged": ["admin_controller", "reboot_jarvis", "shutdown_jarvis", "python_sandbox", "relay_command"]
        }

    def _get_tool(self, module_name, func_name=None):
        """Lazy load a tool module and return the function."""
        if module_name not in self._tool_cache:
            try:
                mod = importlib.import_module(f"actions.{module_name}")
                self._tool_cache[module_name] = mod
            except Exception as e:
                print(f"[ToolManager] ❌ Failed to load {module_name}: {e}")
                return None
        
        mod = self._tool_cache[module_name]
        return getattr(mod, func_name or module_name, None)

    def _get_safety_tier(self, tool_name):
        for tier, tools in self._Tiers.items():
            if tool_name in tools: return tier
        return "unknown"

    async def dispatch(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        
        # Rate limit & autonomous mode injection (handled by orchestrator logic)
        if self.orch.autonomous_enabled and "auto" not in args:
            args["auto"] = True
            
        print(f"[JARVIS] 🔧 {name} {args}")
        self.ui.set_state("THINKING")
        
        # Loop Protection: Detect and break recursive tool calls
        call_sig = f"{name}:{json.dumps(args, sort_keys=True)}"
        if call_sig == self._last_call:
            self._loop_count += 1
            if self._loop_count >= 3:
                msg = f"Loop Protection: Aborted repeated call to {name}."
                print(f"[JARVIS] 🛡️ {msg}")
                return types.FunctionResponse(id=fc.id, name=name, response={"result": msg})
        else:
            self._last_call = call_sig
            self._loop_count = 0
            
        tier = self._get_safety_tier(name)
        if tier == "privileged":
            print(f"[JARVIS] 🛡️ Privileged tool '{name}' invoked. Monitoring closely.")
        
        result = "Done."
        
        try:
            # Execution Watchdog: 30-60s timeout threshold
            timeout = 60 if name in ["browser_control", "python_sandbox", "web_automation"] else 30
            
            async def _execute_logic():
                # 1. CORE SYSTEM TOOLS
                if name == "system_control":
                    action = args.get("action", "")
                    if action == "toggle_silence":
                        target_state = args.get("state")
                        if target_state is None:
                            target_state = not self.orch.silent_mode
                        
                        # AI PROTECT: Prevent the AI from deactivating its own silent mode.
                        # Only activation is allowed via tool. Deactivation must happen via 'wake up' voice command.
                        if not target_state and self.orch.silent_mode:
                            return "I cannot deactivate silent mode myself, sir. You must say 'wake up' to restore my voice."
                        
                        self.orch.voice_enabled = not target_state
                        self.orch.silent_mode = target_state
                        return f"Silence mode {'activated' if target_state else 'deactivated'}, sir."
                    elif action == "set_autonomous_mode":
                        auto = args.get("autonomous", True)
                        self.orch._update_config_autonomous(auto)
                        return f"Autonomous mode {'enabled' if auto else 'disabled'}, sir."
                    elif action == "switch_brain":
                        brain = args.get("brain", "gemini")
                        self.orch._update_config_brain(brain)
                        self.orch._restart_connection()
                        return f"Switched to {brain} brain, sir."
                    elif action == "system_diagnostic":
                        results = []
                        try:
                            from agent.planner import _get_api_key
                            if _get_api_key("gemini"): results.append("Gemini: Online ✅")
                            else: results.append("Gemini: Missing Key ❌")
                        except: results.append("Gemini: Error ❌")
                        try:
                            if _get_api_key("openrouter"): results.append("OpenRouter: Online ✅")
                            else: results.append("OpenRouter: Missing Key ❌")
                        except: results.append("OpenRouter: Error ❌")
                        try:
                            from core.local_llm import is_ollama_online
                            if is_ollama_online(): results.append("Ollama (Local): Online ✅")
                            else: results.append("Ollama (Local): Offline ❌")
                        except: results.append("Ollama (Local): Error ❌")
                        
                        summary = " | ".join(results)
                        return f"System Diagnostic: {summary}"

                # 2. TASK DELEGATION (HIVE MIND ROUTER)
                if name == "delegate_task":
                    goal = args.get("goal", "")
                    priority = args.get("priority", "NORMAL")
                    context = args.get("context", "")
                    
                    from agent.task_queue import get_queue, TaskPriority
                    prio_map = {"HIGH": TaskPriority.HIGH, "NORMAL": TaskPriority.NORMAL, "LOW": TaskPriority.LOW}
                    
                    # Submit to the Hive Mind Task Queue
                    get_queue().submit(
                        goal=goal, 
                        priority=prio_map.get(priority, TaskPriority.NORMAL),
                        speak=lambda m: self.orch.speak(f"Sir, regarding your request for {goal[:30]}... {m}")
                    )
                    return f"Task delegated to Expert Brains. I'm working on '{goal}' now, sir."
                            else: results.append("OpenRouter: Missing Key ❌")
                        except: results.append("OpenRouter: Error ❌")
                        try:
                            from core.local_llm import is_ollama_online
                            if is_ollama_online(): results.append("Local Ollama: Online ✅")
                            else: results.append("Local Ollama: Offline ❌")
                        except: results.append("Local Ollama: Not Found ❌")
                        status = "\n".join(results)
                        return f"System Diagnostic Complete, Sir:\n{status}"

                elif name == "preference_manager":
                    from memory.memory_manager import remember, get_memory_manager
                    mm = get_memory_manager()
                    action = args.get("action", "")
                    key = args.get("preference_key", "")
                    val = args.get("value", "")
                    
                    if action == "set" and key and val:
                        remember(key, val, "preferences")
                        return f"Preference '{key}' set to '{val}', sir."
                    elif action == "get" and key:
                        p = mm.get_preference(key)
                        return f"The preference for '{key}' is '{p}', sir." if p else f"No preference found for '{key}', sir."
                    elif action == "list":
                        prefs = mm.get_all_preferences()
                        if prefs:
                            p_str = ", ".join([f"{k}: {v}" for k, v in prefs.items()])
                            return f"Current preferences: {p_str}"
                        return "No preferences recorded yet, sir."

                elif name == "save_memory":
                    from memory.memory_manager import remember
                    cat = args.get("category", "notes")
                    key = args.get("key", "")
                    val = args.get("value", "")
                    if key and val:
                        remember(key, val, cat)
                        if self.orch.silent_mode:
                            self.ui.write_log(f"SYS: 🧠 Ghost Memo: {key} -> {val[:40]}...")
                    return "Memory saved."

                elif name == "camera_feed":
                    camera_index = args.get("camera_index", None)
                    if camera_index is not None:
                        self.ui.camera = camera_index
                        return f"Switched to camera {camera_index}, sir."
                    else:
                        state = args.get("state", True)
                        if hasattr(self.ui, 'hud') and hasattr(self.ui.hud, 'toggle_camera'):
                            self.ui.hud.toggle_camera(bool(state))
                            return f"Camera feed {'activated' if state else 'deactivated'}, sir."

                elif name == "face_manager":
                    from actions.face_memory import get_face_memory
                    face_mem = get_face_memory()
                    action = args.get("action", "")
                    
                    if action == "learn":
                        n = args.get("name", "")
                        rel = args.get("relationship", "friend")
                        path = args.get("image_path") or self.ui.current_file
                        if not n or not path: return "I need a name and an image to learn a face, sir."
                        r = face_mem.learn_face(path, n, rel)
                        return r.get("message", "Face learned, sir.")
                    
                    elif action == "recognize":
                        path = args.get("image_path") or self.ui.current_file
                        if not path: return "Please provide an image for me to analyze, sir."
                        results = face_mem.recognize_face_from_image(path)
                        if results:
                            names = [r.get("name", "Unknown") for r in results]
                            return f"I see {len(results)} faces: {', '.join(names)}, sir."
                        else: return "I couldn't recognize anyone in that image, sir."
                    
                    elif action == "list":
                        faces = face_mem.list_known_faces()
                        if faces:
                            names = [f["name"] for f in faces]
                            return f"I know {len(faces)} people: {', '.join(names)}, sir."
                        else: return "My identity database is currently empty, sir."
                    
                    elif action == "forget":
                        n = args.get("name", "")
                        if not n: return "Whom should I forget, sir?"
                        r = face_mem.delete_face(n)
                        return r.get("message", "Identity removed.")

                elif name == "shutdown_jarvis":
                    confirmed = args.get("confirmed", False)
                    if confirmed or getattr(self.orch, 'auto_confirm_destructive', False):
                        if hasattr(self.orch, '_execute_shutdown'):
                            self.orch._execute_shutdown(confirmed=True)
                            return "Shutting down..."
                    return "Awaiting confirmation for shutdown."

                elif name == "reboot_jarvis":
                    confirmed = args.get("confirmed", False)
                    if confirmed or getattr(self.orch, 'auto_confirm_destructive', False):
                        if hasattr(self.orch, '_execute_reboot'):
                            self.orch._execute_reboot(confirmed=True)
                            return "Rebooting..."
                    return "Awaiting confirmation for reboot."

                # 2. EXTERNAL ACTION TOOLS (Lazy Loaded)
                elif name == "open_app":
                    func = self._get_tool("open_app")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "web_search":
                    func = self._get_tool("web_search")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "weather_report":
                    func = self._get_tool("weather_report", "weather_action")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "ip_checker":
                    func = self._get_tool("ip_checker", "check_ip")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "youtube_control":
                    func = self._get_tool("youtube_controller", "youtube_control")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "desktop_control":
                    func = self._get_tool("desktop", "desktop_control")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "vision_inspector":
                    func = self._get_tool("screen_processor", "screen_process")
                    source = args.get("source", "screen")
                    angle = "camera" if source == "webcam" else "screen"
                    focus = args.get("focus", "everything")
                    prompt = f"Inspect the {angle} and focus on {focus}."
                    v_args = {"angle": angle, "text": prompt}
                    threading.Thread(target=func, kwargs={"parameters": v_args, "player": self.ui}, daemon=True).start()
                    return f"Vision inspector activated on {source}."

                elif name == "screen_process":
                    func = self._get_tool("screen_processor", "screen_process")
                    threading.Thread(target=func, kwargs={"parameters": args, "player": self.ui}, daemon=True).start()
                    return "Vision module activated."

                elif name == "neural_inspector":
                    from actions.neural_inspector import neural_inspector
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: neural_inspector(parameters=args, player=self.ui)) or "Neural analysis complete."

                elif name == "browser_control":
                    func = self._get_tool("browser_control")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "computer_control":
                    func = self._get_tool("computer_control")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "file_controller":
                    func = self._get_tool("file_controller")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "python_sandbox":
                    func = self._get_tool("python_sandbox")
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."

                elif name == "relay_command":
                    from actions.ghost_relay import publish_command
                    target = args.get("target", "").upper()
                    cmd = args.get("command", "")
                    if target and cmd:
                        success = publish_command(target, cmd)
                        return f"Command sent to {target}." if success else f"Failed to send command to {target}."

                else:
                    # Dynamic Fallback
                    func = self._get_tool(name)
                    if func:
                        return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."
                    else:
                        return f"Tool '{name}' is not yet fully wired in modular core."

            result = await asyncio.wait_for(_execute_logic(), timeout=timeout)
        except asyncio.TimeoutExpired:
            result = f"Tool '{name}' timed out after {timeout} seconds. Process aborted for safety."
            print(f"[JARVIS] ⚠️ {result}")
        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()

        if not self.ui.muted and not self.orch.silent_mode:
            self.ui.set_state("LISTENING")
        
        print(f"[JARVIS] 📤 {name} -> {str(result)[:80]}")
        return types.FunctionResponse(id=fc.id, name=name, response={"result": result})
