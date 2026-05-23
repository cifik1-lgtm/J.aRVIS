"""
Hands-off Netflix control for JARVIS (Windows).

Goals:
- Control the installed Netflix app without global hotkeys / mouse moves on your work monitor.
- Place playback on a chosen monitor (e.g. monitor 1) at full size.
- Pause between internal steps (rate-limit friendly) and restore your previous foreground window.

Voice example:
  "Jarvis, open Netflix, play SWAT on monitor 1 fullscreen"
  -> netflix_manager action=play_title title="SWAT" monitor=1 fullscreen=true
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_SYSTEM = sys.platform
_CREATE_NO_WINDOW = 0x08000000 if _SYSTEM == "win32" else 0

try:
    import win32con
    import win32gui

    _WIN32 = True
except ImportError:
    _WIN32 = False

try:
    import pymonctl

    _PYMONCTL = True
except ImportError:
    _PYMONCTL = False

try:
    import pygetwindow as gw

    _PYGETWINDOW = True
except ImportError:
    _PYGETWINDOW = False

_BASE = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _BASE / "config" / "api_keys.json"

# Common Microsoft Store Netflix AUMIDs (fallbacks; discovered at runtime when possible)
_NETFLIX_AUMIDS = [
    "NetflixInc.Netflix_mzkn817j654kp!Netflix.App",
    "NetflixInc.Netflix_8wekyb3d8bbwe!Netflix.App",
]

# Explorer opens this folder when the AUMID is wrong — do not treat as Netflix
_APPS_FOLDER_TITLES = ("apps", "applications", "shell", "program manager")

# Netflix search bar placeholder (user-confirmed UI label)
_NETFLIX_SEARCH_PLACEHOLDERS = (
    "titles, people, genres",
    "title, people, genre",
    "titles people genres",
    "title people genre",
    "titles people genre",
)


def _log(msg: str, player=None) -> None:
    print(f"[Netflix] {msg}")
    if player:
        try:
            player.write_log(f"[Netflix] {msg}")
        except Exception:
            pass


def _load_cfg() -> Dict[str, Any]:
    defaults = {
        "step_delay_sec": 2.5,
        "monitor_index": 1,
        "restore_focus_after_step": True,
        "window_title_contains": "Netflix",
        "launch_timeout_sec": 45,
        "netflix_aumid": "",
        "use_keyboard": False,
        "playback_wait_sec": 8,
        "search_overlay_wait_sec": 3.5,
        "search_placeholder": "title people genre",
        "detail_page_wait_sec": 4.0,
        "prefer_tv_series": True,
        "play_invoke_retries": 4,
        "fullscreen_invoke_retries": 3,
        "wake_ui_for_player_controls": True,
        "video_double_click_fallback": True,
    }
    try:
        if _CONFIG_PATH.exists():
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            user = raw.get("netflix_automation") or {}
            if isinstance(user, dict):
                defaults.update(user)
    except Exception:
        pass
    return defaults


# "More to explore" suggestions — never click these for play_title
_EXPLORE_NOISE = (
    "miami swat",
    "las vegas",
    "detroit",
    "l.a.",
    "more to explore",
    "more like",
    "because you watched",
)


class _FocusGuard:
    """Save / restore the HWND the user was working in."""

    def __init__(self, enabled: bool):
        self.enabled = enabled and _WIN32
        self._prev: Optional[int] = None

    def save(self) -> None:
        if self.enabled:
            try:
                self._prev = win32gui.GetForegroundWindow()
            except Exception:
                self._prev = None

    def restore(self) -> None:
        if self.enabled and self._prev:
            try:
                win32gui.SetForegroundWindow(self._prev)
            except Exception:
                pass


def _step_pause(cfg: Dict[str, Any], player=None, label: str = "") -> None:
    delay = float(cfg.get("step_delay_sec", 2.5))
    if label:
        _log(f"Step pause ({delay}s): {label}", player)
    time.sleep(max(0.5, delay))


def _discover_netflix_aumid(cfg: Dict[str, Any]) -> List[str]:
    """Resolve App User Model IDs from config + Get-StartApps."""
    ids: List[str] = []
    custom = (cfg.get("netflix_aumid") or "").strip()
    if custom:
        ids.append(custom)
    ids.extend(_NETFLIX_AUMIDS)

    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-StartApps | Where-Object { $_.Name -match 'Netflix' } | "
                "Select-Object -ExpandProperty AppID",
            ],
            capture_output=True,
            text=True,
            timeout=12,
            creationflags=_CREATE_NO_WINDOW,
        )
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if line and line not in ids:
                ids.insert(0, line)
    except Exception as e:
        _log(f"AUMID discovery skipped: {e}")

    # de-dupe preserve order
    seen = set()
    out: List[str] = []
    for a in ids:
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _is_netflix_title(title: str, sub: str) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return False
    if t in _APPS_FOLDER_TITLES or t == "apps folder":
        return False
    if "appsfolder" in t.replace(" ", ""):
        return False
    return sub in t


def _enum_netflix_hwnds(title_sub: str) -> List[int]:
    found: List[int] = []
    sub = (title_sub or "Netflix").lower()

    try:
        import win32process
    except ImportError:
        win32process = None  # type: ignore

    netflix_pids: set = set()
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name"]):
            name = (proc.info.get("name") or "").lower()
            if "netflix" in name:
                netflix_pids.add(proc.info["pid"])
    except Exception:
        pass

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            if win32gui.GetWindowRect(hwnd)[2] <= win32gui.GetWindowRect(hwnd)[0]:
                return True
        except Exception:
            return True
        t = win32gui.GetWindowText(hwnd) or ""
        if _is_netflix_title(t, sub):
            found.append(hwnd)
            return True
        if win32process and netflix_pids:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in netflix_pids:
                    r = win32gui.GetWindowRect(hwnd)
                    w, h = r[2] - r[0], r[3] - r[1]
                    if w > 240 and h > 180:
                        found.append(hwnd)
            except Exception:
                pass
        return True

    if _WIN32:
        win32gui.EnumWindows(cb, None)
    return found


def _get_monitor_rect(monitor_index_1based: int) -> Optional[Tuple[int, int, int, int]]:
    """Return (left, top, width, height) for monitor N (1-based)."""
    if not _PYMONCTL:
        return None
    try:
        monitors = pymonctl.getAllMonitors()
        if not monitors:
            return None
        idx = max(0, min(len(monitors) - 1, int(monitor_index_1based) - 1))
        mon = monitors[idx]
        pos = mon.position
        size = mon.size
        return (pos.x, pos.y, size.width, size.height)
    except Exception:
        return None


def _place_on_monitor(
    hwnd: int,
    monitor_index: int,
    fullscreen: bool,
    cfg: Dict[str, Any],
    player=None,
) -> str:
    if not _WIN32:
        return "Win32 not available."

    rect = _get_monitor_rect(monitor_index)
    if not rect:
        return f"Could not resolve monitor {monitor_index}."

    left, top, w, h = rect
    flags = win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW

    try:
        if fullscreen:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                left,
                top,
                w,
                h,
                flags,
            )
            _log(f"Placed Netflix on monitor {monitor_index} ({w}x{h}) without stealing focus.", player)
            return f"Netflix on monitor {monitor_index}, full screen area."
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, left + 40, top + 40, w - 80, h - 80, flags)
        return f"Netflix on monitor {monitor_index}."
    except Exception as e:
        return f"Failed to place window: {e}"


def _try_start_aumid(aumid: str, player=None) -> bool:
    """Start a Store app by AUMID without opening the Apps folder listing."""
    # Must be shell:AppsFolder (capital F). Wrong casing opens the Apps folder UI.
    target = f"shell:AppsFolder\\{aumid}"

    attempts = [
        ["cmd", "/c", "start", "", target],
        ["powershell", "-NoProfile", "-Command", f"Start-Process '{target}'"],
        ["explorer.exe", target],
    ]
    for argv in attempts:
        try:
            subprocess.Popen(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW,
                shell=False,
            )
            _log(f"Launch attempt: {' '.join(argv[:3])} ... ({aumid})", player)
            return True
        except Exception as e:
            _log(f"Launch attempt failed: {e}", player)
    return False


def _launch_netflix(cfg: Dict[str, Any], player=None) -> bool:
    """Launch Netflix; try each known AUMID until a Netflix window appears."""
    aumids = _discover_netflix_aumid(cfg)
    if not aumids:
        _log("No Netflix AUMID found.", player)
    else:
        _log(f"Trying AUMIDs: {', '.join(aumids[:3])}{'...' if len(aumids) > 3 else ''}", player)

    sub = cfg.get("window_title_contains", "Netflix")
    per_try = min(18.0, float(cfg.get("launch_timeout_sec", 45)) / max(1, len(aumids)))

    for aumid in aumids:
        if _enum_netflix_hwnds(sub):
            return True
        if not _try_start_aumid(aumid, player):
            continue
        deadline = time.time() + per_try
        while time.time() < deadline:
            if _enum_netflix_hwnds(sub):
                _log(f"Netflix window detected after AUMID launch.", player)
                return True
            time.sleep(0.6)

    # WindowsApps stub / protocol
    for extra in (
        ["cmd", "/c", "start", "", "netflix:"],
        ["cmd", "/c", "start", "", "ms-windows-store://pdp/?productid=9WZDNCRFJ3TJ"],
    ):
        try:
            subprocess.Popen(
                extra,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW,
            )
            time.sleep(4.0)
            if _enum_netflix_hwnds(sub):
                return True
        except Exception:
            pass

    from actions.open_app import open_app

    res = open_app({"app_name": "netflix"}, player=player)
    _log(f"Fallback open_app: {res}", player)
    time.sleep(3.0)
    return bool(_enum_netflix_hwnds(sub)) or ("Opened" in res or "opened" in res.lower())


def _wait_for_window(cfg: Dict[str, Any], player=None) -> Optional[int]:
    sub = cfg.get("window_title_contains", "Netflix")
    timeout = float(cfg.get("launch_timeout_sec", 25))
    end = time.time() + timeout
    while time.time() < end:
        hwnds = _enum_netflix_hwnds(sub)
        if hwnds:
            return hwnds[0]
        time.sleep(0.5)
    return None


def _uia_window(hwnd: int):
    from pywinauto import Application

    app = Application(backend="uia").connect(handle=hwnd, timeout=10)
    return app.window(handle=hwnd)


def _uia_invoke_first(dlg, *, title_re: str = "", name_contains: str = "", control_types=None) -> bool:
    """Click via UIA Invoke pattern only (no keyboard, no physical mouse)."""
    if control_types is None:
        control_types = ("Button", "Hyperlink", "ListItem", "MenuItem", "TabItem")

    try:
        items = dlg.descendants()
    except Exception:
        return False

    name_lower = name_contains.lower()
    for el in items:
        try:
            ctype = el.element_info.control_type
            if ctype not in control_types:
                continue
            labels = [x for x in _element_labels(el) if x]
            text = labels[0] if labels else ""
            hay = " ".join(labels).lower()
            if title_re:
                if not any(re.search(title_re, lab, re.I) for lab in labels):
                    continue
            elif name_contains:
                if name_lower not in hay:
                    continue
            else:
                continue
            el.invoke()
            _log(f"UIA invoke: [{ctype}] {text[:60]}")
            return True
        except Exception:
            continue
    return False


def _normalize_ui_label(text: str) -> str:
    return re.sub(r"[\s,.\-_]+", " ", (text or "").lower()).strip()


def _element_labels(el) -> List[str]:
    labels: List[str] = []
    try:
        labels.append(el.window_text() or "")
    except Exception:
        pass
    try:
        labels.append(getattr(el.element_info, "name", "") or "")
    except Exception:
        pass
    try:
        labels.append(getattr(el.element_info, "rich_text", "") or "")
    except Exception:
        pass
    return [x for x in labels if x]


def _is_netflix_search_placeholder(label: str, cfg: Optional[Dict[str, Any]] = None) -> bool:
    """Match Netflix search hint: 'Titles, people, genres' / 'title people genre'."""
    n = _normalize_ui_label(label)
    if not n:
        return False

    custom = ""
    if cfg:
        custom = _normalize_ui_label(str(cfg.get("search_placeholder", "")))
    if custom and (custom in n or n in custom):
        return True

    for ph in _NETFLIX_SEARCH_PLACEHOLDERS:
        p = _normalize_ui_label(ph)
        if p == n or p in n or n in p:
            return True

    # All three words present (any order) — covers split labels in UIA
    words = set(n.split())
    if {"title", "titles", "people", "genre", "genres"} & words:
        hits = sum(1 for w in ("title", "titles", "people", "genre", "genres") if w in n)
        if hits >= 2 and ("people" in n or "genre" in n or "genres" in n):
            return True
    return False


def _uia_find_and_fill_placeholder(dlg, text: str, cfg: Dict[str, Any], player=None) -> bool:
    """Target the search field by its placeholder label (no keyboard)."""
    try:
        items = dlg.descendants()
    except Exception:
        return False

    for el in items:
        for lab in _element_labels(el):
            if not _is_netflix_search_placeholder(lab, cfg):
                continue
            _log(f"UIA found search placeholder: '{lab[:50]}'", player)
            try:
                el.invoke()
                time.sleep(0.35)
            except Exception:
                pass
            if _uia_try_set_value_on_element(el, text, player):
                return True
            # Parent may hold the editable region (common in UWP)
            try:
                parent = el.parent()
                if parent and _uia_try_set_value_on_element(parent, text, player):
                    return True
            except Exception:
                pass
    return False


def _uia_open_search(dlg) -> bool:
    if _uia_invoke_first(dlg, title_re=r"^search$"):
        return True
    if _uia_invoke_first(dlg, name_contains="search"):
        return True
    return False


def _uia_try_set_value_on_element(el, text: str, player=None) -> bool:
    """Set text on a control without sending keys to the user's keyboard."""
    text = (text or "").strip()
    if not text:
        return False

    label = (el.window_text() or "")[:40]
    ctype = el.element_info.control_type

    # 1) UIA Value pattern
    try:
        iface = el.iface_value
        if iface and iface.CurrentIsReadOnly == 0:
            iface.SetValue(text)
            _log(f"UIA SetValue on [{ctype}] '{label}': {text}", player)
            return True
    except Exception:
        pass

    # 2) pywinauto set_edit_text (WM_SETTEXT on native handle when available)
    try:
        el.set_edit_text(text)
        _log(f"UIA set_edit_text on [{ctype}] '{label}': {text}", player)
        return True
    except Exception:
        pass

    # 3) Win32 WM_SETTEXT to control HWND (not global keyboard)
    if _WIN32:
        try:
            hwnd = int(el.handle)
            if hwnd:
                import win32con

                win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, text)
                _log(f"WM_SETTEXT on [{ctype}] hwnd={hwnd}: {text}", player)
                return True
        except Exception:
            pass

    # 4) UIA Text pattern (Document controls in UWP)
    try:
        tp = el.iface_text
        if tp:
            rng = tp.DocumentRange
            rng.Select()
            rng.SetText(text)
            _log(f"UIA TextPattern on [{ctype}]: {text}", player)
            return True
    except Exception:
        pass

    return False


