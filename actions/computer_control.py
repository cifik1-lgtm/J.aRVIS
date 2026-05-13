#computer_control.py
import io
import json
import re
import string
import subprocess
import sys
import time
import random
import platform
from pathlib import Path

try:
    import pygetwindow
    _PYGETWINDOW = True
except ImportError:
    _PYGETWINDOW = False

try:
    import pymonctl
    _PYMONCTL = True
except ImportError:
    _PYMONCTL = False

try:
    import win32gui
    import win32con
    _WIN32 = True
except ImportError:
    _WIN32 = False

_SYSTEM = platform.system()
_CREATE_NO_WINDOW = 0x08000000 if _SYSTEM == "Windows" else 0

# Shown to the Live model as the tool description (keep in sync with dispatch below).
COMPUTER_CONTROL_REFERENCE = """
Desktop automation via PyAutoGUI. Always set `action` to one of the names below. Use `keys` with + between modifiers (e.g. ctrl+c, win+r). Coordinates are screen pixels.

| action | Required / typical parameters |
|--------|-------------------------------|
| type | text |
| write | text (same as type) |
| smart_type | text, clear_first (optional bool) |
| click, left_click | x, y optional (omit to click at cursor) |
| double_click | x, y optional |
| triple_click | x, y optional |
| right_click | x, y optional |
| middle_click | x, y optional |
| move | x, y — move pointer (if title or dx='other_monitor' is provided, moves window) |
| move_window | title (optional), target='other_monitor' or x,y |
| move_rel, move_relative | dx, dy — move from current position; duration (optional, default 0.2) |
| drag | x1, y1, x2, y2 |
| hotkey | keys e.g. alt+tab, win+r |
| press | key e.g. enter, esc, f5 |
| key_down | key — hold modifier before click/hotkey |
| key_up | key — release after key_down |
| scroll | direction up|down|left|right, amount (optional) |
| copy | (reads clipboard; may use ctrl+c fallback) |
| paste | text — put text on clipboard and paste |
| screenshot | path optional (must stay under user home) |
| screen_find | description — returns x,y or NOT_FOUND (vision) |
| screen_click | description — find element and left-click |
| screen_double_click | description — find element and double-click |
| wait | seconds (max 30) |
| clear_field | — ctrl+a delete on focused field |
| focus_window | title — substring of window title |
| open_folder, open_directory | folder or path or description with drive/path |
| diagnose_system | — text CPU/RAM/disk summary |
| random_data | type e.g. name, email, phone, password |
| user_data | field — value from long_term memory identity |
| mouse_position, get_position, cursor_position | — returns current x,y |
| run | only if description/path implies opening a folder; else returns guidance |

Do not invent other action names. For OS shortcuts (volume, brightness, Control Panel) use computer_settings.
""".strip()


try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE         = _base_dir()
_CONFIG_PATH  = _BASE / "config" / "api_keys.json"
_MEMORY_PATH  = _BASE / "memory" / "long_term.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _get_os() -> str:
    return _load_config().get("os_system", "windows").lower()


def _get_api_key() -> str:
    return _load_config().get("gemini_api_key", "")

_SAFE_SCREENSHOT_ROOTS = (
    Path.home(),
)

def _safe_screenshot_path(requested: str | None) -> Path:
    fallback = Path.home() / "Desktop" / "jarvis_screenshot.png"
    if not requested:
        return fallback
    try:
        p = Path(requested).expanduser().resolve()
        for root in _SAFE_SCREENSHOT_ROOTS:
            if p.is_relative_to(root.resolve()):
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    return fallback

def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Harper",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "mail.com"]


def _random_data(data_type: str) -> str:
    dt = data_type.lower().strip()

    if dt == "first_name":
        return random.choice(_FIRST_NAMES)

    if dt == "last_name":
        return random.choice(_LAST_NAMES)

    if dt == "name":
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

    if dt == "email":
        first = random.choice(_FIRST_NAMES).lower()
        last  = random.choice(_LAST_NAMES).lower()
        num   = random.randint(10, 999)
        return f"{first}.{last}{num}@{random.choice(_DOMAINS)}"

    if dt == "username":
        return f"{random.choice(_FIRST_NAMES).lower()}{random.randint(100, 9999)}"

    if dt == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        raw   = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(chars, k=9))
        )
        return "".join(random.sample(raw, len(raw)))

    if dt == "phone":
        return f"+1{random.randint(200,999)}{random.randint(1_000_000, 9_999_999)}"

    if dt == "birthday":
        y = random.randint(1980, 2000)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        return f"{m:02d}/{d:02d}/{y}"

    if dt == "address":
        num    = random.randint(100, 9999)
        street = random.choice(["Main St", "Oak Ave", "Park Blvd", "Elm St", "Cedar Ln"])
        return f"{num} {street}"

    if dt == "zip_code":
        return str(random.randint(10000, 99999))

    if dt == "city":
        return random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"])

    return f"random_{data_type}_{random.randint(1000, 9999)}"

