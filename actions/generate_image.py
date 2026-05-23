"""
Live tool: generate images via OpenRouter (image-capable models) or Pollinations fallback.
Wired for ToolDispatcher modular path: actions.generate_image -> generate_image(parameters, player).
"""

from __future__ import annotations

import base64
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

_BASE = Path(__file__).resolve().parent.parent


def _config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "config" / "api_keys.json"
    return _BASE / "config" / "api_keys.json"


def _load_keys() -> Dict[str, Any]:
    p = _config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _out_dir() -> Path:
    d = _BASE / "memory" / "generated_images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_b64_image(b64: str, dest: Path) -> None:
    raw = b64
    if "," in raw:
        raw = raw.split(",", 1)[1]
    dest.write_bytes(base64.b64decode(raw))


def _pollinations(prompt: str, model: str, api_key: Optional[str], out: Path) -> bool:
    import requests

    p_model = "flux"
    if model.startswith("pollinations/"):
        p_model = model.replace("pollinations/", "")
    elif model not in ("pollinations", "flux", ""):
        p_model = model

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
    r = requests.get(
        url,
        headers=headers,
        params={"model": p_model, "width": 1024, "height": 1024, "seed": 42},
        timeout=120,
    )
    if r.status_code != 200:
        return False
    out.write_bytes(r.content)
    return True


def _openrouter_image(prompt: str, model: str, api_key: str, out: Path) -> bool:
    import requests

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
        },
        timeout=180,
    )
    if r.status_code != 200:
        return False

    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return False
    message = choices[0].get("message") or {}
    images: list = []

    if message.get("images"):
        images = message["images"]
    elif message.get("content"):
        content = message["content"]
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image":
                    images.append(part)

    if not images:
        return False

    img0 = images[0]
    if isinstance(img0, dict):
        if "image_url" in img0 and isinstance(img0["image_url"], dict):
            url = img0["image_url"].get("url") or ""
            if url.startswith("data:"):
                _save_b64_image(url, out)
                return True
        if "url" in img0:
            u = img0["url"]
            if isinstance(u, str) and u.startswith("data:"):
                _save_b64_image(u, out)
                return True
    return False


def generate_image(parameters: dict | None, player=None, session_memory=None) -> str:
    """Entry point for JARVIS ToolDispatcher."""
    parameters = parameters or {}
    prompt = (parameters.get("prompt") or "").strip()
    if not prompt:
        return "Sir, I need a text prompt to generate an image."

    cfg = _load_keys()
    or_key = (cfg.get("openrouter_api_key") or "").strip()
    pol_key = (cfg.get("pollinations_api_key") or "").strip()
    model = (parameters.get("model") or "google/gemini-3.1-flash-image-preview").strip()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w\-]+", "_", prompt[:40]).strip("_") or "image"
    out = _out_dir() / f"{ts}_{safe}.png"

    try:
        if or_key:
            ok = _openrouter_image(prompt, model, or_key, out)
            if ok:
                msg = f"Image generated and saved to: {out}"
                if player:
                    try:
                        player.write_log(f"[generate_image] {msg}")
                    except Exception:
                        pass
                return msg + " You can open that folder from Explorer, sir."

        if _pollinations(prompt, model or "flux", pol_key or None, out):
            msg = f"Image generated (Pollinations) and saved to: {out}"
            if player:
                try:
                    player.write_log(f"[generate_image] {msg}")
                except Exception:
                    pass
            return msg + " You can open that folder from Explorer, sir."
    except Exception as e:
        err = f"Image generation failed: {e}"
        if player:
            try:
                player.write_log(f"[generate_image] {err}")
            except Exception:
                pass
        return err + " Sir, check OpenRouter / Pollinations keys in config/api_keys.json."

    return (
        "Sir, I could not produce an image. Configure openrouter_api_key (preferred) "
        "or pollinations_api_key in config/api_keys.json, then try again."
    )