def _uia_search_field_candidates(dlg, cfg: Optional[Dict[str, Any]] = None) -> List[Tuple[int, Any]]:
    """Score likely search inputs (Netflix UWP often uses Document/Text, not Edit)."""
    candidates: List[Tuple[int, Any]] = []
    search_hints = (
        "search",
        "title",
        "titles",
        "genre",
        "genres",
        "people",
        "person",
        "find",
        "query",
        "type to",
    )
    try:
        items = dlg.descendants()
    except Exception:
        return candidates

    for el in items:
        try:
            ctype = el.element_info.control_type or ""
            if ctype not in (
                "Edit",
                "Document",
                "ComboBox",
                "Text",
                "Pane",
                "Group",
                "Custom",
            ):
                continue
            labels = _element_labels(el)
            combined = " ".join(labels).lower()
            auto_id = (getattr(el.element_info, "automation_id", None) or "").lower()
            cls = (getattr(el.element_info, "class_name", None) or "").lower()

            score = 0
            for lab in labels:
                if _is_netflix_search_placeholder(lab, cfg):
                    score += 55
                    break
            if ctype in ("Edit", "Document", "Text"):
                score += 12
            if ctype == "ComboBox":
                score += 8
            for hint in search_hints:
                if hint in combined or hint in auto_id or hint in cls:
                    score += 18
            if combined.strip() == "" and ctype in ("Edit", "Document", "Text"):
                score += 6
            try:
                if el.is_enabled():
                    score += 4
            except Exception:
                pass
            try:
                if el.iface_value and el.iface_value.CurrentIsReadOnly == 0:
                    score += 10
            except Exception:
                pass

            if score >= 10:
                candidates.append((score, el))
        except Exception:
            continue

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates


