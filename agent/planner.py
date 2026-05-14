import json
import re
import sys
import os
from pathlib import Path
from typing import Optional
from core.intent_classifier import IntentClassifier


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
_classifier = IntentClassifier()


PLANNER_PROMPT = """You are the planning module of Cifik Intelegents, a personal AI assistant.
Your job: break any user goal into a sequence of steps using ONLY the tools listed below.

ABSOLUTE RULES:
- NEVER use open_app to open a website or browser. ALWAYS use browser_control or youtube_video for web-related goals.
- Use file_controller to save content to disk.
- Max 5 steps. Use the minimum steps needed.

AVAILABLE TOOLS AND THEIR PARAMETERS:

open_app
  app_name: string (required)

web_search
  query: string (required) — write a clear, focused search query
  mode: "search" or "compare" (optional, default: search)
  items: list of strings (optional, for compare mode)
  aspect: string (optional, for compare mode)

game_updater
  action: "update" | "install" | "list" | "download_status" | "schedule" (required)
  platform: "steam" | "epic" | "both" (optional, default: both)
  game_name: string (optional)
  app_id: string (optional)
  shutdown_when_done: boolean (optional)

browser_navigate
  url: string (required) — e.g. google.com
  browser: string (optional, default: brave)

browser_control
  action: "go_to" | "search" | "click" | "type" | "scroll" | "get_text" | "press" | "close" (required)
  url: string (for go_to)
  query: string (for search)
  text: string (for click/type)
  direction: "up" | "down" (for scroll)

file_controller
  action: "write" | "create_file" | "read" | "list" | "delete" | "move" | "copy" | "find" | "disk_usage" | "change_directory" | "cd" (required)
  path: string — use "desktop" for Desktop, "cwd" after change_directory, or e.g. "D:\\"
  name: string — filename
  content: string — file content (for write/create_file)

computer_settings
  action: string (optional if description is set)
  description: natural language — "control panel" -> open_control_panel; "settings" -> open_settings; "resource monitor" -> monitor_performance
  value: string (optional)

computer_control
  action (required): type | write | smart_type | click | double_click | triple_click | right_click | middle_click |
    move | move_rel | drag | hotkey | press | key_down | key_up | scroll | copy | paste | screenshot |
    screen_find | screen_click | screen_double_click | wait | clear_field | focus_window |
    open_folder | diagnose_system | random_data | user_data | mouse_position | get_position | cursor_position
  text: string (type/write/smart_type/paste)
  x, y: numbers (click/move; or dx/dy fallback for move_rel)
  dx, dy: numbers (move_rel)
  x1,y1,x2,y2: drag
  keys, key, title, description, folder, path, seconds, amount, direction, field, type, clear_first: as needed

screen_process
  text: string (required) — what to analyze or ask about the screen
  angle: "screen" | "camera" (optional)

send_message
  receiver: string (required)
  message_text: string (required)
  platform: string (required)

reminder
  date: string YYYY-MM-DD (required)
  time: string HH:MM (required)
  message: string (required)

desktop_control
  action: "wallpaper" | "organize" | "clean" | "list" | "task" (required)
  path: string (optional)
  task: string (optional)

youtube_video
  action: "play" | "summarize" | "trending" (required)
  query: string (for play)

weather_report
  city: string (required)

flight_finder
  origin: string (required)
  destination: string (required)
  date: string (required)

code_helper
  action: "write" | "edit" | "run" | "explain" (required)
  description: string (required)
  language: string (optional)
  output_path: string (optional)
  file_path: string (optional)

dev_agent
  description: string (required)
  language: string (optional)

detect_monitors
  action: "count" | "details" | "all" (required) — get number of screens or full resolutions

gesture_control
  action: "start" | "stop" | "toggle" (required) — enable/disable hand tracking
EXAMPLES:

Goal: "research mechanical engineering and save it to a notepad file"
Steps:

web_search | query: "mechanical engineering overview definition history"
web_search | query: "mechanical engineering applications and future trends"
file_controller | action: write, path: desktop, name: mechanical_engineering.txt, content: "MECHANICAL ENGINEERING RESEARCH\n\nThis file will be filled with web research results."

Goal: "What is the price of Bitcoin"
Steps:

web_search | query: "Bitcoin price today USD"

Goal: "List the files on the desktop and find the largest 5 files"
Steps:

file_controller | action: list, path: desktop
file_controller | action: largest, path: desktop, count: 5

Goal: "Install PUBG from Steam"
Steps:

game_updater | action: install, platform: steam, game_name: "PUBG"

Goal: "Update all my Steam games"
Steps:

game_updater | action: update, platform: steam

Goal: "Send John a message on WhatsApp saying there is a meeting tomorrow"
Steps:

send_message | receiver: John, message_text: "There is a meeting tomorrow", platform: WhatsApp

Goal: "Open the clock and set a reminder for 30 minutes later"
Steps:

reminder | date: [today], time: [now+30min], message: "Reminder"

OUTPUT — return ONLY valid JSON, no markdown, no explanation, no code blocks:
{
  "goal": "...",
  "steps": [
    {
      "step": 1,
      "tool": "tool_name",
      "description": "what this step does",
      "parameters": {},
      "critical": true
    }
  ]
}
"""

