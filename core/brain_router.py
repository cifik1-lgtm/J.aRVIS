import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Any, Tuple
from core.intent_classifier import IntentClassifier

class BrainRouter:
    def __init__(self, config_path: Path, ui=None):
        self.config_path = config_path
        self.ui = ui
        self.classifier = IntentClassifier()
        
        # Load config to get model preferences
        config = self._load_config()
        
        self.engines = {
            'gemini': False,      # Primary Real-time Brain
            'groq': False,        # High-Speed Inference (LPU)
            'openrouter': False,  # DeepSeek / Complex Reasoning
            'minimax': False,     # Creative / High Context
            'ollama': False,      # Local Privacy Brain
            'poe': False,          # Poe API (bots like Claude-Opus-4.6)
            'codewords': False,    # CodeWords Automation Agent
        }
        self.model_names = {
            'gemini': "gemini-2.5-flash",
            'groq': "llama-3.3-70b-versatile",
            'openrouter': config.get("openrouter_model", "deepseek/deepseek-chat"),
            'minimax': "abab6.5s-chat",
            'ollama': config.get("local_model", "hermes3:8b"),
            'poe': (config.get("poe_models") or {}).get("reasoning", config.get("poe_planner_bot", "Claude-Opus-4.6")),
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

        # Check Poe
        if config.get("poe_api_key"):
            self.engines['poe'] = True
            
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
            
        # Check CodeWords
        if config.get("codewords_api_key"):
            self.engines['codewords'] = True
            
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

    def route_task(self, user_input: str, context: str = "") -> Tuple[str, Dict]:
        """
        Automatically route task to best agent
        Returns: (agent_name, response)
        """
        config = self._load_config()
        forced = config.get("force_brain", "auto").lower()
        
        # If forced to a specific brain, try that first
        if forced != "auto":
            if self.ui:
                self.ui.write_log(f"🧠 Router \u2192 FORCED to {forced.upper()} (Manual override)")
            try:
                return self._call_agent(forced, user_input, context)
            except Exception as e:
                if self.ui:
                    self.ui.write_log(f"\u26a0\ufe0f Forced engine {forced} failed: {e}. Falling back to autonomous router.")

        # Classify the intent
        decision = self.classifier.classify(user_input)
        
        agent = decision.agent
        confidence = decision.confidence
        reason = decision.reason
        
        if self.ui:
            self.ui.write_log(f"🧠 Router \u2192 {agent.upper()} ({confidence:.0%} confidence) - {reason}")
        
        # Route to selected agent
        try:
            return self._call_agent(agent, user_input, context)
        except Exception as e:
            if self.ui:
                self.ui.write_log(f"\u26a0\ufe0f {agent} failed: {e}. Trying fallbacks...")
            
            for fallback in decision.fallback_agents:
                try:
                    if self.ui:
                        self.ui.write_log(f"\ud83d\udd04 Trying fallback: {fallback}")
                    return self._call_agent(fallback, user_input, context)
                except:
                    continue
            
            return ("error", {"response": "I'm having trouble processing that request, sir. All agents failed."})

    def _call_agent(self, agent_name: str, prompt: str, context: str) -> Tuple[str, Dict]:
        if agent_name == "qwen_coder":
            return self._route_to_qwen(prompt, context)
        elif agent_name == "codewords":
            return self._route_to_codewords(prompt, context)
        elif agent_name == "groq":
            return self._route_to_groq(prompt, context)
        elif agent_name == "poe_claude":
            return self._route_to_poe(prompt, context)
        elif agent_name == "openrouter":
            return self._route_to_openrouter(prompt, context)
        elif agent_name == "gemini_voice":
            return self._route_to_gemini(prompt, context)
        else:
            return self._route_to_groq(prompt, context)

    def _route_to_qwen(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.local_llm import call_ollama
        response = call_ollama(prompt, system_prompt="You are JARVIS, a helpful AI assistant.")
        if response:
            return ("qwen_coder", {"response": response})
        raise Exception("Ollama/Qwen response failed")

    def _route_to_groq(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        response = call_llm(prompt, model="llama-3.3-70b-versatile")
        return ("groq", {"response": response})

    def _route_to_openrouter(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        config = self._load_config()
        model = config.get("openrouter_model", "deepseek/deepseek-chat")
        response = call_llm(prompt, model=model)
        return ("openrouter", {"response": response})

    def _route_to_poe(self, prompt: str, context: str) -> Tuple[str, Dict]:
        # Poe API implementation placeholder or actual call if library exists
        return ("poe_claude", {"response": "[Poe Claude] Reasoning through your request, sir..."})

    def _route_to_codewords(self, prompt: str, context: str) -> Tuple[str, Dict]:
        # CodeWords API implementation placeholder
        return ("codewords", {"response": "CodeWords automation started for your request, sir."})

    def _route_to_gemini(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        response = call_llm(prompt, model="gemini-2.5-flash")
        return ("gemini_voice", {"response": response})


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
            status = "\u2705 Online" if active else "\u274c Offline"
            report.append(f"{name.capitalize()}: {status}")
        return " | ".join(report)