def _uia_set_search_text_on_dlg(dlg, text: str, player=None, cfg: Optional[Dict[str, Any]] = None) -> bool:
    text = (text or "").strip()
    if not text:
        return False

    cfg = cfg or _load_cfg()

    # 1) Direct hit on "Titles, people, genres" placeholder
    if _uia_find_and_fill_placeholder(dlg, text, cfg, player):
        return True

    # Invoke top candidates first (helps UWP accept SetValue)
    for score, el in _uia_search_field_candidates(dlg, cfg)[:5]:
        try:
            el.invoke()
            time.sleep(0.3)
        except Exception:
            pass

    for score, el in _uia_search_field_candidates(dlg, cfg):
        if _uia_try_set_value_on_element(el, text, player):
            return True

    # ComboBox: editable child
    try:
        for cb in dlg.descendants(control_type="ComboBox"):
            for child in cb.descendants():
                try:
                    if child.element_info.control_type in ("Edit", "Document", "Text"):
                        if _uia_try_set_value_on_element(child, text, player):
                            return True
                except Exception:
                    continue
    except Exception:
        pass

    # Last resort: any writable Value pattern in the tree (Netflix UWP / WebView2)
    tried = 0
    try:
        for el in dlg.descendants():
            if tried > 40:
                break
            try:
                iface = el.iface_value
                if iface and iface.CurrentIsReadOnly == 0:
                    tried += 1
                    iface.SetValue(text)
                    _log(f"UIA brute SetValue on [{el.element_info.control_type}]", player)
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def _uia_set_search_text(hwnd: int, text: str, player=None, cfg: Optional[Dict[str, Any]] = None) -> bool:
    """Try main window + any Netflix HWND (search overlay may be a separate tree)."""
    text = (text or "").strip()
    if not text:
        return False

    cfg = cfg or _load_cfg()
    sub = cfg.get("window_title_contains", "Netflix")
    hwnds: List[int] = []
    for h in [hwnd] + _enum_netflix_hwnds(sub):
        if h not in hwnds:
            hwnds.append(h)

    for h in hwnds:
        try:
            dlg = _uia_window(h)
            if _uia_set_search_text_on_dlg(dlg, text, player, cfg):
                return True
        except Exception as e:
            _log(f"Search fill on hwnd={h}: {e}", player)

    return False


