import smtplib
from email.message import EmailMessage
import json
from pathlib import Path
import sys

try:
    from imap_tools import MailBox, AND
    HAS_IMAP = True
except ImportError:
    HAS_IMAP = False

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

CONFIG_PATH = get_base_dir() / "config" / "email_keys.json"

def get_config():
    if not CONFIG_PATH.exists():
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def email_manager(parameters: dict, player=None) -> str:
    cfg = get_config()
    if not cfg:
        if not CONFIG_PATH.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps({
                "email": "your_email@gmail.com",
                "password": "your_app_password",
                "imap_server": "imap.gmail.com",
                "smtp_server": "smtp.gmail.com"
            }, indent=4))
        return (
            "Email is not configured. I have created config/email_keys.json. "
            "Please add your email, an app password, and IMAP/SMTP server details."
        )
        
    action = parameters.get("action", "read")
    
    try:
        if action == "send":
            to = parameters.get("to", "")
            subject = parameters.get("subject", "")
            body = parameters.get("body", "")
            if not to: return "No recipient provided."
            
            msg = EmailMessage()
            msg.set_content(body)
            msg["Subject"] = subject
            msg["From"] = cfg["email"]
            msg["To"] = to
            
            with smtplib.SMTP_SSL(cfg["smtp_server"], 465) as smtp:
                smtp.login(cfg["email"], cfg["password"])
                smtp.send_message(msg)
            return f"Email successfully sent to {to}."
            
        elif action == "read":
            if not HAS_IMAP:
                return "imap-tools is not installed. Run: python -m pip install imap-tools"
            limit = int(parameters.get("limit", 5))
            with MailBox(cfg["imap_server"]).login(cfg["email"], cfg["password"], 'INBOX') as mailbox:
                emails = []
                for msg in mailbox.fetch(AND(seen=False), limit=limit, reverse=True):
                    emails.append(f"From: {msg.from_}\nSubject: {msg.subject}\nPreview: {msg.text[:120]}...\n")
                if not emails:
                    return "No unread emails found in your inbox."
                return "Unread Emails:\n\n" + "\n".join(emails)
    except Exception as e:
        return f"Email error: {str(e)}"
    return "Unknown action."
