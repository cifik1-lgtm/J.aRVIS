import requests
import json
import re
import threading
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
DEFAULT_MODEL = "hermes3:8b"

# Per-model timeouts (seconds). Bigger models on GPU need more time.
_MODEL_TIMEOUTS = {
    "qwen3.5-9b:latest":                     600,  # 10 min — 9B is slow on AMD GPU
    "gemma-4:latest":                         600,  # 10 min — reasoning model
    "hermes3:8b":                             300,  # 5 min
    "jetbrains/mellum-4b-sft-kotlin:latest": 300,  # 5 min
    "nemotron-3-super:cloud":                 300,  # 5 min — cloud model
    "gemma4:31b-cloud":                       300,  # 5 min — cloud model
    "glm-4.7:cloud":                          180,  # 3 min — super-fast general chat cloud model
}
_DEFAULT_TIMEOUT = 600  # fallback for unknown models


def _model_timeout(model: str) -> int:
    for key, val in _MODEL_TIMEOUTS.items():
        if key in (model or ""):
            return val
    return _DEFAULT_TIMEOUT


def call_ollama(prompt: str, system_prompt: str = "", model: str = None) -> Optional[str]:
    """
    Calls local Ollama API with specified model.
    
    Models available in your setup:
    - hermes3:8b (agentic tasks, roleplay, function calling)
    - gemma-4:latest (reasoning, analysis)
    - qwen3.5-9b:latest (code generation — needs up to 10min on GPU)
    - jetbrains/mellum-4b-sft-kotlin:latest (Kotlin specialist)
    """
    
    # Load model from config if not provided
    if model is None:
        try:
            from core.llm_provider import get_config
            config = get_config()
            model = config.get("local_model", DEFAULT_MODEL)
        except:
            model = DEFAULT_MODEL

    timeout = _model_timeout(model)

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
        print(f"[Ollama] ⏱️ Calling {model} (timeout={timeout}s)...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
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

def call_lmstudio(prompt: str, system_prompt: str = "", model: str = None) -> Optional[str]:
    """Calls local LMStudio API with specified model."""
    if model is None:
        try:
            from core.llm_provider import get_config
            config = get_config()
            # fallback to whatever is default
            model = config.get("lmstudio_models", {}).get("fallback", "local-model")
        except:
            model = "local-model"

    timeout = _model_timeout(model)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "stream": False
    }
    
    try:
        response = requests.post(LMSTUDIO_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[LMStudio] Error calling {model}: {e}")
        return None

def is_lmstudio_online() -> bool:
    """Checks if LMStudio is running and responsive."""
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=2)
        return response.status_code == 200
    except:
        return False

# Warm up functions to pre-load models
def warm_up_qwen():
    """Send a test prompt to wake up Qwen"""
    print("[Ollama] 🐍 Warming up Qwen 3.5 9B...")
    call_ollama("Respond with 'ready'", model="qwen3.5-9b:latest")

def warm_up_gemma():
    """Send a test prompt to wake up Gemma 4"""
    print("[Ollama] 🧠 Warming up Gemma 4...")
    call_ollama("Respond with 'ready'", model="gemma-4:latest")

def warm_up_hermes():
    """Send a test prompt to wake up Hermes"""
    print("[Ollama] 🎭 Warming up Hermes 3 8B...")
    call_ollama("Respond with 'ready'", model="hermes3:8b")

def warm_up_mellum():
    """Send a test prompt to wake up Mellum (Kotlin Expert)"""
    print("[Ollama] 🧪 Warming up Mellum Kotlin...")
    call_ollama("Respond with 'ready'", model="jetbrains/mellum-4b-sft-kotlin:latest")

def warm_up_nemotron_cloud():
    """Send a test prompt to wake up Nemotron Cloud"""
    print("[Ollama] ☁️ Warming up Nemotron 3 Super Cloud...")
    call_ollama("Respond with 'ready'", model="nemotron-3-super:cloud")

def warm_up_gemma_cloud():
    """Send a test prompt to wake up Gemma 4 31B Cloud"""
    print("[Ollama] ☁️ Warming up Gemma 4 31B Cloud...")
    call_ollama("Respond with 'ready'", model="gemma4:31b-cloud")

def warm_up_glm_cloud():
    """Send a test prompt to wake up GLM Cloud"""
    print("[Ollama] ☁️ Warming up GLM Cloud...")
    call_ollama("Respond with 'ready'", model="glm-4.7:cloud")

def warm_up_all_local_brains():
    """Pre-load all local and cloud-proxied models for faster first response"""
    if not is_ollama_online():
        return
        
    def warm_up_task():
        # Cloud-proxied models
        warm_up_gemma_cloud()
        warm_up_nemotron_cloud()
        warm_up_glm_cloud()
        # Local fallback models
        warm_up_hermes()
        warm_up_gemma()
        warm_up_qwen()
        warm_up_mellum()
        print("[Ollama] ✅ All local and cloud brains warmed up.")

    threading.Thread(target=warm_up_task, daemon=True).start()
