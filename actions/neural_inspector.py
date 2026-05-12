import os
import sys
import json
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime

# Lazy-load TensorFlow to keep startup fast
def _get_tf():
    try:
        import tensorflow as tf
        from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input, decode_predictions
        return tf, MobileNetV2, preprocess_input, decode_predictions
    except ImportError:
        return None, None, None, None

def neural_inspector(parameters: dict, player=None) -> str:
    """
    Deep learning object detection using TensorFlow/MobileNetV2.
    Usage: {'image_path': 'path/to/img.jpg'} or {'source': 'screen'}
    """
    image_path = parameters.get("image_path")
    source = parameters.get("source", "screen")
    
    # 1. Handle dynamic capture if no path provided
    if not image_path:
        from actions.screen_processor import screen_process
        # We use screen_process to capture, but we need the file path
        # In this environment, we'll assume a standard temp path for now
        temp_dir = Path.home() / "Desktop" / "JARVIS_SHARE" / "Mark-XXXIX" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        image_path = temp_dir / "neural_capture.jpg"
        
        # Capture logic based on source
        if source == "webcam":
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(str(image_path), frame)
            cap.release()
        else:
            import mss
            with mss.mss() as sct:
                sct.shot(output=str(image_path))

    if not Path(image_path).exists():
        return "I couldn't find the image to analyze, sir."

    # 2. Load and Run TensorFlow
    tf, MobileNetV2, preprocess_input, decode_predictions = _get_tf()
    if tf is None:
        return "TensorFlow is not yet initialized or installed correctly, sir. Please run the requirements install."

    try:
        # Load pre-trained model (cached after first run)
        model = MobileNetV2(weights='imagenet')
        
        # Load and preprocess image
        img = cv2.imread(str(image_path))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img, (224, 224))
        x = np.expand_dims(img_resized, axis=0)
        x = preprocess_input(x)
        
        # Predict
        preds = model.predict(x)
        results = decode_predictions(preds, top=5)[0]
        
        # Format findings
        findings = []
        for _, label, score in results:
            if score > 0.1: # 10% confidence threshold
                findings.append(f"{label.replace('_', ' ')} ({score:.1%})")
        
        if not findings:
            return "I see the image, but I can't quite make out any distinct objects, sir."
            
        summary = ", ".join(findings)
        
        if player:
            player.write_log(f"SYS: 🧠 Neural Retina identified: {summary[:50]}...")
            
        return f"Neural analysis complete, sir. I've identified: {summary}."

    except Exception as e:
        return f"Neural analysis failed: {str(e)}"

if __name__ == "__main__":
    # Test run
    print(neural_inspector({"source": "screen"}))
