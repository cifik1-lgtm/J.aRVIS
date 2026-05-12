import cv2
import json
from pathlib import Path
import io

def get_api_key():
    base = Path(__file__).resolve().parent.parent
    conf = base / "config" / "api_keys.json"
    try:
        return json.loads(conf.read_text()).get("gemini_api_key", "")
    except:
        return ""

def webcam_vision(parameters: dict, player=None) -> str:
    prompt = parameters.get("prompt", "Describe everything you see in this webcam picture in detail.")
    
    # Try multiple camera indices if 0 fails
    cap = None
    for i in range(3):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            break
            
    if not cap or not cap.isOpened():
        return "Failed to open the webcam."
    
    # Warm up camera to adjust exposure
    for _ in range(10):
        cap.read()
        
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return "Failed to capture a frame from the webcam."
        
    is_success, buffer = cv2.imencode(".png", frame)
    if not is_success:
        return "Failed to encode the webcam frame."
        
    api_key = get_api_key()
    if not api_key:
        return "No API key found in config/api_keys.json."
        
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        
        if player:
            player.write_log("Analyzing webcam feed...")
            
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=buffer.tobytes(), mime_type="image/png"),
                prompt
            ]
        )
        return response.text
    except Exception as e:
        return f"Webcam Vision AI Error: {str(e)}"
