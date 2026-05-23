import win32gui
import win32con
import win32api
import time

def find_browser_window():
    """Find active Chrome or Brave window"""
    browser_handles = []
    
    def enum_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if 'Chrome' in title or 'Brave' in title:
                windows.append((hwnd, title))
        return True
    
    win32gui.EnumWindows(enum_callback, browser_handles)
    # Prioritize the foreground window if it's a browser
    hwnd_fg = win32gui.GetForegroundWindow()
    title_fg = win32gui.GetWindowText(hwnd_fg)
    if 'Chrome' in title_fg or 'Brave' in title_fg:
        return [(hwnd_fg, title_fg)]
        
    return browser_handles

def send_f11_to_window(hwnd):
    """Send F11 key to a specific window for true fullscreen"""
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    
    VK_F11 = 0x7A
    win32api.keybd_event(VK_F11, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(VK_F11, 0, win32con.KEYEVENTF_KEYUP, 0)
    print("✅ F11 key sent for true fullscreen")

def fullscreen_browser():
    """Find browser window and make it TRUE fullscreen (F11 mode)"""
    browser_windows = find_browser_window()
    
    if not browser_windows:
        print(" No Chrome or Brave window found!")
        return False
    
    hwnd, title = browser_windows[0]
    print(f"✅ Found: {title}")
    
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
    time.sleep(0.2)
    
    send_f11_to_window(hwnd)
    
    print(f"✅ True fullscreen activated: {title}")
    return True

if __name__ == "__main__":
    fullscreen_browser()