def _norm_title_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _query_core_title(query: str) -> str:
    """Strip hints like 'series' from voice queries before title matching."""
    q = (query or "").strip()
    q = re.sub(r"\b(tv\s*)?series\b", "", q, flags=re.I).strip()
    q = re.sub(r"\b(the\s*)?show\b", "", q, flags=re.I).strip()
    return q or (query or "").strip()


def _query_wants_series(query: str) -> bool:
    ql = (query or "").lower()
    return bool(re.search(r"\b(series|tv\s*show|season)\b", ql))


def _rect_metrics(el) -> Tuple[int, int]:
    """Return (center_x, area) for tie-breaking duplicate search cards."""
    try:
        r = el.rectangle()
        w, h = max(0, r.right - r.left), max(0, r.bottom - r.top)
        return (r.left + r.right) // 2, w * h
    except Exception:
        return (0, 0)


def _automation_id(el) -> str:
    try:
        return (getattr(el.element_info, "automation_id", None) or "") or ""
    except Exception:
        return ""


def _element_blob(el, max_depth: int = 4) -> str:
    parts: List[str] = []
    try:
        parts.extend(_element_labels(el))
        parts.append(_automation_id(el))
    except Exception:
        pass

    def walk(node, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            for child in node.children():
                try:
                    parts.extend(_element_labels(child))
                    parts.append(_automation_id(child))
                except Exception:
                    pass
                walk(child, depth + 1)
        except Exception:
            pass

    walk(el, 0)
    return " ".join(parts).lower()


def _is_explore_noise(text: str) -> bool:
    tl = (text or "").lower()
    if len(tl) > 45:
        return True
    for noise in _EXPLORE_NOISE:
        if noise in tl:
            return True
    return False


def _card_metadata_bonus(el, prefer_series: bool, query: str = "") -> int:
    """Boost TV series card (2017) over 2003 movie on Netflix search grid."""
    bonus = 0
    try:
        blob = _element_blob(el)
        try:
            parent = el.parent()
            for _ in range(3):
                if parent is None:
                    break
                blob += " " + _element_blob(parent, max_depth=2)
                parent = parent.parent()
        except Exception:
            pass

        if prefer_series or _query_wants_series(query):
            if re.search(r"\b20(1[6-9]|2[0-9])\b", blob):
                bonus += 180
            if "2017" in blob or "tv programme" in blob or "tv series" in blob:
                bonus += 200
            if re.search(r"\bseries\b|\btv\b", blob):
                bonus += 120
            if "2003" in blob or re.search(r"\b20(0[0-9]|10|11|12)\b", blob):
                bonus -= 120
            if "recently added" in blob:
                bonus -= 60
        if "movie" in blob and "series" not in blob and "tv" not in blob:
            bonus -= 50
        if _query_wants_series(query) and "series" in blob:
            bonus += 80
    except Exception:
        pass
    return bonus


def _score_search_result(result_text: str, query: str) -> int:
    """
    Rank Netflix search rows. Prefer exact title (SWAT / S.W.A.T.) over partials (Miami SWAT).
    """
    q = (query or "").strip()
    t = (result_text or "").strip()
    if not q or not t or len(t) < 2:
        return -1

    if _is_explore_noise(t):
        return -1

    # Skip placeholder / junk labels
    if _is_netflix_search_placeholder(t):
        return -1
    if len(t) <= 2 and not t.isalnum():
        return -1

    qn, tn = _norm_title_key(q), _norm_title_key(t)
    if qn == tn:
        return 1000
    if tn == qn or (qn in tn and len(tn) <= len(qn) + 2):
        return 920

    tl, ql = t.lower(), q.lower()
    if tl == ql:
        return 950
    if re.match(rf"^{re.escape(ql)}[\s.:!\-–]*$", tl):
        return 900
    if re.match(rf"^{re.escape(ql)}\b", tl):
        return 850

    if ql not in tl:
        return -1

    # Query is inside a longer title — penalize extra words (e.g. Miami SWAT)
    q_words = ql.split()
    t_words = tl.split()
    extra = [w for w in t_words if w not in q_words]
    if not extra:
        return 800
    if len(extra) == 1 and len(t_words) == len(q_words) + 1:
        return 350
    return max(50, 300 - 80 * len(extra))


def _uia_rank_search_results(
    dlg, query: str, player=None, cfg: Optional[Dict[str, Any]] = None
) -> List[Tuple[int, str, Any, int, int]]:
    """Rank cards as (final_score, label, element, center_x, area)."""
    cfg = cfg or _load_cfg()
    prefer_series = bool(cfg.get("prefer_tv_series", True)) or _query_wants_series(query)
    core = _query_core_title(query)
    ranked: List[Tuple[int, str, Any, int, int]] = []
    skip_types = ("Edit", "Document", "Text", "Pane", "ScrollBar", "Thumb")

    try:
        for el in dlg.descendants():
            try:
                labels = _element_labels(el)
                text = labels[0] if labels else ""
                if not text:
                    continue
                if _is_explore_noise(text):
                    continue
                ctype = el.element_info.control_type or ""
                if ctype in skip_types:
                    continue
                if ctype not in ("ListItem", "Hyperlink", "Button", "Custom", "Group", "Image"):
                    continue
                score = -1
                for lab in labels:
                    if _is_explore_noise(lab):
                        continue
                    score = max(
                        score,
                        _score_search_result(lab, core),
                        _score_search_result(lab, query),
                    )
                if score < 100:
                    continue
                bonus = _card_metadata_bonus(el, prefer_series, query)
                cx, area = _rect_metrics(el)
                ranked.append((score + bonus, text, el, cx, area))
            except Exception:
                continue
    except Exception as e:
        _log(f"UIA result scan failed: {e}", player)
        return []

    if not ranked:
        return []

    # Prefer higher score; on ties prefer rightmost/larger card (2017 series is often 2nd tile).
    ranked.sort(key=lambda x: (x[0], x[3], x[4]), reverse=True)
    return ranked


def _uia_pick_best_search_result(dlg, query: str, player=None, cfg: Optional[Dict[str, Any]] = None) -> bool:
    """Pick highest-scored search result card (main grid, not 'More to explore')."""
    ranked = _uia_rank_search_results(dlg, query, player, cfg)
    if not ranked:
        return False

    best_score, best_text, best_el, cx, _area = ranked[0]
    _log(f"UIA best match ({best_score}, x={cx}): {best_text[:80]}", player)
    if len(ranked) > 1:
        r1 = ranked[1]
        _log(f"UIA runner-up ({r1[0]}, x={r1[3]}): {r1[1][:60]}", player)

    try:
        best_el.invoke()
        _log(f"UIA selected result: {best_text[:80]}", player)
        return True
    except Exception as e:
        _log(f"UIA invoke result failed: {e}", player)
        return False


def _play_label_score(label: str) -> int:
    tl = (label or "").strip().lower()
    if not tl or len(tl) > 80:
        return 0
    if "trailer" in tl or "preview" in tl or "my list" in tl or "download" in tl:
        return 0
    patterns = (
        (r"^play$", 100),
        (r"^play\s", 95),
        (r"watch\s*now", 98),
        (r"^resume$", 72),
        (r"play\s*episode", 92),
        (r"episode\s*1", 88),
        (r"\be1\b", 75),
        (r"season\s*1", 65),
    )
    best = 0
    for pat, pts in patterns:
        if re.search(pat, tl, re.I):
            best = max(best, pts)
    if "play" in tl and best == 0:
        best = 55
    return best


def _uia_detail_page_ready(hwnd: int) -> bool:
    """True when title detail view loaded (Play visible or search overlay gone)."""
    try:
        dlg = _uia_window(hwnd)
    except Exception:
        return False
    try:
        for el in dlg.descendants():
            try:
                for lab in _element_labels(el):
                    if _play_label_score(lab) >= 55:
                        return True
                aid = _automation_id(el).lower()
                if aid and re.search(r"play|watchnow|resume", aid) and "trailer" not in aid:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _uia_wait_for_detail_page(hwnd: int, timeout: float = 8.0, player=None) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if _uia_detail_page_ready(hwnd):
            _log("UIA: title detail page ready", player)
            return True
        time.sleep(0.5)
    return False


def _uia_navigate_back_from_detail(hwnd: int, player=None) -> bool:
    """Return from title detail to search/browse (keyboard-free)."""
    try:
        dlg = _uia_window(hwnd)
    except Exception:
        return False
    for pattern in (r"^back$", r"^close$", r"^cancel$"):
        if _uia_invoke_first(dlg, title_re=pattern):
            _log(f"UIA back: matched {pattern}", player)
            time.sleep(1.2)
            return True
    if _uia_invoke_first(dlg, name_contains="back"):
        time.sleep(1.2)
        return True
    return False


def _uia_ensure_search_view(hwnd: int, player=None) -> bool:
    """Open search UI from home, results, or title detail."""
    try:
        dlg = _uia_window(hwnd)
    except Exception:
        return False

    if _uia_detail_page_ready(hwnd):
        _log("UIA: on title detail — navigating back before search", player)
        _uia_navigate_back_from_detail(hwnd, player)
        time.sleep(0.8)
        try:
            dlg = _uia_window(hwnd)
        except Exception:
            dlg = None

    if dlg and _uia_open_search(dlg):
        return True

    try:
        dlg = _uia_window(hwnd)
        return _uia_open_search(dlg)
    except Exception:
        return False


def _uia_fill_search(hwnd: int, query: str, player=None, cfg: Optional[Dict[str, Any]] = None) -> bool:
    """Open search and type query only (no result pick)."""
    query = (query or "").strip()
    if not query:
        return False

    cfg = cfg or _load_cfg()
    _uia_ensure_search_view(hwnd, player)
    wait_overlay = float(cfg.get("search_overlay_wait_sec", 3.5))
    time.sleep(wait_overlay)

    if not _uia_set_search_text(hwnd, query, player, cfg):
        _log(
            "UIA: could not fill search box (looked for placeholder 'titles, people, genres')",
            player,
        )
        return False
    return True


def _uia_search_and_select(hwnd: int, query: str, player=None) -> bool:
    """Search + pick best matching title — keyboard-free."""
    query = (query or "").strip()
    if not query:
        return False

    cfg = _load_cfg()
    if not _uia_fill_search(hwnd, query, player, cfg):
        return False

    time.sleep(2.8)

    try:
        dlg = _uia_window(hwnd)
    except Exception:
        return False

    if _uia_pick_best_search_result(dlg, query, player, cfg):
        _uia_wait_for_detail_page(hwnd, timeout=12.0, player=player)
        return True

    return _uia_invoke_first(dlg, name_contains=_query_core_title(query))


def _uia_try_episode_play(dlg, player=None) -> bool:
    """Series fallback: Episodes tab → first playable row."""
    opened = _uia_invoke_first(dlg, title_re=r"^episodes?$")
    if opened:
        time.sleep(1.8)
    try:
        for el in dlg.descendants():
            try:
                if (el.element_info.control_type or "") not in ("ListItem", "Button", "Hyperlink", "Custom"):
                    continue
                blob = _element_blob(el, max_depth=2)
                if not re.search(r"episode\s*1|\be1\b|1\s*of\s*\d|season\s*1", blob, re.I):
                    continue
                for child in el.descendants():
                    for lab in _element_labels(child):
                        if _play_label_score(lab) >= 80:
                            child.invoke()
                            _log(f"UIA episode Play invoke: {lab[:50]}", player)
                            time.sleep(1.5)
                            return True
                el.invoke()
                _log(f"UIA episode row invoke: {blob[:60]}", player)
                time.sleep(1.5)
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _uia_scan_play_controls(dlg) -> List[Tuple[int, str, Any]]:
    play_ranked: List[Tuple[int, str, Any]] = []
    try:
        for el in dlg.descendants():
            try:
                ctype = el.element_info.control_type or ""
                best = 0
                label_used = ""
                for lab in _element_labels(el):
                    pts = _play_label_score(lab)
                    if pts > best:
                        best, label_used = pts, lab
                aid = _automation_id(el).lower()
                if aid and re.search(r"play|watchnow|resume", aid) and "trailer" not in aid:
                    best = max(best, 90)
                    label_used = label_used or aid
                if best < 55:
                    continue
                if ctype in (
                    "Button",
                    "Hyperlink",
                    "MenuItem",
                    "Custom",
                    "ListItem",
                    "SplitButton",
                    "Toggle",
                    "Image",
                ):
                    play_ranked.append((best, label_used or ctype, el))
            except Exception:
                continue
    except Exception:
        pass
    play_ranked.sort(key=lambda x: x[0], reverse=True)
    return play_ranked


def _uia_start_playback(hwnd: int, player=None) -> bool:
    """Press Play on title / episode page — Invoke only, with retries."""
    cfg = _load_cfg()
    wait = float(cfg.get("detail_page_wait_sec", 4.0))
    retries = int(cfg.get("play_invoke_retries", 4))

    for attempt in range(retries):
        if attempt:
            time.sleep(2.0)
        else:
            time.sleep(wait)

        try:
            dlg = _uia_window(hwnd)
        except Exception:
            continue

        play_ranked = _uia_scan_play_controls(dlg)
        for pts, text, el in play_ranked[:10]:
            try:
                el.invoke()
                _log(f"UIA Play invoke ({pts}): {text[:50]}", player)
                time.sleep(1.5)
                return True
            except Exception:
                continue

        for pattern in (r"^play$", r"watch\s*now", r"^resume$", r"play\s*episode"):
            if _uia_invoke_first(dlg, title_re=pattern):
                _log(f"UIA Play via pattern {pattern}", player)
                time.sleep(1.5)
                return True

        if _uia_try_episode_play(dlg, player):
            return True

    return False


def _netflix_hwnds_for_uia(hwnd: int, cfg: Optional[Dict[str, Any]] = None) -> List[int]:
    cfg = cfg or _load_cfg()
    sub = cfg.get("window_title_contains", "Netflix")
    out: List[int] = []
    for h in [hwnd] + _enum_netflix_hwnds(sub):
        if h not in out:
            out.append(h)
    return out


def _uia_wake_player_ui(hwnd: int, cfg: Dict[str, Any], player=None) -> None:
    """Briefly focus Netflix so playback overlay controls appear in UIA."""
    if not _WIN32 or not cfg.get("wake_ui_for_player_controls", True):
        return
    guard = _FocusGuard(bool(cfg.get("restore_focus_after_step", True)))
    guard.save()
    try:
        win32gui.SetForegroundWindow(hwnd)
        _log("UIA: focused Netflix to reveal player controls", player)
    except Exception as e:
        _log(f"UIA: focus Netflix failed: {e}", player)
    time.sleep(0.6)
    guard.restore()


def _uia_control_zone(el, dlg) -> str:
    """
    Classify where a control lives: title (window chrome), player (bottom bar), client.
    Window Maximize/Restore must not be treated as in-player fullscreen.
    """
    try:
        wr = dlg.rectangle()
        er = el.rectangle()
        h = max(1, wr.bottom - wr.top)
        if er.bottom < wr.top + int(h * 0.11):
            return "title"
        if er.top > wr.top + int(h * 0.70):
            return "player"
    except Exception:
        pass
    return "client"


def _uia_label_matches_enter_video_fs(label: str) -> bool:
    tl = (label or "").lower()
    if not tl:
        return False
    if "exit" in tl or "leave" in tl or "restore" in tl or "close" in tl:
        return False
    if re.search(r"full\s*screen|enter\s*full|^maximize$|\bexpand\b", tl, re.I):
        return True
    return "maximize" in tl and "window" not in tl


def _uia_label_matches_exit_video_fs(label: str) -> bool:
    tl = (label or "").lower()
    if re.search(r"exit\s*full|leave\s*full|minimize\s*full|\bshrink\b", tl, re.I):
        return True
    return False


def _uia_player_has_enter_fullscreen_button(dlg) -> bool:
    """True if the bottom player bar still offers Enter fullscreen / Maximize (video not FS)."""
    try:
        for el in dlg.descendants():
            zone = _uia_control_zone(el, dlg)
            if zone == "title":
                continue
            if zone not in ("player", "client"):
                continue
            for lab in _element_labels(el):
                if _uia_label_matches_enter_video_fs(lab):
                    return True
    except Exception:
        pass
    return False


def _uia_player_video_is_fullscreen(dlg) -> bool:
    """True only when the player bar shows exit-fullscreen, not window chrome Restore."""
    has_exit = False
    try:
        for el in dlg.descendants():
            if _uia_control_zone(el, dlg) != "player":
                continue
            for lab in _element_labels(el):
                if _uia_label_matches_exit_video_fs(lab):
                    has_exit = True
                    break
    except Exception:
        pass
    if has_exit:
        return True
    # No enter button in player bar and playback chrome visible => likely video FS
    if not _uia_player_has_enter_fullscreen_button(dlg):
        try:
            for el in dlg.descendants():
                if _uia_control_zone(el, dlg) != "player":
                    continue
                for lab in _element_labels(el):
                    if re.search(r"^pause$|^play$|^resume$", lab, re.I):
                        return True
        except Exception:
            pass
    return False


def _uia_invoke_player_zone_fullscreen(dlg, player=None) -> bool:
    """Invoke Maximize / Full screen on the player bar only (never title-bar Maximize)."""
    ranked: List[Tuple[int, str, Any]] = []
    try:
        for el in dlg.descendants():
            zone = _uia_control_zone(el, dlg)
            if zone not in ("player", "client"):
                continue
            ctype = el.element_info.control_type or ""
            if ctype not in ("Button", "Hyperlink", "Custom", "Toggle", "SplitButton", "Image"):
                continue
            for lab in _element_labels(el):
                if not _uia_label_matches_enter_video_fs(lab):
                    continue
                pts = 100 if re.search(r"full\s*screen", lab, re.I) else 90
                ranked.append((pts, lab, el))
                break
    except Exception:
        pass

    ranked.sort(key=lambda x: x[0], reverse=True)
    for _pts, lab, el in ranked[:5]:
        try:
            el.invoke()
            _log(f"UIA player-bar fullscreen invoke: {lab[:50]}", player)
            time.sleep(0.8)
            return True
        except Exception:
            continue
    return False


def _netflix_double_click_video(hwnd: int, player=None) -> bool:
    """Toggle in-player fullscreen via client-area double-click (no global keyboard)."""
    if not _WIN32:
        return False
    try:
        import win32api

        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        w, h = right - left, bottom - top
        if w < 120 or h < 120:
            return False
        cx = left + w // 2
        cy = top + int(h * 0.42)
        lparam = win32api.MAKELONG(cx & 0xFFFF, cy & 0xFFFF)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.05)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        time.sleep(0.08)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDBLCLK, win32con.MK_LBUTTON, lparam)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        _log(f"UIA: double-click video client ({cx},{cy})", player)
        time.sleep(0.8)
        return True
    except Exception as e:
        _log(f"Video double-click failed: {e}", player)
        return False


