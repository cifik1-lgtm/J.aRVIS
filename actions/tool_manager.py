import subprocess
import shutil

def ensure_tool(tool_name: str, install_command: str) -> bool:
    """Check if a CLI tool is available. If not, auto-install it."""
    if shutil.which(tool_name) is None:
        print(f"⚙️ [TOOL MISSING] {tool_name}. Auto-installing...")
        try:
            # Run the installation command in a shell
            subprocess.run(install_command, shell=True, check=True)
            print(f"✅ [INSTALLED] {tool_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ [FAILED] Could not install {tool_name}: {e}")
            return False
    return True
