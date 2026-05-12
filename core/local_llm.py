import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:7b" # Much stronger for coding and logic than phi3

def call_ollama(prompt, system_prompt="", model=None):
    """Calls local Ollama API with a fallback mechanism."""
    
    # Load model from config if not provided
    if model is None:
        try:
            from core.llm_provider import get_config
            config = get_config()
            model = config.get("local_model", "qwen2.5-coder:7b")
        except:
            model = "qwen2.5-coder:7b"

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

def warm_up_qwen():
    """Wakes up the local brain by sending a tiny test prompt."""
    if not is_ollama_online():
        return
    print("[Qwen] 🧠 Warming up local brain...")
    try:
        # Send a tiny prompt to force model loading into memory
        call_ollama("Respond with one word: ready", system_prompt="One word response only.")
        print("[Qwen] ✅ Local brain warmed up and ready.")
    except Exception as e:
        print(f"[Qwen] ⚠️ Warm-up failed: {e}")
