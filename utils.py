import os
import sys

def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS      
    return os.path.dirname(os.path.abspath(__file__))

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(*parts):
    return os.path.join(get_exe_dir(), *parts)

def block_esc(widget):
    widget.bind("<Escape>", lambda e: "break")

def safe_destroy(win):
    try:
        if win and win.winfo_exists():
            win.destroy()
    except:
        pass
