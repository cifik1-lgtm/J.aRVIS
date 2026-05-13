import cv2
import threading
import time

def open_camera_view(index=0):
    """Simple camera viewer that doesn't use gestures, just displays the feed."""
    cap = cv2.VideoCapture(index, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    
    if not cap.isOpened():
        return {"status": "error", "message": f"Could not open camera at index {index}."}

    def view_loop():
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            cv2.imshow(f"JARVIS Visual Feed (Index {index})", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cap.release()
        cv2.destroyAllWindows()

    threading.Thread(target=view_loop, daemon=True).start()
    return {"status": "success", "message": f"Camera feed {index} opened in a new window, Sir."}

def camera_viewer(jarvis, index=0):
    """Tool entry point."""
    if jarvis.ui:
        jarvis.ui.write_log(f"📷 Opening camera feed {index}...")
    return open_camera_view(index)
