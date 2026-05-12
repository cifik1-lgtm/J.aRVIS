import subprocess
import sys
import json
import re
import time
from pathlib import Path
from core.llm_provider import call_llm

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR           = get_base_dir()
API_CONFIG_PATH    = BASE_DIR / "config" / "api_keys.json"
DESKTOP            = Path.home() / "Desktop"
MAX_BUILD_ATTEMPTS = 3

def _clean_code(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()

def _resolve_save_path(output_path: str, language: str) -> Path:
    ext_map = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "html": ".html", "css": ".css",
    }
    if output_path:
        p = Path(output_path)
        return p if p.is_absolute() else DESKTOP / p
    ext = ext_map.get((language or "python").lower(), ".py")
    return DESKTOP / f"jarvis_code{ext}"

def _read_file(file_path: str) -> tuple[str, str]:
    if not file_path: return "", "No file path."
    p = Path(file_path)
    if not p.exists(): return "", f"Not found: {file_path}"
    try: return p.read_text(encoding="utf-8"), ""
    except Exception as e: return "", str(e)

def _save_file(path: Path, content: str) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Saved to: {path}"
    except Exception as e: return f"Error saving: {e}"

def _has_error(output: str) -> bool:
    return any(s in output.lower() for s in ["error", "exception", "traceback", "syntaxerror", "stderr"])

def _write(description: str, language: str, output_path: str) -> tuple[str, Path]:
    prompt = f"Write complete {language} code for: {description}\nRules: Output ONLY raw code, no backticks."
    code = _clean_code(call_llm(prompt))
    path = _resolve_save_path(output_path, language)
    _save_file(path, code)
    return code, path

def _fix_code(code: str, error_output: str, description: str) -> str:
    prompt = f"Fix this code:\n{code}\n\nError:\n{error_output}\n\nGoal: {description}\nRules: Output ONLY fixed code."
    return _clean_code(call_llm(prompt))

def _edit_code(code: str, change_description: str, language: str) -> str:
    prompt = f"Edit this {language} code:\n{code}\n\nChange required: {change_description}\nRules: Output ONLY the complete updated code."
    return _clean_code(call_llm(prompt))

def _run_file(path: Path, args: list, timeout: int) -> str:
    interpreters = {".py": [sys.executable], ".js": ["node"], ".sh": ["bash"]}
    interp = interpreters.get(path.suffix.lower())
    if not interp: return f"No interpreter for {path.suffix}."
    try:
        result = subprocess.run(interp + [str(path)] + (args or []), capture_output=True, text=True, timeout=timeout, cwd=str(path.parent))
        return f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Execution error: {e}"

def _build(description, language, output_path, args, timeout, speak=None, player=None) -> str:
    code, path = _write(description, language, output_path)
    for attempt in range(1, MAX_BUILD_ATTEMPTS + 1):
        output = _run_file(path, args, timeout)
        if not _has_error(output):
            msg = f"Build complete. Code is working at {path}."
            if speak: speak(msg)
            return msg
        code = _fix_code(code, output, description)
        _save_file(path, code)
    return f"Failed to build after {MAX_BUILD_ATTEMPTS} attempts."

def code_helper(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "write").lower().strip()
    desc = p.get("description", "").strip()
    file_path = p.get("file_path", "").strip()
    code_input = p.get("code", "").strip()
    lang = p.get("language", "python")

    if action == "write":
        code, path = _write(desc, lang, p.get("output_path"))
        return f"Code written. Saved to: {path}"
    
    if action == "edit" or action == "fix":
        if not file_path and not code_input: return "Please specify file_path or code, sir."
        current_code = code_input
        if file_path:
            current_code, err = _read_file(file_path)
            if err: return err
        
        if action == "fix":
            new_code = _fix_code(current_code, p.get("error", "General fix requested"), desc)
        else:
            new_code = _edit_code(current_code, desc, lang)
            
        if file_path:
            _save_file(Path(file_path), new_code)
            return f"Code {action}ed. Saved to: {file_path}"
        return f"Code {action}ed. Result:\n{new_code}"
    
    if action == "run":
        if not file_path: return "Please specify file_path, sir."
        return _run_file(Path(file_path), p.get("args"), int(p.get("timeout", 30)))
    
    if action == "build":
        return _build(desc, lang, p.get("output_path"), p.get("args"), int(p.get("timeout", 30)), speak, player)

    if action == "create_exe":
        if not file_path: return "Please specify file_path of the script to compile, sir."
        path = Path(file_path)
        if not path.exists(): return f"File not found: {file_path}"
        
        print(f"[Code] 🔨 Compiling {path.name} to EXE...")
        if player: player.write_log(f"🔨 Compiling {path.name} to EXE...")
        
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], capture_output=True)
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole", str(path)],
                capture_output=True, text=True, timeout=300, cwd=str(path.parent)
            )
            if result.returncode == 0:
                exe_path = path.parent / "dist" / f"{path.stem}.exe"
                msg = f"Successfully compiled to EXE! You can find it at: {exe_path}"
                if speak: speak("Compilation complete, sir. Your executable is ready.")
                return msg
            else:
                return f"Compilation failed:\n{result.stderr[:1000]}"
        except Exception as e:
            return f"Error during compilation: {e}"

    if action == "explain":
        if file_path: code_input, _ = _read_file(file_path)
        prompt = f"Explain this code concisely:\n{code_input}"
        return call_llm(prompt)

    if action == "optimize":
        if file_path: code_input, _ = _read_file(file_path)
        prompt = f"Optimize this {lang} code for performance and readability. Return ONLY code.\n{code_input}"
        opt = _clean_code(call_llm(prompt))
        if file_path: _save_file(Path(file_path), opt)
        return f"Optimization complete. Preview:\n{opt[:500]}"

    return f"Action '{action}' is not supported yet."