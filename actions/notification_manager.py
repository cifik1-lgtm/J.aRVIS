try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

def notification_manager(parameters: dict, player=None) -> str:
    if not HAS_PLYER:
        return "Plyer library not installed. Run: pip install plyer"
        
    title = parameters.get("title", "Jarvis")
    message = parameters.get("message", "")
    timeout = parameters.get("timeout", 5)
    
    if not message:
        return "No message provided for notification."
        
    try:
        notification.notify(
            title=title,
            message=message,
            app_name='Jarvis Assistant',
            timeout=timeout
        )
        if player:
            player.write_log(f"🔔 Notification sent: {title} - {message}")
        return f"Desktop notification displayed: {title}"
    except Exception as e:
        return f"Notification failed: {str(e)}"