def _uia_video_fullscreen_on_dlg(dlg, hwnd: Optional[int] = None, cfg: Optional[Dict[str, Any]] = None, player=None) -> bool:
    """Enter in-player video fullscreen (not the app window title-bar Maximize)."""
    cfg = cfg or _load_cfg()
    if _uia_player_video_is_fullscreen(dlg):
        _log("UIA: video already in player fullscreen", player)
        return True
    if _uia_invoke_player_zone_fullscreen(dlg, player):
        return True
    if hwnd and cfg.get("video_double_click_fallback", True):
        if _netflix_double_click_video(hwnd, player):
            try:
                dlg2 = _uia_window(hwnd)
                return _uia_player_video_is_fullscreen(dlg2) or not _uia_player_has_enter_fullscreen_button(dlg2)
            except Exception:
                return True
    return False


def _uia_enter_video_fullscreen(hwnd: int, cfg: Dict[str, Any], player=None) -> Tuple[bool, str]:
    """
    Enter in-player video fullscreen across all Netflix HWNDs.
    Does not confuse window Maximize/Restore with video fullscreen.
    """
    hwnds = _netflix_hwnds_for_uia(hwnd, cfg)
    attempts = int(cfg.get("fullscreen_invoke_retries", 3))

    for attempt in range(attempts):
        _uia_wake_player_ui(hwnd, cfg, player)
        if attempt:
            time.sleep(0.4)

        for h in hwnds:
            try:
                dlg = _uia_window(h)
            except Exception:
                continue

            if _uia_player_video_is_fullscreen(dlg):
                return True, "Netflix video is already in fullscreen, sir."

            if _uia_video_fullscreen_on_dlg(dlg, h, cfg, player):
                try:
                    dlg = _uia_window(h)
                except Exception:
                    dlg = None
                if dlg and (
                    _uia_player_video_is_fullscreen(dlg)
                    or not _uia_player_has_enter_fullscreen_button(dlg)
                ):
                    return True, "Netflix video fullscreen enabled, sir."

    return (
        False,
        "Could not enter video fullscreen, sir. The app window may be maximized while the "
        "video is still letterboxed — hover the video on monitor 1 and say fullscreen again.",
    )


