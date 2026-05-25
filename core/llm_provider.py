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
    if model and not (model.startswith("gemini") or model.startswith("gpt") or model.startswith("claude")):
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

def call_llm(prompt: str, system_prompt: str = "", model="gemini-2.5-flash", brain: str = None, category: str = None) -> str:
    """Central router for all LLM calls in the JARVIS system with automatic fallback."""
    config = get_config()
    forced = config.get("force_brain", "hive")
    
    # Order of attempt: Pollinations first (primary), Gemini as last-resort fallback
    if brain:
        attempts = [brain]
        # Add fallbacks if specific brain was requested but fails
        for b in ["pollinations", "gemini"]:
            if b not in attempts:
                attempts.append(b)
    else:
        # Default chain: pollinations -> gemini
        attempts = ["pollinations", "gemini"]
        if forced in attempts:
            attempts.remove(forced)
            attempts.insert(0, forced)
        elif forced != "hive":
            attempts.insert(0, forced)

    last_error = None
    for brain_type in attempts:
        try:
            if brain_type == "gemini":
                from google import genai
                g_model = config.get("gemini_model", "gemini-2.5-flash")
                actual_model = model if model and model.startswith("gemini") else g_model
                
                # Fetch array of keys or fallback to single key
                keys = config.get("gemini_api_keys", [])
                single_key = config.get("gemini_api_key", "")
                if single_key and single_key not in keys:
                    keys.append(single_key)
                
                if not keys:
                    raise ValueError("No Gemini API keys found in config.")

                g_last_err = None
                for api_key in keys:
                    if not api_key: continue
                    try:
                        client = genai.Client(api_key=api_key)
                        response = client.models.generate_content(
                            model=actual_model,
                            contents=f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                        )
                        return response.text
                    except Exception as e:
                        msg = str(e).lower()
                        if "429" in msg or "quota" in msg:
                            print(f"[Gemini] Key ending in '...{api_key[-4:]}' hit rate limit. Rotating to next key...")
                            g_last_err = e
                            continue
                        raise e
                raise g_last_err or ValueError("All Gemini keys failed.")

            elif brain_type == "pollinations":
                import requests
                api_key = config.get("pollinations_api_key", "")
                
                p_models = config.get("pollinations_models", {
                    "default": "gpt-5.4-mini",
                    "code": "deepseek",
                    "vision": "qwen-vision-pro",
                    "search": "perplexity-reasoning"
                })
                
                # Intelligent Model Routing for Pollinations
                sys_lower = system_prompt.lower()
                if category == "code" or "planner" in sys_lower or "code" in sys_lower:
                    actual_model = p_models.get("code", "deepseek")
                elif category == "search" or "search" in sys_lower:
                    actual_model = p_models.get("search", "perplexity-reasoning")
                elif category == "vision" or "image" in sys_lower:
                    actual_model = p_models.get("vision", "qwen-vision-pro")
                else:
                    actual_model = p_models.get("default", "gpt-5.4-mini")
                
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

        except Exception as e:
            print(f"[LLM] Brain '{brain_type}' failed: {e}. Trying next fallback...")
            last_error = e
            continue

    raise last_error or ValueError("All AI engines failed to respond.")