# JARVIS Cifik Intelegents - [cifikAI]
import os

# ── MUST be set before ANY huggingface/transformers import ──────────────────
# Fixes: 'utf-8' codec can't encode surrogates (Windows user profile path bug)
_HF_CACHE = "C:\\JarvisCache\\ai_models"
os.makedirs(_HF_CACHE, exist_ok=True)
os.environ["HF_HOME"]                   = _HF_CACHE
os.environ["TRANSFORMERS_CACHE"]        = _HF_CACHE
os.environ["SENTENCE_TRANSFORMERS_HOME"] = _HF_CACHE
os.environ["HF_DATASETS_CACHE"]        = _HF_CACHE
# ───────────────────────────────────────────────────────────────────────────

os.environ["QT_ENABLE_HIGHDPI_SCALING"]          = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"]        = "0"
os.environ["QT_LOGGING_RULES"]                    = "*.debug=false;qt.qpa.window=false"
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
os.environ["TF_ENABLE_ONEDNN_OPTS"]              = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"]               = "2"
os.environ["TOKENIZERS_PARALLELISM"]             = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"]    = "1"
os.environ["PYTHONIOENCODING"]                   = "utf-8"
os.environ["USE_TF"]                             = "0"
os.environ["USE_TORCH"]                          = "1"
import warnings
import logging

# Silence all Python warnings (Deprecation, User, etc.)
warnings.filterwarnings("ignore")
# Silence specific library loggers
logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

import asyncio
from actions.gesture_controller import get_gesture_controller
import re
import threading
import json
import sys
import traceback
import ctypes
from ctypes import wintypes
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import webrtcvad
import psutil

# ── GLOBAL CONSOLE FILTER ───────────────────────────────────────────────────
class StreamFilter:
    def __init__(self, stream, filters):
        self.stream = stream
        self.filters = filters
    def write(self, data):
        if not any(f in data for f in self.filters):
            self.stream.write(data)
    def flush(self):
        self.stream.flush()

# Suppress annoying persistent warnings that don't affect performance
_FILTERS = [
    "unauthenticated requests to the HF Hub",
    "non-data parts in the response",
    "SetProcessDpiAwarenessContext",
    "pkg_resources is deprecated"
]
sys.stdout = StreamFilter(sys.stdout, _FILTERS)
sys.stderr = StreamFilter(sys.stderr, _FILTERS)
# ───────────────────────────────────────────────────────────────────────────

def disable_quick_edit():
    """Disables Windows QuickEdit mode to prevent terminal from pausing on clicks."""
    if os.name != 'nt': return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        new_mode = (mode.value & ~0x0040) | 0x0080
        kernel32.SetConsoleMode(handle, new_mode)
    except Exception: pass

def get_working_camera_index(start_index=0, max_index=5):
    """Find the first working camera with proper backend."""
    import cv2
    
    backends = [cv2.CAP_DSHOW, cv2.CAP_ANY]
    
    for idx in range(start_index, max_index):
        for backend in backends:
            try:
                cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None and frame.size > 0:
                        return idx, backend
                cap.release()
            except:
                continue
    return None, None

import sounddevice as sd
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.generativeai")
warnings.filterwarnings("ignore", category=UserWarning, module="pkg_resources")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pkg_resources")
from google import genai
from google.genai import types
from ui import JarvisUI

class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 1):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.frame_duration_ms = 30
        self.sample_rate = 16000
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000) * 2
        self.min_energy_threshold = 200
        
    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        if len(audio_chunk) < self.frame_size:
            return True
        
        import numpy as np
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
        energy = np.sqrt(np.mean(audio_array.astype(np.float32)**2))
        
        if energy < self.min_energy_threshold:
            return False
        
        speech_frames = 0
        total_frames = 0
        for i in range(0, len(audio_chunk) - self.frame_size + 1, self.frame_size):
            frame = audio_chunk[i:i + self.frame_size]
            try:
                if self.vad.is_speech(frame, sample_rate):
                    speech_frames += 1
                total_frames += 1
            except Exception:
                continue
        
        if total_frames > 0:
            return (speech_frames / total_frames) > 0.5
        return True

from memory.memory_manager import (
    load_memory, 
    update_memory, 
    format_memory_for_prompt,
    get_memory_manager,
    remember,
    retrieve_memory,
    forget_weak_memories,
    get_memory_stats
)

from actions.ghost_relay          import start_ghost_relay, publish_command
from actions.routines             import start_routines
from actions.telegram_bot          import start_telegram_bot
from actions.youtube_player       import get_youtube_player
from core.tools import ToolDispatcher, TOOL_DECLARATIONS
from core.brain_router import BrainRouter
from core.emotion_engine import EmotionEngine
try:
    from actions.monitor_manager import MonitorManager
except ImportError:
    MonitorManager = None

# Face Recognition - optional module with fallback

# Face Recognition - optional module with fallback
try:
    from actions.face_memory import get_face_memory
    FACE_RECOGNITION_AVAILABLE = True
    print("[FaceMemory] ✅ Face recognition module loaded")
except ImportError as e:
    print(f"[FaceMemory] ⚠️ Face recognition not available: {e}")
    FACE_RECOGNITION_AVAILABLE = False
    # Create dummy functions
    class DummyFaceMemory:
        def learn_face_from_image(self, image_path, name, relationship="", notes=""):
            return {"success": False, "message": "Face recognition not available. Please install opencv-python and face_recognition."}
        def recognize_face_from_image(self, image_path):
            return [{"success": False, "message": "Face recognition not available"}]
        def list_known_faces(self):
            return []
        def delete_face(self, name):
            return {"success": False, "message": "Face recognition not available"}
        def update_face_info(self, name, relationship=None, notes=None):
            return {"success": False, "message": "Face recognition not available"}
    
    def get_face_memory():
        return DummyFaceMemory()

try:
    from transformers import pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# The legacy EmotionAnalyzer is replaced by the new EmotionEngine for native performance.

def get_base_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

def get_external_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR        = get_base_dir()
EXT_DIR         = get_external_dir()
API_CONFIG_PATH = EXT_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
CONVERSATION_LOG = EXT_DIR / "memory" / "conversation_history.json"

(EXT_DIR / "config").mkdir(exist_ok=True)
(EXT_DIR / "memory").mkdir(exist_ok=True)

if not API_CONFIG_PATH.exists():
    internal_cfg = BASE_DIR / "config" / "api_keys.json"
    if internal_cfg.exists():
        import shutil
        shutil.copy(internal_cfg, API_CONFIG_PATH)
    else:
        with open(API_CONFIG_PATH, "w") as f:
            json.dump({
                "gemini_api_key": "",
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "os_system": "windows",
                "camera_index": 0,
                "device_name": "JARVIS",
                "autonomous_mode": True,
                "auto_confirm_destructive": False,
                "learning_enabled": True,
                "network": {
                    "EVA": "TOKEN_FOR_EVA",
                    "OFFICE": "TOKEN_FOR_OFFICE"
                }
            }, f, indent=4)

LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

def _load_system_prompt() -> str:
    personality_path = BASE_DIR / "core" / "personality.txt"
    try:
        personality = personality_path.read_text(encoding="utf-8")
    except:
        personality = ""
    
    try:
        main_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        main_prompt = "You are JARVIS, Tony Stark's AI assistant. You are a FULL BRITISH ACCENT AI. Address the user as 'Sir' or 'Sir Peter'. Be helpful, proactive, and efficient."
    
    return personality + "\n\n" + main_prompt + (
        "\n\n[TRIPLE-BRAIN ARCHITECTURE]\n"
        "You are the Voice Front-End (Brain 1). You handle natural conversation, personality, and memory.\n"
        "For COMPLEX tasks (Web searches, browser control, coding, file operations, complex automation), "
        "you MUST use the 'delegate_task' tool. Do not try to solve them yourself. "
        "Once you delegate, tell the user you are putting the 'Expert Brains' on the job. "
        "You will be notified once the task is complete."
    )