def _uia_video_fullscreen(dlg, player=None, hwnd: Optional[int] = None, cfg: Optional[Dict[str, Any]] = None) -> bool:
    """Legacy entry: single-dialog video fullscreen."""
    cfg = cfg or _load_cfg()
    return _uia_video_fullscreen_on_dlg(dlg, hwnd, cfg, player)


def _uia_media_action(dlg, action: str) -> bool:
    action = action.lower()
    if action in ("pause", "resume", "play", "toggle"):
        for pattern in (r"^pause$", r"^play$", r"^resume$"):
            if _uia_invoke_first(dlg, title_re=pattern):
                return True
    if action == "fullscreen":
        return _uia_video_fullscreen(dlg)
    return False


def _tied_search_candidates(
    ranked: List[Tuple[int, str, Any, int, int]], query: str, cfg: Dict[str, Any]
) -> List[Tuple[int, str, Any, int, int]]:
    if not ranked:
        return []
    core = _norm_title_key(_query_core_title(query))
    top = ranked[0][0]
    tied = [r for r in ranked if r[0] >= top - 5 and _norm_title_key(r[1]) == core]
    if len(tied) <= 1:
        return ranked[:3]
    prefer_series = bool(cfg.get("prefer_tv_series", True)) or _query_wants_series(query)
    if prefer_series:
        tied.sort(key=lambda x: (x[0], x[3], x[4]), reverse=True)
    return tied[:3]


