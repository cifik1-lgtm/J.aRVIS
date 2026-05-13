import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time
import threading
import pygetwindow as gw
from screeninfo import get_monitors

class GestureController:
    def __init__(self):
        # MediaPipe Solutions
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1, 
            refine_landmarks=True, # Essential for Iris tracking
            min_detection_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # State
        self.is_dragging = False
        self.last_x, self.last_y = 0, 0
        self.last_z = 0
        self.flick_start_time = 0
        self.flick_start_x = 0
        
        # Monitor Detection
        self.monitors = get_monitors()
        self.screen_width, self.screen_height = pyautogui.size()
        
        # HUD reference
        self.hud = None 

    def set_hud(self, hud_instance):
        self.hud = hud_instance

    def get_gaze_point(self, landmarks, w, h):
        """Estimate gaze point using iris landmarks"""
        # Right Eye Iris: 468, Left Eye Iris: 473
        iris_right = landmarks[468]
        iris_left = landmarks[473]
        
        # Average iris position (normalized)
        avg_x = (iris_right.x + iris_left.x) / 2
        avg_y = (iris_right.y + iris_left.y) / 2
        
        # Map to screen with slight sensitivity boost
        screen_x = np.interp(avg_x, [0.4, 0.6], [0, self.screen_width])
        screen_y = np.interp(avg_y, [0.4, 0.6], [0, self.screen_height])
        return screen_x, screen_y

    def process_frame(self, frame):
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        hand_res = self.hands.process(rgb)
        face_res = self.face_mesh.process(rgb)
        
        gaze_x, gaze_y = -100, -100
        hand_x, hand_y = -100, -100
        commands = []

        # 1. GAZE TRACKING
        if face_res.multi_face_landmarks:
            landmarks = face_res.multi_face_landmarks[0].landmark
            gaze_x, gaze_y = self.get_gaze_point(landmarks, w, h)

        # 2. HAND TRACKING
        if hand_res.multi_hand_landmarks:
            landmarks = hand_res.multi_hand_landmarks[0].landmark
            index_tip = landmarks[8]
            hand_x = np.interp(index_tip.x, [0, 1], [0, self.screen_width])
            hand_y = np.interp(index_tip.y, [0, 1], [0, self.screen_height])
            hand_z = index_tip.z # Depth
            
            # GESTURES
            # Thumb (4) to Index (8) distance for PINCH
            thumb_tip = landmarks[4]
            dist = np.sqrt((index_tip.x - thumb_tip.x)**2 + (index_tip.y - thumb_tip.y)**2)
            is_pinching = dist < 0.05
            
            # FLICK DETECTION (Rapid X movement)
            curr_time = time.time()
            if is_pinching:
                if not self.is_dragging:
                    self.is_dragging = True
                    self.flick_start_x = hand_x
                    self.flick_start_time = curr_time
                    pyautogui.mouseDown()
                
                # Check for flick at end of motion
                dx = hand_x - self.flick_start_x
                dt = curr_time - self.flick_start_time
                if dt < 0.3 and abs(dx) > self.screen_width * 0.2:
                    direction = "right" if dx > 0 else "left"
                    self.flick_window(direction)
                    self.is_dragging = False
                    pyautogui.mouseUp()
                    commands.append(f"flick_{direction}")
                else:
                    pyautogui.moveTo(hand_x, hand_y)
            else:
                if self.is_dragging:
                    self.is_dragging = False
                    pyautogui.mouseUp()

            # PUSH GESTURE (Z-depth jump)
            if self.last_z - hand_z > 0.05: # Moving toward camera
                commands.append("push_action")
                # Highlight window under gaze
                self.highlight_window_at(gaze_x, gaze_y)
            
            self.last_z = hand_z
            self.last_x, self.last_y = hand_x, hand_y

        # Update HUD
        if self.hud:
            self.hud.set_tracking_data(gaze_x, gaze_y, hand_x, hand_y)
            
        return frame, commands

    def flick_window(self, direction):
        """Move active window to next/prev monitor"""
        try:
            win = gw.getActiveWindow()
            if not win: return
            
            # Simple monitor swap (Assuming dual monitor)
            if len(self.monitors) > 1:
                target_idx = 1 if direction == "right" else 0
                target = self.monitors[target_idx]
                win.moveTo(target.x + 100, target.y + 100)
                win.maximize()
        except: pass

    def highlight_window_at(self, x, y):
        """Focus the window the user is looking at"""
        try:
            windows = gw.getWindowsAt(int(x), int(y))
            if windows:
                windows[0].activate()
        except: pass

# Global instance
_gesture_controller = None

def get_gesture_controller():
    global _gesture_controller
    if _gesture_controller is None:
        _gesture_controller = GestureController()
    return _gesture_controller
