"""
Intent Classifier - Routes tasks to the best AI brain
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass(frozen=True)
class IntentDecision:
    agent: str
    confidence: float
    reason: str
    fallback_agents: List[str]

    def as_dict(self) -> Dict:
        return {
            "agent": self.agent,
            "confidence": self.confidence,
            "reason": self.reason,
            "fallback_agents": list(self.fallback_agents)
        }

class IntentClassifier:
    """Automatically selects the best agent for any task"""
    
    # Agent definitions with capabilities and costs
    AGENTS = {
        "pollinations_qwen": {
            "priority": 1,
            "cost": 0.0,
            "speed": "medium",
            "best_for": ["code", "write", "create", "generate", "python", "script", "program", "html", "css", "javascript", "file", "folder", "directory", "save", "website", "page", "app", "application", "function", "class", "analyze", "debug", "review", "explain in detail", "complex", "architecture", "design", "plan", "strategy", "compare", "contrast"],
            "description": "Pollinations (Qwen-Large) - Deep reasoning and coding"
        },
        "gemini_voice": {
            "priority": 2,
            "cost": 0,
            "speed": "fast",
            "best_for": ["quick", "simple", "fact", "what is", "who is", "time", "weather", "search", "find", "google", "look up", "research", "news", "article", "latest", "trending", "info about", "information on"],
            "description": "Gemini Core (Live audio, chat, and quick searches)"
        }
    }
    
    def __init__(self):
        self.last_task_type = None
        
    def classify(self, text: str) -> IntentDecision:
        """
        Analyze user input and return best agent
        """
        text_lower = text.lower()
        
        # ===== AGENT SELECTION LOGIC =====
        
        # 0. EXPLICIT ENGINE REQUESTS
        for agent_key in ["gemini", "pollinations"]:
            if f"use {agent_key}" in text_lower or f"set engine {agent_key}" in text_lower:
                return IntentDecision(
                    agent="pollinations_kimi" if agent_key == "pollinations" else "gemini_voice",
                    confidence=1.0,
                    reason=f"Explicit engine request: {agent_key}",
                    fallback_agents=["pollinations_kimi" if agent_key == "gemini" else "gemini_voice"]
                )
        
        # 1. CODE & COMPLEX TASKS → Pollinations Qwen
        code_keywords = [
            "code", "write", "create", "generate", "python", "script", "program",
            "html", "css", "javascript", "file", "folder", "directory", "save",
            "website", "page", "app", "application", "function", "class",
            "analyze", "debug", "review", "explain in detail", "complex",
            "architecture", "design", "plan", "strategy", "compare", "contrast"
        ]
        if any(kw in text_lower for kw in code_keywords):
            return IntentDecision(
                agent="pollinations_qwen",
                confidence=0.95,
                reason="Code/complex reasoning task detected",
                fallback_agents=["gemini_voice"]
            )
        
        # 2. QUICK FACTS & WEB SEARCH → Gemini
        quick_keywords = [
            "what is", "who is", "when is", "where is", "time", "date",
            "weather", "temperature", "quick", "simple", "tell me",
            "search", "find", "google", "look up", "research", "news",
            "article", "latest", "trending", "info about", "information on"
        ]
        if any(kw in text_lower for kw in quick_keywords):
            return IntentDecision(
                agent="gemini_voice",
                confidence=0.9,
                reason="Quick fact or search query (using Gemini)",
                fallback_agents=["pollinations_kimi"]
            )
        
        # 3. Default fallback
        return IntentDecision(
            agent="gemini_voice",
            confidence=0.7,
            reason="Simple conversation (using Gemini voice)",
            fallback_agents=["pollinations_kimi"]
        )
    
    def get_agent_config(self, agent_name: str) -> Dict:
        """Get configuration for a specific agent"""
        return self.AGENTS.get(agent_name, self.AGENTS["gemini_voice"])
