import os
import sys
import zipfile
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STUB_FILE = BASE_DIR / "installer_stub.py"
BUILD_DIR = BASE_DIR / "build"
DIST_DIR = BASE_DIR / "dist"
FINAL_EXE = BASE_DIR / "JARVIS_Setup.exe"

def build():
    print("Starting JARVIS Installer Build Process...")
    
    # 1. Compile the stub with PyInstaller
    print("Compiling installer GUI...")
    try:
        subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--onefile",
            "--windowed",
            "--name", "installer_stub",
            "--clean",
            str(STUB_FILE)
        ], check=True)
    except subprocess.CalledProcessError:
        print("PyInstaller failed. Make sure it is installed: pip install pyinstaller")
        return

    stub_exe = DIST_DIR / "installer_stub.exe"
    if not stub_exe.exists():
        print("Failed to find compiled stub.")
        return

    # 2. Create the ZIP archive
    zip_path = BASE_DIR / "project_payload.zip"
    print(f"Zipping project files (This may take a few minutes depending on size)...")
    
    # Items to exclude from the zip
    exclude_dirs = {'.git', '.venv', '__pycache__', 'build', 'dist', 'installer_stub.spec'}
    exclude_files = {'project_payload.zip', 'JARVIS_Setup.exe', 'installer_stub.py', 'build_installer.py'}
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_DIR):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file in exclude_files or file.endswith('.pyc'):
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, BASE_DIR)
                zf.write(file_path, rel_path)

    zip_size = zip_path.stat().st_size
    print(f"Created ZIP payload: {zip_size / (1024*1024):.2f} MB")

    # 3. Combine Stub + Zip
    print(f"Linking GUI and Payload into {FINAL_EXE.name}...")
    with open(FINAL_EXE, 'wb') as final:
        # Write EXE
        with open(stub_exe, 'rb') as exe:
            final.write(exe.read())
        
        # Write ZIP
        with open(zip_path, 'rb') as z:
            final.write(z.read())
            
        # Write zip size padded to 8 bytes at the very end
        size_str = str(zip_size).zfill(8).encode('utf-8')
        final.write(size_str)

    print("Cleaning up temporary files...")
    if zip_path.exists(): os.remove(zip_path)
    if BUILD_DIR.exists(): shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists(): shutil.rmtree(DIST_DIR)
    if (BASE_DIR / "installer_stub.spec").exists(): os.remove(BASE_DIR / "installer_stub.spec")

    print(f"\nSUCCESS! Installer created at:\n{FINAL_EXE}")

if __name__ == "__main__":
    build()