def _user_profile() -> dict:
    """Read identity fields from long-term memory."""
    try:
        if _MEMORY_PATH.exists():
            data     = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            identity = data.get("identity", {})
            return {k: v.get("value", "") for k, v in identity.items()}
    except Exception:
        pass
    return {}

def _type(text: str, interval: float = 0.03) -> str:
    _require_pyautogui()
    time.sleep(0.3)
    pyautogui.typewrite(text, interval=interval)
    return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _smart_type(text: str, clear_first: bool = True) -> str:
    _require_pyautogui()
    if clear_first:
        _clear_field()
        time.sleep(0.1)

    if len(text) > 20 and _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        return f"Smart-typed (clipboard): {text[:60]}{'…' if len(text) > 60 else ''}"

    pyautogui.typewrite(text, interval=0.04)
    return f"Smart-typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _click(x=None, y=None, button: str = "left", clicks: int = 1) -> str:
    _require_pyautogui()
    if clicks >= 3:
        verb = "Triple-c"
    elif clicks == 2:
        verb = "Double-c"
    else:
        verb = "C"
    if x is not None and y is not None:
        pyautogui.click(x, y, button=button, clicks=clicks)
        return f"{verb}licked ({x}, {y}) [{button}]"
    pyautogui.click(button=button, clicks=clicks)
    return f"{verb}licked at current position [{button}]"


def _hotkey(*keys) -> str:
    _require_pyautogui()
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def _press(key: str) -> str:
    _require_pyautogui()
    pyautogui.press(key)
    return f"Pressed: {key}"


def _scroll(direction: str = "down", amount: int = 3) -> str:
    _require_pyautogui()
    vertical   = direction in ("up", "down")
    clicks     = amount if direction in ("up", "right") else -amount
    pyautogui.scroll(clicks) if vertical else pyautogui.hscroll(clicks)
    return f"Scrolled {direction} ×{amount}"


def _move(x: int, y: int, duration: float = 0.3) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse → ({x}, {y})"


def _drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x1, y1, duration=0.2)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


def _clipboard_get() -> str:
    if _PYPERCLIP:
        return pyperclip.paste()
    _hotkey("ctrl", "c")
    time.sleep(0.2)
    return "(copied — pyperclip unavailable for read)"


def _clipboard_paste(text: str) -> str:
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        _require_pyautogui()
        pyautogui.hotkey("ctrl", "v")
        return f"Pasted: {text[:60]}{'…' if len(text) > 60 else ''}"
    return "pyperclip not available"


def _screenshot(save_path: str | None = None) -> str:
    _require_pyautogui()
    path = _safe_screenshot_path(save_path)
    img  = pyautogui.screenshot()
    img.save(str(path))
    return f"Screenshot saved: {path}"


def _clear_field() -> str:
    _require_pyautogui()
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    return "Field cleared"

