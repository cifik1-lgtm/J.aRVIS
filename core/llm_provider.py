import json
import sys
from pathlib import Path

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def get_config():
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def call_local_llm(prompt: str, system_prompt: str = "", model: str = None) -> str:
    """Call a local Ollama model."""
    import requests
    config = get_config()
    l_model = config.get("local_model", "hermes3:8b")
    if model:
        l_model = model
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": l_model, "prompt": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt, "stream": False},
        timeout=180
    )
    data = resp.json()
    if "response" not in data:
        raise ValueError(f"Local LLM error: {data}")
    return data["response"]

def call_llm(prompt: str, system_prompt: str = "", model="gemini-2.5-flash", brain: str = None) -> str:
    """Central router for all LLM calls in the JARVIS system with automatic fallback."""
    config = get_config()
    forced = config.get("force_brain", "hive")
    
    # Order of attempt: Pollinations first (primary), Gemini as last-resort fallback
    if brain:
        attempts = [brain]
        # Add fallbacks if specific brain was requested but fails
        for b in ["pollinations", "gemini", "local"]:
            if b not in attempts:
                attempts.append(b)
    else:
        # Default chain: pollinations -> gemini -> local
        attempts = ["pollinations", "gemini", "local"]
        if forced not in ("hive", "pollinations", "gemini", "local"):
            attempts.insert(0, forced)

    last_error = None
    for brain_type in attempts:
        try:
            if brain_type == "gemini":
                from google import genai
                g_model = config.get("gemini_model", "gemini-2.0-flash-exp")
                actual_model = model if model.startswith("gemini") else g_model
                
                client = genai.Client(api_key=config.get("gemini_api_key", ""))
                response = client.models.generate_content(
                    model=actual_model,
                    contents=f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                )
                return response.text

            elif brain_type == "pollinations":
                import requests
                api_key = config.get("pollinations_api_key", "")
                
                p_models = config.get("pollinations_models", {})
                # Always use Pollinations-native models — NEVER pass Gemini model names
                # Use deepseek for code/complex tasks, gpt-5.4-mini for everything else
                if model and not model.startswith("gemini"):
                    actual_model = model  # Only use if it's already a Pollinations model
                else:
                    actual_model = p_models.get("code", "deepseek")
                
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                
                resp = requests.post(
                    url="https://gen.pollinations.ai/v1/chat/completions",
                    headers=headers,
                    data=json.dumps({
                        "model": actual_model,
                        "messages": [
                            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False
                    }),
                    timeout=550
                )
                data = resp.json()
                if "choices" not in data:
                    raise ValueError(f"Pollinations Chat Error: {data}")
                return data["choices"][0]["message"]["content"]

            elif brain_type == "local":
                return call_local_llm(prompt, system_prompt, model)

        except Exception as e:
            print(f"[LLM] Brain '{brain_type}' failed: {e}. Trying next fallback...")
            last_error = e
            continue

    raise last_error or ValueError("All AI engines failed to respond.")