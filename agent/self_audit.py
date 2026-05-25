import subprocess

def audit_success(file_path: str, test_command: str) -> tuple[bool, str]:
    """Run a test/linter on a specific file and check if it succeeds."""
    print(f"🔍 [AUDIT] Auditing success of {file_path} using '{test_command}'...")
    try:
        result = subprocess.run(test_command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return True, "Audit passed."
        else:
            err = result.stderr.strip() or result.stdout.strip()
            return False, f"Audit failed: {err}"
    except Exception as e:
        return False, f"Audit execution failed: {e}"

def validate_integration(project_path: str, validation_command: str) -> tuple[bool, str]:
    """Run final integration validation for the whole project."""
    print(f"🛡️ [VALIDATION] Running integration tests using '{validation_command}' in '{project_path}'...")
    try:
        result = subprocess.run(validation_command, shell=True, capture_output=True, text=True, cwd=project_path)
        if result.returncode == 0:
            return True, "Integration validation passed."
        else:
            err = result.stderr.strip() or result.stdout.strip()
            return False, f"Integration validation failed: {err}"
    except Exception as e:
        return False, f"Integration validation execution failed: {e}"
