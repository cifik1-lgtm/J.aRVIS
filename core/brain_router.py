import json
import requests
from pathlib import Path
from typing import Dict, List, Any, Tuple
from core.intent_classifier import IntentClassifier

class BrainRouter:
    def __init__(self, config_path: Path, ui=None, orch=None):
        self.config_path = config_path
        self.ui = ui
        self.orch = orch
        self.classifier = IntentClassifier()
        self.preferred_brain = None
        self._forced_brain = None
        
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
                    print("[BrainRouter] [OK] Mistral 7B detected")
                if any("qwen" in m.lower() and "coder" in m.lower() for m in model_list):
                    self.engines['qwen_coder'] = True
                    print("[BrainRouter] [OK] Qwen Coder detected")
                if any("hermes" in m.lower() for m in model_list):
                    self.engines['hermes'] = True
                    print("[BrainRouter] [OK] Hermes 3 8B detected")
        except Exception as e:
            print(f"[BrainRouter] [WARN] Ollama detection failed: {e}")
            self.engines['ollama'] = False
        
        return self.engines

    def set_forced_brain(self, brain_name: str):
        """Sets a forced brain for all future routing decisions."""
        self._forced_brain = brain_name
        print(f"[Router] Brain forced to: {brain_name}")

    def clear_forced_brain(self):
        """Clears the forced brain setting, returning to automatic routing."""
        self._forced_brain = None
        print("[Router] Forced brain cleared, returning to auto-routing.")

    def get_active_brain(self) -> str:
        """Returns the currently active brain based on config or availability."""
        # 1. Check for user-forced brain from voice command
        if self._forced_brain:
            print(f"[Router] [LOCK] Using forced brain: {self._forced_brain}")
            return self._forced_brain

        if self.preferred_brain and self.engines.get(self.preferred_brain):
            return self.preferred_brain
            
        config = self._load_config()
        forced = config.get("force_brain", "gemini").lower()
        
        if forced in self.engines and self.engines[forced]:
            return forced
        
        # Fallback sequence
        for engine in ['openrouter', 'gemini', 'groq', 'hermes', 'mistral']:
            if self.engines.get(engine):
                return engine
        return 'offline'

    def _is_complex_reasoning(self, text: str) -> bool:
        """Determine if task needs advanced reasoning"""
        complex_keywords = [
            "architectural differences", "gemma 4", "26b", "31b",
            "parameter count", "moe", "transformer layers",
            "attention heads", "scaling laws", "model architecture",
            "compare", "contrast", "analyze", "explain in detail",
            "explain", "why", "how", "calculate", "math", "solve"
        ]
        text_lower = text.lower()
        if any(kw in text_lower for kw in complex_keywords):
            return True
        if len(text) > 150:
            return True
        return False

    def route_task(self, user_input: str, context: str = "") -> Tuple[str, Dict]:
        """Route to best brain based on task type and availability"""
        goal_lower = user_input.lower()
        
        # ===== BUG HUNTER OVERRIDE =====
        if "security scan" in goal_lower or "bug audit" in goal_lower or "hunt bounties" in goal_lower:
            print("[Router] 🦾 Security audit → Bug Hunter tool")
            return self._route_to_bug_hunter(user_input, context)

        # ===== STEP 0: Check for user-forced brain from voice command =====
        if self._forced_brain:
            print(f"[Router] [LOCK] Using forced brain: {self._forced_brain}")
            return self._call_agent(self._forced_brain, user_input, context)
            
        # ===== STEP 1: Check for forced reasoning brain =====
        if self.orch and hasattr(self.orch, 'reasoning_brain') and self.orch.reasoning_brain != "auto":
            if self._is_complex_reasoning(user_input):
                target_brain = self.orch.reasoning_brain
                print(f"[Router] [BRAIN] Using forced reasoning brain: {target_brain}")
                if target_brain == "openrouter":
                    return self._route_to_openrouter(user_input, context)
                elif target_brain == "gemini":
                    return self._route_to_gemini(user_input, context)
                else:
                    return self._call_agent(target_brain, user_input, context)

        # ===== STEP 2: Auto-detect complex tasks =====
        if self._is_complex_reasoning(user_input):
            if self.engines.get('openrouter'):
                print("[Router] [BRAIN] Complex reasoning detected -> OpenRouter")
                return self._route_to_openrouter(user_input, context)
            elif self.engines.get('mistral'):
                print("[Router] [BRAIN] Complex reasoning detected -> Mistral")
                return self._route_to_mistral(user_input, context)
        
        goal_lower = user_input.lower()

        # ===== PHILOSOPHICAL / ETHICAL QUESTIONS → Direct to Gemma 4 =====
        reasoning_keywords = [
            "ethical implications", "utilitarian", "deontological",
            "philosophical", "analyse", "analyze", "compare frameworks",
            "moral", "ethics", "should ai", "what is the right"
        ]
        
        if any(kw in goal_lower for kw in reasoning_keywords):
            print("[Router] [BRAIN] Philosophical/ethical question -> Direct to Gemma 4")
            return self._route_to_gemma4_direct(user_input, context)
        
        # ===== SEARCH-SPECIFIC TASKS → web_search =====
        search_keywords = ["weather", "news", "stock price", "current", "latest"]
        if any(kw in goal_lower for kw in search_keywords):
            print("[Router] [WEB] Real-time data -> web_search")
            return self._route_to_web_search(user_input, context)

        # ===== STEP 3: Code tasks → Qwen =====
        code_keywords = ["python", "code", "script", "function", "class", "html", "css", "javascript", "website", "automate", "debug"]
        if any(kw in goal_lower for kw in code_keywords):
            if self.engines.get('qwen_coder'):
                print("[Router] [CODE] Code task -> Qwen Coder")
                return self._call_agent("qwen_coder", user_input, context)
            else:
                print("[Router] [CODE] Local code brain offline -> Using OpenRouter")
                return self._route_to_openrouter(user_input, context)

        # ===== STEP 4: Personality / Agent Tasks =====
        hermes_keywords = ["act as", "pretend", "roleplay", "character", "be more", "persona", "british", "butler"]
        if any(kw in goal_lower for kw in hermes_keywords):
            if self.engines.get('hermes'):
                return self._call_agent("hermes", user_input, context)

        # ===== STEP 5: Default Intent Classification =====
        decision = self.classifier.classify(user_input)
        agent = decision.agent
        if agent in self.engines and self.engines[agent]:
            return self._call_agent(agent, user_input, context)

        # ===== STEP 6: Simple Q&A → OpenRouter/Gemini (Fallback) =====
        print("[Router] [CHAT] Simple query -> OpenRouter/Gemini")
        for fallback in [decision.agent] + decision.fallback_agents + ['openrouter', 'gemini', 'groq', 'hermes']:
            if self.engines.get(fallback):
                return self._call_agent(fallback, user_input, context)

        return ("error", {"response": "All agents failed, sir."})

    def _call_agent(self, agent_name: str, prompt: str, context: str) -> Tuple[str, Dict]:
        if self.ui:
            self.ui.write_log(f"[BRAIN] Router -> Using {agent_name.upper()}")
            
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
        try:
            resp = call_llm(prompt, model="gemini-2.5-flash")
            if "RESOURCE_EXHAUSTED" in str(resp) or "429" in str(resp):
                print("[Router] ⚠️ Gemini Exhausted. Falling back to OpenRouter...")
                return self._route_to_openrouter(prompt, context)
            return ("gemini", {"response": resp})
        except Exception as e:
            print(f"[Router] ❌ Gemini Error: {e}. Falling back...")
            return self._route_to_openrouter(prompt, context)

    def _route_to_groq(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        resp = call_llm(prompt, model="llama-3.3-70b-versatile")
        return ("groq", {"response": resp})

    def get_optimal_openrouter_model(self, user_input: str) -> str:
        """Intelligently select the best model for the task"""
        goal_lower = user_input.lower()
        config = self._load_config()
        models = config.get("openrouter_models", {})
        
        # 1. Agentic/Multi-Step Tasks -> Nemotron (1M context, best for automation)
        agentic_keywords = ["automate", "organize", "schedule", "monitor", "multi-step", "workflow"]
        if any(kw in goal_lower for kw in agentic_keywords) or len(user_input) > 10000:
            print("[Router] [AGENT] Agentic task -> Nemotron 3 Super")
            return models.get("agentic", "nvidia/nemotron-3-super-120b-a12b:free")
        
        # 2. Multimodal/Image Tasks -> Llama 4 Maverick
        multimodal_keywords = ["image", "picture", "screenshot", "see", "visual", "screen", "photo", "camera"]
        if any(kw in goal_lower for kw in multimodal_keywords):
            print("[Router] [IMAGE] Multimodal task -> Llama 4 Maverick")
            return models.get("multimodal", "meta-llama/llama-4-maverick:free")
        
        # 3. Deep Reasoning -> Hy3 Preview (best benchmarks)
        reasoning_keywords = ["explain", "why", "philosophical", "analyze", "compare", "contrast", "evaluate"]
        if any(kw in goal_lower for kw in reasoning_keywords) and len(user_input) > 200:
            print("[Router] [BRAIN] Deep reasoning -> Hy3 Preview")
            return models.get("reasoning", "tencent/hy3-preview:free")
        
        # 4. Code Generation -> GPT-OSS 120B
        code_keywords = ["code", "python", "script", "function", "class", "write", "program", "develop"]
        if any(kw in goal_lower for kw in code_keywords):
            print("[Router] [CODE] Code task -> GPT-OSS 120B")
            return models.get("coding", "openai/gpt-oss-120b:free")
        
        # 5. Default/Fallback -> Gemma 4 26B (fast & efficient)
        print("[Router] [FAST] Fast task -> Gemma 4 26B")
        return models.get("fallback", "google/gemma-4-26b-a4b-it:free")

    def _route_to_openrouter(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        model = self.get_optimal_openrouter_model(prompt)
        resp = call_llm(prompt, model=model)
        return ("openrouter", {"response": resp})

    def _route_to_gemma4_direct(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        resp = call_llm(prompt, model="google/gemma-4-26b-a4b-it:free")
        return ("openrouter", {"response": resp})

    def _route_to_web_search(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from actions.web_search import web_search
        try:
            result = web_search({"query": prompt})
        except Exception as e:
            result = f"Search failed: {e}"
        return ("web_search", {"response": result})

    def _route_to_bug_hunter(self, goal: str, context: str = "") -> Tuple[str, Dict]:
        """Route security audits directly to Bug Hunter tool"""
        import re
        import asyncio
        from google.genai import types
        
        # Extract repo URL from goal or context
        repo_match = re.search(r'https?://github\.com/[^\s]+', goal + " " + context)
        if not repo_match:
            repo_match = re.search(r'([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)', goal + " " + context)
            if not repo_match:
                return ("bug_hunter", {"response": "Please provide a GitHub repository URL, sir."})
            repo_url = f"https://github.com/{repo_match.group(0)}"
        else:
            repo_url = repo_match.group(0)
            
        print(f"[Router] Hunting bugs on: {repo_url}")
        
        fc = types.FunctionCall(
            name="hunt_bugs",
            args={"repo_url": repo_url, "action": "full_audit"},
            id="bug_hunt_" + str(hash(repo_url))
        )
        
        try:
            if self.orch and hasattr(self.orch, "tools"):
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(self.orch.tools.dispatch(fc), loop)
                    res = future.result() 
                else:
                    res = loop.run_until_complete(self.orch.tools.dispatch(fc))
                
                result_text = res.response.get("result", "Audit completed.") if hasattr(res, 'response') else str(res)
            else:
                result_text = "Tools dispatcher not available."
        except Exception as e:
            result_text = f"Audit failed: {e}"

        return ("bug_hunter", {"response": result_text})

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
            status = "[OK]" if active else "[FAIL]"
            report.append(f"{name.title()}: {status}")
        return " | ".join(report)
