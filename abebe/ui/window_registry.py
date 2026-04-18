
import tkinter as tk

_game_windows = set()

def register(win: tk.Toplevel):
    _game_windows.add(win)

def unregister(win: tk.Toplevel):
    _game_windows.discard(win)

def close_all():
    for win in list(_game_windows):
        if win.winfo_exists():
            win.destroy()
    _game_windows.clear()