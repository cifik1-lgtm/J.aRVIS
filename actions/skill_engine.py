import os
import subprocess
import re
from pathlib import Path

def learn_new_skill(skill_name: str, objective: str, jarvis=None):
    """
    Autonomous Learning Protocol: JARVIS writes and installs his own tools.
    """
    if not jarvis:
        return "System error: Jarvis core not connected to skill engine."

    # 1. Generate the Code
    prompt = f"""
    You are the JARVIS Skill Engine. Your task is to write a standalone Python function for a new tool.
    
    SKILL NAME: {skill_name}
    OBJECTIVE: {objective}
    
    RULES:
    1. The file must be a valid Python script.
    2. Include all necessary imports (use standard libraries or common ones like requests).
    3. The main entry point must be a function named `{skill_name}`.
    4. The function must return a string (the result to show the user).
    5. Ensure the code is robust and handles errors.
    
    Return ONLY the Python code block.
    """
    
    from core.llm_provider import call_local_llm
    jarvis.ui.write_log(f"🧠 Skill Engine: Researching '{skill_name}'...")
    
    code = call_local_llm(prompt, model="qwen2.5-coder:7b")
    if "```python" in code:
        code = re.search(r"```python\n(.*?)\n```", code, re.DOTALL).group(1)
    elif "```" in code:
        code = re.search(r"```\n(.*?)\n```", code, re.DOTALL).group(1)

    # 2. Save to Temporary File for Testing
    temp_path = Path("actions") / f"temp_{skill_name}.py"
    temp_path.write_text(code, encoding="utf-8")
    
    # 3. Test the Code
    jarvis.ui.write_log(f"🧪 Skill Engine: Testing code for '{skill_name}'...")
    try:
        # Check syntax
        subprocess.check_call(["python", "-m", "py_compile", str(temp_path)])
        
        # 4. Final Installation
        final_path = Path("actions") / f"{skill_name}.py"
        temp_path.rename(final_path)
        
        jarvis.ui.write_log(f"✅ Skill Engine: New skill '{skill_name}' learned and installed.")
        jarvis.speak(f"Sir, I have successfully learned a new skill: {skill_name}. I can now {objective}.")
        
        return f"Successfully learned and installed '{skill_name}' tool."
        
    except Exception as e:
        if temp_path.exists(): temp_path.unlink()
        jarvis.ui.write_log(f"❌ Skill Engine: Learning failed for '{skill_name}': {e}")
        return f"Skill learning failed: {e}"

def skill_engine(parameters: dict = None, player=None, jarvis=None):
    """Tool entry point."""
    params = parameters or {}
    name = params.get("skill_name", "new_tool").lower().replace(" ", "_")
    goal = params.get("objective", "")
    
    if not goal: return "Please specify the objective of the new skill, sir."
    
    return learn_new_skill(name, goal, jarvis=jarvis)
