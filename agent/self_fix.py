import subprocess
import re
from core.llm_provider import call_llm

MAX_RETRIES = 3

def execute_with_healing(code_block: str, file_path: str, test_command: str) -> tuple[bool, str]:
    """Write code, test it, and self-heal up to MAX_RETRIES times."""
    current_code = code_block
    for attempt in range(MAX_RETRIES):
        # 1. Write code to file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(current_code)
        except Exception as e:
            print(f"❌ [WRITE ERROR] Failed to write to {file_path}: {e}")
            return False, current_code

        # 2. Run the test command
        print(f"⚙️ Running test command '{test_command}' (Attempt {attempt + 1}/{MAX_RETRIES})...")
        result = subprocess.run(test_command, shell=True, capture_output=True, text=True)

        # 3. Success!
        if result.returncode == 0:
            print(f"✅ [PASS] Attempt {attempt + 1}")
            return True, current_code

        # 4. Failure - Heal
        err_output = result.stderr.strip() or result.stdout.strip()
        print(f"⚠️ [FAIL] Attempt {attempt + 1}. Error: {err_output[:200]}")

        # 5. Ask Gemini/LLM to fix the code
        fix_prompt = f"""
The following code failed the test command '{test_command}'.
ERROR OUTPUT:
{err_output}

ORIGINAL CODE:
{current_code}

Provide the complete, corrected code block. Do not add explanations. Return ONLY the code block.
"""
        try:
            response = call_llm(fix_prompt, system_prompt="You are an expert Python developer and system architect.")
            # Clean markdown codeblocks if present
            response = re.sub(r"^```[a-zA-Z]*\n?", "", response)
            response = re.sub(r"\n?```$", "", response)
            current_code = response.strip()
        except Exception as e:
            print(f"❌ [HEAL ERROR] LLM call failed: {e}")
            break

    # All retries exhausted
    return False, current_code
