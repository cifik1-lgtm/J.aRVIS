import asyncio
import importlib
import traceback
import threading
import json
from datetime import datetime
from google.genai import types
from pathlib import Path

# Path Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# ============================================================================
# TOOL DECLARATIONS (Lazy-Loaded Registry)
# ============================================================================

TOOL_DECLARATIONS = [
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
        "name": "detect_monitors",
        "description": "Detects how many monitors are connected and provides their specifications.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": ["count", "details", "all"],
                    "description": "What monitor info to retrieve"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "gesture_control",
        "description": "Enable or disable hand gesture control via webcam. Gestures: fist=mute, open_palm=stop, pointing=click, peace=volume_up, thumbs_up=confirm, rock=volume_down.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start | stop | toggle"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "camera_viewer",
        "description": "Opens a local camera feed window to show what the camera sees. Use this when the user wants to see the video feed.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "index": {"type": "INTEGER", "description": "Camera index (default 0)"}
            }
        }
    },
    {
        "name": "workspace_architect",
        "description": "Architect Protocol: Automatically snaps and resizes windows into optimized layouts. Layouts: 'coding' (VS Code + Browser + Terminal), 'social' (Telegram + Browser), 'cinema' (VLC/Full Screen).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "layout": {"type": "STRING", "description": "coding | social | cinema"}
            },
            "required": ["layout"]
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
        "name": "system_control",
        "description": "Controls JARVIS system states like silencing, autonomous mode, and brain switching. WARNING: DO NOT use this to switch to 'local' or 'openrouter' for tasks; use 'delegate_task' instead to keep your voice active.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["toggle_silence", "set_autonomous_mode", "switch_brain", "system_diagnostic"]},
                "state": {"type": "BOOLEAN"},
                "autonomous": {"type": "BOOLEAN"},
                "brain": {"type": "STRING", "description": "gemini | hive. (DO NOT switch to local/qwen here)"},
                "confirmed": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "save_memory",
        "description": "Saves a specific fact, user preference, or project detail to long-term memory.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "key": {"type": "STRING", "description": "The name of the fact to remember."},
                "value": {"type": "STRING", "description": "The details of the fact."},
                "category": {"type": "STRING", "description": "identity | preferences | projects | relationships | notes"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "retrieve_memory",
        "description": "Recalls specific information from long-term memory by key.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "key": {"type": "STRING"},
                "category": {"type": "STRING"}
            },
            "required": ["key"]
        }
    },
    {
        "name": "get_memory_stats",
        "description": "Returns statistics about the size and composition of the memory database.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "forget_weak_memories",
        "description": "Cleans up old or irrelevant memories that haven't been accessed recently.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "threshold": {"type": "NUMBER", "description": "0.0 to 1.0"}
            },
            "required": []
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
        "description": "Control built-in camera feed on the main HUD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "state": {"type": "BOOLEAN"},
                "camera_index": {"type": "INTEGER"}
            },
            "required": ["state"]
        }
    },
    {
        "name": "camera_viewer",
        "description": "Open a dedicated, standalone window for a camera feed.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "camera_index": {"type": "INTEGER"}
            },
            "required": []
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
        "name": "youtube_manager",
        "description": "UNIFIED YouTube control: playback (pause/next/mute), system volume, playlists, open/close tabs, video search, transcript summaries, and trending videos.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "play_song | play | pause | resume | next | previous | fullscreen | mute | volume_up | volume_down | like | theater | set_volume | volume_up_system | volume_down_system | create_playlist | next_song | previous_song | search | summarize | get_info | trending | open_tab | close_tab | switch_tab"
                },
                "query": {"type": "STRING", "description": "Song, artist, or search query"},
                "url": {"type": "STRING", "description": "YouTube video URL for summarize/get_info"},
                "level": {"type": "INTEGER", "description": "Volume level 0-100"},
                "amount": {"type": "INTEGER", "description": "Volume change amount (default 10)"},
                "songs": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of song names for playlist"},
                "region": {"type": "STRING", "description": "Region code for trending (e.g. TR, US)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "generate_image",
        "description": "Generate an image via Poe (e.g. nano-banana-2) and save it locally.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING", "description": "Image prompt"},
                "model": {"type": "STRING", "description": "Poe image bot name (default: nano-banana-2)"},
                "aspect_ratio": {"type": "STRING", "description": "Aspect ratio like 16:9, 1:1, 4:3 (optional)"},
                "path": {"type": "STRING", "description": "Save directory: desktop | documents | absolute path (optional)"},
                "filename": {"type": "STRING", "description": "Optional filename (e.g. my_image.png)"},
                "size": {"type": "STRING", "description": "Optional size hint if supported by model (e.g. 1024x1024)"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "codewords_agent",
        "description": "Run complex automations and AI agents on CodeWords platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service_id": {"type": "STRING", "description": "ID of the CodeWords workflow/service to run"},
                "inputs": {"type": "OBJECT", "description": "Input parameters for the workflow"}
            },
            "required": ["service_id"]
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
    },
    {
        "name": "rag_search",
        "description": "Search JARVIS's long-term vector memory for semantically relevant information. Use this when you need to recall something from past conversations, personal facts, or user preferences that aren't immediately in context.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "The question or topic to search memory for."},
                "top_k": {"type": "INTEGER", "description": "Number of results to return (default 5)"}
            },
            "required": ["query"]
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
            "harmless": ["web_search", "weather_report", "ip_checker", "save_memory", "vision_inspector", "preference_manager", "monitor_detection"],
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
            # Execution Watchdog: Load from config or use smart defaults
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                timeouts = json.load(f).get("tool_timeouts", {})
            
            default_t = timeouts.get("default", 30)
            timeout = timeouts.get(name, 180 if name in ["browser_control", "python_sandbox", "web_automation", "code_helper"] else default_t)
            
            async def _execute_logic():
                # 0. RAG SEARCH
                if name == "rag_search":
                    query = args.get("query", "")
                    top_k = int(args.get("top_k", 5))
                    try:
                        from memory.rag_engine import get_rag_engine
                        rag = get_rag_engine()
                        if rag and rag._ready:
                            results = rag.search(query, top_k=top_k)
                            if results:
                                lines = [f"🧠 RAG Memory Search — '{query}'"]
                                for r in results:
                                    lines.append(f"  • [{r['category'].upper()}] {r['key']}: {r['value']} (match: {r['score']:.0%})")
                                return "\n".join(lines)
                            return f"No relevant memories found for: '{query}'"
                        return "RAG engine is still initializing, please try again shortly, sir."
                    except Exception as e:
                        return f"Memory search failed: {e}"

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
                        self.orch._detect_engines() # Trigger a fresh scan
                        status = self.orch.brain_router.get_status_report()
                        return f"System Diagnostic: {status}"

                # 1.5 DISPLAY TOOLS
                if name == "detect_monitors":
                    action = args.get("action", "count")
                    try:
                        import win32api
                        import win32con
                        
                        monitors = win32api.EnumDisplayMonitors()
                        count = len(monitors)
                        
                        if action == "count":
                            return f"You have {count} monitor(s) connected, sir."
                        
                        elif action == "details" or action == "all":
                            details = []
                            for i, monitor in enumerate(monitors, 1):
                                monitor_info = win32api.GetMonitorInfo(monitor[0])
                                monitor_rect = monitor_info.get('Monitor', (0,0,0,0))
                                width = monitor_rect[2] - monitor_rect[0]
                                height = monitor_rect[3] - monitor_rect[1]
                                is_primary = bool(monitor_info.get('Flags', 0) & 1)
                                details.append(f"Monitor {i}: {width}x{height}" + (" (Primary)" if is_primary else ""))
                            
                            if action == "details":
                                return "; ".join(details)
                            else:
                                return f"You have {count} monitor(s) connected, sir.\n" + "\n".join(details)
                        return f"Detection complete. Count: {count}."
                    except ImportError:
                        # Fallback using pymonctl if available (already installed)
                        try:
                            import pymonctl
                            count = pymonctl.getMonitorsCount()
                            if action == "count":
                                return f"You have {count} monitor(s) connected, sir."
                            else:
                                monitors = pymonctl.getAllMonitors()
                                details = [f"Monitor {i+1}: {m.getSize().width}x{m.getSize().height}" for i, m in enumerate(monitors)]
                                return f"You have {count} monitor(s). " + "; ".join(details)
                        except:
                            return "Monitor detection failed, sir. Please check if pywin32 is installed."
                    except Exception as e:
                        return f"Monitor detection failed: {e}, sir."

                if name == "camera_viewer":
                    idx = args.get("index", 0)
                    from actions.camera_viewer import camera_viewer
                    return camera_viewer(self.orch, idx)

                if name == "workspace_architect":
                    layout = args.get("layout", "coding").lower()
                    from actions.workspace_architect import workspace_architect
                    return workspace_architect(self.orch, layout)

                if name == "gesture_control":
                    action = args.get("action", "toggle").lower()
                    if not hasattr(self.orch, 'gesture_manager') or self.orch.gesture_manager is None:
                        from actions.gesture_control import GestureControlManager
                        self.orch.gesture_manager = GestureControlManager(self.orch)
                    gm = self.orch.gesture_manager
                    if action == "start":
                        gm.start()
                        return "Gesture control started, sir. Show me your hands."
                    elif action == "stop":
                        gm.stop()
                        return "Gesture control deactivated, sir."
                    else:  # toggle
                        gm.toggle()
                        status = "activated" if gm.enabled else "deactivated"
                        return f"Gesture control {status}, sir."

                # 2. TASK DELEGATION (HIVE MIND ROUTER)
                if name == "delegate_task":
                    goal = args.get("goal", "")
                    priority = args.get("priority", "NORMAL")
                    context = args.get("context", "")
                    
                    # Smart Brain Routing
                    goal_l = goal.lower()
                    if any(x in goal_l for x in ["code", "python", "script", "develop", "debug"]):
                        brain_hint = "ollama"
                    elif any(x in goal_l for x in ["search", "web", "find", "google", "browse", "research"]):
                        brain_hint = "openrouter"
                    else:
                        brain_hint = self.orch.brain_router.get_active_brain()

                    from agent.task_queue import get_queue, TaskPriority
                    prio_map = {"HIGH": TaskPriority.HIGH, "NORMAL": TaskPriority.NORMAL, "LOW": TaskPriority.LOW}
                    
                    # Submit to the Hive Mind Task Queue with brain hint
                    get_queue().submit(
                        goal=goal, 
                        priority=prio_map.get(priority, TaskPriority.NORMAL),
                        preferred_brain=brain_hint,
                        speak=lambda m: self.orch.speak(f"Sir, regarding your request for {goal[:30]}... {m}")
                    )
                    return f"Task delegated to Expert Brains ({brain_hint}). I'm working on '{goal}' now, sir."

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

                elif name == "retrieve_memory":
                    from memory.memory_manager import retrieve_memory
                    key = args.get("key", "")
                    cat = args.get("category")
                    if key:
                        mem = retrieve_memory(key, cat)
                        if mem:
                            return f"Recall for '{key}': {mem.get('value')} (Updated: {mem.get('updated')})"
                        return f"I have no record of '{key}' in my memory banks, sir."
                    return "What should I recall, sir?"

                elif name == "get_memory_stats":
                    from memory.memory_manager import get_memory_stats
                    stats = get_memory_stats()
                    return f"Memory Database Stats: {stats['total_memories']} records. ({stats['identity_count']} identity, {stats['relationships_count']} relationships, {stats['preferences_count']} preferences, {stats['notes_count']} notes). Semantic search is {'enabled' if stats['semantic_enabled'] else 'disabled'}."

                elif name == "forget_weak_memories":
                    from memory.memory_manager import forget_weak_memories
                    threshold = args.get("threshold", 0.15)
                    count = forget_weak_memories(threshold)
                    return f"Memory cleanup complete. {count} old or irrelevant memories purged."

                elif name == "camera_feed":
                    state = args.get("state", True)
                    camera_index = args.get("camera_index", None)
                    
                    if camera_index is not None:
                        self.ui.camera = camera_index
                    
                    if hasattr(self.ui, 'hud') and hasattr(self.ui.hud, 'toggle_camera'):
                        self.ui.hud.toggle_camera(bool(state))
                        msg = f"Camera feed {'activated' if state else 'deactivated'}"
                        if camera_index is not None:
                            msg += f" (Index {camera_index})"
                        return f"{msg} in the HUD, sir."
                    return "HUD not available."

                elif name == "camera_viewer":
                    from actions.camera_viewer import camera_viewer
                    index = args.get("camera_index", 0)
                    return camera_viewer(self.orch, index)["message"]

                elif name == "vision_inspector":
                    from actions.screen_processor import vision_inspector
                    source = args.get("source", "webcam")
                    focus = args.get("focus", "text")
                    return vision_inspector(self.orch, source, focus)

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

                elif name == "youtube_manager":
                    from actions.youtube_manager import get_youtube_manager
                    yt = get_youtube_manager(self.ui)
                    return await asyncio.get_event_loop().run_in_executor(
                        None, lambda: yt.handle_command(args, speak=self.orch.speak)
                    ) or "Done."

                elif name == "youtube_video":
                    func = self._get_tool("youtube_video", "youtube_video")
                    return await asyncio.get_event_loop().run_in_executor(
                        None, lambda: func(parameters=args, player=self.ui, speak=self.orch.speak)
                    ) or "Done."

                elif name == "generate_image":
                    import base64
                    import os
                    import requests
                    from datetime import datetime
                    from pathlib import Path

                    api_key = os.environ.get("POE_API_KEY")
                    if not api_key and API_CONFIG_PATH.exists():
                        try:
                            cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                            api_key = cfg.get("poe_api_key", "")
                        except Exception:
                            api_key = ""

                    if not api_key:
                        return "Poe API key missing. Set POE_API_KEY env var or add poe_api_key to config/api_keys.json, sir."

                    prompt = (args.get("prompt") or "").strip()
                    if not prompt:
                        return "Please provide an image prompt, sir."

                    model = (args.get("model") or "").strip()
                    if not model and API_CONFIG_PATH.exists():
                        try:
                            cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                            model = ((cfg.get("poe_models") or {}).get("image_gen") or "").strip()
                        except Exception:
                            model = ""
                    if not model:
                        model = "nano-banana-2"
                    aspect_ratio = (args.get("aspect_ratio") or "").strip()
                    size = (args.get("size") or "").strip()

                    payload = {"model": model, "prompt": prompt}
                    # Optional parameters (only included if provided; models may ignore)
                    params = {}
                    if aspect_ratio:
                        params["aspect_ratio"] = aspect_ratio
                    if size:
                        params["size"] = size
                    if params:
                        payload["parameters"] = params

                    resp = requests.post(
                        "https://api.poe.com/v1/images",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=60,
                    )

                    if resp.status_code != 200:
                        return f"Image generation failed: {resp.status_code} — {resp.text[:200]}"

                    data = resp.json()

                    # Determine save directory
                    save_dir = (args.get("path") or "desktop").strip().lower()
                    if save_dir == "desktop":
                        out_dir = Path.home() / "Desktop"
                    elif save_dir == "documents":
                        out_dir = Path.home() / "Documents"
                    else:
                        out_dir = Path(args.get("path")) if args.get("path") else (Path.home() / "Desktop")

                    out_dir.mkdir(parents=True, exist_ok=True)

                    # Determine filename
                    filename = (args.get("filename") or "").strip()
                    if not filename:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_model = "".join(c for c in model if c.isalnum() or c in ("-", "_"))[:40]
                        filename = f"poe_{safe_model}_{ts}.png"
                    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                        filename += ".png"
                    out_path = out_dir / filename

                    # Handle common response shapes:
                    # - OpenAI-style: {"data":[{"url":...}]} or {"data":[{"b64_json":...}]}
                    # - Some bots: {"url":...} / {"image_url":...}
                    image_url = None
                    b64 = None

                    if isinstance(data, dict):
                        if isinstance(data.get("data"), list) and data["data"]:
                            item = data["data"][0] if isinstance(data["data"][0], dict) else {}
                            image_url = item.get("url") or item.get("image_url")
                            b64 = item.get("b64_json") or item.get("b64")
                        image_url = image_url or data.get("url") or data.get("image_url")
                        b64 = b64 or data.get("b64_json") or data.get("b64")

                    if image_url:
                        img_resp = requests.get(image_url, timeout=60)
                        if img_resp.status_code != 200:
                            return f"Image URL download failed: {img_resp.status_code}"
                        out_path.write_bytes(img_resp.content)
                        return f"Image generated and saved to {out_path}, sir."

                    if b64:
                        try:
                            raw = base64.b64decode(b64)
                            out_path.write_bytes(raw)
                            return f"Image generated and saved to {out_path}, sir."
                        except Exception as e:
                            return f"Image generated but could not decode/save it: {e}"

                    # As a last resort, try if API returned raw bytes (unlikely)
                    try:
                        out_path.write_bytes(resp.content)
                        return f"Image generated and saved to {out_path}, sir."
                    except Exception:
                        return "Image generated, but the response format was not recognized, sir."

                elif name == "codewords_agent":
                    import requests

                    service_id = (args.get("service_id") or "").strip()
                    inputs = args.get("inputs") or {}
                    if not service_id:
                        return "Please provide a CodeWords service_id, sir."
                    if not isinstance(inputs, dict):
                        return "CodeWords inputs must be an object/dictionary, sir."

                    # Load CodeWords config (env first, then api_keys.json)
                    import os
                    api_key = os.environ.get("CODEWORDS_API_KEY")
                    base_url = os.environ.get("CODEWORDS_BASE_URL")

                    if API_CONFIG_PATH.exists():
                        try:
                            cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                            api_key = api_key or cfg.get("codewords_api_key", "")
                            base_url = base_url or cfg.get("codewords_base_url", "")
                        except Exception:
                            pass

                    api_key = (api_key or "").strip()
                    base_url = (base_url or "https://runtime.codewords.ai").rstrip("/")

                    if not api_key or api_key == "cwk-your-key-here":
                        return "CodeWords API key missing. Set CODEWORDS_API_KEY or edit config/api_keys.json (codewords_api_key), sir."

                    url = f"{base_url}/run/{service_id}"
                    try:
                        resp = requests.post(
                            url,
                            headers={"Authorization": f"Bearer {api_key}"},
                            json=inputs,
                            timeout=60,
                        )
                    except Exception as e:
                        return f"CodeWords request failed: {e}"

                    if resp.status_code == 200:
                        # Keep it short; full JSON can be huge
                        try:
                            data = resp.json()
                        except Exception:
                            data = {"raw": resp.text[:400]}
                        return f"CodeWords agent completed: {str(data)[:800]}"

                    return f"CodeWords agent failed: {resp.status_code} — {resp.text[:200]}"

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
        except asyncio.TimeoutError:
            result = f"Tool '{name}' timed out after {timeout} seconds. Process aborted for safety."
            print(f"[JARVIS] ⚠️ {result}")
        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()

        if not self.ui.muted and not self.orch.silent_mode:
            self.ui.set_state("LISTENING")
        
        print(f"[JARVIS] 📤 {name} -> {str(result)[:80]}")
        return types.FunctionResponse(id=fc.id, name=name, response={"result": result})
