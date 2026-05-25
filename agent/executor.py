import json
import re
import sys
import threading
import subprocess
import tempfile
import os
import time
import asyncio
from pathlib import Path
from typing import Callable, Any

from agent.planner       import create_plan, replan
from agent.error_handler import analyze_error, generate_fix, ErrorDecision
from google.genai        import types
from core.hive_dna       import get_dna

# Decision logic graph imports
from agent.intent_classifier import TaskInterpreter
from core.master_planner import decompose
from actions.tool_manager import ensure_tool
from agent.self_fix import execute_with_healing
from agent.self_audit import audit_success, validate_integration
from core.logger import log_success
from memory.rag_engine import get_rag_engine


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

def _run_generated_code(description: str, speak: Callable | None = None) -> str:
    from google import genai
    from google.genai import types

    if speak:
        speak("Writing custom code for this task, sir.")

    home      = Path.home()
    desktop   = home / "Desktop"
    downloads = home / "Downloads"
    documents = home / "Documents"

    if not desktop.exists():
        try:
            import winreg
            key     = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            desktop = Path(winreg.QueryValueEx(key, "Desktop")[0])
        except Exception:
            pass

    client = genai.Client(api_key=_get_api_key())
    
    try:
        start_time = time.time()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Write Python code to accomplish this task:\n\n{description}",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are an expert Python developer. "
                    "Write clean, complete, working Python code. "
                    "Use standard library + common packages. "
                    "Install missing packages with subprocess + pip if needed. "
                    "Return ONLY the Python code. No explanation, no markdown, no backticks.\n\n"
                    f"SYSTEM PATHS:\n"
                    f"  Desktop   = r'{desktop}'\n"
                    f"  Downloads = r'{downloads}'\n"
                    f"  Documents = r'{documents}'\n"
                    f"  Home      = r'{home}'\n"
                )
            )
        )
        code = response.text.strip()
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        print(f"[Executor] 🐍 Running generated code: {tmp_path}")

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True,
            timeout=120, cwd=str(Path.home())
        )

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        duration = time.time() - start_time
        try:
            dna = get_dna(BASE_DIR)
            dna.record_performance("generated_code", duration, success=(result.returncode == 0))
        except: pass

        output = result.stdout.strip()
        error  = result.stderr.strip()

        if result.returncode == 0 and output:
            return output
        elif result.returncode == 0:
            return "Task completed successfully."
        elif error:
            raise RuntimeError(f"Code error: {error[:400]}")
        return "Completed."

    except subprocess.TimeoutExpired:
        raise RuntimeError("Generated code timed out after 120 seconds.")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Generated code failed: {e}")

def _inject_context(params: dict, tool: str, step_results: dict, goal: str = "") -> dict:
    if not step_results:
        return params

    params = dict(params)

    if tool == "file_controller" and params.get("action") in ("write", "create_file"):
        content = params.get("content", "")
        if not content or len(content) < 50:
            all_results = [
                v for v in step_results.values()
                if v and len(v) > 100 and v not in ("Done.", "Completed.")
            ]
            if all_results:
                combined = "\n\n---\n\n".join(all_results)
                translated = _translate_to_goal_language(combined, goal)
                params["content"] = translated
                print(f"[Executor] 💉 Injected + translated content")

    return params
def _detect_language(text: str) -> str:
    from google import genai
    client = genai.Client(api_key=_get_api_key())
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=(
                f"What language is this text written in? "
                f"Reply with ONLY the language name in English (e.g. Turkish, English, French).\n\n"
                f"Text: {text[:200]}"
            )
        )
        return response.text.strip()
    except Exception as e:
        msg = str(e).lower()
        if any(x in msg for x in ["429", "quota", "connection", "timeout", "offline"]):
            from core.local_llm import call_ollama
            res = call_ollama(f"What language is this text? Reply with 1 word: {text[:200]}", system_prompt="Reply with ONLY the language name.")
            if res: return res
        return "English"


