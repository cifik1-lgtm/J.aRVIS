import sys
import io
import contextlib
import traceback
import textwrap

def python_sandbox(parameters: dict, player=None) -> str:
    code = parameters.get("code", "")
    if not code:
        return "No code provided to execute."
        
    code = textwrap.dedent(code)
    
    output_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            # Safe execution namespace
            local_vars = {}
            exec(code, {}, local_vars)
            
        output = output_buffer.getvalue()
        if not output:
            output = "Code executed successfully with no output."
        return f"Execution Output:\n{output}"
        
    except Exception as e:
        err = traceback.format_exc()
        return f"Execution Error:\n{err}"
