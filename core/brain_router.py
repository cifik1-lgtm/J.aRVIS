import json
import requests
from pathlib import Path
from typing import Dict, List, Any, Tuple
from core.intent_classifier import IntentClassifier

class BrainRouter:
    def __init__(self, config_path: Path, ui=None):
        self.config_path = config_path
        self.ui = ui
        self.classifier = IntentClassifier()
        self.preferred_brain = None
        
        # Load config
        config = self._load_config()
        
        self.engines = {
            'gemini': False,
            'groq': False,
            'openrouter': False,
            'minimax': False,
            'mistral': False,      # Local - reasoning
            'qwen_coder': False,   # Local - code
            'hermes': False,       # Local - agentic/personality
            'poe': False,
            'codewords': False,
            'ollama': False        # General Ollama status
        }

    def detect_engines(self) -> Dict[str, bool]:
        """Check availability of all configured engines."""
        config = self._load_config()
        
        # Cloud engines
        if config.get("gemini_api_key"): self.engines['gemini'] = True
        if config.get("groq_api_key"): self.engines['groq'] = True
        if config.get("openrouter_api_key"): self.engines['openrouter'] = True
        if config.get("minimax_api_key"): self.engines['minimax'] = True
        if config.get("poe_api_key"): self.engines['poe'] = True
        if config.get("codewords_api_key"): self.engines['codewords'] = True
        
        # Local Ollama models
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                self.engines['ollama'] = True
                model_list = [m['name'] for m in resp.json().get('models', [])]
                
                if any("mistral" in m.lower() for m in model_list):
                    self.engines['mistral'] = True
                    print("[BrainRouter] ✅ Mistral 7B detected")
                if any("qwen" in m.lower() and "coder" in m.lower() for m in model_list):
                    self.engines['qwen_coder'] = True
                    print("[BrainRouter] ✅ Qwen Coder detected")
                if any("hermes" in m.lower() for m in model_list):
                    self.engines['hermes'] = True
                    print("[BrainRouter] ✅ Hermes 3 8B detected")
        except Exception as e:
            print(f"[BrainRouter] ⚠️ Ollama detection failed: {e}")
            self.engines['ollama'] = False
        
        return self.engines

    def get_active_brain(self) -> str:
        """Returns the currently active brain based on config or availability."""
        if self.preferred_brain and self.engines.get(self.preferred_brain):
            return self.preferred_brain
            
        config = self._load_config()
        forced = config.get("force_brain", "gemini").lower()
        
        if forced in self.engines and self.engines[forced]:
            return forced
        
        # Fallback sequence
        for engine in ['gemini', 'groq', 'openrouter', 'hermes', 'mistral']:
            if self.engines.get(engine):
                return engine
        return 'offline'

    def route_task(self, user_input: str, context: str = "") -> Tuple[str, Dict]:
        """Route to best brain based on task type and availability"""
        config = self._load_config()
        forced = config.get("force_brain", "auto").lower()
        
        # If forced to a specific brain, try that first
        if forced != "auto":
            if self.engines.get(forced):
                return self._call_agent(forced, user_input, context)

        goal_lower = user_input.lower()

        # 1. SPECIALIZED CODE ROUTING
        code_keywords = ["python", "code", "script", "function", "class", "html", "css", "javascript", "website", "automate", "debug"]
        if any(kw in goal_lower for kw in code_keywords):
            if self.engines.get('qwen_coder'):
                return self._call_agent("qwen_coder", user_input, context)

        # 2. PERSONALITY / AGENT ROUTING
        hermes_keywords = ["act as", "pretend", "roleplay", "character", "be more", "persona", "british", "butler"]
        if any(kw in goal_lower for kw in hermes_keywords):
            if self.engines.get('hermes'):
                return self._call_agent("hermes", user_input, context)

        # 3. REASONING / MATH ROUTING
        reasoning_keywords = ["explain", "analyze", "why", "how", "calculate", "math", "solve", "compare"]
        if any(kw in goal_lower for kw in reasoning_keywords):
            if self.engines.get('mistral'):
                return self._call_agent("mistral", user_input, context)

        # 4. DEFAULT INTENT CLASSIFICATION
        decision = self.classifier.classify(user_input)
        agent = decision.agent
        
        # If classifier picked a local brain we have, use it
        if agent in self.engines and self.engines[agent]:
            return self._call_agent(agent, user_input, context)

        # 5. FINAL FALLBACKS
        for fallback in [decision.agent] + decision.fallback_agents + ['gemini', 'groq', 'hermes']:
            if self.engines.get(fallback):
                return self._call_agent(fallback, user_input, context)

        return ("error", {"response": "All agents failed, sir."})

    def _call_agent(self, agent_name: str, prompt: str, context: str) -> Tuple[str, Dict]:
        if self.ui:
            self.ui.write_log(f"🧠 Router \u2192 Using {agent_name.upper()}")
            
        if agent_name == "qwen_coder":
            return self._route_to_qwen(prompt, context)
        elif agent_name == "mistral":
            return self._route_to_mistral(prompt, context)
        elif agent_name == "hermes":
            return self._route_to_hermes(prompt, context)
        elif agent_name == "gemini":
            return self._route_to_gemini(prompt, context)
        elif agent_name == "groq":
            return self._route_to_groq(prompt, context)
        elif agent_name == "openrouter":
            return self._route_to_openrouter(prompt, context)
        else:
            # Default fallback to Groq or Gemini
            fallback = "gemini" if self.engines.get('gemini') else "groq"
            return self._call_agent(fallback, prompt, context)

    def _route_to_qwen(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.local_llm import call_ollama
        sys = "You are Qwen Coder, JARVIS's code specialist. Write clean code. Address user as 'sir'."
        resp = call_ollama(prompt, system_prompt=sys, model="qwen2.5-coder:7b")
        return ("qwen_coder", {"response": resp or "Failed to generate code, sir."})

    def _route_to_mistral(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.local_llm import call_ollama
        sys = "You are JARVIS using Mistral. You excel at reasoning and analysis. Address user as 'sir'."
        resp = call_ollama(prompt, system_prompt=sys, model="mistral:7b")
        return ("mistral", {"response": resp or "Failed to reason, sir."})

    def _route_to_hermes(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.local_llm import call_ollama
        sys = "You are JARVIS, Tony Stark's AI assistant. Poised, witty, British butler. Address user as 'sir'."
        resp = call_ollama(prompt, system_prompt=sys, model="hermes3:8b")
        return ("hermes", {"response": resp or "How may I assist you, sir?"})

    def _route_to_gemini(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        resp = call_llm(prompt, model="gemini-2.5-flash")
        return ("gemini", {"response": resp})

    def _route_to_groq(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        resp = call_llm(prompt, model="llama-3.3-70b-versatile")
        return ("groq", {"response": resp})

    def _route_to_openrouter(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        cfg = self._load_config()
        model = cfg.get("openrouter_model", "deepseek/deepseek-chat")
        resp = call_llm(prompt, model=model)
        return ("openrouter", {"response": resp})

    def _load_config(self) -> Dict[str, Any]:
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except: pass
        return {}

    def get_status_report(self) -> str:
        report = []
        for name, active in self.engines.items():
            if name == 'ollama': continue
            status = "✅" if active else "❌"
            report.append(f"{name.title()}: {status}")
        return " | ".join(report)
