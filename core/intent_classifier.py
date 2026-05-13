"""
Intent Classifier - Routes tasks to the best AI brain
"""

import re
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
        "qwen_coder": {
            "priority": 1,
            "cost": 0,
            "speed": "medium",
            "best_for": ["code", "file", "local", "script", "python", "html", "css", "chat", "reasoning"],
            "description": "Local Brain (Hermes 3) - Free, private, and unlimited"
        },
        "codewords": {
            "priority": 2,
            "cost": 0.01,  # $0.01 per run approx
            "speed": "medium",
            "best_for": ["workflow", "automation", "schedule", "webhook", "agent", "complex"],
            "description": "Cloud automation platform ($2/day free)"
        },
        "groq": {
            "priority": 3,
            "cost": 0,
            "speed": "fast",
            "best_for": ["quick", "simple", "fact", "what is", "who is", "time", "weather"],
            "description": "Ultra-fast responses (free tier)"
        },
        "poe_claude": {
            "priority": 4,
            "cost": 0.02,  # Points based
            "speed": "slow",
            "best_for": ["deep", "reasoning", "analyze", "debug", "complex", "plan"],
            "description": "Claude Opus (best reasoning, 300 pts/day)"
        },
        "openrouter": {
            "priority": 5,
            "cost": 0,
            "speed": "medium",
            "best_for": ["search", "web", "find", "research", "news"],
            "description": "Web search and APIs (free tier)"
        },
        "gemini_voice": {
            "description": "Voice input/output only"
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
        for agent_key in ["gemini", "groq", "openrouter", "minimax", "ollama", "poe", "codewords"]:
            if f"use {agent_key}" in text_lower or f"set engine {agent_key}" in text_lower:
                return IntentDecision(
                    agent=agent_key if agent_key != "gemini" else "gemini_voice",
                    confidence=1.0,
                    reason=f"Explicit engine request: {agent_key}",
                    fallback_agents=["groq"]
                )
        
        # 1. CODE & FILE TASKS → Qwen (local, free, unlimited)
        code_keywords = [
            "code", "write", "create", "generate", "python", "script", "program",
            "html", "css", "javascript", "file", "folder", "directory", "save",
            "website", "page", "app", "application", "function", "class"
        ]
        if any(kw in text_lower for kw in code_keywords):
            return IntentDecision(
                agent="qwen_coder",
                confidence=0.95,
                reason="Code/file generation task detected",
                fallback_agents=["codewords", "poe_claude"]
            )
        
        # 2. QUICK FACTS → Groq (fastest)
        quick_keywords = [
            "what is", "who is", "when is", "where is", "time", "date",
            "weather", "temperature", "quick", "simple", "tell me"
        ]
        if any(kw in text_lower for kw in quick_keywords) and len(text) < 100:
            return IntentDecision(
                agent="groq",
                confidence=0.9,
                reason="Quick fact query (using fast Groq)",
                fallback_agents=["openrouter", "poe_claude"]
            )
        
        # 3. WEB SEARCH → OpenRouter
        search_keywords = [
            "search", "find", "google", "look up", "research", "news",
            "article", "latest", "trending", "info about", "information on"
        ]
        if any(kw in text_lower for kw in search_keywords):
            return IntentDecision(
                agent="openrouter",
                confidence=0.85,
                reason="Web search needed",
                fallback_agents=["groq", "poe_claude"]
            )
        
        # 4. DEEP REASONING → Poe Claude
        deep_keywords = [
            "analyze", "debug", "review", "explain in detail", "complex",
            "architecture", "design", "plan", "strategy", "compare", "contrast"
        ]
        if any(kw in text_lower for kw in deep_keywords) and len(text) > 50:
            return IntentDecision(
                agent="poe_claude",
                confidence=0.8,
                reason="Deep reasoning task (using Claude Opus)",
                fallback_agents=["codewords", "qwen_coder"]
            )
        
        # 5. AUTOMATION/WORKFLOW → CodeWords
        automation_keywords = [
            "automate", "workflow", "schedule", "every day", "daily",
            "webhook", "trigger", "when", "then", "if this then that"
        ]
        if any(kw in text_lower for kw in automation_keywords):
            return IntentDecision(
                agent="codewords",
                confidence=0.85,
                reason="Automation/workflow task",
                fallback_agents=["qwen_coder", "poe_claude"]
            )
        
        if len(text) < 50 and not any(kw in text_lower for kw in code_keywords + search_keywords):
            return IntentDecision(
                agent="gemini_voice",
                confidence=0.7,
                reason="Simple conversation (using Gemini voice)",
                fallback_agents=["groq"]
            )
        
        
        # 7. Default fallback
        return IntentDecision(
            agent="groq",
            confidence=0.6,
            reason="Uncertain, using fast Groq as default",
            fallback_agents=["qwen_coder", "openrouter"]
        )
    
    def get_agent_config(self, agent_name: str) -> Dict:
        """Get configuration for a specific agent"""
        return self.AGENTS.get(agent_name, self.AGENTS["groq"])


