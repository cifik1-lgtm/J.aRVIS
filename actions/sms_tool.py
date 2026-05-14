import os
import json
from pathlib import Path
from smsmobileapi import SMSSender

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

class SMSManager:
    def __init__(self, ui=None):
        self.ui = ui
        self.api_key = self._load_api_key()
        
        if not self.api_key:
            error_msg = "SMSMOBILEAPI_KEY not found in environment or config/api_keys.json."
            if self.ui:
                self.ui.write_log(f"[SMSManager] ❌ {error_msg}")
            raise ValueError(error_msg)
        
        # Initialize the SMS sender
        self.sms = SMSSender(api_key=self.api_key)

    def _load_api_key(self):
        # 1. Check environment variable
        key = os.getenv('SMSMOBILEAPI_KEY')
        if key:
            return key
            
        # 2. Check api_keys.json
        if API_CONFIG_PATH.exists():
            try:
                with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("smsmobileapi_key")
            except Exception:
                pass
        return None

    def send_sms(self, to_number: str, message_body: str) -> dict:
        """
        Send an SMS message using your connected phone.
        """
        if self.ui:
            self.ui.write_log(f"[SMSManager] 📤 Sending SMS to {to_number}...")
            
        try:
            response = self.sms.send_message(to=to_number, message=message_body)
            if self.ui:
                self.ui.write_log(f"[SMSManager] ✅ SMS sent successfully.")
            return {"status": "success", "response": response}
        except Exception as e:
            if self.ui:
                self.ui.write_log(f"[SMSManager] ❌ Error sending SMS: {e}")
            return {"status": "error", "message": str(e)}

    def check_received_messages(self) -> dict:
        """
        Retrieve received SMS messages from your connected phone.
        """
        if self.ui:
            self.ui.write_log("[SMSManager] 📥 Checking for received messages...")
            
        try:
            messages = self.sms.get_received_messages()
            if self.ui:
                self.ui.write_log(f"[SMSManager] ✅ Retrieved {len(messages) if messages else 0} messages.")
            return {"status": "success", "messages": messages}
        except Exception as e:
            if self.ui:
                self.ui.write_log(f"[SMSManager] ❌ Error retrieving messages: {e}")
            return {"status": "error", "message": str(e)}

def sms_tool(parameters: dict, player=None, **kwargs) -> str:
    """
    JARVIS tool entry point for SMS operations.
    Actions: 'send', 'receive'
    """
    action = parameters.get("action", "send")
    
    try:
        # Use player as UI if available
        mgr = SMSManager(ui=player)
        
        if action == "send":
            to = str(parameters.get("to", "")).strip()
            msg = parameters.get("message", "").strip()
            
            if not to or not msg:
                return "Error: Both 'to' (number) and 'message' are required for sending SMS."
            
            # Clean number: remove '+', '00', spaces, dashes
            clean_to = "".join(filter(str.isdigit, to))
            
            result = mgr.send_sms(clean_to, msg)
            if result["status"] == "success":
                return f"Successfully sent SMS to {to}: '{msg}'"
            else:
                return f"Failed to send SMS: {result['message']}"
                
        elif action == "receive":
            result = mgr.check_received_messages()
            if result["status"] == "success":
                msgs = result.get("messages", [])
                if not msgs:
                    return "No new messages received, sir."
                
                formatted_msgs = []
                for m in msgs:
                    sender = m.get('from', 'Unknown')
                    text = m.get('message', '')
                    time = m.get('received_at', 'Unknown time')
                    formatted_msgs.append(f"From {sender} at {time}: {text}")
                
                return "Received messages:\n" + "\n".join(formatted_msgs)
            else:
                return f"Failed to retrieve messages: {result['message']}"
        
        else:
            return f"Unknown SMS action: {action}. Use 'send' or 'receive'."
            
    except Exception as e:
        return f"SMS tool error: {e}"
