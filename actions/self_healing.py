import json
import os
from pathlib import Path
import traceback
import re
from core.llm_provider import call_llm

def self_healing(parameters: dict, player=None) -> str:
    target_file = parameters.get("target_file", "")
    error_message = parameters.get("error_message", "")
    
    if not target_file or not error_message:
        return "Missing target_file or error_message."
        
    base = Path(__file__).resolve().parent.parent
    file_path = base / target_file
    
    if not file_path.exists():
        file_path = base / "actions" / target_file
        if not file_path.exists():
            return f"File does not exist: {target_file}"
        
    try:
        current_code = file_path.read_text(encoding="utf-8")
        
        prompt = f"""You are an advanced AI self-healing agent.
A python file inside your own system crashed with an error.

File: {target_file}
Error: {error_message}

Current Code:
{current_code}

Task: Fix the bug. Return ONLY the full corrected python code. No markdown, no explanations.
"""
        if player: player.write_log(f"🛠️ Self-healing initiating for {target_file}...")
            
        fixed_code = call_llm(prompt)
        fixed_code = fixed_code.strip()
        
        # Clean up markdown fences if model included them
        if "```" in fixed_code:
            fixed_code = re.sub(r"```[a-zA-Z]*\n?", "", fixed_code).replace("```", "").strip()
            
        file_path.write_text(fixed_code, encoding="utf-8")
        if player: player.write_log(f"✅ Self-healing complete. Rewrote {target_file}.")
        return f"Successfully healed {target_file}."
        
    except Exception as e:
        return f"Self-healing failed: {str(e)}"
