import sys
import os
import json
import requests
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QRadioButton, QCheckBox, QScrollArea, QButtonGroup
)

# Premium Stark HUD Holographic Theme Colors
class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    WHITE     = "#d8f8ff"
    GREEN     = "#00ff88"
    AMBER     = "#ffaa00"
    RED       = "#ff3355"

BRAIN_DEFINITIONS = [
    {"id": "gemini", "name": "Brain 1: Gemini 2.0 Live", "type": "cloud", "key_name": "gemini_api_key", "desc": "Live Voice & Orchestration Core"},
    {"id": "openrouter", "name": "Brain 2: OpenRouter", "type": "cloud", "key_name": "openrouter_api_key", "desc": "Cognitive Specialist (Maverick/Maestro)"},
    {"id": "groq", "name": "Brain 3: Groq (LPU)", "type": "cloud", "key_name": "groq_api_key", "desc": "Ultra-Fast Backup Brain"},
    {"id": "gemma", "name": "Brain 4: Gemma 4 (Local)", "type": "local", "key_name": None, "model_tag": "gemma", "desc": "Local Deep Reasoning Specialist"},
    {"id": "qwen", "name": "Brain 5: Qwen 3.5 9B (Local)", "type": "local", "key_name": None, "model_tag": "qwen", "desc": "Local Expert Code Generator"},
    {"id": "hermes", "name": "Brain 6: Hermes 3 (Local)", "type": "local", "key_name": None, "model_tag": "hermes", "desc": "Local Roleplay/Agentic Specialized Core"},
    {"id": "mellum", "name": "Brain 7: Mellum Kotlin (Local)", "type": "local", "key_name": None, "model_tag": "mellum", "desc": "Local Kotlin Syntactic Expert"},
    {"id": "poe", "name": "Brain 8: Poe (Cloud)", "type": "cloud", "key_name": "poe_api_key", "desc": "Alternative Multi-Model Router"},
    {"id": "minimax", "name": "Brain 9: Minimax", "type": "cloud", "key_name": "minimax_api_key", "desc": "Dynamic Conversational Agent"},
    {"id": "pollinations", "name": "Brain 10: Pollinations.ai", "type": "free", "key_name": None, "desc": "Free cloud reasoning - No API key"},
]

def get_config_paths():
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent
    config_dir = base / "config"
    return config_dir / "brain_config.json", config_dir / "api_keys.json", config_dir

