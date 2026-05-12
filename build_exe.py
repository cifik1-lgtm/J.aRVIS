import subprocess
import sys
import os
import shutil

def build():
    print("Starting Build Process for JARVIS Mark-XXXIX...")
    
    # 1. Install PyInstaller if not present
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # 2. Define the build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "JARVIS_Mark_XXXIX",
        "--windowed",             # No console window
        "--onefile",              # COMPACT MODE: One single EXE
        "--noconfirm",            # Overwrite existing dist
        "--clean",                # Clean cache
        "--add-data", "actions;actions", 
        "--add-data", "core;core",
        "--add-data", "config;config",
        "--add-data", "memory;memory",
        "main.py"
    ]

    print(f"Executing PyInstaller command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    print("\nBUILD COMPLETE!")
    print(f"Your standalone EXE is located in: {os.path.abspath('dist')}")
    print("You can now move the JARVIS_Mark_XXXIX.exe anywhere!")

if __name__ == "__main__":
    build()
