import asyncio
import importlib
import traceback
import threading
import json
from datetime import datetime, timedelta
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
        "name": "swarm_coordinator",
        "description": "Multi-Agent Swarm Mode: Delegate a complex task to multiple local Ollama sub-agents running in parallel to save API costs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task": {"type": "STRING", "description": "The complex task to delegate"},
                "agents": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of agent roles, e.g. ['coder', 'researcher', 'tester']"}
            },
            "required": ["task"]
        }
    },
    {
        "name": "deep_research",
        "description": "Deep Research Mode: Scrape web pages or read PDF files and save their text into the Vector RAG memory.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "URL to scrape"},
                "file_path": {"type": "STRING", "description": "Path to PDF or text file to parse"}
            }
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
        "name": "external_camera_window",
        "description": "Open or close a separate pop-up webcam window (not the main HUD). Use only when the user asks for an external/standalone camera window, gesture setup, or face-training UI. For normal 'show my camera' on the dashboard, use the HUD webcam tool instead.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["start", "stop"], "description": "start (default) to open, stop to close"},
                "camera_index": {"type": "INTEGER", "description": "Camera index (default 0)"}
            }
        }
    },
    {
        "name": "detect_cameras",
        "description": "Physically scan the system for connected cameras and return their indices. Use this for accurate hardware diagnostics.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "workspace_architect",
        "description": "The Architect Protocol 2.0: Snaps/resizes windows and LAUNCHES missing apps. Layouts: 'coding' (VS Code, Browser, Terminal), 'social' (Telegram, Browser), 'cinema' (VLC), 'gaming' (Steam, Discord).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "layout": {"type": "STRING", "description": "coding | social | cinema | gaming"},
                "launch_missing": {"type": "BOOLEAN", "description": "If true, automatically starts required apps if they aren't running."}
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
        "description": "Controls JARVIS system states like autonomous mode and brain switching. WARNING: DO NOT use this to switch to 'local' or 'openrouter' for tasks; use 'delegate_task' instead to keep your voice active.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["set_autonomous_mode", "switch_brain", "system_diagnostic"]},
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
        "name": "browser_navigate",
        "description": "Composite tool to open a browser and navigate to a URL. Use this for all simple 'open website' or 'go to url' tasks.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "The URL to navigate to (e.g. google.com, facebook.com)"},
                "browser": {"type": "STRING", "description": "Optional: brave | chrome | edge | firefox (default: brave)"}
            },
            "required": ["url"]
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
        "description": "CRITICAL TOOL for reading and writing files. Actions: 'read' (read a file), 'write' (create/overwrite a file with content), 'list', 'create_folder', 'delete', 'move', 'copy'. DO NOT use shell_runner to echo or cat files; use file_controller instead.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "read | write | list | create_folder | delete | move | copy"},
                "path": {"type": "STRING", "description": "The path to the file or directory. Can be absolute or relative."},
                "name": {"type": "STRING", "description": "The file name if path is just a directory."},
                "content": {"type": "STRING", "description": "The exact code or text to write to the file (only for 'write' action)."},
                "destination": {"type": "STRING"},
                "target": {"type": "STRING"},
                "auto": {"type": "BOOLEAN"}
            },
            "required": ["action", "path"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct mouse/keyboard control and OS tasks. Actions: type, click, scroll, move, drag, hotkey, screenshot, smart_close, list_processes, get_active_window, focus_window, open_folder, move_window. To move any window programmatically to another monitor or position without using hotkeys or mouse actions, use the 'move_window' action with 'title' (window title to target, e.g. 'YouTube' or 'Brave') and 'target' (e.g. 'other_monitor' or 'Monitor 1').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "type | click | scroll | move | drag | hotkey | screenshot | smart_close | list_processes | get_active_window | focus_window | open_folder | move_window"
                },
                "text": {"type": "STRING", "description": "Text to type or command parameters"},
                "target": {"type": "STRING", "description": "Target monitor/destination (e.g. 'other_monitor' or monitor name) or app name for smart_close."},
                "title": {"type": "STRING", "description": "Title of target window for focus_window or move_window (e.g. 'YouTube', 'Brave')."},
                "keys": {"type": "STRING", "description": "Keys or shortcut sequence to simulate (only for hotkey action)"},
                "x": {"type": "NUMBER", "description": "Target X coordinate"},
                "y": {"type": "NUMBER", "description": "Target Y coordinate"},
                "amount": {"type": "INTEGER", "description": "Scroll amount"},
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
        "description": "The PRIMARY and DEFAULT tool to control and show the webcam feed to the user inside the main holographic HUD/dashboard. Use this when the user asks to 'show camera feed', 'start webcam', 'open camera', or 'see camera feed' inside the HUD dashboard.",
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
        "name": "self_fix",
        "description": "JARVIS internal self-healing and self-learning system. Use this ONLY to repair and fix crashes in JARVIS's own source code files (under actions/ or core/ or agent/). Do NOT use this to fix external files, websites, or user documents — for those, use code_helper instead. Modes: 'heal_file' fixes a specific crashed file; 'audit' scans the error ledger for recurring bugs and auto-patches source files; 'report' shows a summary of all logged errors; 'clear' resets the error ledger.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "mode": {"type": "STRING", "enum": ["heal_file", "audit", "report", "clear"], "description": "heal_file=fix one file, audit=scan+auto-patch recurring errors, report=show error stats, clear=reset ledger."},
                "file_name": {"type": "STRING", "description": "The file to fix (e.g. 'file_controller.py'). Required for heal_file mode."},
                "error_message": {"type": "STRING", "description": "The specific error message observed. Required for heal_file mode."}
            },
            "required": ["mode"]
        }
    },
    {
        "name": "netflix_manager",
        "description": (
            "Control the installed Netflix Windows app on a chosen monitor using UI Automation only (Invoke/SetValue) — NO keyboard, NO paste, NO Enter/F11. "
            "play_title: open app, move to monitor, search title, invoke Play, then in-player fullscreen (not just resizing the app window). "
            "Example: action=play_title, title=SWAT, monitor=1, fullscreen=true. Steps are paced (step_delay_sec) to avoid rate limits."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": [
                        "launch", "play_title", "search", "pause", "resume", "play",
                        "fullscreen", "move_monitor", "place"
                    ],
                    "description": "launch=open app; play_title=search+play+video fullscreen via UIA; search=UIA search only; pause/resume/play/fullscreen=UIA player buttons; move_monitor=position on monitor N"
                },
                "title": {"type": "STRING", "description": "Movie or show name (e.g. SWAT)"},
                "query": {"type": "STRING", "description": "Alias for title"},
                "monitor": {"type": "INTEGER", "description": "Monitor number (1 = first monitor, 2 = second, etc.)"},
                "monitor_index": {"type": "INTEGER", "description": "Same as monitor"},
                "fullscreen": {"type": "BOOLEAN", "description": "Fill target monitor (default true)"}
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
                    "enum": ["play_song", "play_song_background", "play_song_foreground", "stop", "pause", "resume", "next", "previous", "fullscreen", "mute", "volume_up", "volume_down", "like", "theater", "set_volume", "volume_up_system", "volume_down_system", "create_playlist", "next_song", "previous_song", "search", "summarize", "get_info", "trending", "open_tab", "close_tab", "switch_tab"],
                    "description": "Action to perform. Use play_song for default (video), play_song_background for audio-only, or play_song_foreground for immersive PWA video."
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
        "name": "sms_tool",
        "description": "Send and receive SMS messages via a connected phone using smsmobileapi. Action 'send' requires 'to' (phone number) and 'message'. Action 'receive' retrieves recent messages.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "enum": ["send", "receive"],
                    "description": "Whether to send a message or check for received ones."
                },
                "to": {
                    "type": "STRING",
                    "description": "Recipient phone number (e.g. 15551234567)"
                },
                "message": {
                    "type": "STRING",
                    "description": "The text message content to send."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "generate_image",
        "description": "CRITICAL: You HAVE the ability to generate images! Use this tool to generate an image locally via GPU whenever the user asks for a picture or image. Do NOT say you cannot generate images.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING", "description": "Highly detailed image prompt"}
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
        "name": "self_improvement",
        "description": "AI self-improvement and auto-optimization loop.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "run_audit | status | optimize_tool"},
                "tool_name": {"type": "STRING", "description": "File name or tool name to optimize (for optimize_tool)"}
            },
            "required": ["action"]
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
        "description": "Advanced AI code editor and problem solver. Actions: 'read_file', 'write_file', 'edit_file' (find and replace), 'find_files', 'analyze_error'. This is the BEST tool for coding tasks.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "read_file | write_file | edit_file | find_files | analyze_error | search_code"},
                "file_path": {"type": "STRING", "description": "Path to the file being edited or read"},
                "content": {"type": "STRING", "description": "The full code to write (for 'write_file')"},
                "old_text": {"type": "STRING", "description": "Text to find (for 'edit_file')"},
                "new_text": {"type": "STRING", "description": "Replacement text (for 'edit_file')"},
                "pattern": {"type": "STRING", "description": "Search pattern (for 'find_files' or 'search_code')"},
                "error_text": {"type": "STRING", "description": "Error trace (for 'analyze_error')"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Delegates a large coding task to a specialized coding LLM. This is the BEST tool to use when you need to write a full file, app, or website from scratch, edit existing code, or run/optimize/fix code. Provide a description and output_path or file_path.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["write", "edit", "build", "run", "explain", "optimize", "fix"], "description": "write=new code; edit/fix=change/repair existing file; build=write and test; run=execute; explain=analyze; optimize=make faster."},
                "description": {"type": "STRING", "description": "What to build, write, edit, or fix."},
                "language": {"type": "STRING", "description": "e.g. 'html', 'python', 'javascript'"},
                "output_path": {"type": "STRING", "description": "Absolute path to save the generated code (for 'write' or 'build')"},
                "file_path": {"type": "STRING", "description": "Absolute path to the file to edit, run, explain, optimize, or fix (for 'edit', 'run', 'explain', 'optimize', 'fix')"}
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
    },
    {
        "name": "telegram_manager",
        "description": "Send or broadcast Telegram messages via the telegram bot.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "send"},
                "text": {"type": "STRING"}
            },
            "required": ["action", "text"]
        }
    },
    {
        "name": "routine_manager",
        "description": "Manage scheduled background routines.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "add | list | clear"},
                "time": {"type": "STRING", "description": "Time in HH:MM format (24h) for 'add' action"},
                "task": {"type": "STRING", "description": "Task description for 'add' action"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "memory_manager",
        "description": "Manage simple key-value facts in basic long term memory facts.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "save | retrieve | delete"},
                "key": {"type": "STRING"},
                "value": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "hunt_bugs",
        "description": "Autonomously scan GitHub repos for security vulnerabilities and claim bug bounties",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "repo_url": {"type": "STRING", "description": "GitHub repository URL to scan"},
                "action": {"type": "STRING", "enum": ["scan", "verify", "patch", "full_audit"]}
            },
            "required": ["repo_url", "action"]
        }
    },
    {
        "name": "learn_skill",
        "description": "Autonomous Learning: Writes, tests, and installs a NEW tool for yourself based on a user goal.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "skill_name": {"type": "STRING", "description": "The name of the new tool (e.g. 'crypto_tracker')."},
                "objective": {"type": "STRING", "description": "What the tool should do (e.g. 'get the current price of Ethereum')."}
            },
            "required": ["skill_name", "objective"]
        }
    },
    {
        "name": "self_fix",
        "description": "Uses AI to diagnose and repair a specific file in the JARVIS system if an error occurs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_name": {"type": "STRING", "description": "The name of the file to fix (e.g. 'ui.py' or 'tools.py')."},
                "error_message": {"type": "STRING", "description": "The specific error message or traceback observed."}
            },
            "required": ["file_name"]
        }
    },
    {
        "name": "system_reboot",
        "description": "Restarts the computer immediately. Use with caution.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "system_shutdown",
        "description": "Shuts down the computer immediately. Use with caution.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "ghost_browser",
        "description": "Autonomous Web Agent: Navigate, search, and extract content from websites in a dedicated background browser. Actions: 'navigate', 'search', 'capture'.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["navigate", "search", "capture"]},
                "url": {"type": "STRING"},
                "query": {"type": "STRING"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "remote_command",
        "description": "Send a command/goal to your OTHER PC (EVA or CIFIK) to execute it remotely.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {"type": "STRING", "description": "EVA | CIFIK | ALL"},
                "command": {"type": "STRING", "description": "The goal to execute (e.g. 'open notepad' or 'search for AI news')"}
            },
            "required": ["target", "command"]
        }
    },
    {
        "name": "hive_sync",
        "description": "Teleport/Transfer a file from this PC to your OTHER PC instantly via the cloud relay.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {"type": "STRING", "description": "EVA | CIFIK"},
                "file_path": {"type": "STRING", "description": "Absolute path to the local file to send"}
            },
            "required": ["target", "file_path"]
        }
    },
    {
        "name": "neural_fusion",
        "description": "Analyze an external GitHub repository and compare its code to JARVIS to identify superior features for absorption.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["analyze", "extract"]},
                "repo_url": {"type": "STRING", "description": "The GitHub URL of the external project (for analyze)"},
                "target_file": {"type": "STRING", "description": "The file name to extract DNA from (for extract)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "update_sentinel",
        "description": "Check for cloud updates and autonomously upgrade the JARVIS system code.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["check", "upgrade"]}
            },
            "required": ["action"]
        }
    },
    {
        "name": "hive_dna",
        "description": "Analyze the fitness of current skills and autonomously evolve weak tools into superior mutations.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["report", "evolve"]},
                "target_tool": {"type": "STRING", "description": "Specific tool to evolve"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "audio_master",
        "description": "Control system and application-specific volume, mute, and unmute audio.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["set_volume", "mute", "unmute", "app_volume"]},
                "level": {"type": "INTEGER", "description": "0 to 100"},
                "app_name": {"type": "STRING", "description": "e.g., chrome.exe, spotify.exe"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "hot_reload",
        "description": "Refresh and reload all tool definitions and actions without rebooting the system.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "project_architect",
        "description": "Scaffold a complete new project autonomously with folders, files, and Git initialization.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "The name of the new project folder"},
                "description": {"type": "STRING", "description": "What the project is about"},
                "tech_stack": {"type": "STRING", "description": "python | web | node"}
            },
            "required": ["name", "description"]
        }
    },
    {
        "name": "hive_status",
        "description": "Get the hardware status (CPU, GPU, Temp) and activity of your OTHER PC.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {"type": "STRING", "description": "EVA | CIFIK"}
            },
            "required": ["target"]
        }
    },
    {
        "name": "shell_runner",
        "description": "Execute any shell/terminal command silently in the background — no windows open. Use this for running scripts, installing packages, git operations, npm/pip commands, compiling code, etc. DO NOT use this tool to write code or text to files (e.g. do not use echo > file), and do not use it to read files. For reading/writing files, use 'file_controller' or 'code_agent' instead. Supports PowerShell (default on Windows), cmd, and bash.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {"type": "STRING", "description": "The full shell command to run (e.g. 'mkdir desktop\\my-project', 'pip install flask', 'git clone https://...')"},
                "cwd": {"type": "STRING", "description": "Working directory. Supports shortcuts: 'desktop', 'home', 'downloads', or any absolute path."},
                "timeout": {"type": "INTEGER", "description": "Max seconds to wait for completion (default 30)."},
                "shell_type": {"type": "STRING", "description": "powershell | cmd | bash | auto (default: auto — PowerShell on Windows, bash on Linux/Mac)"}
            },
            "required": ["command"]
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
            "state_changing": ["file_controller", "open_app", "browser_control", "browser_navigate", "face_manager", "desktop_control", "youtube_control", "netflix_manager", "sms_tool"],
            "privileged": ["admin_controller", "reboot_jarvis", "shutdown_jarvis", "python_sandbox", "relay_command", "self_improvement"]
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
            timeout = timeouts.get(name, 
                600 if name in ["shell_runner", "file_controller", "python_sandbox"] else  # local execution tools
                600 if name in ["dev_agent", "code_helper", "code_agent", "project_architect", "learn_skill", "generate_image", "netflix_manager"] else  # heavy AI tools
                180 if name in ["browser_control", "web_automation", "ghost_browser"] else  # browser tools
                default_t
            )
            
            async def _execute_logic():
                # 0. RAG SEARCH
                if name == "swarm_coordinator":
                    from actions.swarm_coordinator import swarm_coordinator
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: swarm_coordinator(args, player=self.ui))

                elif name == "deep_research":
                    from actions.deep_research import deep_research
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: deep_research(args, player=self.ui))

                elif name == "rag_search":
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
                        return "Silence mode is handled locally by the system. Do not use this tool to control it."
                    elif action == "set_autonomous_mode":
                        auto = args.get("autonomous", True)
                        self.orch._update_config_autonomous(auto)
                        return f"Autonomous mode {'enabled' if auto else 'disabled'}, sir."
                    elif action == "switch_brain":
                        brain = args.get("brain", "gemini")
                        if brain.lower() in ["hive", "gemini", "auto"]:
                            self.orch.brain_router.clear_forced_brain()
                        else:
                            self.orch.brain_router.set_forced_brain(brain)
                        return f"Switched to {brain} brain, sir."
                    elif action == "system_diagnostic":
                        self.orch._detect_engines() # Trigger a fresh scan
                        status = self.orch.brain_router.get_status_report()
                        return f"System Diagnostic: {status}"
                    elif action in ["restart", "reboot"]:
                        confirmed = str(args.get("confirmed", "false")).lower() == "true" or args.get("auto", False)
                        if confirmed:
                            self.orch._execute_reboot(confirmed=True)
                            return "Rebooting system now, sir."
                        else:
                            self.orch._pending_action = "reboot"
                            self.orch._pending_action_timeout = datetime.now() + timedelta(seconds=15)
                            return "Awaiting confirmation to reboot."
                    elif action == "shutdown":
                        confirmed = str(args.get("confirmed", "false")).lower() == "true" or args.get("auto", False)
                        if confirmed:
                            self.orch._execute_shutdown(confirmed=True)
                            return "Shutting down system now, sir."
                        else:
                            self.orch._pending_action = "shutdown"
                            self.orch._pending_action_timeout = datetime.now() + timedelta(seconds=15)
                            return "Awaiting confirmation to shutdown."

                elif name == "reboot_jarvis":
                    confirmed = str(args.get("confirmed", "false")).lower() == "true" or args.get("auto", False)
                    if confirmed:
                        self.orch._execute_reboot(confirmed=True)
                        return "Rebooting system now, sir."
                    else:
                        self.orch._pending_action = "reboot"
                        self.orch._pending_action_timeout = datetime.now() + timedelta(seconds=15)
                        return "Awaiting confirmation to reboot."

                elif name == "neural_fusion":
                    from actions.neural_fusion import neural_fusion
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: neural_fusion(args, base_dir=BASE_DIR))

                elif name == "update_sentinel":
                    from actions.update_sentinel import update_sentinel
                    return update_sentinel(args, base_dir=BASE_DIR)

                elif name == "hive_dna":
                    from core.hive_dna import evolve_skill, get_dna
                    action = args.get("action", "report")
                    if action == "report":
                        return get_dna(BASE_DIR).get_dna_report()
                    return await evolve_skill(args, jarvis=self, player=self.ui)

                elif name == "audio_master":
                    from actions.audio_master import audio_master
                    return audio_master(args, player=self.ui)

                elif name == "shutdown_jarvis":
                    confirmed = str(args.get("confirmed", "false")).lower() == "true" or args.get("auto", False)
                    if confirmed:
                        self.orch._execute_shutdown(confirmed=True)
                        return "Shutting down system now, sir."
                    else:
                        self.orch._pending_action = "shutdown"
                        self.orch._pending_action_timeout = datetime.now() + timedelta(seconds=15)
                        return "Awaiting confirmation to shutdown."

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

                if name in ("camera_viewer", "external_camera_window"):
                    idx = args.get("camera_index", args.get("index", 0))
                    action = args.get("action", "start")
                    from actions.camera_viewer import camera_viewer
                    res = camera_viewer(self.orch, idx, action)
                    if isinstance(res, dict):
                        return res.get("message", str(res))
                    return res

                if name == "detect_cameras":
                    from actions.camera_scanner import detect_cameras
                    res = detect_cameras()
                    return res["message"]

                if name == "workspace_architect":
                    from actions.workspace_architect import workspace_architect
                    return workspace_architect(parameters=args, player=self.ui)

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
                    
                    try:
                        from actions.action_ledger import get_recent_actions
                        recent_ctx = get_recent_actions()
                        if recent_ctx != "No recent background actions.":
                            context = f"{context}\n\n{recent_ctx}".strip()
                    except Exception:
                        pass
                    
                    
                    # Smart Brain Routing
                    goal_l = goal.lower()
                    if any(x in goal_l for x in ["code", "python", "script", "develop", "debug"]):
                        brain_hint = "pollinations"
                    elif any(x in goal_l for x in ["search", "web", "find", "google", "browse", "research"]):
                        brain_hint = "gemini"
                    else:
                        brain_hint = self.orch.brain_router.get_active_brain()

                    from agent.task_queue import get_queue, TaskPriority
                    prio_map = {"HIGH": TaskPriority.HIGH, "NORMAL": TaskPriority.NORMAL, "LOW": TaskPriority.LOW}
                    
                    # Submit to the Hive Mind Task Queue with brain hint
                    get_queue().submit(
                        goal=f"{goal}\n\nContext:\n{context}" if context else goal, 
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

                elif name == "remote_command":
                    from actions.ghost_relay import publish_command
                    target = args.get("target", "ALL").upper()
                    cmd = args.get("command", "")
                    if publish_command(target, cmd):
                        return f"Command '{cmd}' sent to {target} hive node, sir."
                    return "Hive communication failed."

                elif name == "hive_sync":
                    from actions.ghost_relay import publish_command
                    target = args.get("target", "").upper()
                    path = Path(args.get("file_path", ""))
                    if not path.exists(): return "File not found."
                    
                    import base64
                    content = base64.b64encode(path.read_bytes()).decode("utf-8")
                    payload = f"FILE_SYNC:|{path.name}|{content}"
                    if publish_command(target, payload):
                        return f"File '{path.name}' teleported to {target}, sir."
                    return "Teleportation failed."

                elif name == "hive_status":
                    status_path = BASE_DIR / "memory" / "hive_status.json"
                    if not status_path.exists(): return f"Target hive node {args.get('target')} is currently offline."
                    return status_path.read_text(encoding="utf-8")

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

                elif name == "hunt_bugs":
                    from actions.bug_hunter import get_bug_hunter
                    hunter = get_bug_hunter(self.ui)
                    repo_url = args.get("repo_url", "")
                    action = args.get("action", "full_audit")
                    if not repo_url: return "Please provide a repository URL, sir."
                    
                    # Clone repo
                    repo_name = repo_url.split("/")[-1].replace(".git", "")
                    clone_path = Path.home() / "Desktop" / "bug_bounties" / repo_name
                    clone_path.mkdir(parents=True, exist_ok=True)
                    
                    import subprocess
                    if not (clone_path / ".git").exists():
                        subprocess.run(["git", "clone", repo_url, str(clone_path)], capture_output=True)
                    
                    if action == "scan":
                        findings = hunter.scan_repository(str(clone_path))
                        return f"Found {len(findings)} potential vulnerabilities, sir."
                    elif action == "full_audit":
                        findings = hunter.scan_repository(str(clone_path))
                        real_findings = []
                        for f in findings:
                            if hunter.verify_vulnerability(f):
                                real_findings.append(f)
                                patch = hunter.generate_patch(f)
                                hunter.create_pull_request(str(clone_path), patch, f)
                        return f"Found {len(real_findings)} verified vulnerabilities in {repo_url}. PRs created, sir."

                elif name == "camera_feed":
                    state = args.get("state", True)
                    camera_index = args.get("camera_index", None)
                    if camera_index is not None: self.ui.camera = camera_index
                    if hasattr(self.ui, 'hud') and hasattr(self.ui.hud, 'toggle_camera'):
                        self.ui.hud.toggle_camera(bool(state))
                        msg = f"Camera feed {'activated' if state else 'deactivated'}"
                        if camera_index is not None: msg += f" (Index {camera_index})"
                        return f"{msg} in the HUD, sir."
                    return "HUD not available."

                elif name in ("camera_viewer", "external_camera_window"):
                    from actions.camera_viewer import camera_viewer
                    index = args.get("camera_index", args.get("index", 0))
                    action = args.get("action", "start")
                    res = camera_viewer(self.orch, index, action)
                    if isinstance(res, dict):
                        return res.get("message", str(res))
                    return res

                elif name == "vision_inspector":
                    from actions.screen_processor import screen_process
                    source = args.get("source", "webcam")
                    focus = args.get("focus", "text")
                    angle = "camera" if source == "webcam" else "screen"
                    params = {"angle": angle, "text": f"Focusing on {focus}. What do you see?"}
                    success = screen_process(params, player=self.ui)
                    return "Vision module activated and analyzing feed, sir." if success else "Failed to start vision session."

                elif name == "face_manager":
                    from actions.face_memory import get_face_memory
                    face_mem = get_face_memory()
                    action = args.get("action", "")
                    if action == "learn":
                        n, rel = args.get("name", ""), args.get("relationship", "friend")
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
                        return "I couldn't recognize anyone in that image, sir."

                elif name == "self_fix":
                    from actions.self_healing import self_healing
                    mode   = args.get("mode", "heal_file")
                    target = args.get("file_name", args.get("target_file", ""))
                    error  = args.get("error_message", "")
                    # Build params compatible with new self_healing
                    heal_params = {"mode": mode, "target_file": target, "error_message": error}
                    return await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self_healing(heal_params, player=self.ui)
                    ) or "Self-healing complete."

                elif name == "project_architect":
                    from actions.project_architect import project_architect
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: project_architect(args, player=self.ui)) or "Project scaffolded, sir."

                elif name == "learn_skill":
                    from actions.skill_engine import skill_engine
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: skill_engine(parameters=args, player=self.ui, jarvis=self.orch)) or "Done."

                elif name == "ghost_browser":
                    from actions.ghost_browser import ghost_browser
                    return await asyncio.get_event_loop().run_in_executor(None, lambda: ghost_browser(parameters=args, player=self.ui)) or "Done."

                elif name == "ip_checker":
                    from actions.ip_checker import check_ip
                    return check_ip(parameters=args, player=self.ui)

                elif name == "screen_process":
                    from actions.screen_processor import screen_process
                    return screen_process(parameters=args, player=self.ui)

                elif name == "desktop_control":
                    from actions.desktop import desktop_control
                    return desktop_control(parameters=args, player=self.ui)

                elif name == "telegram_manager":
                    from actions.telegram_bot import telegram_manager
                    return telegram_manager(parameters=args, player=self.ui)

                elif name == "routine_manager":
                    from actions.routines import routine_manager
                    return routine_manager(parameters=args, player=self.ui)

                elif name == "youtube_control":
                    from actions.youtube_controller import youtube_control
                    return youtube_control(parameters=args, player=self.ui)

                elif name == "netflix_manager":
                    from actions.netflix_manager import netflix_manager
                    return netflix_manager(parameters=args, player=self.ui)

                elif name == "weather_report":
                    from actions.weather_report import weather_action
                    return weather_action(parameters=args, player=self.ui)

                elif name == "system_reboot":
                    from actions.computer_settings import restart_computer
                    return restart_computer() or "Rebooting system, Sir."

                elif name == "system_shutdown":
                    from actions.computer_settings import shutdown_computer
                    return shutdown_computer() or "Shutting down, Sir."

                elif name == "hot_reload":
                    # Re-import this module to refresh declarations
                    import importlib
                    import core.tools
                    importlib.reload(core.tools)
                    
                    # Clear lazy loading tool cache to force re-importing changed actions
                    self._tool_cache.clear()
                    
                    # Update the live session tools if possible
                    if hasattr(self.orch, "update_tools"):
                        self.orch.update_tools()

                    # Dashboard Telemetry
                    try:
                        from pathlib import Path
                        import json
                        from datetime import datetime
                        base_dir = Path(__file__).resolve().parent.parent
                        log_file = base_dir / "memory" / "hot_reload_logs.json"
                        logs = []
                        if log_file.exists():
                            logs = json.loads(log_file.read_text(encoding="utf-8"))
                        logs.append({"timestamp": datetime.now().isoformat(), "message": "Neural synchronization successful."})
                        log_file.write_text(json.dumps(logs[-50:], indent=2), encoding="utf-8")
                    except:
                        pass
                        
                    return "Neural synchronization complete, sir. My new skills are now active without a reboot."

                else:
                    # Dynamic Fallback for modular tools
                    func = self._get_tool(name)
                    if func:
                        return await asyncio.get_event_loop().run_in_executor(None, lambda: func(parameters=args, player=self.ui)) or "Done."
                    return f"Tool '{name}' is not yet fully wired in modular core."

            result = await asyncio.wait_for(_execute_logic(), timeout=timeout)
        except asyncio.TimeoutError:
            result = f"Tool '{name}' timed out after {timeout} seconds. Process aborted for safety."
            print(f"[JARVIS] ⚠️ {result}")
        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            error_trace = traceback.format_exc()
            traceback.print_exc()
            
            # RUNTIME SELF-HEALING
            if hasattr(self.orch, "healer") and self.orch.healer:
                # Attempt to identify the culprit file (usually actions/name.py)
                tool_file_name = f"{name}.py"
                
                # SPECIAL MAPPINGS: When tool name doesn't match filename
                mappings = {
                    "vision_inspector": "screen_processor.py",
                    "rag_search": "../memory/rag_engine.py",
                    "save_memory": "../memory/memory_manager.py",
                    "retrieve_memory": "../memory/memory_manager.py"
                }
                if name in mappings:
                    tool_file_name = mappings[name]
                
                tool_path = Path("actions") / tool_file_name
                full_path = self.orch.healer.base_dir / tool_path
                
                if full_path.exists():
                    self.ui.write_log(f"⚠️ {name} crashed. Triggering Self-Healing...")
                    healed, msg = self.orch.healer.attempt_repair(full_path, error_trace)
                    if healed:
                        result += " | 🛠️ Self-healing patch applied. Please try the command again."
                    else:
                        result += f" | ❌ Self-healing could not resolve: {msg}"

        if not self.ui.muted and not self.orch.silent_mode:
            self.ui.set_state("LISTENING")
        
        print(f"[JARVIS] 📤 {name} -> {str(result)[:80]}")
        return types.FunctionResponse(id=fc.id, name=name, response={"result": result})
