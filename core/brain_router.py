import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Any

class BrainRouter:
    def __init__(self, config_path: Path, ui=None):
        self.config_path = config_path
        self.ui = ui
        
        # Load config to get model preferences
        config = self._load_config()
        
        self.engines = {
            'gemini': False,      # Primary Real-time Brain
            'groq': False,        # High-Speed Inference (LPU)
            'openrouter': False,  # DeepSeek / Complex Reasoning
            'minimax': False,     # Creative / High Context
            'ollama': False       # Local Privacy Brain
        }
        self.model_names = {
            'gemini': "gemini-2.5-flash",
            'groq': "llama-3.3-70b-versatile",
            'openrouter': config.get("openrouter_model", "deepseek/deepseek-chat"),
            'minimax': "abab6.5s-chat",
            'ollama': config.get("local_model", "qwen2.5-coder:7b")
        }

    def detect_engines(self) -> Dict[str, bool]:
        """Check availability of all configured engines."""
        config = self._load_config()
        
        # Check Gemini
        if config.get("gemini_api_key"):
            self.engines['gemini'] = True
            
        # Check Groq
        if config.get("groq_api_key"):
            self.engines['groq'] = True
            
        # Check OpenRouter
        if config.get("openrouter_api_key"):
            self.engines['openrouter'] = True
            
        # Check MiniMax
        if config.get("minimax_api_key"):
            self.engines['minimax'] = True
            
        # Check Ollama
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                # Check if specific model is pulled
                models = [m['name'] for m in resp.json().get('models', [])]
                if any(self.model_names['ollama'] in m for m in models):
                    self.engines['ollama'] = True
        except:
            self.engines['ollama'] = False
            
        return self.engines

    def get_active_brain(self) -> str:
        """Returns the currently active brain based on config or availability."""
        config = self._load_config()
        forced = config.get("force_brain", "gemini").lower()
        
        if forced in self.engines and self.engines[forced]:
            return forced
        
        # Fallback sequence
        for engine in ['gemini', 'groq', 'openrouter', 'ollama', 'minimax']:
            if self.engines.get(engine):
                return engine
                
        return 'offline'

    def _load_config(self) -> Dict[str, Any]:
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {}

    def get_status_report(self) -> str:
        """Returns a string describing engine status."""
        report = []
        for name, active in self.engines.items():
            status = "✅ Online" if active else "❌ Offline"
            report.append(f"{name.capitalize()}: {status}")
        return " | ".join(report)
