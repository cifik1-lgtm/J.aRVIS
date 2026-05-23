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
API_FILE = BASE_DIR / "config" / "api_keys.json"

def load_settings():
    if API_FILE.exists():
        try:
            return json.loads(API_FILE.read_text(encoding="utf-8"))
        except: pass
    return {}

def save_settings(gemini, poe, telegram_token, telegram_chat, sms_key):
    data = {}
    if API_FILE.exists():
        try:
            data = json.loads(API_FILE.read_text(encoding="utf-8"))
        except: pass
    
    data["gemini_api_key"] = gemini
    data["poe_api_key"] = poe
    data["telegram_bot_token"] = telegram_token
    data["telegram_chat_id"] = telegram_chat
    data["smsmobileapi_key"] = sms_key

    try:
        API_FILE.parent.mkdir(exist_ok=True)
        API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return "🟢 Settings saved successfully! The HUD will synchronize in real-time."
    except Exception as e:
        return f"🔴 Failed to save settings: {e}"

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
            
        with gr.Tab("⚙️ System Cores"):
            gr.Markdown("### ⚙️ **J.A.R.V.I.S Neural Settings**")
            cfg = load_settings()
            
            with gr.Group():
                gr.Markdown("#### **Primary AI Cognitive Cores**")
                gemini_input = gr.Textbox(label="Gemini API Key", value=cfg.get("gemini_api_key", ""), type="password")
                poe_input = gr.Textbox(label="Poe API Key", value=cfg.get("poe_api_key", ""), type="password")
                
            with gr.Group():
                gr.Markdown("#### **Communications & Telemetry**")
                tg_token_input = gr.Textbox(label="Telegram Bot Token", value=cfg.get("telegram_bot_token", ""), type="password")
                tg_chat_input = gr.Textbox(label="Telegram Chat ID", value=cfg.get("telegram_chat_id", ""))
                sms_input = gr.Textbox(label="SMS Mobile API Key", value=cfg.get("smsmobileapi_key", ""), type="password")
                
            save_status = gr.Markdown()
            save_settings_btn = gr.Button("💾 Save and Synchronize Settings", variant="primary")
            
            save_settings_btn.click(
                save_settings, 
                inputs=[gemini_input, poe_input, tg_token_input, tg_chat_input, sms_input], 
                outputs=[save_status]
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