def needs_setup() -> bool:
    brain_cfg, api_cfg, _ = get_config_paths()
    if not brain_cfg.exists() or not api_cfg.exists():
        return True
    try:
        with open(api_cfg, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Setup is needed if Gemini or OpenRouter keys are missing
        return not data.get("gemini_api_key")
    except Exception:
        return True

class BrainConfigWizard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — Brain Deployment Wizard")
        self.setFixedSize(620, 680)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._drag_pos = QPoint()

        # Layout Setup
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame(self)
        self.container.setStyleSheet(f"""
            QFrame {{
                background: rgba(0, 6, 10, 245);
                border: 2px solid {C.BORDER};
                border-radius: 12px;
            }}
        """)
        layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(24, 20, 24, 20)
        container_layout.setSpacing(10)
        
        # Header / Stark Title
        title = QLabel("🦾 J.A.R.V.I.S — BRAIN CONFIGURATION WIZARD")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
        container_layout.addWidget(title)
        
        subtitle = QLabel("Synchronize your 10-Brain architecture. Choose offline or hybrid routing.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Courier New", 8))
        subtitle.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; background: transparent;")
        container_layout.addWidget(subtitle)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border: none; background-color: {C.BORDER}; height: 1px;")
        container_layout.addWidget(sep)
        
        # 1. Deployment Mode Selector
        mode_lbl = QLabel("▪ SELECT DEPLOYMENT MODE:")
        mode_lbl.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        mode_lbl.setStyleSheet(f"color: {C.PRI}; border: none; background: transparent;")
        container_layout.addWidget(mode_lbl)
        
        mode_frame = QFrame()
        mode_frame.setStyleSheet(f"border: 1px solid {C.BORDER}; border-radius: 6px; background: #000c14; padding: 6px;")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(10, 4, 10, 4)
        
        self.mode_group = QButtonGroup(self)
        
        self.modes = {
            "local": QRadioButton("Local Only"),
            "cloud": QRadioButton("Cloud Only"),
            "hybrid": QRadioButton("Hybrid (Recommended)"),
            "manual": QRadioButton("Manual Select")
        }
        
        for mid, btn in self.modes.items():
            btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            btn.setStyleSheet(f"""
                QRadioButton {{ color: {C.TEXT_DIM}; border: none; }}
                QRadioButton::indicator {{ width: 10px; height: 10px; border-radius: 5px; border: 1px solid {C.BORDER}; background: #00070a; }}
                QRadioButton::indicator:checked {{ background: {C.PRI}; border: 1px solid {C.PRI}; }}
                QRadioButton:hover {{ color: {C.TEXT}; }}
            """)
            self.mode_group.addButton(btn)
            mode_layout.addWidget(btn)
            
        self.modes["hybrid"].setChecked(True)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        container_layout.addWidget(mode_frame)

        # 2. Local Models Presence Indicator
        self.check_local_ollama()
        
        # 3. Brains Scroll Area Form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: 1px solid {C.BORDER}; border-radius: 6px; }}
            QScrollBar:vertical {{ background: {C.BG}; width: 6px; border: none; }}
            QScrollBar::handle:vertical {{ background: {C.BORDER_B}; border-radius: 3px; }}
        """)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent; border: none;")
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(12, 10, 12, 10)
        self.scroll_layout.setSpacing(10)
        
        self.brain_toggles = {}
        self.brain_keys = {}
        self.key_inputs = {}
        
        for brain in BRAIN_DEFINITIONS:
            row_frame = QFrame()
            row_frame.setStyleSheet(f"border-bottom: 1px solid {C.PRI_GHO}; background: transparent; padding: 2px;")
            row_layout = QVBoxLayout(row_frame)
            row_layout.setContentsMargins(0, 0, 0, 6)
            row_layout.setSpacing(4)
            
            # Header Row (Checkbox + Title + Status)
            hdr_layout = QHBoxLayout()
            hdr_layout.setSpacing(8)
            
            cb = QCheckBox()
            cb.setChecked(True)
            cb.setStyleSheet(f"""
                QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {C.BORDER}; background: #00070a; border-radius: 2px; }}
                QCheckBox::indicator:checked {{ image: url(none); background: {C.PRI}; border: 1px solid {C.PRI}; }}
            """)
            self.brain_toggles[brain["id"]] = cb
            hdr_layout.addWidget(cb)
            
            name_lbl = QLabel(brain["name"])
            name_lbl.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            name_lbl.setStyleSheet(f"color: {C.WHITE}; border: none;")
            hdr_layout.addWidget(name_lbl)
            
            hdr_layout.addStretch()
            
            # Status badge (Cloud / Local Online status)
            status_lbl = QLabel()
            status_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            
            if brain["type"] == "local":
                # Check downloaded status
                found = any(brain["model_tag"] in m.lower() for m in self.ollama_models)
                if not self.ollama_online:
                    status_lbl.setText("⚠️ OLLAMA OFFLINE")
                    status_lbl.setStyleSheet(f"color: {C.RED}; border: none;")
                elif found:
                    status_lbl.setText("🟢 RUNNING")
                    status_lbl.setStyleSheet(f"color: {C.GREEN}; border: none;")
                else:
                    status_lbl.setText("⚠️ MODEL MISSING")
                    status_lbl.setStyleSheet(f"color: {C.AMBER}; border: none;")
            elif brain["type"] == "free":
                status_lbl.setText("🌐 FREE CORE")
                status_lbl.setStyleSheet(f"color: {C.GREEN}; border: none;")
            else:
                status_lbl.setText("☁️ CLOUD CORE")
                status_lbl.setStyleSheet(f"color: {C.PRI}; border: none;")
                
            hdr_layout.addWidget(status_lbl)
            row_layout.addLayout(hdr_layout)
            
            # Subtitle
            desc_lbl = QLabel(brain["desc"])
            desc_lbl.setFont(QFont("Courier New", 7))
            desc_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; border: none; padding-left: 22px;")
            row_layout.addWidget(desc_lbl)
            
            # API Key Row (If Cloud)
            if brain["key_name"]:
                key_layout = QHBoxLayout()
                key_layout.setContentsMargins(22, 0, 0, 0)
                
                key_lbl = QLabel("API KEY:")
                key_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
                key_lbl.setStyleSheet(f"color: {C.PRI_DIM}; border: none;")
                key_layout.addWidget(key_lbl)
                
                inp = QLineEdit()
                inp.setEchoMode(QLineEdit.EchoMode.Password)
                inp.setFont(QFont("Courier New", 8))
                inp.setFixedHeight(24)
                inp.setStyleSheet(f"""
                    QLineEdit {{
                        background: #000c12; color: {C.TEXT};
                        border: 1px solid {C.BORDER}; border-radius: 3px; padding: 1px 6px;
                    }}
                    QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
                """)
                self.key_inputs[brain["id"]] = inp
                key_layout.addWidget(inp)
                
                # Show/Hide Password Eye Button
                eye_btn = QPushButton("👁️")
                eye_btn.setFixedSize(24, 24)
                eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                eye_btn.setStyleSheet(f"""
                    QPushButton {{ background: #000c12; color: {C.TEXT_DIM}; border: 1px solid {C.BORDER}; border-radius: 3px; }}
                    QPushButton:hover {{ color: {C.PRI}; }}
                """)
                # Toggle Echo Mode
                eye_btn.clicked.connect(lambda checked=False, i=inp: i.setEchoMode(
                    QLineEdit.EchoMode.Normal if i.echoMode() == QLineEdit.EchoMode.Password else QLineEdit.EchoMode.Password
                ))
                key_layout.addWidget(eye_btn)
                
                row_layout.addLayout(key_layout)
                
            self.scroll_layout.addWidget(row_frame)
            
        scroll.setWidget(scroll_content)
        container_layout.addWidget(scroll)
        
        # Load Defaults
        self.load_current_configs()
        
        # Actions Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(0, 10, 0, 0)
        
        save_btn = QPushButton("▸ SAVE & SYNCHRONIZE")
        save_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        save_btn.setFixedHeight(38)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.GREEN};
                border: 1px solid {C.GREEN}; border-radius: 4px;
            }}
            QPushButton:hover {{
                background: rgba(0, 255, 136, 20); border: 1px solid {C.GREEN};
            }}
        """)
        save_btn.clicked.connect(self.save_and_boot)
        btn_layout.addWidget(save_btn)
        
        skip_btn = QPushButton("✕ SKIP SETUP")
        skip_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        skip_btn.setFixedHeight(38)
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{
                color: {C.WHITE}; border: 1px solid {C.BORDER_B};
            }}
        """)
        skip_btn.clicked.connect(self.skip_setup)
        btn_layout.addWidget(skip_btn)
        
        container_layout.addLayout(btn_layout)

    def check_local_ollama(self):
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=1)
            if resp.status_code == 200:
                self.ollama_online = True
                self.ollama_models = [m["name"] for m in resp.json().get("models", [])]
                return
        except:
            pass
        self.ollama_online = False
        self.ollama_models = []

    def on_mode_changed(self, btn):
        mode = None
        for mid, r in self.modes.items():
            if r.isChecked():
                mode = mid
                break
                
        if not mode or mode == "manual":
            return
            
        for brain in BRAIN_DEFINITIONS:
            bid = brain["id"]
            if mode == "local":
                self.brain_toggles[bid].setChecked(brain["type"] == "local")
            elif mode == "cloud":
                self.brain_toggles[bid].setChecked(brain["type"] in ["cloud", "free"])
            elif mode == "hybrid":
                self.brain_toggles[bid].setChecked(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def load_current_configs(self):
        brain_cfg, api_cfg, _ = get_config_paths()
        
        # Load API keys
        if api_cfg.exists():
            try:
                with open(api_cfg, "r", encoding="utf-8") as f:
                    api_data = json.load(f)
                for bid, inp in self.key_inputs.items():
                    brain = next(b for b in BRAIN_DEFINITIONS if b["id"] == bid)
                    inp.setText(str(api_data.get(brain["key_name"], "")))
            except:
                pass

        # Load Deployment Mode / Brain Checklist states
        if brain_cfg.exists():
            try:
                with open(brain_cfg, "r", encoding="utf-8") as f:
                    brain_data = json.load(f)
                mode = brain_data.get("deployment_mode", "hybrid")
                if mode in self.modes:
                    self.modes[mode].setChecked(True)
                
                brains_dict = brain_data.get("brains", {})
                for bid, togg in self.brain_toggles.items():
                    if bid in brains_dict:
                        togg.setChecked(bool(brains_dict[bid].get("enabled", True)))
            except:
                pass

    def save_and_boot(self):
        # Validation Check: If cloud/hybrid mode is selected, ensure Gemini is enabled & has key
        mode = "hybrid"
        for mid, btn in self.modes.items():
            if btn.isChecked():
                mode = mid
                break
                
        if mode in ["cloud", "hybrid", "manual"]:
            if self.brain_toggles["gemini"].isChecked():
                gemini_key = self.key_inputs["gemini"].text().strip()
                if not gemini_key:
                    self.key_inputs["gemini"].setStyleSheet(f"background: #140006; color: {C.TEXT}; border: 1px solid {C.RED};")
                    return

        brain_cfg, api_cfg, config_dir = get_config_paths()
        config_dir.mkdir(exist_ok=True)
        
        # 1. Write config/brain_config.json
        brain_config = {
            "deployment_mode": mode,
            "brains": {}
        }
        for brain in BRAIN_DEFINITIONS:
            bid = brain["id"]
            brain_config["brains"][bid] = {
                "enabled": self.brain_toggles[bid].isChecked()
            }
        
        try:
            with open(brain_cfg, "w", encoding="utf-8") as f:
                json.dump(brain_config, f, indent=4)
        except Exception as e:
            print(f"[Wizard] Failed to save brain config: {e}")

        # 2. Write config/api_keys.json (compatible with existing system)
        api_data = {}
        if api_cfg.exists():
            try:
                with open(api_cfg, "r", encoding="utf-8") as f:
                    api_data = json.load(f)
            except:
                pass
                
        # Merge updated input values
        for bid, inp in self.key_inputs.items():
            brain = next(b for b in BRAIN_DEFINITIONS if b["id"] == bid)
            api_data[brain["key_name"]] = inp.text().strip()

        # Update force_brain value for existing router logic
        if mode == "local":
            api_data["force_brain"] = "local"
        elif mode == "cloud" or mode == "hybrid":
            api_data["force_brain"] = "gemini"
        
        # Set OS
        if "os_system" not in api_data:
            api_data["os_system"] = "windows" if os.name == "nt" else "linux"

        try:
            with open(api_cfg, "w", encoding="utf-8") as f:
                json.dump(api_data, f, indent=4)
            print("[Wizard] Saved all cognitive paths.")
            self.close()
        except Exception as e:
            print(f"[Wizard] Error writing keys: {e}")

    def skip_setup(self):
        # Skip saves hybrid defaults so system is initialized
        brain_cfg, api_cfg, config_dir = get_config_paths()
        config_dir.mkdir(exist_ok=True)
        
        # Default fallback
        if not api_cfg.exists():
            data = {
                "gemini_api_key": "",
                "openrouter_api_key": "",
                "groq_api_key": "",
                "os_system": "windows" if os.name == "nt" else "linux",
                "force_brain": "local"
            }
            try:
                with open(api_cfg, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            except: pass
            
        print("[Wizard] Skipped config setup.")
        self.close()

def run_setup_wizard():
    app = QApplication.instance() or QApplication(sys.argv)
    wizard = BrainConfigWizard()
    wizard.show()
    screen = app.primaryScreen().geometry()
    wizard.move((screen.width() - wizard.width()) // 2, (screen.height() - wizard.height()) // 2)
    app.exec()

if __name__ == "__main__":
    run_setup_wizard()
