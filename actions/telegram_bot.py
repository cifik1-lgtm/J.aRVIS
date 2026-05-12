import threading
import json
from pathlib import Path
import sys

try:
    import telebot
    HAS_TELEBOT = True
except ImportError:
    HAS_TELEBOT = False

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

API_CONFIG_PATH = get_base_dir() / "config" / "api_keys.json"
_bot_thread = None
_bot_instance = None
_allowed_chat_id = None
_queue_ref = None
_speak_ref = None

def get_config():
    if API_CONFIG_PATH.exists():
        try:
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                token = data.get("telegram_bot_token")
                chat_id = data.get("telegram_chat_id")
                if token and token != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
                    return {"bot_token": token, "allowed_chat_id": chat_id}
        except: pass
    return None
    return None

def save_config(cfg):
    # No longer used since we consolidated, but kept for compatibility
    pass

def start_telegram_bot(queue, speak=None):
    global _bot_thread, _bot_instance, _allowed_chat_id, _queue_ref, _speak_ref
    if not HAS_TELEBOT: return
    if _bot_thread is not None: return
    
    cfg = get_config()
    if not cfg or not cfg.get("bot_token") or cfg["bot_token"] == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        return
        
    _bot_instance = telebot.TeleBot(cfg["bot_token"])
    _allowed_chat_id = str(cfg.get("allowed_chat_id", ""))
    _queue_ref = queue
    _speak_ref = speak
    
    @_bot_instance.message_handler(func=lambda message: True)
    def handle_message(message):
        chat_id = str(message.chat.id)
        cfg = get_config()
        
        if not cfg.get("allowed_chat_id"):
            cfg["allowed_chat_id"] = chat_id
            save_config(cfg)
            global _allowed_chat_id
            _allowed_chat_id = chat_id
            _bot_instance.reply_to(message, f"You are now registered as the owner of this Jarvis instance. (Chat ID: {chat_id})")
            return
            
        text = message.text
        if text and _queue_ref:
            from agent.task_queue import TaskPriority
            
            # Multi-PC Routing Logic
            device_name = "JARVIS"
            current_allowed_id = str(cfg.get("allowed_chat_id", "")).strip()
            
            # Group ID check (Group IDs start with -)
            is_group = chat_id.startswith("-")

            # Security Check
            if current_allowed_id and chat_id != current_allowed_id:
                # If it's a new group/user, JARVIS will tell you the ID so you can authorize it
                _bot_instance.reply_to(message, f"Unauthorized. ID: {chat_id}")
                return

            try:
                # Get the local device name
                main_cfg_path = get_base_dir() / "config" / "api_keys.json"
                if main_cfg_path.exists():
                    main_cfg = json.loads(main_cfg_path.read_text(encoding="utf-8"))
                    device_name = main_cfg.get("device_name", "JARVIS").upper()
            except: pass

            # Flexible Name Matching
            is_for_me = False
            raw_text = text if text else ""
            
            print(f"[Telegram] 👂 Heard: '{raw_text}' from {message.from_user.first_name} (Bot: {message.from_user.is_bot})")

            if ":" in raw_text:
                parts = raw_text.split(":", 1)
                prefix = parts[0].strip().upper()
                command_text = parts[1].strip()
                
                # Match if prefix is my name or contains my name (e.g. "EVA-PC" matches "EVA")
                # We allow bots to trigger this!
                if prefix == device_name or device_name in prefix or prefix == "ALL":
                    is_for_me = True
                    text = command_text # Strip the prefix for processing
            else:
                # If no prefix, only respond if it's NOT from another bot 
                # (to prevent loops unless explicitly addressed)
                if not message.from_user.is_bot:
                    is_for_me = True

            # HARD-ROUTING: If user says "on [another pc]", relay it and STOP locally.
            if not message.from_user.is_bot and ":" not in raw_text:
                lower_text = raw_text.lower()
                target_pc = None
                if "on eva" in lower_text: target_pc = "EVA"
                elif "on cifik" in lower_text: target_pc = "CIFIK"
                
                if target_pc and target_pc != device_name:
                    print(f"[Telegram] 🔀 Hard-Routing detected for {target_pc}. Relaying and stopping locally.")
                    from actions.ghost_relay import publish_command
                    # Clean the command (remove the "on device" part)
                    clean_cmd = re.sub(r"(?i)\s*on\s+(eva|cifik|jarvis)(\s+pc)?", "", raw_text).strip()
                    publish_command(target_pc, clean_cmd)
                    _bot_instance.reply_to(message, f"Relaying to {target_pc}: {clean_cmd[:20]}...")
                    return # STOP HERE! Do not execute locally.

            if is_for_me:
                # Clean up the command: strip the device prefix and any "on [device]" suffixes
                clean_text = text
                if ":" in clean_text: clean_text = clean_text.split(":", 1)[1].strip()
                
                # Remove common routing phrases that cause recursive relaying
                clean_text = re.sub(r"(?i)\s*on\s+(eva|cifik|jarvis)(\s+pc)?", "", clean_text).strip()
                clean_text = re.sub(r"(?i)tell\s+(eva|cifik|jarvis)(\s+to\s+)?", "", clean_text).strip()

                print(f"[Telegram] 🎯 Executing clean command: {clean_text}")
                from agent.task_queue import TaskPriority
                _queue_ref.submit(goal=clean_text, priority=TaskPriority.HIGH)
                _bot_instance.reply_to(message, f"[{device_name}] Executing: {clean_text[:20]}...")
            
            if _speak_ref:
                try: _speak_ref(f"Sir, new remote command received for {device_name}.")
                except: pass
            
    def run_bot():
        print("[Telegram] 👂 Thread starting... checking for messages.")
        import time
        import random
        import logging
        
        # Suppress telebot's internal error logging to console
        logger = logging.getLogger('TeleBot')
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        logger.addHandler(logging.NullHandler())

        while True:
            try:
                _bot_instance.polling(none_stop=True, timeout=30, long_polling_timeout=30)
            except Exception as e:
                err_msg = str(e)
                if "Conflict" in err_msg or "409" in err_msg:
                    wait_time = random.randint(60, 120)
                    print(f"[Telegram] ! Connection on standby (Another instance active). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    time.sleep(10)
            
    _bot_thread = threading.Thread(target=run_bot, daemon=True)
    _bot_thread.start()
    print(f"[Telegram] 🤖 Unified Bot Listener active for '{_allowed_chat_id}'")

def telegram_manager(parameters: dict, player=None) -> str:
    action = parameters.get("action", "send")
    text = parameters.get("text", "")
    # 1. Try to load from telegram_keys.json or main api_keys.json
    cfg = get_config()
    bot_token = None
    chat_id = None
    
    if cfg:
        bot_token = cfg.get("bot_token")
        chat_id = cfg.get("allowed_chat_id")

    # Final Fallback: Check api_keys.json directly if get_config missed it
    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        try:
            main_cfg_path = get_base_dir() / "config" / "api_keys.json"
            if main_cfg_path.exists():
                main_data = json.loads(main_cfg_path.read_text(encoding="utf-8"))
                bot_token = main_data.get("telegram_bot_token")
                chat_id = main_data.get("telegram_chat_id", chat_id)
        except: pass

    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        return "Telegram bot is not configured. (Token missing)"
        
    if action == "send":
        if not HAS_TELEBOT: return "telebot library not installed."
        
        target_token = bot_token
        target_chat_id = chat_id
        
        # We always use our LOCAL token to broadcast in the group.
        # This way, the OTHER bot (the target) can hear us.
        target_token = bot_token
        
        try:
            # 1. Standard Telegram Broadcast
            final_chat_id = target_chat_id
            try: final_chat_id = int(target_chat_id)
            except: pass

            temp_bot = telebot.TeleBot(target_token)
            temp_bot.send_message(final_chat_id, text)
            
            # 2. GHOST RELAY BACKUP (The real workhorse)
            try:
                from actions.ghost_relay import publish_command
                if ":" in text:
                    target_name, cmd_text = text.split(":", 1)
                    import json
                    from pathlib import Path
                    cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
                    my_name = json.loads(cfg_path.read_text(encoding="utf-8")).get("device_name", "").upper()
                    if target_name.upper() != my_name:
                        publish_command(target_name.strip(), cmd_text.strip())
            except: pass

            return f"Broadcasted command for {text.split(':', 1)[0] if ':' in text else 'network'}."
        except Exception as e:
            err_msg = str(e)
            print(f"[Telegram] ❌ Relay failed: {err_msg}")
            return f"Relay failed: {err_msg[:100]}"
            
    return "Unknown action."
