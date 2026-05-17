import cv2
import threading
import time

_active_captures = {}

def open_camera_view(index=0):
    """Simple camera viewer that doesn't use gestures, just displays the feed."""
    if index in _active_captures:
        return {"status": "success", "message": f"Camera feed {index} is already open."}
        
    cap = cv2.VideoCapture(index, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    
    if not cap.isOpened():
        return {"status": "error", "message": f"Could not open camera at index {index}."}

    _active_captures[index] = cap

    def view_loop():
        while index in _active_captures and cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            cv2.imshow(f"JARVIS Visual Feed (Index {index})", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        try:
            cv2.destroyWindow(f"JARVIS Visual Feed (Index {index})")
        except:
            pass
        if index in _active_captures:
            del _active_captures[index]

    threading.Thread(target=view_loop, daemon=True).start()
    return {"status": "success", "message": f"Camera feed {index} opened in a new window, Sir."}

def close_camera_view(index=0):
    """Close the active camera feed window programmatically."""
    if index in _active_captures:
        # Deleting from dictionary breaks the while loop instantly,
        # which releases the cap and destroys the window cleanly.
        del _active_captures[index]
        return {"status": "success", "message": f"Camera feed {index} closed successfully, Sir."}
    return {"status": "error", "message": f"No active camera viewer found at index {index}, Sir."}

def camera_viewer(jarvis, index=0, action="start"):
    """Tool entry point."""
    action = (action or "start").lower().strip()
    if action == "stop":
        if jarvis.ui:
            jarvis.ui.write_log(f"📷 Closing camera feed {index}...")
        return close_camera_view(index)
        
    if jarvis.ui:
        jarvis.ui.write_log(f"📷 Opening camera feed {index}...")
    return open_camera_view(index)
