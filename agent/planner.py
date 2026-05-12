import json
import re
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


PLANNER_PROMPT = """You are the planning module of MARK XXXIX, a personal AI assistant.
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
LOCAL_PLANNER_PROMPT = """You are the local fallback brain for JARVIS (Mark-XXXIX).
Convert the user's request into a JSON plan using ONLY these tools:

1. computer_settings: { "action": "string", "description": "natural language" }
2. file_controller: { "action": "write|create_file|read|list|delete|move|copy|change_directory|cd", "path": "desktop|documents|D:\\\\|cwd", "name": "string", "content": "string" }
3. computer_control: { "action": "type|click|hotkey|screenshot", "text": "str", "keys": "str" }
4. open_app: { "app_name": "string" }
5. system_control: { "action": "switch_brain", "brain": "gemini|local|openrouter" }
6. talk: { "text": "your response to the user" }

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
        return config.get("gemini_api_key", "")

def _is_rate_limit(e: Exception) -> bool:
    msg = str(e).lower()
    return any(x in msg for x in ["429", "quota", "resource_exhausted", "connection", "timeout", "offline", "network"])

def create_plan_gemini(goal: str, context: str = "") -> dict | None:
    import google.generativeai as genai
    genai.configure(api_key=_get_api_key("gemini"))
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        system_instruction=PLANNER_PROMPT
    )
    user_input = f"Goal: {goal}"
    if context: user_input += f"\n\nContext: {context}"
    try:
        response = model.generate_content(user_input)
        text     = response.text.strip()
        return _parse_and_validate_plan(text)
    except Exception as e:
        print(f"[Gemini] ❌ Error: {e}")
        return None

def create_plan_hive(goal: str, context: str = "") -> dict:
    print("[Planner] 🐝 HIVE MIND: Consulting Gemini, OpenRouter, and Local GPU...")
    
    g_plan = create_plan_gemini(goal, context)
    or_plan = create_plan_openrouter(goal, context)
    
    from core.local_llm import call_ollama, is_ollama_online
    l_plan = None
    if is_ollama_online():
        l_resp = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT)
        try: l_plan = _parse_and_validate_plan(l_resp)
        except: pass
    
    if g_plan and or_plan:
        print("[Planner] ✅ Hive Consensus reached (Cloud & Local agree).")
        return g_plan
    elif g_plan:
        print("[Planner] ⚠️ Hive partially active (Gemini only).")
        return g_plan
    elif or_plan:
        print("[Planner] ⚠️ Hive partially active (OpenRouter only).")
        return or_plan
    
    return l_plan or _fallback_plan(goal)


def create_plan(goal: str, context: str = "") -> dict:
    # Check for manual brain override in config
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            forced = json.load(f).get("force_brain", "gemini")
            if forced == "hive":
                return create_plan_hive(goal, context)
            elif forced == "openrouter":
                print("[Planner] 🧠 Manual Override: Using OpenRouter...")
                return create_plan_openrouter(goal, context)
            elif forced == "minimax":
                print("[Planner] 🧠 Manual Override: Using MiniMax (Coding Brain)...")
                return create_plan_minimax(goal, context)
            elif forced == "local":
                print("[Planner] 🧠 Manual Override: Using Local Ollama...")
                from core.local_llm import call_ollama, is_ollama_online
                if is_ollama_online():
                    local_resp = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT)
                    if local_resp: return _parse_and_validate_plan(local_resp)
    except: pass

    # Default to Gemini but with fallback
    try:
        plan = create_plan_gemini(goal, context)
        if plan: return plan
    except Exception as e:
        if _is_rate_limit(e):
            print("[Planner] ⚠️ Gemini is busy. Switching to OpenRouter Brain...")
            or_plan = create_plan_openrouter(goal, context)
            if or_plan: return or_plan
            
            print("[Planner] ⚠️ OpenRouter unavailable. Attempting MiniMax...")
            mm_plan = create_plan_minimax(goal, context)
            if mm_plan: return mm_plan

            print("[Planner] ⚠️ Cloud Brains unavailable. Attempting LOCAL OLLAMA brain...")
            from core.local_llm import call_ollama, is_ollama_online
            if is_ollama_online():
                local_resp = call_ollama(goal, system_prompt=LOCAL_PLANNER_PROMPT)
                if local_resp:
                    try:
                        return _parse_and_validate_plan(local_resp)
                    except: pass

            print("[Planner] ⚠️ All AI brains offline. Using 'Fast-Brain' regex fallback...")
            # FAST-BRAIN: Handle simple "Open App" or "Search" commands without LLM
            goal_lower = goal.lower()
            if goal_lower.startswith("cloud command:"):
                goal_lower = goal_lower.replace("cloud command:", "").strip()
                
            # If it's a web-related goal, use browser_control instead of open_app to avoid duplicates
            if any(x in goal_lower for x in ["youtube", "google", "wikipedia", "facebook", "instagram", "twitter", "website", ".com", ".org", "http"]):
                if "youtube" in goal_lower:
                     return {
                        "goal": goal,
                        "steps": [{"step": 1, "tool": "youtube_video", "description": f"Play {goal_lower}", "parameters": {"action": "play", "query": goal_lower}}]
                    }
                return {
                    "goal": goal,
                    "steps": [{"step": 1, "tool": "browser_control", "description": f"Go to {goal_lower}", "parameters": {"action": "go_to", "url": goal_lower}}]
                }

            if "open" in goal_lower:
                app = goal_lower.replace("open", "").strip()
                return {
                    "goal": goal,
                    "steps": [{"step": 1, "tool": "open_app", "description": f"Open {app}", "parameters": {"app_name": app}}]
                }
            if "search" in goal_lower or "what" in goal_lower or "who" in goal_lower:
                return _fallback_plan(goal)
        
        print(f"[Planner] ⚠️ Planning failed: {e}")
        return _fallback_plan(goal)

def create_plan_openrouter(goal: str, context: str = "") -> dict | None:
    """Uses OpenRouter as a high-performance fallback for planning."""
    import requests
    api_key = _get_api_key("openrouter")
    if not api_key: return None

    user_input = f"Goal: {goal}"
    if context: user_input += f"\n\nContext: {context}"

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/FatihMakes/Mark-XXXIX",
                "X-Title": "JARVIS Mark-XXXIX",
            },
            data=json.dumps({
                "model": "deepseek/deepseek-chat", # High reasoning, low cost
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
    # Remove markdown blocks if present
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    
    # Try to find JSON block if it's embedded in text
    if not text.startswith("{"):
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match: text = match.group(1)

    plan = json.loads(text)

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
    import google.generativeai as genai

    genai.configure(api_key=_get_api_key())
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=PLANNER_PROMPT
    )

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
        response = model.generate_content(prompt)
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