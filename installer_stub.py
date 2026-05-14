import os
import sys
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys.executable
    return __file__

class InstallerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JARVIS Setup")
        self.geometry("500x300")
        self.configure(padx=20, pady=20)
        self.resizable(False, False)
        
        # UI Elements
        tk.Label(self, text="Welcome to JARVIS Installer", font=("Arial", 16, "bold")).pack(pady=10)
        tk.Label(self, text="Choose installation directory:").pack(anchor="w")
        
        frame = tk.Frame(self)
        frame.pack(fill="x", pady=5)
        
        self.path_var = tk.StringVar()
        self.path_var.set(os.path.join(os.environ.get("USERPROFILE", "C:\\"), "JARVIS"))
        
        tk.Entry(frame, textvariable=self.path_var, width=50).pack(side="left", padx=(0, 10))
        tk.Button(frame, text="Browse...", command=self.browse).pack(side="left")
        
        self.progress = ttk.Progressbar(self, orient="horizontal", length=460, mode="determinate")
        self.progress.pack(pady=20)
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready to install.")
        tk.Label(self, textvariable=self.status_var).pack(anchor="w")
        
        self.install_btn = tk.Button(self, text="Install", command=self.start_install, width=15, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.install_btn.pack(pady=10)

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.path_var.get())
        if folder:
            self.path_var.set(os.path.join(folder, "JARVIS"))

    def start_install(self):
        self.install_btn.config(state="disabled")
        self.progress["value"] = 0
        target_dir = self.path_var.get()
        threading.Thread(target=self.extract_files, args=(target_dir,), daemon=True).start()

    def extract_files(self, target_dir):
        exe_path = get_base_dir()
        
        try:
            self.status_var.set("Initializing extraction...")
            os.makedirs(target_dir, exist_ok=True)
            
            # Read the last 8 bytes to get the zip size
            with open(exe_path, "rb") as f:
                f.seek(-8, os.SEEK_END)
                size_bytes = f.read(8)
                try:
                    zip_size = int(size_bytes.decode('utf-8').strip())
                except:
                    # If reading the appended size fails, try reading the file as a zip directly
                    # (zipfile module can often find the zip signature at the end of an exe)
                    pass
            
            self.status_var.set("Extracting files...")
            
            # Open the exe itself as a zip file
            with zipfile.ZipFile(exe_path, "r") as z:
                total_files = len(z.namelist())
                for i, file_info in enumerate(z.infolist()):
                    z.extract(file_info, target_dir)
                    
                    # Update progress safely
                    progress_val = int((i / total_files) * 100)
                    self.after(0, self.update_progress, progress_val, f"Extracting: {file_info.filename[:40]}...")
            
            self.after(0, self.finish_install)
            
        except Exception as e:
            self.after(0, self.show_error, str(e))

    def update_progress(self, val, text):
        self.progress["value"] = val
        self.status_var.set(text)

    def finish_install(self):
        self.progress["value"] = 100
        self.status_var.set("Installation Complete!")
        messagebox.showinfo("Success", f"JARVIS installed successfully to:\n{self.path_var.get()}\n\nTo start JARVIS on any PC, run:\nSTART_JARVIS.bat")
        self.destroy()

    def show_error(self, err):
        messagebox.showerror("Installation Error", f"An error occurred:\n{err}")
        self.install_btn.config(state="normal")
        self.status_var.set("Installation failed.")

if __name__ == "__main__":
    app = InstallerGUI()
    app.mainloop()
