import requests
import json
import re
import threading
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "hermes3:8b"

def call_ollama(prompt: str, system_prompt: str = "", model: str = None) -> Optional[str]:
    """
    Calls local Ollama API with specified model.
    
    Models available in your setup:
    - hermes3:8b (agentic tasks, roleplay, function calling)
    - mistral:7b (general reasoning, math)
    - qwen2.5-coder:7b (code generation)
    """
    
    # Load model from config if not provided
    if model is None:
        try:
            from core.llm_provider import get_config
            config = get_config()
            model = config.get("local_model", DEFAULT_MODEL)
        except:
            model = DEFAULT_MODEL

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
        response = requests.post(OLLAMA_URL, json=payload, timeout=180) # Increased timeout for slow GPUs (RX 580)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        print(f"[Ollama] Error calling {model}: {e}")
        return None

def is_ollama_online() -> bool:
    """Checks if Ollama is running and responsive."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

def get_available_models() -> list:
    """Get list of available Ollama models via API"""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            return [m['name'] for m in resp.json().get('models', [])]
        return []
    except:
        return []

# Warm up functions to pre-load models
def warm_up_qwen():
    """Send a test prompt to wake up Qwen"""
    print("[Ollama] 🐍 Warming up Qwen Coder...")
    call_ollama("Respond with 'ready'", model="qwen2.5-coder:7b")

def warm_up_mistral():
    """Send a test prompt to wake up Mistral"""
    print("[Ollama] 🧠 Warming up Mistral 7B...")
    call_ollama("Respond with 'ready'", model="mistral:7b")

def warm_up_hermes():
    """Send a test prompt to wake up Hermes"""
    print("[Ollama] 🎭 Warming up Hermes 3 8B...")
    call_ollama("Respond with 'ready'", model="hermes3:8b")

def warm_up_mellum():
    """Send a test prompt to wake up Mellum (Kotlin Expert)"""
    print("[Ollama] 🧪 Warming up Mellum Kotlin...")
    call_ollama("Respond with 'ready'", model="jetbrains/mellum-4b-sft-kotlin:latest")

def warm_up_all_local_brains():
    """Pre-load all local models for faster first response"""
    if not is_ollama_online():
        return
        
    def warm_up_task():
        warm_up_hermes()
        warm_up_mistral()
        warm_up_qwen()
        warm_up_mellum()
        print("[Ollama] ✅ All local brains warmed up.")

    threading.Thread(target=warm_up_task, daemon=True).start()
