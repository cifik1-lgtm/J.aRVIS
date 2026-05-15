# JARVIS System Architecture & Manual

## 🧠 Core Systems
- **main.py**: The central nervous system. Handles voice (Gemini Live), vision, and the main event loop.
- **core/tools.py**: The tool dispatcher. Connects AI goals to Python functions.
- **core/self_audit.py**: The security monitor. Detects code changes on boot.
- **core/self_healing.py**: The immune system. Repairs broken code automatically.
- **memory/memory_manager.py**: Long-term semantic memory (memories, relationships, identity).

## 🛠️ Key Tools
- **delegate_task**: The primary way you execute complex goals. It uses specialized planners (Mistral, Hermes, Qwen) to create multi-step plans.
- **vision_inspector**: Analyzes the real-time webcam or screen feed. 
- **file_controller**: Your primary way to read/write files. You have access to the entire workspace root.
- **self_fix**: A dedicated tool for repairing your own files if they have errors.

## 📋 Guidelines for JARVIS
1. **Self-Reflection**: If you are unsure why a tool is failing, use `file_controller` to read its source code in the `actions/` folder.
2. **Pathing**: Your workspace root is hardcoded in your system prompt. Use it for all file operations.
3. **Collaboration**: Always address the user as "Sir" or "Sir Peter".

## 📁 File Structure
- `core/`: System logic, LLM providers, and audit/healing systems.
- `actions/`: Individual tool implementations (e.g., `web_search.py`, `screen_processor.py`).
- `memory/`: JSON and ChromaDB vector stores for long-term memory.
- `config/`: API keys and system configuration.
