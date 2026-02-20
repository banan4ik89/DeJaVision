# settings_window.py

import tkinter as tk
from background_music import stop_music, resume_music
from utils import block_esc


def make_draggable(win, bar):
    def start(e):
        win.x = e.x
        win.y = e.y

    def move(e):
        win.geometry(f"+{e.x_root - win.x}+{e.y_root - win.y}")

    bar.bind("<Button-1>", start)
    bar.bind("<B1-Motion>", move)


def show_settings(root):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg="black")
    win.attributes("-topmost", True)
    win.geometry("420x300+500+250")

    # ===== TITLE BAR =====
    title_bar = tk.Frame(win, bg="#C0C0C0", height=26)
    title_bar.pack(fill="x")

    tk.Label(
        title_bar,
        text="SYSTEM_SETTINGS.EXE",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 10)
    ).pack(side="left", padx=8)

    close_btn = tk.Label(
        title_bar,
        text=" ✕ ",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 10, "bold"),
        cursor="hand2"
    )
    close_btn.pack(side="right", padx=6)
    close_btn.bind("<Button-1>", lambda e: win.destroy())
    close_btn.bind("<Enter>", lambda e: close_btn.config(bg="red", fg="white"))
    close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#C0C0C0", fg="black"))

    make_draggable(win, title_bar)

    # ===== CONTENT =====
    content = tk.Frame(
        win,
        bg="black",
        highlightbackground="lime",
        highlightthickness=2
    )
    content.pack(expand=True, fill="both", padx=6, pady=6)

    tk.Label(
        content,
        text="AUDIO SETTINGS",
        fg="lime",
        bg="black",
        font=("Terminal", 14)
    ).pack(pady=10)

    # ===== MUSIC TOGGLE =====
    music_on = tk.BooleanVar(value=True)

    def toggle_music():
        if music_on.get():
            resume_music()
        else:
            stop_music()

    tk.Checkbutton(
        content,
        text="Background Music",
        variable=music_on,
        command=toggle_music,
        fg="white",
        bg="black",
        selectcolor="black",
        activebackground="black",
        activeforeground="lime",
        font=("Terminal", 12)
    ).pack(pady=5)

    # ===== FULLSCREEN TOGGLE =====
    fullscreen = tk.BooleanVar(value=True)

    def toggle_fullscreen():
        root.attributes("-fullscreen", fullscreen.get())

    tk.Checkbutton(
        content,
        text="Fullscreen Mode",
        variable=fullscreen,
        command=toggle_fullscreen,
        fg="white",
        bg="black",
        selectcolor="black",
        activebackground="black",
        activeforeground="lime",
        font=("Terminal", 12)
    ).pack(pady=5)

    # ===== SYSTEM RESET BUTTON =====
    def reset_system():
        root.destroy()

    tk.Button(
        content,
        text="RESTART SYSTEM",
        command=reset_system,
        font=("Terminal", 12),
        bg="black",
        fg="red",
        activeforeground="lime",
        relief="ridge",
        width=22
    ).pack(pady=20)