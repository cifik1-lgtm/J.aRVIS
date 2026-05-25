import json
import re
from core.llm_provider import call_llm

class TaskInterpreter:
    """Uses Gemini to parse user commands into a structured goal."""
    
    def interpret(self, command: str) -> dict:
        prompt = f"""
You are the Task Interpreter for JARVIS. Your job is to parse the user's command into a structured JSON goal.

USER COMMAND: "{command}"

Output MUST be a JSON object matching this schema:
{{
  "goal": "Clear, refined goal statement",
  "category": "code | search | simple_conversation | other",
  "priority": 1,
  "preferred_brain": "gemini | pollinations"
}}

Rules: Return ONLY the JSON object. No markdown, no explanations.
"""
        try:
            raw = call_llm(prompt, system_prompt="You are a precise task interpreter.")
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
            return json.loads(raw)
        except Exception as e:
            print(f"[TaskInterpreter] Error parsing command via LLM: {e}")
            # Fallback
            return {
                "goal": command,
                "category": "other",
                "priority": 3,
                "preferred_brain": "gemini"
            }
