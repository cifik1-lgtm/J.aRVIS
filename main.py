# JARVIS Cifik Intelegents - [cifikAI]
import asyncio
# Fix Qt DPI warning (harmless but annoying)
import os
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"

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
from core.tools import ToolDispatcher, TOOL_DECLARATIONS

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

class EmotionAnalyzer:
    def __init__(self):
        self.classifier = None
        if HAS_TRANSFORMERS:
            try:
                self.classifier = pipeline("text-classification", 
                                         model="bhadresh-savani/bert-base-uncased-emotion")
            except:
                pass
    
    def analyze(self, text: str) -> str:
        if not self.classifier or not text:
            return "neutral"
        try:
            result = self.classifier(text[:512])[0]
            return result['label']
        except:
            return "neutral"
    
    def adapt_response(self, emotion: str, response: str) -> str:
        if emotion == "anger":
            return f"I understand you're frustrated, sir. {response}"
        elif emotion == "sadness":
            return f"I'm sorry to hear that, sir. {response}"
        elif emotion == "joy":
            return f"I'm glad to see you're in high spirits, sir. {response}"
        return response

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
        
        # Rate limiting for saves
        self._last_save_time = datetime.now() - timedelta(seconds=10)
        
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
        
        # Emotion Analyzer
        self.emotion_analyzer = EmotionAnalyzer()
        
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

    def _check_tool_rate_limit(self, rate_key: str) -> bool:
        """Returns True if this rate_key (tool name or tool:action) is limited."""
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
        if "local" in brain:
            self.force_local = True
            self.force_openrouter = False
        elif "openrouter" in brain:
            self.force_local = True
            self.force_openrouter = True
        elif "hive" in brain:
            self.force_local = False
            self.force_openrouter = False
        else:
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

    def _on_text_command(self, text: str):
        self._last_user_text = text
        cmd = text.lower().strip()
        
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
            self.force_local = True
            self.force_openrouter = False
            self._update_config_brain("local")
            self.ui.write_log("SYS: 🧠 Forced LOCAL mode")
            self._restart_connection()
            return
        elif "switch to openrouter" in cmd or "force openrouter" in cmd:
            self.force_local = True 
            self.force_openrouter = True
            self._update_config_brain("openrouter")
            self.ui.write_log("SYS: 🧠 Forced OPENROUTER mode")
            self._restart_connection()
            return
        elif "switch to online" in cmd or "force online" in cmd or "switch to gemini" in cmd:
            self.force_local = False
            self.force_openrouter = False
            self._update_config_brain("gemini")
            self.ui.write_log("SYS: 🧠 Reverted to ONLINE mode")
            self._restart_connection()
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
        
        if self.force_local or not self._loop or not self.session:
            provider = "OpenRouter" if self.force_openrouter else ("Local GPU" if self.force_local else "Offline")
            print(f"[JARVIS] 🔌 {provider} - Routing to backup brain...")
            from agent.task_queue import get_queue, TaskPriority
            get_queue().submit(goal=text, priority=TaskPriority.HIGH, speak=lambda m: self.ui.write_log(f"🧠 {m}"))
            return
            
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

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
        elif not self.ui.muted and not self.silent_mode:
            self.ui.set_state("LISTENING")

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
        if silent_instruction:
            parts.append(silent_instruction)
        # We no longer inject recent_conv and mem_str here because 
        # the Live API handles context via session_resumption and ongoing stream.
        parts.append(sys_prompt)
        
        # TRIPLE-BRAIN ARCHITECTURE:
        # We only give Gemini Live the 'light' tools for conversation and delegation.
        # Expert tools (Browser, Code, etc.) are hidden from Live and used only by Expert Brains.
        live_tools = ["system_control", "delegate_task", "save_memory", "retrieve_memory", "preference_manager", "get_memory_stats", "forget_weak_memories"]
        filtered_decls = [d for d in TOOL_DECLARATIONS if d["name"] in live_tools]

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": filtered_decls}],
            session_resumption=types.SessionResumptionConfig(), 
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
                            print(f"[JARVIS] 🎤 Interruption detected! (peak={peak}, energy={energy:.0f})")
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
                            await self.audio_in_queue.put(response.data)

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
                                
                                # ONLY trigger _on_text_command for specific system shortcuts
                                # to prevent double-processing with the audio stream
                                shortcuts = ["switch to", "force", "diagnostic", "check models", "status", "reboot", "shutdown", "autonomous", "manual", "silent mode", "wake up"]
                                if any(s in full_in.lower() for s in shortcuts):
                                    self._on_text_command(full_in)
                            in_buf = []
                            full_out = " ".join(out_buf).strip()
                            if full_out and not self.silent_mode:
                                emotion = self.emotion_analyzer.analyze(full_in) if full_in else "neutral"
                                adapted_out = self.emotion_analyzer.adapt_response(emotion, full_out)
                                self.ui.write_log(f"Jarvis: {adapted_out}")
                                
                                # Rate limit conversation saves - only every 5 seconds
                                if full_in and full_out:
                                    now = datetime.now()
                                    if (now - self._last_save_time).seconds > 5:
                                        _save_conversation_turn(full_in, adapted_out)
                                        self._last_save_time = now
                            out_buf = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            # Check for repeating same tool (AI loop detection)
                            if fc.name == last_tool_name:
                                same_tool_count += 1
                                if same_tool_count > 5:
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
                        self.audio_in_queue = asyncio.Queue()
                        self.out_queue = asyncio.Queue(maxsize=50)
                        self._turn_done_event = asyncio.Event()
                        
                        print("[JARVIS] ✅ Connected.")
                        self.ui.set_state("LISTENING")
                        self.ui.write_log("SYS: Cloud connection established.")
                        
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
                                turns=[{"role": "user", "parts": [{"text": f"GREETING_PROTOCOL_START: {greeting}"}]}],
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
    main()