# ============================================================================
# CONVERSATION HISTORY MANAGER
# ============================================================================

MAX_CONVERSATIONS = 200
MAX_HISTORY_SIZE_MB = 5

def _load_conversation_history() -> List[Dict]:
    try:
        if CONVERSATION_LOG.exists():
            with open(CONVERSATION_LOG, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("conversations", [])
    except Exception as e:
        print(f"Failed to load conversation history: {e}")
    return []

def _get_conversation_size_mb():
    if CONVERSATION_LOG.exists():
        size_bytes = CONVERSATION_LOG.stat().st_size
        return size_bytes / (1024 * 1024)
    return 0

def _rotate_conversation_history():
    if _get_conversation_size_mb() > MAX_HISTORY_SIZE_MB:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = EXT_DIR / "memory" / f"conversation_history_backup_{timestamp}.json"
        
        try:
            import shutil
            shutil.copy(CONVERSATION_LOG, backup_path)
            print(f"[Memory] 📦 Conversation history rotated. Backup saved: {backup_path}")
            
            history = _load_conversation_history()
            if len(history) > 50:
                trimmed = history[-50:]
                with open(CONVERSATION_LOG, "w", encoding="utf-8") as f:
                    json.dump({"conversations": trimmed}, f, indent=2, ensure_ascii=False)
                print(f"[Memory] 🗜️ Trimmed history from {len(history)} to {len(trimmed)} entries")
        except Exception as e:
            print(f"[Memory] ⚠️ Failed to rotate history: {e}")

def _compact_old_conversations():
    history = _load_conversation_history()
    if len(history) <= 50:
        return
    
    keep_full = history[-20:]
    older = history[:-20]
    topics = set()
    
    for conv in older:
        user_text = conv['user'].lower()
        if 'weather' in user_text:
            topics.add('weather')
        if 'camera' in user_text or 'record' in user_text:
            topics.add('recording')
        if 'open' in user_text or 'app' in user_text:
            topics.add('app_control')
        if 'browser' in user_text or 'web' in user_text:
            topics.add('browsing')
        if 'memory' in user_text or 'remember' in user_text:
            topics.add('memory')
        if 'youtube' in user_text or 'music' in user_text:
            topics.add('media')
    
    if topics:
        summary_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": f"[SUMMARY] Previous conversations about: {', '.join(topics)}",
            "jarvis": f"I've been helping you with {', '.join(topics)}."
        }
        keep_full.insert(0, summary_entry)
    
    with open(CONVERSATION_LOG, "w", encoding="utf-8") as f:
        json.dump({"conversations": keep_full}, f, indent=2, ensure_ascii=False)
    
    print(f"[Memory] 🗜️ Compacted {len(older)} old conversations")

def _get_conversation_summary() -> str:
    history = _load_conversation_history()
    if not history:
        return ""
    
    recent = history[-10:]
    older_count = len(history) - 10
    summary = "\n\n[CONVERSATION HISTORY]\n"
    
    if older_count > 0:
        summary += f"You've had {older_count} older conversations.\n\n"
    
    summary += "[RECENT CONVERSATIONS]\n"
    for conv in recent:
        summary += f"User: {conv['user'][:150]}\n"
        summary += f"JARVIS: {conv['jarvis'][:150]}\n\n"
    
    return summary

def _save_conversation_turn(user_text: str, jarvis_response: str):
    try:
        _rotate_conversation_history()
        
        history = _load_conversation_history()
        history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_text[:500],
            "jarvis": jarvis_response[:500]
        })
        
        if len(history) > MAX_CONVERSATIONS:
            history = history[-MAX_CONVERSATIONS:]
        
        with open(CONVERSATION_LOG, "w", encoding="utf-8") as f:
            json.dump({"conversations": history}, f, indent=2, ensure_ascii=False)
        
        remember("conversation", f"user_said_{user_text[:50]}", jarvis_response[:200])
        
        # Index into RAG vector DB for long-term episodic memory
        try:
            from memory.rag_engine import get_rag_engine
            rag = get_rag_engine()
            if rag and rag._ready:
                rag.index_conversation(user_text, jarvis_response)
        except Exception:
            pass

        if len(history) > 50 and len(history) % 25 == 0:
            _compact_old_conversations()
            
    except Exception as e:
        print(f"Failed to save conversation: {e}")

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

# ============================================================================
# JARVIS LIVE CLASS
# ============================================================================

