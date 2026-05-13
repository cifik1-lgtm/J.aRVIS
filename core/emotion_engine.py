import threading
import queue
import time
from typing import Dict, Optional
import warnings
import os
from pathlib import Path

# Fix for Windows surrogate encoding issues in user profile paths.
# Use a fully ASCII-safe cache dir that HuggingFace can handle.
_SAFE_CACHE = "C:\\JarvisCache\\ai_models"
os.makedirs(_SAFE_CACHE, exist_ok=True)
os.environ["HF_HOME"] = _SAFE_CACHE
os.environ["TRANSFORMERS_CACHE"] = _SAFE_CACHE
os.environ["SENTENCE_TRANSFORMERS_HOME"] = _SAFE_CACHE
warnings.filterwarnings("ignore", category=UserWarning)

class EmotionEngine:
    def __init__(self):
        self.model_name = "bhadresh-savani/bert-base-uncased-emotion"
        self.classifier = None
        self.current_emotion = "neutral"
        self.emotion_scores = {}
        self._input_queue = queue.Queue()
        self._running = True
        self._lock = threading.Lock()
        
        # Start background initialization to not block JARVIS startup
        self._init_thread = threading.Thread(target=self._initialize, daemon=True)
        self._init_thread.start()
        
        # Start processing loop
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()

    def _initialize(self):
        try:
            # Re-verify env vars just before import
            os.environ["HF_HOME"] = _SAFE_CACHE
            os.environ["TRANSFORMERS_CACHE"] = _SAFE_CACHE
            
            from transformers import pipeline
            print(f"[EmotionEngine] 🧠 Initializing Native Emotion Engine ({self.model_name})...")
            # Force local_files_only=False first time, then it will use cache
            self.classifier = pipeline("text-classification", model=self.model_name)
            print(f"[EmotionEngine] ✅ Emotion Engine Online.")
        except Exception as e:
            # If still failing, it might be a weird path in sys.path
            print(f"[EmotionEngine] ⚠️ Failed to initialize: {e}")
            # Log the problematic path if possible
            try:
                import sys
                print(f"[EmotionEngine] DEBUG: sys.executable: {sys.executable}")
            except: pass

    def _process_loop(self):
        while self._running:
            try:
                text = self._input_queue.get(timeout=1.0)
                if self.classifier:
                    results = self.classifier(text)
                    if results:
                        with self._lock:
                            self.current_emotion = results[0]['label']
                            self.emotion_scores = results[0]
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[EmotionEngine] \u26a0\ufe0f Processing error: {e}")

    def analyze_async(self, text: str):
        """Queue text for background analysis."""
        if text and len(text.strip()) > 0:
            self._input_queue.put(text)

    def get_emotion(self) -> str:
        """Get the latest detected emotion."""
        with self._lock:
            return self.current_emotion

    def get_system_prompt_adjustment(self) -> str:
        """Returns a string to append to the system prompt based on detected emotion."""
        emotion = self.get_emotion()
        
        adjustments = {
            "joy": "The user seems happy or excited. Be enthusiastic and celebratory, share their joy while remaining professional.",
            "sadness": "The user seems sad or disappointed. Be more empathetic, gentle, and supportive. Offer assistance with extra care.",
            "anger": "The user seems frustrated or angry. Remain calm, professional, and extra efficient. Acknowledge frustration if appropriate but stay focused on solutions.",
            "fear": "The user seems worried or anxious. Be reassuring, confident, and provide clear, structured information to help calm the situation.",
            "surprise": "The user seems surprised. Be reactive and helpful in explaining what happened or assisting with the new development.",
            "love": "The user is being very friendly. Be warm and acknowledge the positive rapport while maintaining your role as an AI assistant."
        }
        
        return f"\n\n[EMOTION DETECTED: {emotion.upper()}]\n{adjustments.get(emotion, 'Maintain your standard professional and helpful demeanor.')}"

    def adapt_voice_tone(self, text: str) -> str:
        """Optional: wrap text with SSML or tone markers if the TTS engine supports it."""
        return text

    def stop(self):
        self._running = False