# SIMPLIFIED PROMPT FOR LOCAL GPU FALLBACK (Phi-3 friendly)
LOCAL_PLANNER_PROMPT = """You are the local fallback brain for JARVIS (Cifik Intelegents).
Convert the user's request into a JSON plan using ONLY these tools:

1. computer_settings: { "action": "string", "description": "natural language" }
2. file_controller: { "action": "write|create_file|read|list|delete|move|copy|change_directory|cd", "path": "desktop|documents|D:\\\\|cwd", "name": "string", "content": "string" }
3. computer_control: { "action": "type|click|hotkey|screenshot", "text": "str", "keys": "str" }
4. open_app: { "app_name": "string" } -- ALWAYS include 'app_name' (e.g., 'chrome', 'notepad', 'discord').
5. browser_navigate: { "url": "string", "browser": "string" } -- ALWAYS use this for navigating to websites.
6. system_control: { "action": "switch_brain", "brain": "gemini|local|openrouter" }
7. talk: { "text": "your response to the user" }

When navigating to a URL in a browser manually via computer_control:
1. Type the URL using computer_control(action='type', text='url')
2. ALWAYS press Enter using computer_control(action='press', key='enter')
Never skip the Enter key press - it's required for navigation. Prefer 'browser_navigate' for this.

OUTPUT ONLY VALID JSON:
{
  "steps": [
    { "step": 1, "tool": "tool_name", "description": "desc", "parameters": {} }
  ]
}
"""


def _get_api_key(provider="gemini") -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
        if provider == "openrouter":
            return config.get("openrouter_api_key", "")
        if provider == "minimax":
            return config.get("minimax_api_key", "")
        if provider == "groq":
            return config.get("groq_api_key", "")
        if provider == "poe":
            # Prefer env var to keep secrets out of files
            return os.environ.get("POE_API_KEY") or config.get("poe_api_key", "")
        return config.get("gemini_api_key", "")

def _is_rate_limit(e: Exception) -> bool:
    msg = str(e).lower()
    return any(x in msg for x in ["429", "quota", "resource_exhausted", "connection", "timeout", "offline", "network"])

def create_plan_gemini(goal: str, context: str = "") -> dict | None:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=_get_api_key("gemini"))
        
        user_input = f"Goal: {goal}"
        if context: user_input += f"\n\nContext: {context}"
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_input,
            config=types.GenerateContentConfig(
                system_instruction=PLANNER_PROMPT,
            )
        )
        text = response.text.strip()
        return _parse_and_validate_plan(text)
    except Exception as e:
        print(f"[Gemini] ❌ Error: {e}")
        return None


