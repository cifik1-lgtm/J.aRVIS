"""
Simple IP checker - No admin, no command prompt
"""

import socket
import urllib.request
import re

def get_local_ip() -> str:
    """Get local IP address using pure Python"""
    try:
        # Connect to external server (doesn't actually send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"

def get_public_ip() -> str:
    """Get public IP using HTTP request"""
    services = [
        'https://api.ipify.org',
        'https://icanhazip.com',
        'https://checkip.amazonaws.com'
    ]
    
    for service in services:
        try:
            with urllib.request.urlopen(service, timeout=5) as response:
                ip = response.read().decode('utf-8').strip()
                # Validate IP format
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                    return ip
        except:
            continue
    return "Unknown"

def check_ip(parameters: dict, player=None) -> str:
    """Main handler for IP check"""
    ip_type = parameters.get("type", "both")
    result = ""
    
    if ip_type in ["local", "both"]:
        local = get_local_ip()
        result += f"Your local IP address is {local}. "
    
    if ip_type in ["public", "both"]:
        public = get_public_ip()
        result += f"Your public IP address is {public}. "
    
    if player:
        player.write_log(f"[IP] {result}")
    
    return result.strip()