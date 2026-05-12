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

def call_llm(prompt: str, system_prompt: str = "", model="gemini-2.5-flash") -> str:
    """Central router for all LLM calls in the JARVIS system with automatic fallback."""
    config = get_config()
    forced = config.get("force_brain", "gemini")
    
    # Order of attempt based on choice
    attempts = [forced]
    for b in ["gemini", "groq", "openrouter", "minimax"]:
        if b not in attempts:
            attempts.append(b)

    last_error = None
    for brain in attempts:
        try:
            if brain == "gemini":
                from google import genai
                client = genai.Client(api_key=config.get("gemini_api_key", ""))
                response = client.models.generate_content(
                    model=model,
                    contents=f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                )
                return response.text

            elif brain == "groq":
                from groq import Groq
                api_key = config.get("groq_api_key", "")
                if not api_key: continue
                client = Groq(api_key=api_key)
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2048
                )
                return response.choices[0].message.content

            elif brain == "openrouter":
                import requests
                api_key = config.get("openrouter_api_key", "")
                if not api_key: continue
                model_name = config.get("openrouter_model", "deepseek/deepseek-chat")
                resp = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    data=json.dumps({
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ]
                    }),
                    timeout=60
                )
                return resp.json()["choices"][0]["message"]["content"]

            elif brain == "minimax":
                import requests
                api_key = config.get("minimax_api_key", "")
                if not api_key: continue
                resp = requests.post(
                    url="https://api.minimax.chat/v1/text/chatcompletion_v2",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    data=json.dumps({
                        "model": "abab6.5s-chat",
                        "messages": [
                            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ]
                    }),
                    timeout=60
                )
                data = resp.json()
                if "choices" not in data:
                    raise ValueError(f"MiniMax Error: {data.get('base_resp', {}).get('status_msg', 'Unknown')}")
                return data["choices"][0]["message"]["content"]

            elif brain == "local":
                import requests
                resp = requests.post(
                    "http://localhost:11434/api/generate",
                    json={"model": "phi3:mini", "prompt": f"{system_prompt}\n\n{prompt}", "stream": False},
                    timeout=60
                )
                return resp.json()["response"]

        except Exception as e:
            print(f"[LLM] Brain '{brain}' failed: {e}. Trying next fallback...")
            last_error = e
            continue

    raise last_error or ValueError("All AI engines failed to respond.")

