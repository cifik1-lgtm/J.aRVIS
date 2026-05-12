import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "phi3:mini" # Very small (3.8B), fits on any GPU, great for instructions

def call_ollama(prompt, system_prompt="", model=DEFAULT_MODEL):
    """Calls local Ollama API with a fallback mechanism."""
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
    except Exception:
        return None

def is_ollama_online():
    """Checks if Ollama is running and responsive."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False