def _play_via_uia(hwnd: int, title: str, video_fullscreen: bool, cfg: Dict[str, Any], player=None) -> Tuple[bool, str]:
    """Returns (ok, detail_message)."""
    try:
        _uia_window(hwnd)
    except Exception as e:
        return False, f"UIA connect failed: {e}"

    if not _uia_fill_search(hwnd, title, player, cfg):
        return False, "Could not search or select title via UI Automation."

    time.sleep(2.8)
    try:
        dlg = _uia_window(hwnd)
    except Exception:
        return False, "Could not attach to Netflix for result selection."

    ranked = _uia_rank_search_results(dlg, title, player, cfg)
    if not ranked:
        return False, "Could not find search results for that title."

    candidates = _tied_search_candidates(ranked, title, cfg)
    last_err = "Opened the title page but could not invoke Play."
    playback_ok = False

    for idx, (_score, pick_text, pick_el, cx, _area) in enumerate(candidates):
        if idx > 0:
            _uia_navigate_back_from_detail(hwnd, player)
            _uia_fill_search(hwnd, title, player, cfg)
            time.sleep(2.5)
            try:
                dlg = _uia_window(hwnd)
            except Exception:
                break
            ranked = _uia_rank_search_results(dlg, title, player, cfg)
            candidates = _tied_search_candidates(ranked, title, cfg)
            if idx >= len(candidates):
                break
            _score, pick_text, pick_el, cx, _area = candidates[idx]

        try:
            pick_el.invoke()
            _log(f"UIA try #{idx + 1} ({_score}, x={cx}): {pick_text[:80]}", player)
        except Exception as e:
            last_err = f"Could not open search result: {e}"
            continue

        _uia_wait_for_detail_page(hwnd, timeout=12.0, player=player)
        if _uia_start_playback(hwnd, player):
            playback_ok = True
            break
        last_err = (
            f"Opened '{pick_text[:40]}' but Play was not found. "
            "Trying another match if available."
        )

    if not playback_ok:
        return (
            False,
            last_err + " Say 'Netflix play SWAT series on monitor 1' to prefer the TV show.",
        )

    wait = float(cfg.get("playback_wait_sec", 8))
    _log(f"Waiting {wait}s for playback UI...", player)
    time.sleep(wait)

    try:
        dlg = _uia_window(hwnd)
    except Exception:
        dlg = None

    if video_fullscreen:
        ok_fs, fs_msg = _uia_enter_video_fullscreen(hwnd, cfg, player)
        if ok_fs:
            return True, f"Playback started. {fs_msg}"
        return (
            True,
            "Playback started; video fullscreen was not confirmed (app may be maximized only). "
            f"{fs_msg}",
        )

    return True, "Playback started."


