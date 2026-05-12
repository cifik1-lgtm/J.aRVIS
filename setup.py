import subprocess
import sys
import platform
import os
import json
from pathlib import Path

def run_command(command, description):
    print(f"\n📦 {description}...")
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}: {e}")
        return False

def setup():
    print("🤖 JARVIS MARK XXV - Cifik Intelegents Setup")
    print("=" * 50)

    # 1. Install Python requirements
    run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], "Installing Python requirements")

    # 2. Install Playwright browsers
    run_command([sys.executable, "-m", "playwright", "install", "chromium"], "Installing Playwright (Chromium)")

    # 3. Check for Ollama
    print("\n🧠 Checking for Ollama (local AI)...")
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Ollama detected: {result.stdout.strip()}")
            print("📥 Pulling recommended local models (phi3:mini)...")
            # Run in background or inform it might take time
            subprocess.run(["ollama", "pull", "phi3:mini"], check=False)
        else:
            print("⚠️ Ollama found but returned error. Check installation.")
    except FileNotFoundError:
        print("⚠️ Ollama not found. Install from https://ollama.ai for local AI fallback.")

    # 4. Check/Create Config
    print("\n🔑 Verifying API configuration...")
    config_dir = Path("config")
    config_path = config_dir / "api_keys.json"
    
    config_dir.mkdir(exist_ok=True)
    
    if not config_path.exists():
        print("⚠️ Config file not found. Creating template...")
        template = {
            "gemini_api_key": "",
            "openrouter_api_key": "",
            "openrouter_model": "deepseek/deepseek-chat",
            "minimax_api_key": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "autonomous_mode": True,
            "force_brain": "hive",
            "device_name": platform.node(),
            "os_system": platform.system().lower()
        }
        with open(config_path, "w") as f:
            json.dump(template, f, indent=4)
        print(f"✅ Created {config_path} - PLEASE ADD YOUR KEYS!")
    else:
        print(f"✅ Config file detected at {config_path}")

    # 5. Create directories
    for d in ["memory", "recordings", "actions/temp", "logs"]:
        Path(d).mkdir(exist_ok=True)
        print(f"✅ Directory verified: {d}")

    print("\n" + "=" * 50)
    print("✅ Setup complete! JARVIS is ready for activation.")
    print("\n🚀 To start JARVIS:")
    print("   python main.py")
    print("\n📝 Note: Ensure your API keys are set in config/api_keys.json")
    print("=" * 50)

if __name__ == "__main__":
    setup()