def create_plan_hive(goal: str, context: str = "") -> dict:
    """The 'Router' brain that decides which Expert Brain is best for the job."""
    g = goal.lower()
    
    # 1. BRAIN 3: LOCAL OLLAMA (Code, Files, Local Automation, Privacy)
    # If the task mentions code, files, or local resources, prefer the local brain.
    local_keywords = ["code", "script", "file", "folder", "directory", "local", "python", "debug", "path", "read", "write"]
    if any(w in g for w in local_keywords):
        from core.local_llm import call_ollama, is_ollama_online
        if is_ollama_online():
            # Load model from config
            try:
                with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                    local_model = json.load(f).get("local_model", "qwen2.5-coder:7b")
            except:
                local_model = "qwen2.5-coder:7b"
                
            print(f"[Planner] 🧠 ROUTER: Selecting LOCAL OLLAMA ({local_model}) for file/code task.")
            l_resp = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT, model=local_model)
            try:
                l_plan = _parse_and_validate_plan(l_resp)
                if l_plan: return l_plan
            except: pass

    # 2. BRAIN 2: OPENROUTER (Web Search, Browser Control, API Tasks)
    # If it's a general complex task or needs the web, use OpenRouter.
    print("[Planner] 🧠 ROUTER: Selecting OPENROUTER for complex/web task.")
    or_plan = create_plan_openrouter(goal, context)
    if or_plan:
        return or_plan
    
    # 3. BRAIN 1: GEMINI (Fallback or Simple Reasoning)
    print("[Planner] 🧠 ROUTER: Falling back to GEMINI.")
    return create_plan_gemini(goal, context) or create_plan_groq(goal, context) or _fallback_plan(goal)