class NetflixManager:
    def __init__(self, player=None):
        self.player = player
        self.cfg = _load_cfg()
        self._last_hwnd: Optional[int] = None

    def _guard(self) -> _FocusGuard:
        return _FocusGuard(bool(self.cfg.get("restore_focus_after_step", True)))

    def launch(self) -> str:
        guard = self._guard()
        guard.save()
        if not _launch_netflix(self.cfg, self.player):
            guard.restore()
            return "Could not launch Netflix, sir."
        _step_pause(self.cfg, self.player, "after launch")
        hwnd = _wait_for_window(self.cfg, self.player)
        guard.restore()
        if not hwnd:
            return "Netflix launch started but the window was not detected yet, sir."
        self._last_hwnd = hwnd
        return "Netflix is launching, sir."

    def ensure_window(self) -> Optional[int]:
        if _WIN32 and self._last_hwnd and win32gui.IsWindow(self._last_hwnd):
            return self._last_hwnd
        hwnd = _wait_for_window(self.cfg, self.player)
        if hwnd:
            self._last_hwnd = hwnd
        return hwnd

    def play_title(
        self,
        title: str,
        monitor: Optional[int] = None,
        fullscreen: bool = True,
    ) -> str:
        """
        Full pipeline: open -> wait -> place on monitor -> search title -> play.
        """
        title = (title or "").strip()
        if not title:
            return "What should I play on Netflix, sir?"

        mon = int(monitor if monitor is not None else self.cfg.get("monitor_index", 1))
        guard = self._guard()

        # 1 Launch
        guard.save()
        _launch_netflix(self.cfg, self.player)
        _step_pause(self.cfg, self.player, "launch")
        hwnd = _wait_for_window(self.cfg, self.player)
        guard.restore()
        if not hwnd:
            hint = (
                "Netflix did not appear in time, sir. "
                "If Explorer opened the Apps folder, the App ID may be wrong. "
                "In PowerShell run: Get-StartApps | Where-Object Name -like '*Netflix*' "
                "then set netflix_automation.netflix_aumid in config/api_keys.json to the AppID value."
            )
            return hint

        self._last_hwnd = hwnd
        _log(f"Window hwnd={hwnd}", self.player)

        # 2 Move app to target monitor (in-player fullscreen comes after Play)
        _step_pause(self.cfg, self.player, "before placement")
        place_msg = _place_on_monitor(hwnd, mon, False, self.cfg, self.player)
        _step_pause(self.cfg, self.player, "after placement")

        # 3 Search → select → Play → video fullscreen (UIA only, no keyboard)
        _step_pause(self.cfg, self.player, "before search/play")
        ok, detail = _play_via_uia(hwnd, title, bool(fullscreen), self.cfg, self.player)
        _step_pause(self.cfg, self.player, "after playback")

        if not ok:
            return (
                f"{place_msg} Netflix is on monitor {mon}, but automation failed: {detail} "
                "No keyboard was used — say 'Netflix search SWAT' to retry."
            )

        return (
            f"Netflix on monitor {mon}: {detail} Title: '{title}'. "
            f"{place_msg} No keyboard input was sent to your PC, sir."
        )

    def handle(self, parameters: dict) -> str:
        parameters = parameters or {}
        action = (parameters.get("action") or "play_title").strip().lower()

        if action in ("open", "launch", "start"):
            return self.launch()

        if action in ("play_title", "play", "watch", "search_play"):
            title = (
                parameters.get("title")
                or parameters.get("query")
                or parameters.get("movie")
                or parameters.get("show")
                or ""
            )
            mon = parameters.get("monitor") or parameters.get("monitor_index")
            fs = parameters.get("fullscreen", True)
            if isinstance(fs, str):
                fs = fs.lower() in ("1", "true", "yes", "on")
            return self.play_title(str(title), monitor=mon, fullscreen=fs)

        if action == "search":
            title = parameters.get("title") or parameters.get("query") or ""
            hwnd = self.ensure_window()
            if not hwnd:
                self.launch()
                _step_pause(self.cfg, self.player, "launch for search")
                hwnd = self.ensure_window()
            if not hwnd:
                return "Netflix window not found, sir."
            try:
                if _uia_fill_search(hwnd, str(title), self.player, self.cfg):
                    _step_pause(self.cfg, self.player, "after search only")
                    return f"Searched Netflix for '{title}' via UI Automation, sir."
            except Exception as e:
                return f"Netflix search failed: {e}"
            return "Could not reach Netflix search via UI Automation, sir."

        if action in ("move_monitor", "fullscreen_window", "place"):
            hwnd = self.ensure_window()
            if not hwnd:
                return "Netflix is not open, sir."
            mon = int(parameters.get("monitor") or parameters.get("monitor_index") or self.cfg.get("monitor_index", 1))
            fs = parameters.get("fullscreen", True)
            if isinstance(fs, str):
                fs = fs.lower() in ("1", "true", "yes", "on")
            return _place_on_monitor(hwnd, mon, bool(fs), self.cfg, self.player)

        if action in ("pause", "resume", "play", "toggle", "fullscreen", "escape"):
            hwnd = self.ensure_window()
            if not hwnd:
                return "Netflix is not open, sir."
            _step_pause(self.cfg, self.player, f"before {action}")
            try:
                if action == "fullscreen":
                    ok, msg = _uia_enter_video_fullscreen(hwnd, self.cfg, self.player)
                else:
                    dlg = _uia_window(hwnd)
                    ok = _uia_media_action(dlg, action)
                    msg = (
                        f"Netflix {action} via UI Automation, sir."
                        if ok
                        else f"Could not find a '{action}' control in Netflix, sir."
                    )
            except Exception as e:
                ok, msg = False, f"Netflix {action} failed: {e}"
            _step_pause(self.cfg, self.player, f"after {action}")
            return msg

        return (
            f"Unknown Netflix action '{action}'. "
            "Use: launch, play_title, search, pause, resume, fullscreen, move_monitor."
        )


_manager: Optional[NetflixManager] = None


def get_netflix_manager(player=None) -> NetflixManager:
    global _manager
    if _manager is None or (player and _manager.player is not player):
        _manager = NetflixManager(player)
    return _manager


def netflix_manager(parameters: dict, player=None, session_memory=None) -> str:
    return get_netflix_manager(player).handle(parameters or {})