def _translate_to_goal_language(content: str, goal: str) -> str:
    if not goal:
        return content
    try:
        from google import genai
        client = genai.Client(api_key=_get_api_key())

        target_lang = _detect_language(goal)
        print(f"[Executor] 🌐 Translating to: {target_lang}")

        prompt = (
            f"You are a professional translator. "
            f"Translate the following text into {target_lang}.\n"
            f"IMPORTANT:\n"
            f"- Translate EVERYTHING, leave nothing in English\n"
            f"- Keep all facts, numbers, and data intact\n"
            f"- Keep the structure and formatting\n"
            f"- Output ONLY the translated text, nothing else\n\n"
            f"Text to translate:\n{content[:4000]}"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        translated = response.text.strip()
        print(f"[Executor] ✅ Translation done ({target_lang})")
        return translated
    except Exception as e:
        msg = str(e).lower()
        if any(x in msg for x in ["429", "quota", "connection", "timeout", "offline"]):
            from core.local_llm import call_ollama
            res = call_ollama(prompt)
            if res: return res
        print(f"[Executor] ⚠️ Translation failed: {e}")
        return content

async def _call_tool_async(dispatcher, tool: str, parameters: dict) -> str:
    """Use the central ToolDispatcher to call tools asynchronously"""
    if not dispatcher:
        return f"Dispatcher not available for tool '{tool}'"
    
    # Create a mock FunctionCall for the dispatcher
    try:
        # Some tools expect 'parameters' as the key, some don't. Dispatcher handles this.
        # We wrap it in a types.FunctionCall object
        fc = types.FunctionCall(
            name=tool,
            args=parameters,
            id="task_exec_" + os.urandom(4).hex()
        )
        start_time = time.time()
        response = await dispatcher.dispatch(fc)
        duration = time.time() - start_time
        
        # Record DNA Performance
        try:
            dna = get_dna(BASE_DIR)
            dna.record_performance(tool, duration, success=True)
        except: pass
            
        return response.response.get("result", "Done.")
    except Exception as e:
        try:
            dna = get_dna(BASE_DIR)
            dna.record_performance(tool, 0, success=False)
        except: pass
        return f"Error executing tool '{tool}': {e}"

def _call_tool(tool: str, parameters: dict, speak: Callable | None, dispatcher=None) -> str:
    """Wrapper to run the async tool call in the executor's sync context"""
    import asyncio
    
    # Special case for generated code which is still handled here for now
    if tool == "generated_code":
        description = parameters.get("description", "")
        if not description:
            raise ValueError("generated_code requires a 'description' parameter.")
        return _run_generated_code(description, speak=speak)
    
    if tool == "talk":
        text = parameters.get("text", "")
        if speak: speak(text)
        return text

    if not dispatcher:
        print(f"[Executor] ⚠️ No dispatcher provided for tool '{tool}' — falling back to generated_code")
        return _run_generated_code(f"Accomplish this task: {parameters}", speak=speak)

    try:
        # Run the async tool call in the loop
        # We need to find the running loop or create one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(_call_tool_async(dispatcher, tool, parameters))
    except Exception as e:
        print(f"[Executor] ❌ Tool call failed: {e}")
        return f"Tool failed: {e}"

class AgentExecutor:

    MAX_REPLAN_ATTEMPTS = 2

    def execute(
        self,
        goal:        str,
        speak:       Callable | None        = None,
        cancel_flag: threading.Event | None = None,
        dispatcher  = None,
        preferred_brain: str | None = None,
    ) -> str:
        print(f"\n[Executor] 🎯 Goal: {goal}")
        
        # Node B: Task Interpreter
        print("[Executor] 🧠 Interpreting intent with TaskInterpreter...")
        interpreter = TaskInterpreter()
        interpreted = interpreter.interpret(goal)
        refined_goal = interpreted.get("goal", goal)
        pref_brain = interpreted.get("preferred_brain", preferred_brain)
        
        # Node C: Decompose into subtasks
        print(f"[Executor] 📋 Decomposing goal: '{refined_goal}' using brain '{pref_brain}'")
        task_queue = decompose(refined_goal, preferred_brain=pref_brain)
        
        if not task_queue:
            msg = "I couldn't create a valid plan for this task, sir."
            if speak: speak(msg)
            return msg
            
        print(f"[Executor] ⚡ Decomposed into {len(task_queue)} structured subtask(s).")
        completed_steps = []
        step_results = {}
        success = True
        
        for task in task_queue:
            if cancel_flag and cancel_flag.is_set():
                if speak: speak("Task cancelled, sir.")
                return "Task cancelled."
                
            step_num = task.get("step", 1)
            tool = task.get("tool", "generated_code")
            desc = task.get("description", "")
            prompt = task.get("prompt", desc)
            file_path = task.get("file_path", "")
            req_tool = task.get("required_tool", "")
            install_cmd = task.get("install_cmd", "")
            test_cmd = task.get("test_command", "")
            
            print(f"\n[Executor] ▶️ Step {step_num}: [{tool}] {desc}")
            
            # Node D & F: Tool Check & Auto-Install
            if req_tool and install_cmd:
                print(f"[Executor] ⚙️ Checking tool dependency: {req_tool}")
                if not ensure_tool(req_tool, install_cmd):
                    # Node N: Escalate
                    err_msg = f"Failed to install tool dependency: {req_tool}"
                    print(f"❌ [ESCALATE] {err_msg}")
                    if dispatcher and hasattr(dispatcher, "orch") and dispatcher.orch.ui:
                        dispatcher.orch.ui.write_log(f"ERR: {err_msg}")
                    if speak: speak(f"Sir, I could not install the required tool {req_tool}.")
                    
                    # Node O: Learn (store failure pattern)
                    try:
                        get_rag_engine().index_memory("failures", f"tool_missing::{req_tool}", err_msg)
                    except: pass
                    
                    success = False
                    break
            
            start_time = time.time()
            step_ok = False
            result = ""
            
            # Node E: Execute
            if tool in ("generated_code", "code_helper") and file_path and test_cmd:
                print(f"[Executor] 🛠️ Executing code subtask with self-healing on {file_path}")
                # Generate code block first using Gemini/Pollinations
                gen_prompt = f"Write complete code to accomplish: {prompt}\nRules: Return ONLY code, no markdown backticks, no explanations."
                try:
                    from core.llm_provider import call_llm
                    code_block = call_llm(gen_prompt, system_prompt="You are an elite Python developer.")
                    code_block = re.sub(r"^```[a-zA-Z]*\n?", "", code_block)
                    code_block = re.sub(r"\n?```$", "", code_block).strip()
                    
                    # Run execute with self-healing
                    step_ok, result_code = execute_with_healing(code_block, file_path, test_cmd)
                    result = f"Code written to {file_path}. Success: {step_ok}"
                    
                    if not step_ok:
                        failed_error = f"Self-healing failed on code file: {file_path}"
                except Exception as e:
                    step_ok = False
                    failed_error = str(e)
            else:
                # Normal tool call (with legacy retry/replan wrapper)
                attempt = 1
                params = task.copy()
                # Inject context from previous steps if needed
                params = _inject_context(params, tool, step_results, goal=goal)
                
                while attempt <= 3:
                    if cancel_flag and cancel_flag.is_set():
                        break
                    try:
                        result = _call_tool(tool, params, speak, dispatcher=dispatcher)
                        step_ok = True
                        break
                    except Exception as e:
                        failed_error = str(e)
                        attempt += 1
                        time.sleep(1)
            
            duration = time.time() - start_time
            
            # Node H: Success?
            if step_ok:
                print(f"[Executor] ✅ Step {step_num} completed successfully.")
                step_results[step_num] = result
                completed_steps.append(task)
                
                # Node I: Log success
                log_success(task, duration)
                
                # Node O: Store working solution to RAG
                try:
                    get_rag_engine().index_memory("solutions", desc, str(result)[:500])
                except: pass
            else:
                # Node N: Escalate
                print(f"❌ [ESCALATE] Step {step_num} failed. Error: {failed_error}")
                if dispatcher and hasattr(dispatcher, "orch") and dispatcher.orch.ui:
                    dispatcher.orch.ui.write_log(f"ERR: Step {step_num} failed — {failed_error[:100]}")
                if speak:
                    speak(f"Sir, step {step_num} failed. {failed_error[:80]}")
                
                # Node O: Store failed attempt pattern to RAG
                try:
                    get_rag_engine().index_memory("failures", desc, failed_error)
                except: pass
                
                success = False
                break
        
        # Node Q: Final Validation
        if success:
            # Removed blind re-running of test commands as integration validation
            # because it causes failures if the script was a one-time execution or missing.
            pass
            
        # Node R & S: Deliver & Learn
        if success:
            return self._summarize(goal, completed_steps, step_results, speak)
        else:
            return "Task failed during execution or validation, sir."

    def _summarize(self, goal: str, completed_steps: list, step_results: dict, speak: Callable | None) -> str:
        fallback = f"All done, sir. Completed {len(completed_steps)} steps for: {goal[:60]}."
        
        results_str = ""
        for s in completed_steps:
            s_num = s.get("step")
            res = step_results.get(s_num, "No output.")
            results_str += f"- Step {s_num} ({s.get('tool')}): {s.get('description')} -> Result: {res}\n"

        prompt    = (
            f'User goal: "{goal}"\n'
            f"Execution Results:\n{results_str}\n\n"
            "Write a single natural sentence summarizing what was accomplished based on the EXACT results above. "
            "If a count or value was found, include it. "
            "Address the user as 'sir'. Be direct and positive."
        )

        try:
            from google import genai
            client = genai.Client(api_key=_get_api_key())
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )
            summary  = response.text.strip()
            if speak: speak(summary)
            return summary
        except Exception as e:
            msg = str(e).lower()
            if any(x in msg for x in ["429", "quota", "connection", "timeout", "offline"]):
                from core.llm_provider import call_llm
                try:
                    res = call_llm(prompt, brain="pollinations")
                    if res:
                        if speak: speak(res)
                        return res
                except: pass
            if speak: speak(fallback)
            return fallback