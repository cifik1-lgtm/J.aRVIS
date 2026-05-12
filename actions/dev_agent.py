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

BASE_DIR         = get_base_dir()
PROJECTS_DIR     = Path.home() / "Desktop" / "JarvisProjects"
MAX_FIX_ATTEMPTS = 5

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()

def _is_rate_limit(error: Exception) -> bool:
    msg = str(error).lower()
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg

def _parse_traceback(output: str, project_files: list[str]) -> tuple[str | None, int | None]:
    pattern = re.compile(r'File ["\']([^"\']+\.py)["\'],\s+line\s+(\d+)', re.IGNORECASE)
    matches = pattern.findall(output)
    for raw_path, line_str in reversed(matches):
        raw_name = Path(raw_path).name
        for pf in project_files:
            if Path(pf).name == raw_name or pf == raw_path or raw_path.endswith(pf):
                return pf, int(line_str)
    return None, None

def _classify_error(output: str) -> str:
    low = output.lower()
    if any(x in low for x in ("no module named", "modulenotfounderror", "importerror")):
        return "dependency_error"
    if "syntaxerror" in low or "invalid syntax" in low:
        return "syntax_error"
    if "cannot import" in low or "importerror" in low:
        return "import_error"
    if any(x in low for x in (
        "traceback", "exception", "error:", "nameerror", "typeerror",
        "attributeerror", "valueerror", "keyerror", "indexerror",
        "zerodivisionerror", "filenotfounderror", "permissionerror",
    )):
        return "runtime_error"
    return "none"

def _has_error(output: str, run_command: str) -> bool:
    low = output.lower()
    if "timed out" in low: return False
    if not output.strip(): return False
    error_type = _classify_error(output)
    return error_type != "none"

class RateLimitError(Exception):
    pass

def _plan_project(description: str, language: str) -> dict:
    prompt = f"""You are a senior software architect. Create a minimal, complete file plan for this project.
Language: {language}
Description: {description}

Return ONLY valid JSON:
{{
  "project_name": "snake_case_name",
  "entry_point": "main.py",
  "files": [
    {{
      "path": "main.py",
      "description": "Entry point",
      "imports": []
    }}
  ],
  "run_command": "python main.py",
  "dependencies": []
}}
JSON:"""

    try:
        response_text = call_llm(prompt)
        # Find the first { and last } to isolate JSON
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start != -1 and end != -1:
            raw = response_text[start:end+1]
        else:
            raw = _strip_fences(response_text)
            
        return json.loads(raw)
    except Exception as e:
        if _is_rate_limit(e): raise RateLimitError(str(e))
        print(f"[DevAgent] ❌ JSON Error: {e}\nRaw Response: {response_text[:500]}")
        raise

def _write_file(
    file_info: dict,
    project_description: str,
    all_files: list[dict],
    language: str,
    project_dir: Path,
    already_written: dict[str, str],
) -> str:
    file_path = file_info["path"]
    file_desc = file_info.get("description", "")
    file_imports = file_info.get("imports", [])

    file_list = "\n".join(f"  - {f['path']}: {f.get('description', '')}" for f in all_files)
    
    prompt = f"""Write the complete code for: {file_path}
Project Goal: {project_description}
Structure: {file_list}
Purpose: {file_desc}
Imports: {', '.join(file_imports)}

Rules:
- Output ONLY raw code.
- No placeholders.
Code:"""

    try:
        code = call_llm(prompt)
        code = _strip_fences(code)
        full_path = project_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(code, encoding="utf-8")
        print(f"[DevAgent] ✅ Written: {file_path}")
        return code
    except Exception as e:
        if _is_rate_limit(e): raise RateLimitError(str(e))
        raise

