import cv2

def detect_cameras():
    """Scans for available camera indices."""
    available_indices = []
    # Test first 10 indices
    for i in range(10):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            available_indices.append(i)
            cap.release()
    
    if not available_indices:
        return {"status": "error", "message": "No cameras detected on the system."}
    
    return {
        "status": "success", 
        "count": len(available_indices),
        "indices": available_indices,
        "message": f"Found {len(available_indices)} cameras at indices: {available_indices}"
    }
