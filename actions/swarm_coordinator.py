import os
import requests
import json
from pathlib import Path

def swarm_coordinator(parameters: dict, player=None) -> str:
    """
    Coordinates local sub-agents via Ollama to perform tasks in parallel.
    This saves API costs by using local models for worker agents.
    """
    task = parameters.get("task", "")
    agents = parameters.get("agents", ["coder", "researcher"])
    
    if not task:
        return "Error: No task provided for the swarm."

    # Use Ollama locally for worker agents
    ollama_url = "http://localhost:11434/api/generate"
    model = "gemma" # Assuming gemma or qwen based on Modelfile
    
    results = {}
    
    for agent_role in agents:
        if player:
            player.write_log(f"🐝 Swarm: Deploying {agent_role.upper()} agent...")
        
        prompt = f"You are a JARVIS sub-agent specializing as a {agent_role}. Your task: {task}\nProvide your output:"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            resp = requests.post(ollama_url, json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                results[agent_role] = data.get("response", "").strip()
            else:
                results[agent_role] = f"Error: Ollama returned {resp.status_code}"
        except Exception as e:
            results[agent_role] = f"Error connecting to local Ollama (is it running?): {str(e)}"
    
    # Combine results
    final_report = f"### Swarm Execution Report for Task: {task}\n\n"
    for role, out in results.items():
        final_report += f"#### {role.upper()} Agent:\n{out}\n\n"
        
    return final_report