def _install_dependencies(dependencies: list[str], project_dir: Path) -> str:
    if not dependencies: return "No external dependencies."
    to_install = []
    for dep in dependencies:
        pkg_name = re.split(r"[>=<!]", dep)[0].strip()
        result = subprocess.run([sys.executable, "-m", "pip", "show", pkg_name], capture_output=True, text=True)
        if result.returncode != 0: to_install.append(dep)
    if not to_install: return "All dependencies already installed."
    print(f"[DevAgent] 📦 Installing: {to_install}")
    subprocess.run([sys.executable, "-m", "pip", "install"] + to_install, capture_output=True, text=True, cwd=str(project_dir))
    return f"Installed: {', '.join(to_install)}"

def _open_vscode(project_dir: Path):
    subprocess.Popen(["code", str(project_dir)], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _run_project(run_command: str, project_dir: Path, timeout: int = 30) -> str:
    print(f"[DevAgent] 🚀 Running: {run_command}")
    try:
        parts = run_command.split()
        if parts[0].lower() == "python": parts[0] = sys.executable
        result = subprocess.run(parts, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=str(project_dir))
        return f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return str(e)

def _fix_files(
    error_output: str,
    project_description: str,
    all_files: list[dict],
    file_codes: dict[str, str],
    language: str,
    project_dir: Path,
    entry_point: str,
) -> dict[str, str]:
    error_file, error_line = _parse_traceback(error_output, list(file_codes.keys()))
    fix_path = error_file or entry_point
    current_code = file_codes.get(fix_path, "")
    
    prompt = f"""Fix this broken file: {fix_path}
Error: {error_output}
Current Code:
{current_code}

Return ONLY the complete fixed code. No explanation.
Code:"""

    try:
        response_text = call_llm(prompt)
        fixed = _strip_fences(response_text)
        (project_dir / fix_path).write_text(fixed, encoding="utf-8")
        print(f"[DevAgent] 🔧 Fixed: {fix_path}")
        return {fix_path: fixed}
    except Exception as e:
        if _is_rate_limit(e): raise RateLimitError(str(e))
        raise

def _build_project(description: str, language: str, project_name: str, timeout: int, speak=None, player=None) -> str:
    def log(msg: str):
        print(f"[DevAgent] {msg}")
        if player: player.write_log(f"[DevAgent] {msg}")

    log("Planning project structure...")
    try:
        plan = _plan_project(description, language)
    except RateLimitError:
        msg = "Rate limit reached. Please try again later."
        if speak: speak(msg)
        return msg

    proj_name = project_name or plan.get("project_name", "jarvis_project")
    project_dir = PROJECTS_DIR / proj_name
    project_dir.mkdir(parents=True, exist_ok=True)
    
    files = plan.get("files", [])
    entry_point = plan.get("entry_point", "main.py")
    run_command = plan.get("run_command", f"python {entry_point}")
    dependencies = plan.get("dependencies", [])

    file_codes = {}
    for file_info in files:
        file_path = file_info.get("path")
        log(f"Writing {file_path}...")
        try:
            code = _write_file(file_info, description, files, language, project_dir, file_codes)
            file_codes[file_path] = code
        except RateLimitError:
            log("Rate limit - skipping file.")

    if dependencies: log(_install_dependencies(dependencies, project_dir))
    _open_vscode(project_dir)

    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        log(f"Attempt {attempt}/{MAX_FIX_ATTEMPTS}")
        output = _run_project(run_command, project_dir, timeout)
        if not _has_error(output, run_command):
            msg = f"Project '{proj_name}' complete and running."
            if speak: speak(msg)
            return msg
        log("Fixing errors...")
        try:
            updated = _fix_files(output, description, files, file_codes, language, project_dir, entry_point)
            file_codes.update(updated)
        except RateLimitError:
            break

    return f"Project saved at {project_dir}. Check VSCode."

def dev_agent(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    p = parameters or {}
    description = p.get("description", "").strip()
    if not description: return "Please describe the project, sir."
    return _build_project(description, p.get("language", "python"), p.get("project_name", ""), int(p.get("timeout", 30)), speak, player)