def _focus_window(title: str) -> str:
    os_name = _get_os()

    if os_name == "windows":
        try:
            script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=5,
                creationflags=_CREATE_NO_WINDOW
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (Windows) failed: {e}"

    if os_name == "mac":
        script = (
            f'tell application "System Events" to '
            f'set frontmost of (first process whose name contains "{title}") to true'
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (macOS) failed: {e}"

    if os_name == "linux":
        try:
            result = subprocess.run(
                ["wmctrl", "-a", title],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                time.sleep(0.3)
                return f"Focused window: {title}"
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except FileNotFoundError:
            return "focus_window (Linux) requires wmctrl or xdotool"
        except Exception as e:
            return f"focus_window (Linux) failed: {e}"

    return f"focus_window: unknown OS '{os_name}'"

def _move_window(title: str | None = None, target: str | None = "other_monitor", x: int | None = None, y: int | None = None) -> str:
    if not _PYGETWINDOW:
        return "pygetwindow not installed. Cannot move windows."
    
    if title:
        windows = pygetwindow.getWindowsWithTitle(title)
        if not windows:
            return f"No window found with title containing: '{title}'"
        win = windows[0]
    else:
        win = pygetwindow.getActiveWindow()
        if not win:
            return "No active window found to move."

    # Ensure window is not minimized/maximized in a way that prevents moving
    if win.isMinimized:
        win.restore()
    
    if target == "other_monitor":
        if not _PYMONCTL:
            return "pymonctl not installed. Cannot detect monitors."
        
        monitors = pymonctl.getAllMonitors()
        if len(monitors) < 2:
            return "Only one monitor detected. Cannot move to another monitor."
        
        # Get current window center to find current monitor
        cx = win.left + win.width // 2
        cy = win.top + win.height // 2
        
        current_mon = None
        for mon in monitors:
            m_pos = mon.getPosition()
            m_size = mon.getSize()
            if m_pos.x <= cx <= m_pos.x + m_size.width and m_pos.y <= cy <= m_pos.y + m_size.height:
                current_mon = mon
                break
        
        if not current_mon:
            current_mon = monitors[0]
            
        target_mon = None
        for mon in monitors:
            if mon != current_mon:
                target_mon = mon
                break
        
        if not target_mon:
            return "Could not identify target monitor."
            
        t_pos = target_mon.getPosition()
        t_size = target_mon.getSize()
        c_pos = current_mon.getPosition()
        c_size = current_mon.getSize()

        # Calculate relative position on current monitor to preserve it on the target
        rel_x = (win.left - c_pos.x) / max(1, c_size.width)
        rel_y = (win.top - c_pos.y) / max(1, c_size.height)
        
        new_x = t_pos.x + int(rel_x * t_size.width)
        new_y = t_pos.y + int(rel_y * t_size.height)

        # Keep window within target monitor bounds
        new_x = max(t_pos.x, min(new_x, t_pos.x + t_size.width - win.width))
        new_y = max(t_pos.y, min(new_y, t_pos.y + t_size.height - win.height))
        
        if _SYSTEM == "Windows" and _WIN32:
            try:
                # pygetwindow uses ._hWnd internally on Windows
                hwnd = getattr(win, "_hWnd", None)
                if hwnd:
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, new_x, new_y, 0, 0, 
                                          win32con.SWP_NOSIZE | win32con.SWP_NOZORDER)
                    return f"Moved window '{win.title}' to {target_mon.name} at ({new_x}, {new_y}) (win32)"
            except Exception:
                pass

        win.moveTo(new_x, new_y)
        return f"Moved window '{win.title}' to {target_mon.name} at ({new_x}, {new_y})"

    if x is not None and y is not None:
        win.moveTo(x, y)
        return f"Moved window '{win.title}' to ({x}, {y})"
        
    return "move_window requires target='other_monitor' or explicit x, y coordinates."

def _screen_find(description: str) -> tuple[int, int] | None:
    api_key = _get_api_key()
    if not api_key:
        print("[ComputerControl] ⚠️ No API key for screen_find")
        return None

    try:
        from google import genai
        from google.genai import types as gtypes

        _require_pyautogui()
        w, h  = pyautogui.size()
        img   = pyautogui.screenshot()
        buf   = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        client = genai.Client(api_key=api_key)
        prompt = (
            f"This is a screenshot of a {w}×{h} pixel screen. "
            f"Locate the UI element described as: '{description}'. "
            f"Reply with ONLY the center coordinates as: x,y "
            f"If the element is not visible, reply: NOT_FOUND"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                gtypes.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
        )

        text = (response.text or "").strip()
        if "NOT_FOUND" in text.upper():
            return None

        match = re.search(r"(\d+)\s*,\s*(\d+)", text)
        if match:
            return int(match.group(1)), int(match.group(2))

    except Exception as e:
        print(f"[ComputerControl] ⚠️ screen_find failed: {e}")

    return None


def _extract_folder_from_text(text: str) -> str | None:
    """Pull a Windows/UNC-ish path from natural language (e.g. 'open D: directory')."""
    if not text or not isinstance(text, str):
        return None
    t = text.strip().strip('"').strip("'")
    m = re.search(r"(\\\\[^\s]+)", t)
    if m:
        return m.group(1).rstrip("\\")
    if _SYSTEM == "Windows":
        m = re.search(r"(?i)\b([a-z]:(?:\\[^:*?\"<>|\s]*)*)", t)
        if m:
            s = m.group(1).replace("/", "\\")
            if re.fullmatch(r"(?i)[a-z]:", s):
                return s.upper() + "\\"
            return s
        m = re.search(r"(?i)\bdrive\s+([a-z])\b", t)
        if m:
            return m.group(1).upper() + ":\\"
    if t.startswith("~/") or (t.startswith("/") and "/" in t[1:]):
        m = re.search(r"(~/[^\s]+|/[^\s]+)", t)
        if m:
            try:
                return str(Path(m.group(1)).expanduser())
            except Exception:
                return None
    return None


def _folder_hint_from_params(params: dict) -> str | None:
    for k in ("path", "folder", "target"):
        v = params.get(k)
        if isinstance(v, str) and v.strip():
            h = _extract_folder_from_text(v)
            if h:
                return h
    desc = params.get("description")
    if isinstance(desc, str):
        return _extract_folder_from_text(desc)
    return None


def _open_folder(folder: str) -> str:
    """Open a folder in the OS file manager (Explorer on Windows)."""
    raw = (folder or "").strip().strip('"').strip("'")
    if not raw:
        return "open_folder needs path or folder (e.g. D:\\\\)."
    p = Path(raw).expanduser()
    try:
        p = p.resolve(strict=False)
    except Exception:
        p = Path(raw).expanduser()
    try:
        if _SYSTEM == "Windows":
            subprocess.Popen(["explorer.exe", str(p)])
        elif _SYSTEM == "Darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception as e:
        return f"Could not open folder: {e}"
    return f"Opened in file manager: {p}"


_VALID_CONTROL_ACTIONS = frozenset(
    {
        "type",
        "write",
        "smart_type",
        "click",
        "left_click",
        "double_click",
        "triple_click",
        "right_click",
        "middle_click",
        "move",
        "move_window",
        "move_rel",
        "move_relative",
        "drag",
        "hotkey",
        "press",
        "key_down",
        "key_up",
        "scroll",
        "copy",
        "paste",
        "screenshot",
        "screen_find",
        "screen_click",
        "screen_double_click",
        "wait",
        "clear_field",
        "focus_window",
        "random_data",
        "user_data",
        "diagnose_system",
        "open_folder",
        "mouse_position",
        "get_position",
        "cursor_position",
    }
)


def _diagnose_system() -> str:
    try:
        import psutil
    except ImportError:
        return "Install psutil for diagnostics: pip install psutil"

    import platform as plat

    lines = [f"OS: {plat.system()} {plat.release()} ({plat.machine()})"]
    try:
        lines.append(
            f"CPU: {psutil.cpu_percent(interval=0.35)}% "
            f"({psutil.cpu_count(logical=True)} logical cores)"
        )
        vm = psutil.virtual_memory()
        lines.append(
            f"RAM: {vm.percent}% used — "
            f"{vm.used // (1024**3)} / {vm.total // (1024**3)} GiB"
        )
        root = "C:\\" if _SYSTEM == "Windows" else "/"
        du = psutil.disk_usage(root)
        lines.append(
            f"Disk: {du.percent}% used, "
            f"{du.free // (1024**3)} GiB free of {du.total // (1024**3)} GiB"
        )
    except Exception as e:
        lines.append(f"(System metrics error: {e})")

    lines.append("Top processes by working set:")
    try:
        rows: list[tuple[int, str]] = []
        for p in psutil.process_iter(["name", "memory_info"]):
            try:
                mi = p.info.get("memory_info")
                rss = mi.rss if mi else 0
                if rss:
                    rows.append((rss, p.info.get("name") or "?"))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        rows.sort(key=lambda x: x[0], reverse=True)
        for rss, name in rows[:10]:
            lines.append(f"  {name}: {rss // (1024 * 1024)} MiB")
    except Exception as e:
        lines.append(f"  (process list failed: {e})")

    lines.append(
        "For live graphs: use computer_settings with action monitor_performance "
        "(opens Resource Monitor on Windows)."
    )
    return "\n".join(lines)


def _infer_computer_control_action(goal: str) -> dict:
    """Map a bogus or vague action string to a valid computer_control action (one retry)."""
    goal = (goal or "").strip()
    if not goal:
        return {}

    gl = goal.lower()
    hint = _extract_folder_from_text(goal)
    if hint and any(
        w in gl
        for w in (
            "open",
            "folder",
            "directory",
            "drive",
            "explorer",
            "browse",
            "file manager",
            "show ",
        )
    ):
        return {"action": "open_folder", "folder": hint}

    api_key = _get_api_key()
    if not api_key:
        print("[ComputerControl] ⚠️ No API key for intent inference")
        return {}

    try:
        from google import genai

        names = ", ".join(sorted(_VALID_CONTROL_ACTIONS))
        prompt = f"""The assistant called tool computer_control with a bad or vague action / text:
\"\"\"{goal}\"\"\"

Pick EXACTLY ONE action from this list only:
{names}

Heuristics (do NOT guess clear_field unless the user clearly wants to clear the focused text field):
- diagnose, health, performance, slow, cpu, memory, system check -> diagnose_system
- open a disk path, drive letter, folder in Explorer -> open_folder (include JSON key "folder" with Windows path like D:\\\\ or C:\\\\Users\\\\...)
- screenshot, capture screen -> screenshot
- click something described in words -> screen_click (needs "description"); double-click element -> screen_double_click
- middle mouse / middle click -> middle_click
- triple click -> triple_click
- mouse position, cursor x y -> mouse_position
- hold shift/ctrl for drag -> key_down then key_up with key
- nudge mouse relative -> move_rel with dx dy
- type or write text -> type or write with "text"
- key combination -> hotkey (needs "keys" like ctrl+shift+esc)
- delay, wait, pause -> wait (needs "seconds" number)
- bring window to front -> focus_window (needs "title")
- move window to other monitor, move app, reposition window -> move_window (needs "title" or uses active, "target" can be "other_monitor")

Return ONLY minified JSON. Required: "action". Optional: text, description, keys, key, title, seconds, folder, x, y, x1, y1, x2, y2, dx, dy, duration, amount, direction, path, type, field, clear_first. Use null for unused fields.
Example: {{"action":"diagnose_system"}}"""

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        text = re.sub(r"```(?:json)?", "", (response.text or "")).strip().rstrip("`").strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return {}
        act = str(data.get("action", "")).lower().strip()
        if act not in _VALID_CONTROL_ACTIONS:
            return {}
        out: dict = {"action": act}
        for k in (
            "text",
            "description",
            "keys",
            "key",
            "title",
            "seconds",
            "folder",
            "x",
            "y",
            "x1",
            "y1",
            "x2",
            "y2",
            "amount",
            "direction",
            "path",
            "type",
            "field",
            "button",
            "clear_first",
            "dx",
            "dy",
            "duration",
        ):
            if k not in data:
                continue
            v = data[k]
            if v is None or v == "":
                continue
            out[k] = v
        return out
    except Exception as e:
        print(f"[ComputerControl] intent inference failed: {e}")
        return {}


def computer_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    PyAutoGUI-backed desktop control. Authoritative action + parameter table for the Live model:
    see module constant `COMPUTER_CONTROL_REFERENCE`.

    Common parameters: action (required), text, x, y, x1, y1, x2, y2, dx, dy, duration, keys, key,
    title, description, folder, path, seconds, amount, direction, type (for random_data), field,
    clear_first, path (screenshot save under home only).
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "No action specified for computer_control."

    if player:
        player.write_log(f"[Computer] {action}")

    print(f"[ComputerControl] ▶ {action}  {params}")

    try:

        if action == "run":
            hint = _folder_hint_from_params(params)
            if hint:
                return _open_folder(hint)
            return (
                "The 'run' action cannot execute arbitrary shell commands. "
                "To open a drive or folder, use action open_folder with path or folder "
                "(e.g. D:\\\\) or put the path in description. "
                "For file listings use file_controller (change_directory / list)."
            )

        if action in ("open_folder", "open_directory", "explorer", "browse_folder"):
            fp = params.get("folder") or params.get("path") or ""
            if isinstance(fp, str) and fp.strip():
                return _open_folder(fp.strip())
            hint = _extract_folder_from_text(params.get("description", "") or "")
            if hint:
                return _open_folder(hint)
            return (
                "open_folder needs folder, path, or description naming a drive or path "
                "(e.g. open D: drive)."
            )

        if action == "type":
            return _type(params.get("text", ""))

        if action == "write":
            return _type(params.get("text", ""))

        if action == "smart_type":
            return _smart_type(
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        if action in ("click", "left_click"):
            return _click(params.get("x"), params.get("y"), "left", 1)

        if action == "double_click":
            return _click(params.get("x"), params.get("y"), "left", 2)

        if action == "triple_click":
            return _click(params.get("x"), params.get("y"), "left", 3)

        if action == "middle_click":
            return _click(params.get("x"), params.get("y"), "middle", 1)

        if action == "right_click":
            return _click(params.get("x"), params.get("y"), "right", 1)

        if action == "move":
            target = params.get("target") or params.get("dx")
            title  = params.get("title")
            if target == "other_monitor" or title:
                return _move_window(
                    title=title,
                    target=target if target == "other_monitor" else None,
                    x=params.get("x"),
                    y=params.get("y")
                )
            return _move(int(params.get("x", 0)), int(params.get("y", 0)))

        if action == "move_window":
            return _move_window(
                title=params.get("title"),
                target=params.get("target") or params.get("dx"),
                x=params.get("x"),
                y=params.get("y")
            )

        if action in ("move_rel", "move_relative"):
            _require_pyautogui()
            dx = int(params.get("dx", params.get("x", 0)) or 0)
            dy = int(params.get("dy", params.get("y", 0)) or 0)
            dur = float(params.get("duration", 0.2) or 0.2)
            dur = max(0.05, min(dur, 5.0))
            pyautogui.moveRel(dx, dy, duration=dur)
            return f"Moved relative ({dx}, {dy}) over {dur}s"

        if action == "drag":
            return _drag(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
            )

        if action == "hotkey":
            raw  = params.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            return _hotkey(*keys)

        if action == "press":
            return _press(params.get("key", "enter"))

        if action == "key_down":
            _require_pyautogui()
            k = str(params.get("key", "")).strip()
            if not k:
                return "key_down requires key."
            pyautogui.keyDown(k)
            return f"Key down: {k}"

        if action == "key_up":
            _require_pyautogui()
            k = str(params.get("key", "")).strip()
            if not k:
                return "key_up requires key."
            pyautogui.keyUp(k)
            return f"Key up: {k}"

        if action == "scroll":
            return _scroll(
                direction=params.get("direction", "down"),
                amount=int(params.get("amount", 3)),
            )

        if action == "copy":
            return _clipboard_get()

        if action == "paste":
            return _clipboard_paste(params.get("text", ""))

        if action == "screenshot":
            return _screenshot(params.get("path"))

        if action == "screen_find":
            coords = _screen_find(params.get("description", ""))
            return f"{coords[0]},{coords[1]}" if coords else "NOT_FOUND"

        if action == "screen_click":
            desc   = params.get("description", "")
            coords = _screen_find(desc)
            if coords:
                time.sleep(0.2)
                _click(x=coords[0], y=coords[1])
                return f"Clicked '{desc}' at {coords}"
            return f"Element not found on screen: '{desc}'"

        if action == "screen_double_click":
            desc = params.get("description", "")
            coords = _screen_find(desc)
            if coords:
                time.sleep(0.2)
                _click(x=coords[0], y=coords[1], clicks=2)
                return f"Double-clicked '{desc}' at {coords}"
            return f"Element not found on screen: '{desc}'"

        if action == "wait":
            secs = float(params.get("seconds", 1.0))
            secs = min(secs, 30.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        if action == "clear_field":
            return _clear_field()

        if action == "focus_window":
            return _focus_window(params.get("title", ""))

        if action == "random_data":
            dt     = params.get("type", "name")
            result = _random_data(dt)
            print(f"[ComputerControl] 🎲 random {dt} → {result}")
            return result

        if action == "user_data":
            field   = params.get("field", "name")
            profile = _user_profile()
            value   = profile.get(field, "")
            if not value:
                value = _random_data(field)
                print(f"[ComputerControl] ⚠️ No '{field}' in memory, using random: {value}")
            return value

        if action == "diagnose_system":
            return _diagnose_system()

        if action in ("mouse_position", "get_position", "cursor_position"):
            _require_pyautogui()
            pos = pyautogui.position()
            return f"Mouse position: x={int(pos.x)}, y={int(pos.y)}"

        if action not in _VALID_CONTROL_ACTIONS:
            if not params.get("_cc_infer"):
                goal = f"{params.get('action', '')} {params.get('description', '')}".strip()
                inferred = _infer_computer_control_action(goal)
                if inferred.get("action") in _VALID_CONTROL_ACTIONS:
                    merged = dict(params)
                    merged.update(inferred)
                    merged["_cc_infer"] = True
                    return computer_control(
                        merged,
                        response=response,
                        player=player,
                        session_memory=session_memory,
                    )
            hint = ", ".join(sorted(_VALID_CONTROL_ACTIONS))
            return (
                f"Unknown action: '{params.get('action', action)}'. "
                f"Valid actions: {hint}."
            )

    except Exception as e:
        print(f"[ComputerControl] ❌ {action}: {e}")
        return f"computer_control '{action}' failed: {e}"