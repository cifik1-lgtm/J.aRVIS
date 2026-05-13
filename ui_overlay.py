import sys
import math
import random
import time
import threading
import psutil
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QRadialGradient, QPainterPath, QImage, QPixmap
from PyQt6.QtWidgets import QWidget, QApplication, QMainWindow

class HUDOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Transparent, Always on top, No taskbar entry, Frameless
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Geometry: FULLSCREEN to allow drawing anywhere (reticles, flicks)
        screen = QApplication.primaryScreen().geometry()
        self.screen_w = screen.width()
        self.screen_h = screen.height()
        self.setGeometry(0, 0, self.screen_w, self.screen_h)
        
        # State
        self.pulse = 0.0
        self.rotation = 0.0
        self.cpu_usage = 0.0
        self.mem_usage = 0.0
        self.status_text = "SYSTEM ONLINE"
        self.emotion_text = "NEUTRAL"
        
        # Gaze / Gesture Tracking State
        self.gaze_pos = QPoint(-100, -100)
        self.hand_pos = QPoint(-100, -100)
        self.is_tracking = False
        
        # Camera Feed State
        self.camera_frame = None
        self.show_camera = False
        
        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(33) # ~30 FPS
        
        # Stats timer
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(2000)
        
        self.show()

    def set_tracking_data(self, gaze_x, gaze_y, hand_x, hand_y):
        """Update positions from the GestureController"""
        self.gaze_pos = QPoint(int(gaze_x), int(gaze_y))
        self.hand_pos = QPoint(int(hand_x), int(hand_y))
        self.is_tracking = True

    def set_camera_frame(self, cv_frame):
        """Update the camera frame for the HUD"""
        import cv2
        import numpy as np
        
        try:
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            
            # Convert to QImage
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self.camera_frame = QPixmap.fromImage(qt_image)
            self.show_camera = True
            self.update()
        except Exception as e:
            print(f"[HUD] Camera frame update failed: {e}")

    def update_animation(self):
        self.pulse = (math.sin(time.time() * 2) + 1) / 2 # 0 to 1
        self.rotation = (self.rotation + 1) % 360
        self.update()

    def update_stats(self):
        self.cpu_usage = psutil.cpu_percent()
        self.mem_usage = psutil.virtual_memory().percent

    def set_status(self, text: str):
        self.status_text = text.upper()

    def set_emotion(self, emotion: str):
        self.emotion_text = emotion.upper()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # --- HUD CORE (TOP RIGHT) ---
        hud_x = self.screen_w - 220
        hud_y = 120
        cx, cy = hud_x, hud_y
        core_r = 60 + (self.pulse * 5)
        
        # 1. Outer Rings
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(0, 212, 255, 100), 2, Qt.PenStyle.DashLine))
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.rotation)
        painter.drawEllipse(QRectF(-100, -100, 200, 200))
        painter.restore()
        
        # Static outer ring
        painter.setPen(QPen(QColor(0, 212, 255, 40), 1))
        painter.drawEllipse(QRectF(cx - 120, cy - 120, 240, 240))
        
        # 2. JARVIS Core
        grad = QRadialGradient(cx, cy, core_r)
        core_col = QColor(0, 212, 255)
        if self.emotion_text == "ANGER": core_col = QColor(255, 50, 80)
        elif self.emotion_text == "JOY": core_col = QColor(0, 255, 136)
            
        grad.setColorAt(0.0, core_col)
        grad.setColorAt(0.8, QColor(core_col.red(), core_col.green(), core_col.blue(), 100))
        grad.setColorAt(1.0, Qt.GlobalColor.transparent)
        
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))
        
        # 3. HUD Text
        painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(0, 212, 255, 180)))
        painter.drawText(QRectF(cx - 120, cy + 130, 240, 20), Qt.AlignmentFlag.AlignCenter, f"[ {self.status_text} ]")
        painter.setFont(QFont("Courier New", 8))
        painter.drawText(QRectF(cx - 120, cy + 150, 240, 20), Qt.AlignmentFlag.AlignCenter, f"MOOD: {self.emotion_text}")
        
        # Stats
        painter.drawText(cx - 200, int(cy - 10), f"CPU: {self.cpu_usage}%")
        painter.drawText(cx - 200, int(cy + 10), f"MEM: {self.mem_usage}%")

        # --- GAZE RETICLE ---
        if self.is_tracking:
            gx, gy = self.gaze_pos.x(), self.gaze_pos.y()
            # Outer reticle circle
            painter.setPen(QPen(QColor(0, 212, 255, 150), 2))
            painter.drawEllipse(QRectF(gx - 15, gy - 15, 30, 30))
            # Crosshair
            painter.drawLine(gx - 20, gy, gx - 5, gy)
            painter.drawLine(gx + 20, gy, gx + 5, gy)
            painter.drawLine(gx, gy - 20, gx, gy - 5)
            painter.drawLine(gx, gy + 20, gx, gy + 5)
            # Hand tracking pointer (Subtle dot)
            hx, hy = self.hand_pos.x(), self.hand_pos.y()
            painter.setBrush(QBrush(QColor(0, 212, 255, 100)))
            painter.drawEllipse(hx - 5, hy - 5, 10, 10)

        # --- CAMERA FEED (BOTTOM RIGHT) ---
        if self.show_camera and self.camera_frame:
            cam_w, cam_h = 240, 180
            cam_x = self.screen_w - cam_w - 40
            cam_y = self.screen_h - cam_h - 40
            
            # Glow/Border
            painter.setPen(QPen(QColor(0, 212, 255, 100), 2))
            painter.drawRect(cam_x - 2, cam_y - 2, cam_w + 4, cam_h + 4)
            
            # Draw Frame
            painter.setOpacity(0.8) # Holographic transparency
            painter.drawPixmap(cam_x, cam_y, cam_w, cam_h, self.camera_frame)
            painter.setOpacity(1.0)
            
            # HUD Label
            painter.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            painter.setPen(QColor(0, 212, 255, 180))
            painter.drawText(cam_x, cam_y - 10, "EXTERNAL VISUAL FEED // 720P")

        # Corner Brackets (Screen Corners)
        p = QPainterPath()
        # Top Left
        p.moveTo(20, 40); p.lineTo(20, 20); p.lineTo(40, 20)
        # Top Right
        p.moveTo(self.screen_w-40, 20); p.lineTo(self.screen_w-20, 20); p.lineTo(self.screen_w-20, 40)
        # Bottom Left
        p.moveTo(20, self.screen_h-40); p.lineTo(20, self.screen_h-20); p.lineTo(40, self.screen_h-20)
        # Bottom Right
        p.moveTo(self.screen_w-40, self.screen_h-20); p.lineTo(self.screen_w-20, self.screen_h-20); p.lineTo(self.screen_w-20, self.screen_h-40)
        
        painter.setPen(QPen(QColor(0, 212, 255, 80), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(p)

def run_overlay():
    app = QApplication(sys.argv)
    window = HUDOverlay()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_overlay()
