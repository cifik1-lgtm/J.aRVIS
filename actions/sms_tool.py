import os
import json
from pathlib import Path
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

class SMSManager:
    def __init__(self, ui=None):
        self.ui = ui
        self.api_key = self._load_api_key()
        
        if not self.api_key:
            error_msg = "SMSMOBILEAPI_KEY not found"
            if self.ui:
                self.ui.write_log(f"[SMSManager] ❌ {error_msg}")
            raise ValueError(error_msg)
        
        if self.ui:
            self.ui.write_log(f"[SMSManager] ✅ Initialized")

    def _load_api_key(self):
        # Check environment variable
        key = os.getenv('SMSMOBILEAPI_KEY')
        if key:
            return key
            
        # Check api_keys.json
        if API_CONFIG_PATH.exists():
            try:
                with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("smsmobileapi_key")
            except Exception:
                pass
        return None

    def send_sms(self, to_number: str, message_body: str) -> dict:
        """Send SMS - uses port=0 for immediate sending"""
        
        # Clean number: remove '+', spaces, dashes
        clean_number = "".join(filter(str.isdigit, to_number))
        
        base_url = "https://api.smsmobileapi.com/sendsms/"
        
        params = {
            'apikey': self.api_key,
            'recipients': clean_number,
            'message': message_body,
            'port': '0'  # Key fix - matches working curl
        }
        
        if self.ui:
            self.ui.write_log(f"[SMSManager] 📤 Sending to {clean_number}")
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            result = response.json()
            
            if self.ui:
                self.ui.write_log(f"[SMSManager] 📥 Response: {result}")
            
            if result.get('result', {}).get('error') == 0:
                if self.ui:
                    self.ui.write_log(f"[SMSManager] ✅ Sent!")
                return {"status": "success", "response": result}
            else:
                error_code = result.get('result', {}).get('error')
                return {"status": "error", "message": f"API error {error_code}"}
                
        except Exception as e:
            if self.ui:
                self.ui.write_log(f"[SMSManager] ❌ Error: {e}")
            return {"status": "error", "message": str(e)}

def sms_tool(parameters: dict, player=None, **kwargs) -> str:
    """JARVIS tool entry point for SMS operations"""
    action = parameters.get("action", "send")
    
    try:
        mgr = SMSManager(ui=player)
        
        if action == "send":
            to = str(parameters.get("to", "")).strip()
            msg = parameters.get("message", "").strip()
            
            if not to or not msg:
                return "Error: Both 'to' and 'message' are required."
            
            result = mgr.send_sms(to, msg)
            if result["status"] == "success":
                return f"✅ SMS sent successfully to {to}"
            else:
                return f"❌ Failed: {result['message']}"
        
        else:
            return f"Unknown action: {action}. Use 'send'."
            
    except Exception as e:
        return f"SMS tool error: {e}"