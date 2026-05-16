import gradio as gr
import json
import os
import time
from pathlib import Path
from datetime import datetime

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
MEMORY_DIR = BASE_DIR / "memory"
TASK_FILE = MEMORY_DIR / "task_queue_telemetry.json"
HEALING_FILE = MEMORY_DIR / "self_healing_logs.json"
RELOAD_FILE = MEMORY_DIR / "hot_reload_logs.json"

def get_tasks():
    try:
        if TASK_FILE.exists():
            data = json.loads(TASK_FILE.read_text(encoding="utf-8"))
            return [[t['task_id'], t['goal'], t['status']] for t in data[::-1]]
    except:
        pass
    return []

def get_healing():
    try:
        if HEALING_FILE.exists():
            data = json.loads(HEALING_FILE.read_text(encoding="utf-8"))
            return [[t['timestamp'].split('T')[1][:8], t['message']] for t in data[::-1]]
    except:
        pass
    return []

def get_reloads():
    try:
        if RELOAD_FILE.exists():
            data = json.loads(RELOAD_FILE.read_text(encoding="utf-8"))
            return [[t['timestamp'].split('T')[1][:8], t['message']] for t in data[::-1]]
    except:
        pass
    return []

def get_status():
    # Placeholder for live system status
    return "🟢 HIVE ONLINE | 🧠 GEMINI 2.0 LIVE | 🎙️ MIC ACTIVE"

# --- Dashboard UI ---
with gr.Blocks(fill_height=True, title="JARVIS HIVE COMMAND") as demo:
    gr.Markdown("""
    # 🛰️ **JARVIS HIVE COMMAND CENTER** 🦾
    *Real-time neural synchronization and autonomous goal monitoring.*
    """)
    
    with gr.Row():
        status_box = gr.Textbox(label="System Pulse", value=get_status(), interactive=False)
        
    with gr.Tabs():
        with gr.Tab("🎯 Active Goals"):
            task_table = gr.Dataframe(
                headers=["ID", "Goal", "Status"],
                datatype=["str", "str", "str"],
                value=get_tasks(),
                interactive=False
            )
            refresh_tasks = gr.Button("🔄 Refresh Pulse")
            
        with gr.Tab("🛠️ Neural Repairs"):
            healing_table = gr.Dataframe(
                headers=["Time", "Event"],
                datatype=["str", "str"],
                value=get_healing(),
                interactive=False
            )
            
        with gr.Tab("🧠 Skill Sync"):
            reload_table = gr.Dataframe(
                headers=["Time", "Neural Sync"],
                datatype=["str", "str"],
                value=get_reloads(),
                interactive=False
            )

    def update_all():
        return get_tasks(), get_healing(), get_reloads(), get_status()

    # Auto-refresh logic
    timer = gr.Timer(5)
    timer.tick(update_all, outputs=[task_table, healing_table, reload_table, status_box])
    refresh_tasks.click(update_all, outputs=[task_table, healing_table, reload_table, status_box])

if __name__ == "__main__":
    print("[HiveDashboard] 🚀 Launching Command Center...")
    demo.launch(
        server_name="127.0.0.1", 
        server_port=18788, 
        share=False,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate")
    )
