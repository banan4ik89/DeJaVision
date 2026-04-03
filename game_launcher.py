import tkinter as tk


def run_pygame_session(root, callback, *args, **kwargs):
    if root is None:
        return callback(*args, **kwargs)

    hidden_windows = []

    def hide_window(window):
        try:
            if window.winfo_exists() and window.state() != "withdrawn":
                hidden_windows.append(window)
                window.withdraw()
        except tk.TclError:
            pass

    hide_window(root)
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            hide_window(child)

    try:
        root.update_idletasks()
        return callback(*args, **kwargs)
    finally:
        for window in hidden_windows:
            try:
                if window.winfo_exists():
                    window.deiconify()
            except tk.TclError:
                pass
        try:
            if root.winfo_exists():
                root.lift()
                root.focus_force()
        except tk.TclError:
            pass
