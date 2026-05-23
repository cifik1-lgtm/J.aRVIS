import os
import time
import re
from pathlib import Path
from actions.code_agent import CodeAgent
from core.llm_provider import call_llm

def antigravity_mode(parameters: dict, player=None, jarvis=None) -> str:
    """
    Antigravity Mode: An autonomous coding loop that writes, tests, and self-heals code until it works.
    """
    task = parameters.get("task", parameters.get("objective", ""))
    if not task:
        return "❌ Antigravity Mode requires a 'task' parameter."

    if player: 
        player.write_log(f"🚀 [Antigravity Mode] Activated for task: {task[:60]}...")
    
    agent = CodeAgent()
    
    # We will write the code to a scratch file in the CifikAI directory for testing
    workspace = str(Path(__file__).resolve().parent.parent)
    target_file = os.path.join(workspace, "antigravity_output.py")
    
    # 1. Planning Phase
    plan_prompt = (
        f"You are Antigravity, a Senior AI Software Engineer inside JARVIS.\n"
        f"Your task is: {task}\n"
        f"Provide a step-by-step logic plan to solve this using Python. "
        f"Return ONLY the plan, no pleasantries."
    )
    plan = call_llm(plan_prompt, system_prompt="You are a senior python architect.")
    
    if player: 
        player.write_log(f"📝 Architecture plan created.")
    
    # 2. Execution Loop
    max_loops = 4
    error_output = ""
    
    for i in range(1, max_loops + 1):
        if player: 
            player.write_log(f"⚙️ Loop {i}/{max_loops} - Writing and compiling code...")
        
        # Ask LLM to write the code based on plan and previous errors
        prompt = (
            f"Task: {task}\n\n"
            f"Plan:\n{plan}\n\n"
            f"{'PREVIOUS ERROR TO FIX:' if error_output else ''}\n{error_output}\n\n"
            f"Write the complete, standalone Python code to solve this task.\n"
            f"If there is an error above, fix the bug.\n"
            f"Return ONLY the raw python code inside a ```python block. No markdown explanations."
        )
        
        response = call_llm(prompt, system_prompt="You are an expert coder. Return only code.")
        
        # Extract code safely
        match = re.search(r'```(?:python)?\n?(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        code = match.group(1).strip() if match else response.strip()
        
        # Prevent markdown artifacts
        code = code.replace("```python", "").replace("```", "").strip()
            
        if not code or len(code) < 10:
            error_output = "Model failed to return valid python code."
            continue
            
        # Write code to file
        agent.write_file(target_file, code)
        
        # Run and test the code
        if player: 
            player.write_log(f"🧪 Testing execution...")
            
        test_result = agent.run_tests(target_file, test_command=f"python {target_file}")
        
        if test_result["success"]:
            if player: 
                player.write_log(f"✅ Success! Code executes flawlessly.")
            return f"✅ Antigravity Mode completed task successfully.\nOutput: {test_result['output'][:500]}\nCode saved to: {target_file}"
        else:
            error_output = test_result["error"] or test_result["output"]
            if player: 
                player.write_log(f"⚠️ Bug detected. Self-healing... ({error_output[:60]})")
            time.sleep(2)
            
    return f"❌ Antigravity Mode failed after {max_loops} loops.\nFinal Error: {error_output[:500]}"