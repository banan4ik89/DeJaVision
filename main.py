# Project: Abebe Watcher(ABEBE_PROTOCOL)
# Author: Denis Kravchenko
# Started: Feb 10, 2026
# All assets, story, design, and main game logic by the author.
# Some helper code assisted by AI.

import tkinter as tk
from utils import block_esc
from password_window import show_password_window
from intro import show_intro
from background_music import play_music
from config import BACKGROUND_MUSIC
import time


def styled_button(parent, text, command, fg="white"):
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        font=("Terminal", 16),
        bg="black",
        fg=fg,
        activebackground="black",
        activeforeground="lime",
        relief="ridge",
        borderwidth=2,
        width=34,
        height=2
    )

    btn.bind("<Enter>", lambda e: btn.config(fg="lime"))
    btn.bind("<Leave>", lambda e: btn.config(fg=fg))
    return btn



def make_draggable(win):
    def start(e):
        win.x = e.x
        win.y = e.y

    def move(e):
        win.geometry(f"+{e.x_root - win.x}+{e.y_root - win.y}")

    win.bind("<Button-1>", start)
    win.bind("<B1-Motion>", move)

def show_splash(root):
    splash = tk.Toplevel(root)
    splash.configure(bg="black")
    splash.attributes("-fullscreen", True)
    splash.attributes("-alpha", 1.0)  

    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()

    
    tk.Label(
        splash,
        text="TEST GAME",
        fg="lime",
        bg="black",
        font=("Terminal", 48, "bold")
    ).pack(pady=sh//3)

    
    tk.Label(
        splash,
        text="Made by Mr. Banandee",
        fg="gray",
        bg="black",
        font=("Terminal", 20)
    ).pack(pady=20)

    
    def fade_out(alpha=1.0):
        if alpha > 0:
            splash.attributes("-alpha", alpha)
            splash.after(50, fade_out, alpha - 0.05)
        else:
            splash.destroy()

    
    splash.after(2000, fade_out)

    return splash



def exit_app():
    root.destroy()


root = tk.Tk()
root.configure(bg="black")
root.attributes("-fullscreen", True)
block_esc(root)

sw = root.winfo_screenwidth()
sh = root.winfo_screenheight()
root.geometry(f"{sw}x{sh}+0+0")

play_music(BACKGROUND_MUSIC)
show_splash(root)


title_bar = tk.Frame(root, bg="#C0C0C0", height=28)
title_bar.pack(fill="x", side="top")

make_draggable(title_bar)

tk.Label(
    title_bar,
    text="SECURE_SYSTEM.EXE",
    bg="#C0C0C0",
    fg="black",
    font=("Terminal", 10)
).pack(side="left", padx=8, pady=4)

close_btn = tk.Label(
    title_bar,
    text=" ✕ ",
    bg="#C0C0C0",
    fg="black",
    font=("Terminal", 12, "bold"),
    cursor="hand2"
)
close_btn.pack(side="right", padx=6, pady=2)

close_btn.bind("<Button-1>", lambda e: exit_app())
close_btn.bind("<Enter>", lambda e: close_btn.config(bg="red", fg="white"))
close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#C0C0C0", fg="black"))



content = tk.Frame(root, bg="black")
content.pack(expand=True)

tk.Label(
    content,
    text="Abebe Protocol",
    fg="lime",
    bg="black",
    font=("Terminal", 56)
).pack(pady=30)

tk.Label(
    content,
    text="Made by Mr. Banandee",
    fg="gray",
    bg="black",
    font=("Terminal", 10)
).pack(pady=5)

tk.Label(
    content,
    text="AUTHORIZED ACCESS ONLY",
    fg="gray",
    bg="black",
    font=("Terminal", 14)
).pack(pady=10)

styled_button(
    content,
    "OPEN SECRET FILES",
    command=lambda: show_password_window(root)
).pack(pady=12)

styled_button(
    content,
    "INTRODUCTION",
    command=lambda: show_intro(root)
).pack(pady=12)

styled_button(
    content,
    "EXIT SYSTEM",
    command=exit_app,
    fg="red"
).pack(pady=40)

version_label = tk.Label(
    root,
    text="Version 0.2.0-alpha",
    fg="gray",
    bg="black",
    font=("Terminal", 10)
)
version_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-5)



root.mainloop()
