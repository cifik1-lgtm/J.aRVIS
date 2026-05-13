"""
JARVIS Hand Gesture Control Module
Uses MediaPipe for real-time hand tracking and gesture recognition.
Works on AMD RX 580 (CPU inference, no CUDA required).
"""

import threading
import time

# Lazy imports to avoid startup errors if not needed
cv2 = None
mp = None
pyautogui = None
np = None


def _lazy_import():
    """Import heavy libraries lazily to not block startup."""
    global cv2, mp, pyautogui, np
    try:
        import cv2 as _cv2
        import mediapipe as _mp
        import numpy as _np
        import mediapipe.python.solutions.hands as _mp_hands
        import mediapipe.python.solutions.drawing_utils as _mp_draw
        import pyautogui as _pg
        cv2 = _cv2
        mp = _mp
        np = _np
        # Expose solutions for backward compatibility if needed
        if not hasattr(mp, 'solutions'):
            mp.solutions = type('obj', (object,), {'hands': _mp_hands, 'drawing_utils': _mp_draw})
        pyautogui = _pg
        return True
    except ImportError as e:
        print(f"[GestureControl] ❌ Missing dependency: {e}")
        return False


class HandGestureController:
    def __init__(self, jarvis=None):
        if not _lazy_import():
            raise ImportError("MediaPipe or OpenCV not available.")

        self.jarvis = jarvis
        self.mp_hands = mp.solutions.hands
        self.mp_face_mesh = mp.solutions.face_mesh
        
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        self._last_gesture = None
        self._gesture_cooldown = 0.8
        self._last_trigger_time = 0
        self.last_z = 0
        self.smoothed_gaze = None
        self.ema_alpha = 0.2  # Smoothing factor (lower = smoother but more lag)
        
        # Screen settings
        self.screen_w, self.screen_h = pyautogui.size()

    def get_gaze_point(self, landmarks):
        """Estimate gaze point using iris landmarks with smoothing and mirror fix"""
        iris_right = landmarks[468]
        iris_left = landmarks[473]
        avg_x = (iris_right.x + iris_left.x) / 2
        avg_y = (iris_right.y + iris_left.y) / 2
        
        # Mirror fix: Invert X range
        raw_x = np.interp(avg_x, [0.4, 0.6], [self.screen_w, 0])
        raw_y = np.interp(avg_y, [0.4, 0.6], [0, self.screen_h])
        
        # EMA Smoothing
        if self.smoothed_gaze is None:
            self.smoothed_gaze = [raw_x, raw_y]
        else:
            self.smoothed_gaze[0] = (self.ema_alpha * raw_x) + (1 - self.ema_alpha) * self.smoothed_gaze[0]
            self.smoothed_gaze[1] = (self.ema_alpha * raw_y) + (1 - self.ema_alpha) * self.smoothed_gaze[1]
        
        return self.smoothed_gaze[0], self.smoothed_gaze[1]

    def process_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hand_res = self.hands.process(rgb)
        face_res = self.face_mesh.process(rgb)

        gaze_x, gaze_y = -100, -100
        hand_x, hand_y = -100, -100
        detected_gesture = None

        # 1. Gaze
        if face_res.multi_face_landmarks:
            gaze_x, gaze_y = self.get_gaze_point(face_res.multi_face_landmarks[0].landmark)

        # 2. Hand
        if hand_res.multi_hand_landmarks:
            lm = hand_res.multi_hand_landmarks[0].landmark
            self.mp_draw.draw_landmarks(frame, hand_res.multi_hand_landmarks[0], self.mp_hands.HAND_CONNECTIONS)
            
            index_tip = lm[8]
            # Mirror fix for hand tracking too
            hand_x = np.interp(index_tip.x, [0, 1], [self.screen_w, 0])
            hand_y = np.interp(index_tip.y, [0, 1], [0, self.screen_h])
            
            # Gesture Detection
            fingers_up = []
            fingers_up.append(1 if lm[4].x > lm[3].x else 0) # Thumb
            for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
                fingers_up.append(1 if lm[tip].y < lm[pip].y else 0)
            
            gesture = {
                (0, 0, 0, 0, 0): "fist",
                (1, 1, 1, 1, 1): "open_palm",
                (0, 1, 0, 0, 0): "pointing",
                (0, 1, 1, 0, 0): "peace",
                (1, 1, 0, 0, 0): "thumbs_up",
                (0, 0, 0, 0, 1): "call_me",
                (0, 1, 0, 0, 1): "rock",
            }.get(tuple(fingers_up), "unknown")

            # Push detection
            if self.last_z - index_tip.z > 0.05:
                gesture = "push"
            self.last_z = index_tip.z

            now = time.time()
            if gesture != "unknown" and (gesture != self._last_gesture or now - self._last_trigger_time > self._gesture_cooldown):
                self._last_gesture = gesture
                self._last_trigger_time = now
                detected_gesture = gesture

            cv2.putText(frame, f"✋ {gesture.upper()}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 100), 2)

        # Update Fullscreen HUD
        if self.jarvis and self.jarvis.ui:
            self.jarvis.ui.set_tracking(gaze_x, gaze_y, hand_x, hand_y)

        return frame, detected_gesture


class GestureControlManager:
    """
    Manages the gesture control background thread and maps gestures to JARVIS actions.
    """

    # Maps gesture name → JARVIS command label (for logging)
    COMMAND_MAP = {
        "fist":      "mute",
        "open_palm": "stop",
        "pointing":  "click",
        "peace":     "volume_up",
        "thumbs_up": "confirm",
        "call_me":   "toggle_gesture",
        "rock":      "volume_down",
        "push":      "highlight",
    }

    def __init__(self, jarvis):
        self.jarvis = jarvis
        self.enabled = False
        self._thread = None
        self._controller = None

    def start(self):
        """Start the gesture control background thread."""
        if self.enabled:
            return

        if not _lazy_import():
            if self.jarvis.ui:
                self.jarvis.ui.write_log("SYS: ❌ Gesture control unavailable - missing MediaPipe/OpenCV")
            return

        self.enabled = True
        self._thread = threading.Thread(target=self._gesture_loop, daemon=True)
        self._thread.start()

        if self.jarvis.ui:
            self.jarvis.ui.write_log("SYS: 🤚 Gesture control ACTIVATED")
        self.jarvis.speak("Gesture control activated, sir.")

    def stop(self):
        """Stop the gesture control thread."""
        self.enabled = False
        if self.jarvis.ui:
            self.jarvis.ui.write_log("SYS: ✋ Gesture control DEACTIVATED")
        self.jarvis.speak("Gesture control deactivated, sir.")

    def toggle(self):
        if self.enabled:
            self.stop()
        else:
            self.start()

    def _gesture_loop(self):
        """Main camera loop - runs in background thread."""
        try:
            self._controller = HandGestureController(self.jarvis)
        except ImportError:
            return

        print("[GestureControl] 🎥 Initializing camera index 0...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[GestureControl] ❌ Camera index 0 not accessible, trying index 1...")
            cap = cv2.VideoCapture(1)
            
        if not cap.isOpened():
            print("[GestureControl] ❌ No camera accessible")
            self.enabled = False
            return

        print("[GestureControl] ✅ Camera opened successfully, starting loop...")

        while self.enabled:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame, gesture = self._controller.process_frame(frame)
            
            if gesture:
                command = self.COMMAND_MAP.get(gesture)
                print(f"[GestureControl] 🤚 Detected: {gesture.upper()} -> {command}")
                if command:
                    self._execute_command(command, gesture)

            # Draw HUD
            status = "🟢 Gesture: ON" if self.enabled else "🔴 OFF"
            cv2.putText(frame, status, (10, frame.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow("JARVIS Gesture Control", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.enabled = False

        cap.release()
        cv2.destroyAllWindows()
        print("[GestureControl] 🛑 Gesture loop stopped")

    def _execute_command(self, command: str, gesture: str):
        """Map gesture command to a JARVIS action."""
        j = self.jarvis
        if j.ui:
            j.ui.write_log(f"🤚 Gesture: {gesture.upper()} → {command}")

        try:
            if command == "mute":
                j.ui.muted = not j.ui.muted
                j.speak("Muted." if j.ui.muted else "Unmuted.")

            elif command == "stop":
                j.speak("Stopping, sir.")

            elif command == "highlight":
                j.speak("Highlighting focus, sir.")
                # Logic for highlighting window under gaze could go here

            elif command == "click":
                if pyautogui:
                    pyautogui.click()

            elif command == "volume_up":
                if hasattr(j, 'youtube') and j.youtube:
                    j.youtube.volume_up(10)

            elif command == "volume_down":
                if hasattr(j, 'youtube') and j.youtube:
                    j.youtube.volume_down(10)

            elif command == "confirm":
                j._on_text_command("yes confirm")

            elif command == "toggle_gesture":
                # Schedule stop on next loop iteration
                threading.Timer(0.5, self.stop).start()

        except Exception as e:
            print(f"[GestureControl] ⚠️ Command execution error: {e}")


def start_gesture_control(jarvis):
    """Tool entry point - initialize and start gesture control for JARVIS."""
    if not hasattr(jarvis, 'gesture_manager') or jarvis.gesture_manager is None:
        jarvis.gesture_manager = GestureControlManager(jarvis)
    jarvis.gesture_manager.start()
    return {"status": "success", "message": "Gesture control started, sir."}


def stop_gesture_control(jarvis):
    """Tool entry point - stop gesture control."""
    if hasattr(jarvis, 'gesture_manager') and jarvis.gesture_manager:
        jarvis.gesture_manager.stop()
    return {"status": "success", "message": "Gesture control stopped, sir."}