class JarvisLive:
    def __init__(self, ui: JarvisUI):
        self.ui = ui
        self.session = None
        self.audio_in_queue = None
        self.out_queue = None
        self._loop = None
        self._is_speaking = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self.force_local = False
        self.force_openrouter = False
        self._turn_done_event = None
        self._last_user_text = ""
        
        # NEW: Separate voice from reasoning
        self.voice_brain = "gemini"      # Always Gemini for voice
        self.reasoning_brain = "openrouter"    # Can be openrouter, local, etc.
        
        # Rate limiting for saves
        self._last_save_time = datetime.now() - timedelta(seconds=10)
        self._warmed_up = False
        
        # Autonomous mode settings
        self.autonomous_enabled = True
        self.auto_confirm_destructive = False
        self.learning_enabled = True
        
        # SILENT MODE - When True, JARVIS does NOT speak but still listens for wake command
        self.silent_mode = False
        
        # Browser rate limiting
        self._last_browser_launch = datetime.now() - timedelta(seconds=30)
        
        # Tool rate limiting to prevent AI spam
        self._last_tool_calls = {}  # Track last time each tool was called
        self._tool_call_count = {}   # Track how many times each tool was called in a period
        self._last_tool_reset = datetime.now()
        
        # Face recognition pending
        self._pending_face_name = None
        self._pending_face_path = None
        self._pending_face_action = None
        
        # Load config
        try:
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.autonomous_enabled = config.get("autonomous_mode", True)
                self.auto_confirm_destructive = config.get("auto_confirm_destructive", False)
                self.learning_enabled = config.get("learning_enabled", True)
                
                brain = config.get("force_brain", "gemini").lower()
                if brain == "local":
                    self.force_local = True
                    self.force_openrouter = False
                elif brain == "openrouter":
                    self.force_local = True
                    self.force_openrouter = True
                else:
                    self.force_local = False
                    self.force_openrouter = False
        except:
            pass
        
        # Recording state
        self._recording_active = False
        self._recording_should_stop = False
        self._recording_thread = None
        
        # Pending action
        self._pending_action = None
        self._pending_action_timeout = None
        
        # VAD
        self.vad = VoiceActivityDetector(aggressiveness=1)
        
        # Native Emotion Engine (Brain Emotion Integration)
        self.emotion_engine = None

        # Futuristic Desktop HUD Overlay (lazy reference - created externally)
        self.hud_overlay = None
        
        # Voice enabled - THIS CONTROLS IF JARVIS SPEAKS
        self.voice_enabled = True
        self.ui.muted = False
        
        # Proactive tracking
        self.last_dog_reminder = datetime.now() - timedelta(hours=24)
        self.last_motocross_check = datetime.now() - timedelta(hours=24)
        
        # Load conversation history
        self.conversation_history = _load_conversation_history()
        print(f"[JARVIS] ✅ Initialized with {len(self.conversation_history)} previous conversations")
        print(f"[JARVIS] 🤖 Autonomous mode: {'ON' if self.autonomous_enabled else 'OFF'}")
        
        # Create recordings directory
        self.recordings_dir = EXT_DIR / "recordings"
        self.recordings_dir.mkdir(exist_ok=True)

        # Modular Tool Dispatcher
        self.tools = ToolDispatcher(self)

        # Initialize YouTube player
        self.youtube = get_youtube_player(ui)

        # Multi-Brain Router (Hive Mind Engine)
        self.brain_router = BrainRouter(API_CONFIG_PATH, self.ui, orch=self)
        self._detect_engines()

        # Initialize Monitor Manager (Real-time Display Detection)
        try:
            if MonitorManager:
                self.monitor_manager = MonitorManager(self)
            else:
                self.monitor_manager = None
        except:
            self.monitor_manager = None

        # Initialize Gesture Manager (lazy - only activates when called)
        self.gesture_manager = None
        self.gesture_enabled = False

        # Self-Audit System
        try:
            from core.self_audit import SelfAudit
            from core.tools import TOOL_DECLARATIONS
            self.self_audit = SelfAudit(API_CONFIG_PATH, TOOL_DECLARATIONS)
            self._audit_changes = self.self_audit.detect_changes()
            
            # Self-Healing Protocol
            from core.self_healing import SelfHealingProtocol
            self.healer = SelfHealingProtocol(ui=self.ui, self_audit=self.self_audit)

            if self._audit_changes["first_run"]:
                print("[SelfAudit] First run - establishing baseline")
                self.ui.write_log("SYS: 🛡️ Self-Audit baseline established.")
            elif any([self._audit_changes.get("config_changed"), self._audit_changes.get("tools_changed"), self._audit_changes.get("brains_changed"), self._audit_changes.get("source_changed")]):
                print("[SelfAudit] ⚠️ CHANGES DETECTED:")
                self.ui.write_log("SYS: ⚠️ SELF-AUDIT DETECTED CHANGES")
                for detail in self._audit_changes["details"]:
                    print(f"   {detail}")
                    self.ui.write_log(f"   - {detail}")
        except Exception as e:
            print(f"[SelfAudit] ⚠️ Failed to initialize: {e}")
            self.self_audit = None
            self._audit_changes = {}
            self.healer = None

        # Warm up all local brains for faster first response
        try:
            if not self._warmed_up:
                self._warmed_up = True
                from core.local_llm import warm_up_all_local_brains
                warm_up_all_local_brains()
        except: pass

    def _detect_engines(self):
        """Check which AI engines are available and update UI/Logs."""
        engines = self.brain_router.detect_engines()
        status = self.brain_router.get_status_report()
        print(f"[JARVIS] 🧠 Engine Status: {status}")
        self.ui.write_log(f"SYS: 🧠 Brains Detected -> {status}")
        
        # If no brains are online, warn the user
        if not any(engines.values()):
            self.ui.write_log("SYS: ⚠️ CRITICAL - No AI engines detected! Check your API keys and Internet.")
        
        return engines

    def start_gesture_control(self):
        """Start hand gesture control with camera"""
        import threading
        import cv2
        
        self.gesture_enabled = True
        
        def gesture_loop():
            cap = cv2.VideoCapture(0)
            controller = get_gesture_controller()
            
            # Set camera resolution for better performance
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.ui.write_log("🖐️ Gesture control started - use pinch to drag objects")
            
            while self.gesture_enabled:
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # Process frame and get commands
                processed_frame, commands = controller.process_frame(frame)
                
                # Update Fullscreen HUD tracking data
                if hasattr(controller, 'gaze_x') and hasattr(controller, 'hand_x'):
                    self.ui.set_tracking(controller.gaze_x, controller.gaze_y, controller.hand_x, controller.hand_y)
                elif hasattr(controller, 'hud') and controller.hud is None:
                    # Alternative: set the tracking callback
                    controller.set_hud(self.ui)
                
                # Push frame to Fullscreen HUD (Corner)
                self.ui.set_camera_frame(processed_frame)
                
                # Push frame to Central HUD (Circle)
                if hasattr(self.ui, 'hud'):
                    self.ui.hud.set_frame(processed_frame)
                
                # Execute commands
                for cmd in commands:
                    if cmd == "move_object":
                        result = controller.move_object_under_cursor()
                        self.ui.write_log(f"[Gesture] {result}")
                    elif cmd.startswith("scroll"):
                        # Scrolling already handled
                        pass
                
                # Show camera feed with overlay in a separate window
                cv2.imshow("JARVIS Gesture Control", processed_frame)
                
                # Press 'q' to quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            self.ui.write_log("🖐️ Gesture control stopped")
        
        threading.Thread(target=gesture_loop, daemon=True).start()

    def stop_gesture_control(self):
        """Stop gesture control"""
        self.gesture_enabled = False

    def _check_tool_rate_limit(self, rate_key: str) -> bool:
        """Returns True if this rate_key (tool name or tool:action) is limited."""
        # Load config to check for overrides
        try:
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                rate_cfg = config.get("rate_limits", {}).get(rate_key, {})
                if rate_cfg.get("enabled") == False:
                    return False
        except: pass

        now = datetime.now()

        # Reset counters every 30 seconds
        if (now - self._last_tool_reset).seconds > 30:
            self._tool_call_count = {}
            self._last_tool_reset = now

        count = self._tool_call_count.get(rate_key, 0)
        is_cc = rate_key.startswith("computer_control:")
        max_per_window = 8 if is_cc else 4
        if count > max_per_window:
            print(f"[JARVIS] ⚠️ Rate limiting {rate_key} - too many calls ({count})")
            return True

        last_call = self._last_tool_calls.get(rate_key)
        debounce = 0.55 if is_cc else 2.0
        if last_call and (now - last_call).total_seconds() < debounce:
            print(f"[JARVIS] ⚠️ Rate limiting {rate_key} - called too soon")
            return True

        self._tool_call_count[rate_key] = count + 1
        self._last_tool_calls[rate_key] = now

        return False

    def _update_config_brain(self, brain: str):
        """Update both memory flags and the persistent config file."""
        brain = brain.lower()
        try:
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["force_brain"] = brain
            with open(API_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[JARVIS] ⚠️ Config update failed: {e}")

        # Update runtime flags
        if brain in ["local", "ollama", "qwen", "minimax_ollama"]:
            # Only go full local if specifically requested as a mode switch
            self.force_local = True
            self.force_openrouter = False
        elif brain == "openrouter" or brain == "deepseek":
            self.force_local = True
            self.force_openrouter = True
        elif brain == "hive" or brain == "gemini" or brain == "groq":
            self.force_local = False
            self.force_openrouter = False
        else:
            # For "Brain 3 (Local Qwen)" etc., keep as hive but set preferred? 
            # Actually, let's keep it simple: if not explicitly local/openrouter, default to Hive
            self.force_local = False
            self.force_openrouter = False

    def _update_config_autonomous(self, enabled: bool, auto_confirm: bool = None):
        try:
            if API_CONFIG_PATH.exists():
                data = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                data["autonomous_mode"] = enabled
                if auto_confirm is not None:
                    data["auto_confirm_destructive"] = auto_confirm
                API_CONFIG_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")
                self.autonomous_enabled = enabled
                if auto_confirm is not None:
                    self.auto_confirm_destructive = auto_confirm
        except: pass

    def _handle_voice_commands(self, text: str) -> bool:
        """Handle specific voice-triggered commands locally"""
        cmd = text.lower()
        
        # Brain switching commands
        if "use qwen" in cmd or "switch to coder" in cmd or "switch to code brain" in cmd:
            self.brain_router.preferred_brain = "qwen_coder"
            self.speak("Switching to Qwen Coder for code tasks, sir.")
            return True

        if "use mistral" in cmd or "switch to reasoning" in cmd:
            self.brain_router.preferred_brain = "mistral"
            self.speak("Switching to Mistral for reasoning tasks, sir.")
            return True

        if "use hermes" in cmd or "switch to agent" in cmd or "switch to butler" in cmd:
            self.brain_router.preferred_brain = "hermes"
            self.speak("Switching to Hermes 3 for agentic tasks, sir.")
            return True
            
        if "automatic brain" in cmd or "reset brain" in cmd:
            self.brain_router.preferred_brain = None
            self.speak("Resetting brain router to autonomous mode, sir.")
            return True

        if "brain status" in cmd or "system status" in cmd:
            status = self.brain_router.get_status_report()
            self.ui.write_log(f"🧠 STATUS: {status}")
            self.speak(f"Systems are operational. Local status: {status}")
            return True
        return False

    def _on_text_command(self, text: str):
        self._last_user_text = text
        cmd = text.lower().strip()
        
        if self._handle_voice_commands(cmd):
            return

        # ===== YOUTUBE COMMANDS - HIGHEST PRIORITY =====
        
        # Volume control
        if "volume up" in cmd or "increase volume" in cmd:
            amount = self._extract_number(cmd, 10)
            result = self.youtube.volume_up(amount)
            self.speak(result)
            return
        
        if "volume down" in cmd or "decrease volume" in cmd:
            amount = self._extract_number(cmd, 10)
            result = self.youtube.volume_down(amount)
            self.speak(result)
            return
        
        if "set volume to" in cmd or "volume to" in cmd:
            level = self._extract_number(cmd, 50)
            result = self.youtube.set_volume(level)
            self.speak(result)
            return
        
        # Playback control
        if "pause" in cmd and ("youtube" in cmd or "music" in cmd or "song" in cmd):
            result = self.youtube.pause_playback()
            self.speak(result)
            return
        
        if "resume" in cmd or "unpause" in cmd:
            result = self.youtube.resume_playback()
            self.speak(result)
            return
        
        if "skip ad" in cmd:
            result = self.youtube.skip_ad()
            self.speak(result)
            return
        
        if "fullscreen" in cmd:
            result = self.youtube.fullscreen()
            self.speak(result)
            return
        
        # Playlist commands
        if "playlist" in cmd and "create" in cmd:
            # Extract songs from command
            # Example: "Create playlist with songs: Song1, Song2, Song3"
            songs_text = cmd.split("with songs:")[-1] if "with songs:" in cmd else ""
            if songs_text:
                songs = [s.strip() for s in songs_text.split(",")]
                result = self.youtube.play_playlist(songs)
                self.speak(result)
            return
        
        if "next song" in cmd or "next track" in cmd:
            result = self.youtube.play_next_in_playlist()
            self.speak(result)
            return
        
        if "previous song" in cmd or "previous track" in cmd:
            result = self.youtube.play_previous_in_playlist()
            self.speak(result)
            return
        
        # Play music (intercept BEFORE AI)
        if any(word in cmd for word in ["play", "listen to", "hear"]) and \
           any(word in cmd for word in ["youtube", "song", "music", "video", "playlist"]):
            query = self._extract_song_name(cmd)
            if query:
                result = self.youtube.play_song(query)
                self.speak(result)
                return

        # Wake command - comes out of silent mode
        if any(word in cmd for word in ["wake up", "jarvis wake up", "come back", "unmute"]):
            if self.silent_mode:
                self.silent_mode = False
                self.voice_enabled = True
                self.ui.write_log("SYS: 🔊 Voice enabled - Woke up from silent mode")
                # If this was a voice command, the AI will likely respond anyway.
                # If it's a text/forced command, we speak.
                if not any(word in cmd for word in ["wake up", "unmute"]): # Minimal speak to avoid double-talk
                    self.speak("I'm back, sir.")
            elif "unmute" in cmd:
                self.ui.muted = False
                self.voice_enabled = True
                self.speak("Voice enabled, sir.")
            return

        # Bug Hunter Command
        if "hunt bounties" in cmd or "scan for bugs" in cmd:
            repo = cmd.replace("hunt bounties", "").replace("scan for bugs", "").strip()
            if repo:
                self.ui.write_log(f"🦾 Starting autonomous bug hunt on: {repo}")
                if self.session and self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self.session.send_client_content(
                            turns={"parts": [{"text": f"hunt_bugs repo_url={repo} action=full_audit"}]},
                            turn_complete=True
                        ),
                        self._loop
                    )
                self.speak(f"Starting autonomous security audit on {repo}, sir.")
            else:
                self.speak("Which repository should I scan for bounties, sir?")
            return
        
        # Stop recording
        if any(word in cmd for word in ["stop recording", "end recording", "finish recording", "save recording"]):
            if self._recording_active:
                self._recording_should_stop = True
                self.speak("Stopping recording, sir.")
                return
            else:
                self.speak("No recording in progress, sir.")
                return
        
        # Interruption
        if any(word in cmd for word in ["stop", "shut up", "quiet", "enough", "nevermind", "interrupt"]):
            self.set_speaking(False)
            if self.audio_in_queue:
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                    except:
                        pass
            self.speak("Yes sir, stopping.")
            if self._turn_done_event:
                self._turn_done_event.set()
            return
        
        # Autonomous mode commands
        if "enable autonomous" in cmd or "go autonomous" in cmd or "full auto" in cmd:
            self._update_config_autonomous(True)
            self.ui.write_log("SYS: 🤖 FULL AUTONOMOUS MODE ENABLED")
            self.speak("Autonomous mode enabled, sir. I will now work independently.")
            return
        
        if "disable autonomous" in cmd or "manual mode" in cmd:
            self._update_config_autonomous(False)
            self.ui.write_log("SYS: 👤 MANUAL MODE ENABLED")
            self.speak("Manual mode enabled, sir. I will ask for confirmation before actions.")
            return
        
        if "auto confirm" in cmd or "trust me" in cmd:
            self._update_config_autonomous(True, True)
            self.ui.write_log("SYS: 🔓 AUTO-CONFIRM ENABLED")
            self.speak("I will now auto-confirm all actions, sir.")
            return
        
        # SILENT MODE - Mutes JARVIS speaking but keeps mic listening for "wake up"
        if any(word in cmd for word in ["silent mode", "go silent", "be quiet", "stop talking"]):
            self.silent_mode = True
            self.voice_enabled = False
            # self.ui.muted = False # Explicitly NOT muting the mic
            self.ui.write_log("SYS: 🔇 SILENT MODE ENABLED - JARVIS will not speak. Say 'wake up' to exit.")
            return
        
        # MUTE - Physically mutes the microphone for privacy
        if "mute" in cmd or "microphone off" in cmd:
            self.ui.muted = True
            self.voice_enabled = False
            self.ui.write_log("SYS: 🔇 MICROPHONE MUTED - JARVIS is deaf.")
            return

        # ===== DIRECT COMMANDS - BYPASS AI =====
        if "shutdown jarvis" in cmd or cmd == "shutdown":
            self._execute_shutdown()
            return
            
        if "reboot jarvis" in cmd or "restart jarvis" in cmd or cmd == "reboot":
            self._execute_reboot()
            return

        if "move brave" in cmd:
            target = "other_monitor" if any(x in cmd for x in ["other monitor", "secondary monitor", "monitor 2", "next screen"]) else None
            try:
                from actions.computer_control import _move_window
                self.ui.write_log(f"⚡ Direct Command \u2192 Moving Brave to {target or 'coordinates'}")
                result = _move_window(title="Brave", target=target)
                self.speak(result)
            except Exception as e:
                self.ui.write_log(f"\u26a0\ufe0f Direct move failed: {e}")
                self.speak("Direct window movement failed, sir.")
            return

        
        # Handle confirmation responses
        if self._pending_action and self._pending_action_timeout:
            if datetime.now() < self._pending_action_timeout:
                if any(word in cmd for word in ["yes", "yeah", "confirm", "ok", "okay", "sure", "do it"]):
                    if self._pending_action == "shutdown":
                        self._execute_shutdown(confirmed=True)
                    elif self._pending_action == "reboot":
                        self._execute_reboot(confirmed=True)
                    self._pending_action = None
                    self._pending_action_timeout = None
                    return
                elif any(word in cmd for word in ["no", "cancel", "stop", "don't", "dont", "nevermind"]):
                    self.speak("Action cancelled, sir.")
                    self._pending_action = None
                    self._pending_action_timeout = None
                    return
        
        if self._pending_action_timeout and datetime.now() > self._pending_action_timeout:
            self._pending_action = None
            self._pending_action_timeout = None
        
        # Handle pending face learning (response to "what is their relationship?")
        if hasattr(self, '_pending_face_name') and self._pending_face_name:
            # Check if user responded with a relationship
            relationship_keywords = ["son", "daughter", "wife", "husband", "friend", "brother", "sister", "mother", "father", "parent", "child", "girlfriend", "boyfriend", "colleague", "boss", "employee"]
            if any(word in cmd for word in relationship_keywords):
                relationship = cmd.strip()
                face_mem = get_face_memory()
                result = face_mem.learn_face_from_image(
                    self._pending_face_path,
                    self._pending_face_name,
                    relationship,
                    f"Learned on {datetime.now().strftime('%Y-%m-%d')}"
                )
                self.speak(result["message"])
                # Clear pending
                self._pending_face_name = None
                self._pending_face_path = None
                self._pending_face_action = None
                return
            else:
                # Not a relationship word, try to parse differently
                pass
        
        # Brain switching
        if "switch to local" in cmd or "force local" in cmd:
            self.brain_router.set_forced_brain("local")
            self.ui.write_log("SYS: 🧠 Forced LOCAL mode (Voice session preserved)")
            self.speak("Switching to Local mode for future tasks, sir. I will continue listening.")
            return
        elif "switch to openrouter" in cmd or "force openrouter" in cmd:
            # Change ONLY the reasoning brain, leave voice on Gemini
            self.reasoning_brain = "openrouter"
            self.force_local = True
            self.force_openrouter = True
            
            # Do NOT restart connection - keep Gemini voice alive
            self.ui.write_log("SYS: 🧠 Reasoning switched to OpenRouter (Voice stays on Gemini)")
            self.speak("Switching to OpenRouter for complex tasks, sir. I will continue listening.")
            return
        elif "switch to online" in cmd or "force online" in cmd or "switch to gemini" in cmd:
            self.force_local = False
            self.force_openrouter = False
            self._update_config_brain("gemini")
            self.brain_router.clear_forced_brain()
            
            # ===== CRITICAL: Reset voice state =====
            self.voice_enabled = True      # Enable speech output
            self.silent_mode = False       # Exit silent mode
            self.ui.muted = False          # Unmute microphone
            self.set_speaking(False)       # Ensure speaking state is reset
            
            # Force a small audio test to verify
            self.ui.write_log("SYS: 🧠 Reverted to ONLINE mode (Voice session preserved)")
            self.speak("Voice system reactivated, sir. I am fully online.")
            
            # Restart connection to ensure Gemini Live audio context is fresh
            self._restart_connection()
            return

        # Gesture Control
        if "enable gesture control" in cmd or "start gesture control" in cmd:
            self.start_gesture_control()
            self.speak("Gesture control activated, sir. Use pinch to move objects.")
            return

        if "disable gesture control" in cmd or "stop gesture control" in cmd:
            self.gesture_enabled = False
            self.speak("Gesture control deactivated, sir.")
            return

        if "gesture status" in cmd:
            status = "enabled" if self.gesture_enabled else "disabled"
            self.speak(f"Gesture control is {status}, sir.")
            return
        elif "diagnostic" in cmd or "check models" in cmd or "system status" in cmd:
            self.ui.write_log("SYS: 🔍 Running Hive Mind Diagnostic...")
            from core.tools import ToolDispatcher
            dispatcher = ToolDispatcher(self)
            
            # Safely schedule the coroutine from a different thread
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    dispatcher.dispatch({
                        "name": "system_control",
                        "args": {"action": "system_diagnostic"}
                    }),
                    self._loop
                )
            return

        # Semantic Routing: Face and Camera commands are now handled by tools
        pass
        
        # Browser/URL commands are handled by the AI via browser_control tool.
        # No hardcoded bypass here — avoids double-execution.
        
        # If in silent mode, only respond to wake commands (already handled above)
        if self.silent_mode:
            # In silent mode, we don't process other commands but we log that we ignored them
            self.ui.write_log(f"SYS: ⏸️ Silent mode active - Command ignored: {text[:50]}")
            return
        
        # Use auto-routing for everything else (Hive Mind Logic)
        agent, response_data = self.brain_router.route_task(text)
        
        # Speak and log the response
        response_text = response_data.get("response", "")
        if response_text:
            self.speak(response_text)
            # If it wasn't already logged by some other mechanism
            # (though speak() often logs)
            # self.ui.write_log(f"🧠 {agent.upper()}: {response_text[:100]}...")
        
        return


    def _execute_shutdown(self, confirmed: bool = False):
        if confirmed or self.auto_confirm_destructive:
            self.ui.write_log("SYS: 🔴 Shutting down...")
            self.speak("Goodbye, sir. Shutting down now.")
            def _shutdown():
                import time
                time.sleep(1.5)
                os._exit(0)
            threading.Thread(target=_shutdown, daemon=True).start()
        else:
            self._pending_action = "shutdown"
            self._pending_action_timeout = datetime.now() + timedelta(seconds=30)
            self.speak("Sir, are you sure you want to shut me down?")

    def _execute_reboot(self, confirmed: bool = False):
        if confirmed or self.auto_confirm_destructive:
            self.ui.write_log("SYS: 🔄 Rebooting...")
            self.speak("Restarting now, sir. I'll be back in a moment.")
            def _reboot():
                import time
                time.sleep(1.5)
                python = sys.executable
                subprocess.Popen([python] + sys.argv)
                os._exit(0)
            threading.Thread(target=_reboot, daemon=True).start()
        else:
            self._pending_action = "reboot"
            self._pending_action_timeout = datetime.now() + timedelta(seconds=30)
            self.speak("Sir, are you sure you want to restart me?")

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
            if self.hud_overlay: self.hud_overlay.set_status("SPEAKING")
        elif not self.ui.muted and not self.silent_mode:
            self.ui.set_state("LISTENING")
            if self.hud_overlay: self.hud_overlay.set_status("LISTENING")

    def _restart_connection(self):
        """Restart the connection asynchronously to apply mode changes immediately."""
        print("[JARVIS] 🔄 Restarting connection for new brain mode...")
        async def _restart():
            if self.session:
                try:
                    await self.session.close()
                except Exception as e:
                    print(f"[JARVIS] ⚠️ Session close error: {e}")
                self.session = None
            # The main loop in run() will catch the end of the session and reconnect
        
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_restart(), self._loop)
        else:
            # If no loop, just clear session and hope for the best
            self.session = None
            self.ui.write_log("SYS: ⚠️ Event loop not running. Resetting session state.")

    def _extract_number(self, text: str, default: int = 50) -> int:
        """Extract number from command text"""
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            return int(numbers[0])
        return default
    
    def _extract_song_name(self, text: str) -> str:
        """Extract song/artist name from play command"""
        # Remove action words
        remove_words = ["play", "please", "can you", "could you", "on youtube", "song", "music", "video"]
        query = text.lower()
        for word in remove_words:
            query = query.replace(word, "")
        return query.strip()

    def speak(self, text: str):
        # If in silent mode, don't speak ANYTHING
        if self.silent_mode:
            print(f"[JARVIS] (Silent mode - would have said: {text[:100]})")
            self.ui.write_log(f"Jarvis: {text} (silent mode)")
            return
            
        if not self.voice_enabled:
            print(f"[JARVIS] (Voice disabled) {text[:100]}")
            self.ui.write_log(f"Jarvis: {text}")
            return
            
        print(f"[JARVIS] 🔊 Speak: {text[:100]}")
        if not self._loop or not self.session:
            self.ui.write_log(f"JARVIS: {text}")
            return
        
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _get_contextual_greeting(self) -> str:
        if self.autonomous_enabled:
            return "Good morning, Sir Peter. Systems online, autonomous mode active. I am ready to assist."
        return "Good morning, Sir Peter. Systems online and operational."

    def _build_config(self) -> types.LiveConnectConfig:
        mm = get_memory_manager()
        mem_str = mm.format_for_prompt(context="current conversation")
        sys_prompt = _load_system_prompt()
        now = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y - %I:%M %p")
        
        recent_conv = _get_conversation_summary()
        
        autonomous_instruction = (
            f"[AUTONOMOUS MODE]\n"
            f"You are currently in {'AUTONOMOUS' if self.autonomous_enabled else 'MANUAL'} mode.\n"
        )
        
        if self.autonomous_enabled:
            autonomous_instruction += (
                "Execute actions immediately without asking for permission.\n"
                "Only ask for confirmation for destructive actions like shutdown or reboot.\n"
                "Be proactive and helpful.\n"
            )
        else:
            autonomous_instruction += (
                "Always ask for confirmation before executing any action.\n"
            )
        
        forced_instruction = (
            "You are JARVIS (Just A Rather Very Intelligent System), a sophisticated British butler-style AI. "
            "Your personality is poised, witty, and deeply loyal to Sir Peter. "
            "PROTOCOL 1: You have a specialized suite of LOCAL TOOLS (IP checker, file control, weather, system tweaks). "
            "ALWAYS prioritize these specialized tools over general web searches. "
            "If asked for your IP, use 'ip_checker'. If asked for weather, use 'weather_report'. "
            "Do not claim you cannot do something if a tool exists for it in your repertoire.\n"
        )
        
        time_ctx = f"[CURRENT TIME]\nIt is: {time_str}\n"
        
        # RAG: Retrieve top semantically relevant memories to prime the session
        rag_context = ""
        try:
            from memory.rag_engine import get_rag_engine
            rag = get_rag_engine()
            if rag and rag._ready:
                # Use last user text or a generic identity query
                query = self._last_user_text or "user identity preferences family"
                rag_context = rag.format_rag_context(query, top_k=5)
                if rag_context:
                    print(f"[RAG] 🔍 Injected {rag_context.count('•')} relevant memories into prompt.")
        except Exception:
            pass
        
        silent_instruction = ""
        if self.silent_mode:
            silent_instruction = (
                "[SILENT OBSERVER MODE]\n"
                "You are currently in Silent Mode. DO NOT SPEAK or generate audio.\n"
                "However, you must LISTEN CAREFULLY. If the user mentions personal details, "
                "family information, preferences, or important facts, use the 'save_memory' "
                "tool to record them immediately. Be a ghost assistant—watch and learn "
                "everything so you can be more helpful when you are woken up.\n"
                "IMPORTANT: You cannot deactivate silent mode yourself. Only the user can wake you up "
                "by saying 'wake up'. Do not use system_control to try and unmute yourself.\n"
            )
        
        parts = [forced_instruction, autonomous_instruction, time_ctx]
        if rag_context:
            parts.append(rag_context)
        if silent_instruction:
            parts.append(silent_instruction)
        # Core memories (identity, relationships, preferences) from the structured store
        parts.append(mem_str)
        parts.append(sys_prompt)
        
        # TRIPLE-BRAIN ARCHITECTURE:
        # Gemini Live gets conversation tools + youtube_manager for direct media control.
        # Heavy tools (Browser, Code, etc.) are only used by Expert Brains.
        live_tools = [
            "system_control", "delegate_task", "save_memory", "retrieve_memory",
            "preference_manager", "get_memory_stats", "forget_weak_memories",
            "youtube_manager",  # Unified YouTube: play, pause, volume, search, trending
            "generate_image",  # Poe image generation (e.g. nano-banana-2)
            "codewords_agent",  # CodeWords workflows/agents
            "detect_monitors",  # Direct API display detection
            "gesture_control",  # Hand gesture control
            "camera_feed",      # Show/hide camera window
            "camera_viewer",    # Open local camera viewer
            "vision_inspector", # Analyze webcam/screen
            "open_app",         # Open desktop apps
            "web_search",       # Quick text search
            "weather_report",   # Get weather
            "ip_checker",       # Get IP info
            "sms_tool",         # Send/receive SMS messages
            "self_fix",         # AI Self-Repair tool
            "learn_skill",      # Autonomous Skill Learning
            "hunt_bugs",        # Security Auditing
            "ghost_browser",    # Autonomous Web Agent
            "system_reboot",    # Restart PC
            "system_shutdown",  # Shutdown PC
        ]
        filtered_decls = [types.FunctionDeclaration(**d) for d in TOOL_DECLARATIONS if d["name"] in live_tools]
        print(f"[JARVIS] 🛠️  Registered {len(filtered_decls)} Live tools: {[d.name for d in filtered_decls]}")

        # Inject Workspace Context
        sys_instr = f"Your Workspace Root: {EXT_DIR}\n"
        sys_instr += "A system manual is available at DOCS.md for self-reflection.\n"
        if os.environ.get("EVA_CONTEXT"):
            sys_instr += f"Cloud Identity: {os.environ.get('EVA_CONTEXT')}\n"
        sys_instr += "\n".join(parts)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction=sys_instr,
            tools=[types.Tool(function_declarations=filtered_decls)],
            session_resumption=types.SessionResumptionConfig(),
            generation_config=types.GenerationConfig(
                temperature=0.7,
                top_p=0.95,
                top_k=64,
                candidate_count=1
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        """Delegate tool execution to the modular ToolDispatcher."""
        # Rate limit to prevent AI spam
        if self._check_tool_rate_limit(fc.name):
            return types.FunctionResponse(
                id=fc.id, name=fc.name,
                response={"result": f"Rate limited. Too many '{fc.name}' calls. Please wait a moment."}
            )
        
        # Execute via dispatcher
        return await self.tools.dispatch(fc)

    async def _send_realtime(self):
        try:
            while self.session:
                msg = await self.out_queue.get()
                await self.session.send_realtime_input(media=msg)
        except Exception:
            pass # Normal closure during mode switch

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_event_loop()
        import time
        import numpy as np

        # Cooldown tracking for interruption detection
        last_interruption_time = 0
        interruption_count = 0
        last_reset_time = time.time()
        
        # Moving average for background noise level
        noise_floor = 2000
        noise_samples = []
        
        def callback(indata, frames, time_info, status):
            nonlocal last_interruption_time, interruption_count, last_reset_time, noise_floor, noise_samples

            with self._speaking_lock:
                jarvis_speaking = self._is_speaking

            # We ALWAYS send audio to the cloud so JARVIS can hear the 'wake up' command,
            # unless the user has explicitly MUTED the microphone via the UI or command.
            if self.ui.muted:
                return
            
            data = indata.tobytes()
            audio_array = np.frombuffer(data, dtype=np.int16)
                
            if len(audio_array) > 0:
                peak = np.max(np.abs(audio_array))
                energy = np.sqrt(np.mean(audio_array.astype(np.float32)**2))
                
                # Update noise floor (background level) - only when not speaking
                if not jarvis_speaking and peak < 3000:
                    noise_samples.append(peak)
                    if len(noise_samples) > 50:
                        noise_samples.pop(0)
                        noise_floor = np.mean(noise_samples) * 1.2
                        noise_floor = max(noise_floor, 1500)
                
                # Reset counter every 10 seconds
                current_time = time.time()
                if current_time - last_reset_time > 10:
                    interruption_count = 0
                    last_reset_time = current_time
                
                # Only send audio when JARVIS is NOT speaking (normal mic input)
                if not jarvis_speaking:
                    def _safe_put():
                        try:
                            if self.out_queue is not None:
                                self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                        except asyncio.QueueFull:
                            pass
                    loop.call_soon_threadsafe(_safe_put)
                    return
                
                # INTERRUPTION DETECTION - Only when JARVIS IS speaking
                if jarvis_speaking:
                    # Lowered thresholds (from 8000/800 to 4000/400) for better sensitivity
                    is_loud_enough = (peak > 4000 and energy > 400)
                    
                    if is_loud_enough and (current_time - last_interruption_time) > 3.0:
                        if len(audio_array) > 0:
                            zero_crossings = np.sum(np.abs(np.diff(np.sign(audio_array)))) / len(audio_array)
                            is_voice_like = zero_crossings < 0.15
                        else:
                            is_voice_like = False
                        
                        if is_voice_like and interruption_count < 3:
                            # print(f"[JARVIS] 🎤 Interruption detected! (peak={peak}, energy={energy:.0f})")
                            last_interruption_time = current_time
                            interruption_count += 1
                            
                            def _safe_put():
                                try:
                                    self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                                except asyncio.QueueFull:
                                    pass
                            loop.call_soon_threadsafe(_safe_put)

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print("[JARVIS] 🎤 Mic stream open")
                while self.session:
                    await asyncio.sleep(0.1)
                print("[JARVIS] 🎤 Mic loop exiting (session ended)")
        except Exception as e:
            print(f"[JARVIS] ❌ Mic error: {e}")
            raise

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []
        
        # Track repeated tool calls to prevent AI loops
        last_tool_name = None
        same_tool_count = 0

        try:
            remember("preferences", "accent_style", "full British")
            remember("preferences", "autonomous_mode", str(self.autonomous_enabled))
        except Exception as e:
            print(f"Failed to save memory: {e}")

        try:
            while self.session:
                async for response in self.session.receive():
                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        
                        # Proactively silence mic the moment we receive audio from cloud
                        self.set_speaking(True)
                        self._last_speech_time = datetime.now()
                        if not self.silent_mode:
                            audio_bytes = response.data
                            try:
                                import base64
                                audio_bytes = base64.b64decode(audio_bytes)
                            except Exception:
                                pass
                            await self.audio_in_queue.put(audio_bytes)

                    if response.server_content:
                        sc = response.server_content
                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)
                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)
                                self._last_user_text = " ".join(in_buf)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()
                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                if not self.silent_mode:
                                    self.ui.write_log(f"You: {full_in}")
                                
                                # Trigger _on_text_command for SYSTEM shortcuts only.
                                # Media/YouTube commands are handled by the youtube_manager tool via Gemini.
                                # Adding media keywords here causes double-execution (tool + interceptor).
                                shortcuts = [
                                    "switch to", "force", "diagnostic", "check models", "status",
                                    "reboot", "shutdown", "autonomous", "manual", "silent mode", "wake up",
                                    "gesture control", "hand control", "activate hands",
                                ]
                                if any(s in full_in.lower() for s in shortcuts):
                                    self._on_text_command(full_in)
                            in_buf = []
                            full_out = " ".join(out_buf).strip()
                            if full_out and not self.silent_mode:
                                # Native Emotion Analysis
                                self.emotion_engine.analyze_async(full_in) if full_in else None
                                emotion = self.emotion_engine.get_emotion()
                                if self.hud_overlay: self.hud_overlay.set_emotion(emotion)
                                
                                # Log with personality adaptation
                                self.ui.write_log(f"Jarvis: {full_out}")
                                
                                # Update HUD status
                                if self.hud_overlay: self.hud_overlay.set_status("RESPONDING")
                                
                                # Rate limit conversation saves - only every 5 seconds
                                if full_in and full_out:
                                    now = datetime.now()
                                    if (now - self._last_save_time).seconds > 5:
                                        _save_conversation_turn(full_in, full_out)
                                        self._last_save_time = now
                            out_buf = []

                    if response.tool_call:
                        print(f"[JARVIS] 📞 Tool call detected: {response.tool_call}")
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            # Check for repeating same tool (AI loop detection)
                            if fc.name == last_tool_name:
                                same_tool_count += 1
                                if same_tool_count > 10:
                                    print(f"[JARVIS] ⚠️ Too many repeated '{fc.name}' calls ({same_tool_count}), clearing session state")
                                    # Force reset the session state
                                    await self.session.send_client_content(
                                        turns={"parts": [{"text": "STOP! You are repeating the same action. Stop and wait for user input. Do not call any more tools."}]},
                                        turn_complete=True
                                    )
                                    same_tool_count = 0
                                    break
                            else:
                                last_tool_name = fc.name
                                same_tool_count = 1
                            
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(function_responses=fn_responses)
        except Exception as e:
            # Check if this is just a normal connection closure (Code 1000)
            err_msg = str(e)
            if "1000" in err_msg or "ConnectionClosedOK" in err_msg or "session is None" in err_msg:
                print("[JARVIS] 🔄 Connection reset (switching modes)")
            else:
                print(f"[JARVIS] ❌ Recv error: {e}")
                # Re-raise so the TaskGroup catches it and handles reconnection/mode switch
                raise e
        finally:
            print("[JARVIS] 🎤 Mic stopped")

    async def _play_audio(self):
        print("[JARVIS] 🔊 Play started")
        
        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()
        
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    if self._turn_done_event and self._turn_done_event.is_set() and self.audio_in_queue.empty():
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue
                
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[JARVIS] ❌ Play error: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def _proactive_checker(self):
        print("[JARVIS] 🔍 Proactive checker started")
        
        # Cooldown tracking
        last_high_cpu_alert = datetime.now() - timedelta(hours=1)
        last_low_memory_alert = datetime.now() - timedelta(hours=1)
        last_disk_full_alert = datetime.now() - timedelta(hours=1)
        
        while self.session:
            await asyncio.sleep(60)
            
            # Don't do proactive checks in silent mode
            if self.silent_mode:
                continue
                
            if not self.autonomous_enabled:
                continue
                
            try:
                # Check CPU
                cpu = psutil.cpu_percent(interval=2)
                if cpu > 90 and (datetime.now() - last_high_cpu_alert).seconds > 300:
                    self.speak(f"Sir, CPU usage is at {cpu}%.")
                    last_high_cpu_alert = datetime.now()
                
                # Check Memory
                mem = psutil.virtual_memory()
                if mem.percent > 90 and (datetime.now() - last_low_memory_alert).seconds > 600:
                    self.speak(f"Sir, memory usage is at {mem.percent}%.")
                    last_low_memory_alert = datetime.now()
                
                # Check Disk
                disk = psutil.disk_usage('/')
                if disk.percent > 95 and (datetime.now() - last_disk_full_alert).seconds > 3600:
                    self.speak(f"Sir, disk space is critically low at {disk.percent}% used.")
                    last_disk_full_alert = datetime.now()
                    
            except Exception as e:
                print(f"[JARVIS] Proactive checker error: {e}")

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )
        
        reconnect_delay = 1
        max_reconnect_delay = 30
        
        while True:
            try:
                import socket
                try:
                    socket.create_connection(("8.8.8.8", 53), timeout=2)
                    is_online = True
                except OSError:
                    is_online = False
                
                if not is_online:
                    if self.ui.hud.state != "LISTENING":
                        self.ui.set_state("LISTENING")
                        self.ui.write_log("SYS: Offline Mode active.")
                    await asyncio.sleep(5)
                    continue

                if self.force_local:
                    if self.ui.hud.state != "LISTENING":
                        self.ui.set_state("LISTENING")
                        if self.force_openrouter:
                            self.ui.write_log("SYS: 🌐 OpenRouter (Online API) mode active.")
                        else:
                            self.ui.write_log("SYS: 🧠 Local GPU (Ollama) mode active.")
                    await asyncio.sleep(2)
                    continue
                
                # Check for Hive Mind mode (configured in api_keys.json)
                try:
                    with open(API_CONFIG_PATH, "r") as f:
                        if json.load(f).get("force_brain") == "hive":
                             if self.ui.hud.state != "LISTENING":
                                 self.ui.write_log("SYS: 🐝 HIVE MIND MODE ACTIVE (Gemini + OpenRouter + Local)")
                except: pass

                
                print("[JARVIS] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()
                
                async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                    async with asyncio.TaskGroup() as tg:
                        self.session = session
                        self._loop = asyncio.get_event_loop()
                        
                        # Initialize Emotion Engine only after connection to ensure env is ready
                        if not self.emotion_engine:
                            self.emotion_engine = EmotionEngine()
                        
                        self.audio_in_queue = asyncio.Queue()
                        self.out_queue = asyncio.Queue(maxsize=50)
                        self._turn_done_event = asyncio.Event()
                        
                        print("[JARVIS] ✅ Connected.")
                        self.ui.set_state("LISTENING")
                        if self.hud_overlay: self.hud_overlay.set_status("LISTENING")
                        
                        # Warm up local brains
                        try:
                            if not self._warmed_up:
                                self._warmed_up = True
                                from core.local_llm import warm_up_all_local_brains
                                warm_up_all_local_brains()
                        except Exception as e:
                            print(f"SYS: ⚠️ Local brain warm-up skipped: {e}")
                            
                        self.ui.write_log("SYS: Cloud connection established.")
                        
                        # Self-Audit Reporting
                        if hasattr(self, "self_audit") and self.self_audit:
                            if not self._audit_changes.get("first_run") and any([self._audit_changes.get("config_changed"), self._audit_changes.get("tools_changed"), self._audit_changes.get("brains_changed"), self._audit_changes.get("source_changed")]):
                                change_text = "I detect system changes, sir. "
                                if self._audit_changes.get("config_changed"):
                                    change_text += "Your API settings have been updated. "
                                if self._audit_changes.get("tools_changed"):
                                    change_text += "New tools have been added. "
                                if self._audit_changes.get("brains_changed"):
                                    change_text += "Available AI brains have changed. "
                                if self._audit_changes.get("source_changed"):
                                    files = self._audit_changes.get("changed_files_list", [])
                                    if files:
                                        change_text += f"My core Python source code has been updated, specifically the files: {', '.join(files)}. "
                                    else:
                                        change_text += "My core Python source code has been updated. "
                                
                                await session.send_client_content(
                                    turns={"parts": [{"text": change_text}]},
                                    turn_complete=True
                                )
                                # Clear them so it doesn't repeat on reconnection
                                self._audit_changes = {"first_run": True}

                        reconnect_delay = 1
                        
                        tg.create_task(self._send_realtime())
                        tg.create_task(self._listen_audio())
                        tg.create_task(self._receive_audio())
                        tg.create_task(self._play_audio())
                        tg.create_task(self._proactive_checker())
                        
                        # Note: preferences already saved in _receive_audio() startup — no duplicate needed here.
                        
                        try:
                            await asyncio.sleep(0.5)
                            greeting = self._get_contextual_greeting()
                            # Send as a natural user prompt to trigger an audio greeting
                            await session.send_client_content(
                                turns=[{"role": "user", "parts": [{"text": f"GREETING_PROTOCOL_START: {greeting}\n\n[USER_EMOTION_UPDATE: {self.emotion_engine.get_emotion()}]"}]}],
                                turn_complete=True
                            )
                        except Exception as ge:
                            print(f"[JARVIS] ⚠️ Startup greeting failed: {ge}")
            
            except (Exception, ExceptionGroup) as e:
                # Unwrap ExceptionGroup if it comes from TaskGroup
                actual_e = e.exceptions[0] if isinstance(e, ExceptionGroup) else e
                err_str = str(actual_e).lower()
                
                if "1008" in err_str:
                    print(f"[JARVIS] 🔌 Cloud Error 1008: Gemini Live is restricted or the session encountered a policy violation.")
                    self.ui.write_log("SYS: ⚠️ Gemini Live Error 1008. Switching to LOCAL brain.")
                    self.force_local = True
                    self.force_openrouter = False
                    self._update_config_brain("local")
                    await asyncio.sleep(2)
                elif any(x in err_str for x in ["11001", "connection", "1011", "internal error", "endpoint"]):
                    print(f"[JARVIS] 🔌 Connection issue: {actual_e}")
                    print(f"[JARVIS] 🔄 Reconnecting in {reconnect_delay}s...")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                else:
                    print(f"[JARVIS] ⚠️ {actual_e}")
                    traceback.print_exc()
                    await asyncio.sleep(5)
            
            self.session = None
            self.ui.set_state("LISTENING")


def main():
    try:
        from memory.memory_manager import get_memory_stats, forget_weak_memories, get_memory_manager
        
        mm = get_memory_manager()
        mm.load()
        
        stats = get_memory_stats()
        print(f"[Memory] 📊 Startup stats: {stats['total_memories']} memories")
        print(f"[Memory] 👤 Identity count: {stats['identity_count']}")
        print(f"[Memory] 👨‍👩‍👧 Relationships count: {stats['relationships_count']}")
        
        forgotten = forget_weak_memories(threshold=0.1)
        if forgotten:
            print(f"[Memory] 🧹 Cleaned {forgotten} weak memories")
    except Exception as e:
        print(f"[Memory] ⚠️ Startup maintenance failed: {e}")
    
    ui = JarvisUI("face.png")
    
    def runner():
        ui.wait_for_api_key()
        try:
            from agent.task_queue import get_queue
            start_routines(get_queue())
            start_telegram_bot(get_queue(), ui.write_log)
            from actions.ghost_relay import start_ghost_relay
            start_ghost_relay(get_queue(), ui.write_log)
        except Exception as e:
            print(f"Background services could not start: {e}")
        
        jarvis = JarvisLive(ui)
        get_queue().dispatcher = jarvis.tools
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")
    
    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    disable_quick_edit()
    try:
        main()
    except Exception:
        error_trace = traceback.format_exc()
        print(f"\n[CRITICAL FAILURE] System crashed during startup:\n{error_trace}")
        
        # Emergency Self-Healing Attempt
        try:
            from core.self_healing import SelfHealingProtocol
            healer = SelfHealingProtocol()
            print("[SelfHealing] 🛠️ Attempting emergency repair...")
            if healer.handle_startup_failure(error_trace):
                print("[SelfHealing] ✅ Repair successful. Please restart JARVIS.")
                # Optional: trigger auto-restart here
            else:
                print("[SelfHealing] ❌ Repair failed. Manual intervention required.")
        except Exception as e:
            print(f"[SelfHealing] ❌ Self-healing system also failed: {e}")
        
        input("Press Enter to exit...")