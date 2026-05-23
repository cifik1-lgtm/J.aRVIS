import json
import os
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
        self.engines = {
            'gemini': False,
            'pollinations': False
        }

    def detect_engines(self) -> Dict[str, bool]:
        """Check availability of all configured engines."""
        config = self._load_config()
        # Cloud engines
        if config.get("gemini_api_key"): self.engines['gemini'] = True
        if config.get("pollinations_api_key"): self.engines['pollinations'] = True
        

        
        # Apply granular brain config permissions if brain_config.json exists
        try:
            brain_cfg_path = self.config_path.parent / "brain_config.json"
            if brain_cfg_path.exists():
                with open(brain_cfg_path, "r", encoding="utf-8") as f:
                    b_cfg = json.load(f)
                
                mode = b_cfg.get("deployment_mode", "hybrid")
                brains_perm = b_cfg.get("brains", {})
                
                for bid, value in brains_perm.items():
                    enabled = value.get("enabled", True)
                    if not enabled:
                        if bid in self.engines:
                            self.engines[bid] = False
                            
                # If Local Only mode, force disable all cloud engines explicitly
                if mode == "local":
                    for cloud_bid in ['gemini', 'pollinations']:
                        if cloud_bid in self.engines:
                            self.engines[cloud_bid] = False

        except Exception as e:
            print(f"[BrainRouter] [WARN] Failed to apply brain_config masking: {e}")
            
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
        for engine in ['gemini', 'pollinations']:
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

    def _is_agent_available(self, agent: str) -> bool:
        if agent.startswith("pollinations_"):
            return self.engines.get("pollinations", False)
        if agent == "gemini_voice":
            return self.engines.get("gemini", False)
        return self.engines.get(agent, False)

    def route_task(self, user_input: str, context: str = "") -> Tuple[str, Dict]:
        """Route to best brain based on task type and availability"""
        goal_lower = user_input.lower()

        # ===== BUG HUNTER OVERRIDE =====
        if "security scan" in goal_lower or "bug audit" in goal_lower or "hunt bounties" in goal_lower:
            print("[Router] 🦾 Security audit -> Bug Hunter tool")
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

        
        goal_lower = user_input.lower()
        
        # ===== SEARCH-SPECIFIC TASKS -> web_search =====
        search_keywords = ["weather", "news", "stock price", "current", "latest"]
        if any(kw in goal_lower for kw in search_keywords):
            print("[Router] [WEB] Real-time data -> web_search")
            return self._route_to_web_search(user_input, context)

        # ===== STEP 4: Code tasks =====
        code_keywords = ["python", "code", "script", "function", "class", "html", "css", "javascript", "website", "automate", "debug"]
        if any(kw in goal_lower for kw in code_keywords):
            print("[Router] [CODE] Routing to DeepSeek")
            return self._route_to_pollinations(user_input, context, model="deepseek")
        # ===== STEP 6: Default Intent Classification =====
        decision = self.classifier.classify(user_input)
        agent = decision.agent
        
        if self._is_agent_available(agent):
            return self._call_agent(agent, user_input, context)

        # ===== STEP 7: Simple Q&A =====
        print("[Router] [CHAT] Simple query -> Fallback chain")
        for fallback in [decision.agent] + decision.fallback_agents + ['gemini', 'pollinations_kimi']:
            if self._is_agent_available(fallback):
                return self._call_agent(fallback, user_input, context)

        return ("error", {"response": "All agents failed, sir."})

    def _call_agent(self, agent_name: str, prompt: str, context: str) -> Tuple[str, Dict]:
        if self.ui:
            self.ui.write_log(f"[BRAIN] Router -> Using {agent_name.upper()}")
            
        if agent_name == "gemini" or agent_name == "gemini_voice":
            return self._route_to_gemini(prompt, context)
        elif agent_name == "pollinations_qwen" or agent_name == "deepseek":
            return self._route_to_pollinations(prompt, context, model="deepseek")
        elif agent_name == "pollinations" or agent_name == "pollinations_kimi":
            return self._route_to_pollinations(prompt, context, model="gpt-5.4-mini")
        else:
            # Default fallback
            return self._route_to_gemini(prompt, context)







    def _route_to_gemini(self, prompt: str, context: str) -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        try:
            resp = call_llm(prompt, model="gemini-2.5-flash")
            if "RESOURCE_EXHAUSTED" in str(resp) or "429" in str(resp):
                print("[Router] ⚠️ Gemini Exhausted. Falling back to Pollinations...")
                return self._route_to_pollinations(prompt, context, model="gpt-5.4-mini")
            return ("gemini", {"response": resp})
        except Exception as e:
            print(f"[Router] ❌ Gemini Error: {e}. Falling back...")
            return self._route_to_pollinations(prompt, context, model="gpt-5.4-mini")



    def _route_to_pollinations(self, prompt: str, context: str, model="gpt-5.4-mini") -> Tuple[str, Dict]:
        from core.llm_provider import call_llm
        print(f"[Router] 🚀 Routing chat/reasoning task to Pollinations.ai ({model})...")
        resp = call_llm(prompt, model=model, brain="pollinations")
        return ("pollinations", {"response": resp})

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