def create_plan_poe(goal: str, context: str = "") -> Optional[dict]:
    """
    Use Poe's OpenAI-compatible Chat Completions API for planning.
    IMPORTANT: Poe expects Poe *bot names* for `model` (e.g. "Claude-Opus-4.6"), not Anthropic model IDs.
    """
    import requests

    api_key = _get_api_key("poe")
    if not api_key:
        return None

    # Allow config override for which Poe bot to use for planning
    poe_bot = "Claude-Opus-4.6"
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            poe_bot = (
                (cfg.get("poe_models") or {}).get("reasoning")
                or cfg.get("poe_planner_bot")
                or poe_bot
            )
    except Exception:
        pass

    user_input = f"Goal: {goal}"
    if context:
        user_input += f"\n\nContext: {context}"

    try:
        response = requests.post(
            "https://api.poe.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": poe_bot,
                "messages": [
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            }),
            timeout=30,
        )

        if response.status_code != 200:
            print(f"[Poe] ❌ Error: {response.status_code} - {response.text[:200]}")
            return None

        data = response.json()
        text = (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")
        if not isinstance(text, str):
            return None
        return _parse_and_validate_plan(text.strip())
    except Exception as e:
        print(f"[Poe] ❌ Exception: {e}")
        return None

def _poe_should_use(goal: str) -> bool:
    """
    Cost gate for Poe planning calls.
    - Enabled when config has poe_api_key (or POE_API_KEY)
    - Only used for "deep reasoning" keywords
    - Optional points gate: poe_points_remaining >= poe_min_points_to_use
      (points are user-maintained; Poe API doesn't expose a universal balance endpoint here)
    """
    g = (goal or "").lower()
    deep_keywords = [
        "analyse", "analyze", "debug", "complex", "plan", "planning",
        "architecture", "review", "refactor", "design", "audit",
    ]
    if not any(k in g for k in deep_keywords):
        return False

    try:
        cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
        points = int(cfg.get("poe_points_remaining", 0) or 0)
        min_points = int(cfg.get("poe_min_points_to_use", 0) or 0)
        # If min_points is 0, treat as "no points gating"
        if min_points and points < min_points:
            print(f"[Planner] 💰 Poe skipped: points {points} < min {min_points}")
            return False
    except Exception:
        # If config can't be read, fall back to keyword-only gating
        pass

    return True


def create_plan(goal: str, context: str = "", preferred_brain: Optional[str] = None) -> dict:
    """Create a plan using available brains - Local brains have highest priority."""
    goal_lower = goal.lower()
    
    # ===== PRIORITY 1: LOCAL QWEN (Code tasks) =====
    if any(word in goal_lower for word in ["python", "code", "script", "function", "javascript", "html", "css", "c#", "java"]):
        from core.local_llm import call_ollama, is_ollama_online
        if is_ollama_online():
            print("[Planner] 🐍 PRIORITY 1: Qwen Coder (local)")
            response = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT, model="qwen2.5-coder:7b")
            if response:
                plan = _parse_and_validate_plan(response)
                if plan: return plan
    
    # ===== PRIORITY 2: LOCAL MISTRAL (Reasoning) =====
    if any(word in goal_lower for word in ["explain", "why", "how", "calculate", "analyze", "reason"]):
        from core.local_llm import call_ollama, is_ollama_online
        if is_ollama_online():
            print("[Planner] 🧠 PRIORITY 2: Mistral 7B (local)")
            response = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT, model="mistral:7b")
            if response:
                plan = _parse_and_validate_plan(response)
                if plan: return plan
    
    # ===== PRIORITY 3: LOCAL HERMES (General Agentic) =====
    from core.local_llm import call_ollama, is_ollama_online
    if is_ollama_online():
        print("[Planner] 🎭 PRIORITY 3: Hermes 3 (local)")
        response = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT, model="hermes3:8b")
        if response:
            plan = _parse_and_validate_plan(response)
            if plan: return plan
            
    # 4. Check for manual brain override in config (Force Brain)
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            forced = json.load(f).get("force_brain", "hive")
            if forced != "hive" and forced != "gemini": # If manually set to a specific expert brain
                if forced == "openrouter":
                    print("[Planner] 🧠 Manual Override: Using OpenRouter...")
                    return create_plan_openrouter(goal, context)
                elif forced == "minimax":
                    print("[Planner] 🧠 Manual Override: Using MiniMax (Coding Brain)...")
                    return create_plan_minimax(goal, context)
                elif forced == "groq":
                    print("[Planner] 🧠 Manual Override: Using Groq (High-Speed)...")
                    return create_plan_groq(goal, context)
                elif forced == "local":
                    print("[Planner] 🧠 Manual Override: Using Local Ollama...")
                    from core.local_llm import call_ollama, is_ollama_online
                    if is_ollama_online():
                        local_resp = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT)
                        if local_resp: return _parse_and_validate_plan(local_resp)
    except: pass

    brain_target = preferred_brain

    # Optional: intent-based smart routing (does not bypass forced brain overrides above)
    try:
        cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
        use_intent_router = bool(cfg.get("use_intent_router", True))
    except Exception:
        use_intent_router = True

    intent_order = None
    if use_intent_router and not brain_target:
        decision = _classifier.classify(goal).as_dict()
        intent_order = [decision["agent"]] + decision.get("fallback_agents", [])
        print(f"[Planner] 🧭 IntentRouter -> {decision['agent']} ({int(decision['confidence']*100)}%) {decision['reason']}")

    # If intent router is enabled, try its ordered list first (with safe gating).
    if intent_order:
        for provider in intent_order:
            if provider == "groq" and _get_api_key("groq"):
                print("[Planner] ⚡ IntentRouter: Using Groq")
                g_plan = create_plan_groq(goal, context)
                if g_plan:
                    return g_plan

            if provider == "poe" and _get_api_key("poe") and (preferred_brain == "poe" or _poe_should_use(goal)):
                print("[Planner] 🧠 IntentRouter: Using Poe")
                p_plan = create_plan_poe(goal, context)
                if p_plan:
                    return p_plan

            if provider == "openrouter" and _get_api_key("openrouter"):
                print("[Planner] 🌐 IntentRouter: Using OpenRouter")
                or_plan = create_plan_openrouter(goal, context)
                if or_plan:
                    return or_plan

            if provider == "local_ollama":
                from core.local_llm import call_ollama, is_ollama_online
                if is_ollama_online():
                    try:
                        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                            local_model = json.load(f).get("local_model", "qwen2.5-coder:7b")
                    except Exception:
                        local_model = "qwen2.5-coder:7b"
                    print(f"[Planner] 🧠 IntentRouter: Using LOCAL OLLAMA ({local_model})")
                    l_resp = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT, model=local_model)
                    try:
                        l_plan = _parse_and_validate_plan(l_resp)
                        if l_plan:
                            return l_plan
                    except Exception:
                        pass

        # If intent router couldn't produce a plan, fall back to the legacy priority chain below.

    # Legacy priority chain (kept for reliability)
    if preferred_brain == "groq" and _get_api_key("groq"):
        print("[Planner] ⚡ PRIORITY 2: Using Groq (Ultra-Fast)")
        g_plan = create_plan_groq(goal, context)
        if g_plan:
            return g_plan

    if _get_api_key("groq"):
        print("[Planner] ⚡ PRIORITY 2: Using Groq (Ultra-Fast)")
        g_plan = create_plan_groq(goal, context)
        if g_plan:
            return g_plan

    if _get_api_key("poe") and (preferred_brain == "poe" or _poe_should_use(goal)):
        print("[Planner] 🧠 PRIORITY 3: Using Poe")
        p_plan = create_plan_poe(goal, context)
        if p_plan:
            return p_plan

    if preferred_brain == "openrouter" and _get_api_key("openrouter"):
        print("[Planner] 🌐 PRIORITY 4: Using OpenRouter (DeepSeek)")
        or_plan = create_plan_openrouter(goal, context)
        if or_plan:
            return or_plan

    if _get_api_key("openrouter"):
        print("[Planner] 🌐 PRIORITY 4: Using OpenRouter (DeepSeek)")
        or_plan = create_plan_openrouter(goal, context)
        if or_plan:
            return or_plan

    # 6. PRIORITY 5: MINIMAX (Fallback Reasoning)
    if _get_api_key("minimax"):
        print("[Planner] 🎨 PRIORITY 5: Using MiniMax")
        mm_plan = create_plan_minimax(goal, context)
        if mm_plan: return mm_plan

    # 7. PRIORITY 6: GEMINI (Last resort for planning due to rate limits)
    print("[Planner] ⚠️ PRIORITY 6: Falling back to Gemini (Rate Limited)")
    try:
        plan = create_plan_gemini(goal, context)
        if plan: return plan
    except:
        pass

    # 8. PRIORITY 7: LOCAL QWEN (Last Resort)
    from core.local_llm import call_ollama, is_ollama_online
    if is_ollama_online():
        try:
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                local_model = json.load(f).get("local_model", "qwen2.5-coder:7b")
            print(f"[Planner] 🧠 PRIORITY 7: Using LOCAL QWEN ({local_model}) as last resort.")
            l_resp = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT, model=local_model)
            if l_resp:
                l_plan = _parse_and_validate_plan(l_resp)
                if l_plan: return l_plan
        except: pass

    print("[Planner] ❌ All AI engines failed! Using regex fallback.")
    # FAST-BRAIN: Handle simple commands without LLM
    goal_lower = goal.lower()
    if "open" in goal_lower:
        app = goal_lower.replace("open", "").strip()
        return {"goal": goal, "steps": [{"step": 1, "tool": "open_app", "description": f"Open {app}", "parameters": {"app_name": app}}]}
    
    return _fallback_plan(goal)

