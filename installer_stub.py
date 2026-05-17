import os
import sys
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import subprocess

# Dark Cyberpunk Stark HUD Color Theme
class C:
    BG       = "#00060a"
    PANEL    = "#010d14"
    BORDER   = "#0d3347"
    BORDER_B = "#1a5c7a"
    PRI      = "#00d4ff"
    TEXT     = "#8ffcff"
    TEXT_DIM = "#3a8a9a"
    WHITE    = "#d8f8ff"
    GREEN    = "#00ff88"
    RED      = "#ff3355"

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys.executable
    return __file__

class InstallerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("J.A.R.V.I.S — System Setup Wizard")
        self.geometry("520x420")
        self.configure(bg=C.BG, padx=24, pady=24)
        self.resizable(False, False)
        
        # Center the window on the active monitor screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')

        # Stark HUD Holographic Branding Title Header
        lbl_title = tk.Label(
            self, 
            text="🦾 J.A.R.V.I.S SYSTEM SETUP", 
            font=("Courier New", 16, "bold"), 
            fg=C.PRI, 
            bg=C.BG
        )
        lbl_title.pack(pady=(0, 2))
        
        lbl_sub = tk.Label(
            self, 
            text="CIFIK Intelegents  ·  Autonomous Cognitive Suite", 
            font=("Courier New", 8, "bold"), 
            fg=C.TEXT_DIM, 
            bg=C.BG
        )
        lbl_sub.pack(pady=(0, 20))
        
        # Directory Selection Section
        tk.Label(
            self, 
            text="CHOOSE INSTALLATION CODESPACE DIRECTORY:", 
            font=("Courier New", 8, "bold"), 
            fg=C.PRI, 
            bg=C.BG
        ).pack(anchor="w", pady=(0, 5))
        
        frame = tk.Frame(self, bg=C.BG)
        frame.pack(fill="x", pady=(0, 18))
        
        self.path_var = tk.StringVar()
        # Default destination path to C:\Users\<Name>\JARVIS
        default_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\"), "JARVIS")
        self.path_var.set(default_dir)
        
        self.entry_path = tk.Entry(
            frame, 
            textvariable=self.path_var, 
            font=("Courier New", 9), 
            fg=C.WHITE, 
            bg="#000d14", 
            insertbackground=C.PRI,
            bd=1, 
            relief="solid", 
            highlightthickness=1, 
            highlightbackground=C.BORDER, 
            highlightcolor=C.PRI,
            width=42
        )
        self.entry_path.pack(side="left", ipady=4, padx=(0, 8))
        
        self.btn_browse = tk.Button(
            frame, 
            text="BROWSE", 
            command=self.browse, 
            font=("Courier New", 8, "bold"), 
            fg=C.PRI, 
            bg=C.BG, 
            activeforeground=C.BG, 
            activebackground=C.PRI,
            bd=1, 
            relief="solid", 
            highlightthickness=0,
            cursor="hand2"
        )
        self.btn_browse.pack(side="left", ipady=3, ipadx=8)
        
        # System Boot and Startup Integration Checkboxes
        tk.Label(
            self, 
            text="SYSTEM INTEGRATION OPTIONS:", 
            font=("Courier New", 8, "bold"), 
            fg=C.PRI, 
            bg=C.BG
        ).pack(anchor="w", pady=(0, 5))

        self.startup_var = tk.BooleanVar(value=True)
        self.cb_startup = tk.Checkbutton(
            self, 
            text="Start JARVIS automatically on Windows startup (boot)", 
            variable=self.startup_var, 
            font=("Courier New", 8), 
            fg=C.WHITE, 
            bg=C.BG, 
            activeforeground=C.PRI, 
            activebackground=C.BG,
            selectcolor="#000d14",
            highlightthickness=0,
            bd=0
        )
        self.cb_startup.pack(anchor="w", pady=3)
        
        self.launch_var = tk.BooleanVar(value=True)
        self.cb_launch = tk.Checkbutton(
            self, 
            text="Launch J.A.R.V.I.S Live HUD immediately after installation", 
            variable=self.launch_var, 
            font=("Courier New", 8), 
            fg=C.WHITE, 
            bg=C.BG, 
            activeforeground=C.PRI, 
            activebackground=C.BG,
            selectcolor="#000d14",
            highlightthickness=0,
            bd=0
        )
        self.cb_launch.pack(anchor="w", pady=3)
        
        # Cyber progress canvas element
        self.progress_canvas = tk.Canvas(self, height=12, bg="#000d14", highlightthickness=1, highlightbackground=C.BORDER)
        self.progress_canvas.pack(fill="x", pady=(20, 6))
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready to initialize codespace environment.")
        self.lbl_status = tk.Label(
            self, 
            textvariable=self.status_var, 
            font=("Courier New", 7), 
            fg=C.TEXT_DIM, 
            bg=C.BG
        )
        self.lbl_status.pack(anchor="w")
        
        # Dynamic installation action button
        self.install_btn = tk.Button(
            self, 
            text="▸ RUN SYSTEM DEPLOYMENT", 
            command=self.start_install, 
            font=("Courier New", 10, "bold"), 
            fg=C.GREEN, 
            bg=C.BG, 
            activeforeground=C.BG, 
            activebackground=C.GREEN,
            bd=1, 
            relief="solid",
            cursor="hand2"
        )
        self.install_btn.pack(pady=(20, 0), ipady=5, ipadx=20)

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.path_var.get())
        if folder:
            if not folder.endswith("JARVIS"):
                folder = os.path.join(folder, "JARVIS")
            self.path_var.set(folder)

    def start_install(self):
        self.install_btn.config(state="disabled")
        self.btn_browse.config(state="disabled")
        self.entry_path.config(state="disabled")
        self.cb_startup.config(state="disabled")
        self.cb_launch.config(state="disabled")
        
        self.draw_progress(0)
        target_dir = self.path_var.get()
        threading.Thread(target=self.extract_files, args=(target_dir,), daemon=True).start()

    def draw_progress(self, pct):
        self.progress_canvas.delete("all")
        w = self.progress_canvas.winfo_width()
        h = self.progress_canvas.winfo_height()
        fill_w = (pct / 100.0) * w
        self.progress_canvas.create_rectangle(0, 0, fill_w, h, fill=C.PRI, outline="")

    def extract_files(self, target_dir):
        exe_path = get_base_dir()
        
        try:
            self.status_var.set("Extracting J.A.R.V.I.S filespace...")
            os.makedirs(target_dir, exist_ok=True)
            
            with zipfile.ZipFile(exe_path, "r") as z:
                total_files = len(z.namelist())
                for i, file_info in enumerate(z.infolist()):
                    z.extract(file_info, target_dir)
                    
                    # Update progress safely on UI thread
                    progress_val = int(((i + 1) / total_files) * 100)
                    self.after(0, self.update_progress, progress_val, f"Extracting: {file_info.filename[:45]}...")
            
            # Setup Startup shortcut if selected
            if self.startup_var.get():
                self.after(0, self.status_var.set, "Configuring startup integration boot hooks...")
                self.create_startup_shortcut(target_dir)

            self.after(0, self.finish_install)
            
        except Exception as e:
            self.after(0, self.show_error, str(e))

    def create_startup_shortcut(self, target_dir):
        try:
            startup_folder = os.path.join(
                os.environ["APPDATA"], 
                "Microsoft\\Windows\\Start Menu\\Programs\\Startup"
            )
            shortcut_path = os.path.join(startup_folder, "JARVIS.lnk")
            bat_path = os.path.join(target_dir, "START_JARVIS.bat")
            
            # Native PowerShell cmdlet creates startup shortcut link safely
            ps_cmd = (
                f'$WshShell = New-Object -ComObject WScript.Shell; '
                f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); '
                f'$Shortcut.TargetPath = "{bat_path}"; '
                f'$Shortcut.WorkingDirectory = "{target_dir}"; '
                f'$Shortcut.Save()'
            )
            
            subprocess.run(
                ["powershell", "-Command", ps_cmd], 
                capture_output=True, 
                check=True, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"Failed to create startup shortcut: {e}")

    def update_progress(self, val, text):
        self.draw_progress(val)
        self.status_var.set(text)

    def finish_install(self):
        self.draw_progress(100)
        self.status_var.set("J.A.R.V.I.S codespace deployment established successfully.")
        
        target_dir = self.path_var.get()
        messagebox.showinfo(
            "J.A.R.V.I.S System Initialized", 
            f"JARVIS installed successfully to:\n{target_dir}\n\nAll cognitive cores ready."
        )
        
        # Launch JARVIS immediately if checkbox is ticked
        if self.launch_var.get():
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "START_JARVIS.bat"], cwd=target_dir)
            except Exception as e:
                print(f"Failed to launch script: {e}")
                
        self.destroy()

    def show_error(self, err):
        messagebox.showerror("Installation Core Error", f"Fatal deployment error:\n{err}")
        self.install_btn.config(state="normal")
        self.btn_browse.config(state="normal")
        self.entry_path.config(state="normal")
        self.cb_startup.config(state="normal")
        self.cb_launch.config(state="normal")
        self.status_var.set("Establishment halted due to critical error.")

if __name__ == "__main__":
    app = InstallerGUI()
    # Let window draw before calculating progress bar width
    app.update()
    app.mainloop()
