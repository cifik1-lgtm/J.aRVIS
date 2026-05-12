# JARVIS Mark-XXXIX
**The Ultimate Autonomous AI Orchestrator**

JARVIS Mark-XXXIX is a high-performance, multi-brain agentic system designed for seamless automation, software development, and real-time interaction. Powered by the latest Gemini 2.0 Multimodal Live technology and a resilient cloud/local fallback architecture.

## 🚀 Key Features
- **Multimodal Intelligence**: Real-time voice and vision capabilities via Gemini 2.0.
- **Software Factory**: Autonomous coding, project planning, and EXE compilation.
- **Multi-Brain Routing**: Intelligent failover between Gemini, OpenRouter (DeepSeek), MiniMax, and Local Ollama.
- **Ghost Relay**: Decentralized command routing across the Jarvis Network (EVA/CIFIK).
- **Tool Suite**: Full control over browsers, files, system settings, and media downloads.

## 🛠️ Architecture
- **Core**: `main.py` (Orchestrator), `ui.py` (Holographic HUD).
- **Intelligence**: `core/llm_provider.py` (Resilient Router).
- **Agents**: `agent/planner.py` (Strategist), `actions/dev_agent.py` (Developer).
- **Communication**: `actions/telegram_bot.py` (Relay), `actions/ghost_relay.py` (Network).

## 📦 Installation
1. Install Python 3.12+.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```
3. Configure `config/api_keys.json` with your credentials.
4. Run the main orchestrator:
   ```bash
   python main.py
   ```

## ⚙️ Requirements
- Windows 10/11
- GPU Acceleration (AMD/NVIDIA) for HUD and Local LLM.
- Active Internet for Cloud Brains (Gemini/MiniMax).

---
*Built for the hive-mind by Antigravity.*