def create_plan_openrouter(goal: str, context: str = "") -> dict | None:
    """Uses OpenRouter as a high-performance fallback for planning."""
    import requests
    from core.brain_router import BrainRouter
    api_key = _get_api_key("openrouter")
    if not api_key: return None

    user_input = f"Goal: {goal}"
    if context: user_input += f"\n\nContext: {context}"

    try:
        # Get optimal model
        try:
            br = BrainRouter(API_CONFIG_PATH)
            model_name = br.get_optimal_openrouter_model(goal)
        except Exception:
            model_name = "google/gemma-4-26b-a4b-it:free"

        print(f"[OpenRouter] 🧠 Using: {model_name.split('/')[-1]}")

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/cifikAI/J.aRVIS",
                "X-Title": "JARVIS Cifik Intelegents (cifikAI)",
            },
            data=json.dumps({
                "model": model_name,
                "messages": [
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": user_input}
                ]
            }),
            timeout=15
        )
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        return _parse_and_validate_plan(text)
    except Exception as e:
        print(f"[OpenRouter] ❌ Error: {e}")
        return None

def create_plan_groq(goal: str, context: str = "") -> dict | None:
    """Uses Groq's high-speed LPU infrastructure for planning."""
    from groq import Groq
    api_key = _get_api_key("groq")
    if not api_key: return None

    user_input = f"Goal: {goal}"
    if context: user_input += f"\n\nContext: {context}"

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.3, # Lower temperature for planning precision
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        text = response.choices[0].message.content.strip()
        return _parse_and_validate_plan(text)
    except Exception as e:
        print(f"[Groq Planner] ❌ Error: {e}")
        return None

def create_plan_minimax(goal: str, context: str = "") -> dict | None:
    """Uses MiniMax as a specialized coding/reasoning engine."""
    import requests
    api_key = _get_api_key("minimax")
    if not api_key: return None

    user_input = f"Goal: {goal}"
    if context: user_input += f"\n\nContext: {context}"

    try:
        response = requests.post(
            url="https://api.minimax.chat/v1/text/chatcompletion_v2",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "abab6.5s-chat", # Fast & Strong reasoning
                "messages": [
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                "tools": []
            }),
            timeout=20
        )
        data = response.json()
        # Handle the nesting difference in MiniMax V2 API
        text = data["choices"][0]["message"]["content"].strip()
        return _parse_and_validate_plan(text)
    except Exception as e:
        print(f"[MiniMax] ❌ Error: {e}")
        return None

def _parse_and_validate_plan(text: str) -> dict:
    if not text:
        return None
        
    # Remove markdown blocks if present
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    
    # Try to find JSON block if it's embedded in text
    if not text.startswith("{"):
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: text = match.group(1)
        else: return None

    try:
        plan = json.loads(text)
    except:
        return None

    if "steps" not in plan or not isinstance(plan["steps"], list):
        raise ValueError("Invalid plan structure")

    for step in plan["steps"]:
        if step.get("tool") in ("generated_code",):
            print(f"[Planner] ⚠️ generated_code detected — replacing with web_search")
            step["tool"] = "web_search"
            if "parameters" not in step: step["parameters"] = {}
            step["parameters"]["query"] = step.get("description", "search")[:200]

    print(f"[Planner] ✅ Plan: {len(plan['steps'])} steps")
    return plan


def _create_simple_plan(goal: str, response: str) -> dict:
    """Helper to convert a raw LLM response into a JARVIS plan structure if needed."""
    try:
        # If response is already JSON
        return _parse_and_validate_plan(response)
    except:
        # Fallback to a single-step chat plan
        return {
            "goal": goal,
            "steps": [
                {
                    "step": 1,
                    "tool": "talk",
                    "description": "Respond to user",
                    "parameters": {"text": response},
                    "critical": True
                }
            ]
        }


def _fallback_plan(goal: str) -> dict:
    print("[Planner] 🔄 Fallback plan")
    return {
        "goal": goal,
        "steps": [
            {
                "step": 1,
                "tool": "web_search",
                "description": f"Search for: {goal}",
                "parameters": {"query": goal},
                "critical": True
            }
        ]
    }


def replan(goal: str, completed_steps: list, failed_step: dict, error: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_get_api_key())

    completed_summary = "\n".join(
        f"  - Step {s['step']} ({s['tool']}): DONE" for s in completed_steps
    )

    prompt = f"""Goal: {goal}

Already completed:
{completed_summary if completed_summary else '  (none)'}

Failed step: [{failed_step.get('tool')}] {failed_step.get('description')}
Error: {error}

Create a REVISED plan for the remaining work only. Do not repeat completed steps."""

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=PLANNER_PROMPT,
            )
        )
        text     = response.text.strip()
        return _parse_and_validate_plan(text)
    except Exception as e:
        if _is_rate_limit(e):
            print("[Planner] ⚠️ Gemini Rate Limit hit during replan. Using local GPU model...")
            from core.local_llm import call_ollama
            res = call_ollama(prompt, system_prompt=PLANNER_PROMPT)
            if res:
                try: return _parse_and_validate_plan(res)
                except: pass

        print(f"[Planner] ⚠️ Replan failed: {e}")
        return _fallback_plan(goal)