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
from settings_window import show_settings
import game_state
import testing_maze

import time

game_running = False

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

def exit_game_confirmed():
    global game_running

    # закрываем ВСЕ Toplevel окна
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()

    game_running = False
    unlock_start_button()

def start_new_game():
    testing_maze.start_game(root)

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

    splash.lift()
    splash.attributes("-topmost", True)
    splash.after(10, lambda: splash.attributes("-topmost", False))

    # ===== Skip control =====
    skip_requested = [False]

    def skip_splash(event=None):
        if not skip_requested[0]:
            skip_requested[0] = True
            splash.destroy()

    splash.bind("<Key>", skip_splash)
    splash.bind("<Button-1>", skip_splash)
    splash.focus_set()

    # ===== Console text widget =====
    text_widget = tk.Label(
        splash,
        text="",
        fg="lime",
        bg="black",
        font=("Terminal", 16),
        justify="left",
        anchor="nw"
    )
    text_widget.place(x=40, y=40)

    # ===== Boot lines =====
    lines = [
        "Booting ABEBE_PROTOCOL v0.2.3-alpha...",
        "",
        "Loading core modules...",
        "Loading security layer...",
        "Initializing trust system...",
        "Injecting watcher module...",
        "Watcher status: ONLINE",
        "",
        "Checking system integrity...",
        "Verifying employee database...",
        "",
        "Project: Abebe Protocol",
        "Author: Denis Kravchenko (Mr. Banandee)",
        "",
        "Finalizing boot sequence...",
        "System ready.",
        "",
        "WARNING: Suspicious presence detected.",
        "Analyzing entity...",
        "ACCESS LEVEL: UNKNOWN",
        "CRITICAL SECURITY FAILURE",
        "SYSTEM WILL SHUT DOWN"
    ]

    final_message = "\n\nJust kidding.\nWelcome back."

    full_text = [""]
    line_index = [0]
    warning_triggered = [False]
    
    game_state.init_game_state(root, open_game_btn)
    

    
    # ===== Typing logic =====
    def type_next_line():
        if skip_requested[0]:
            return

        if line_index[0] >= len(lines):
            splash.after(2000, show_final_phase)
            return

        current_line = lines[line_index[0]] + "\n"
        char_index = [0]

        def type_char():
            if skip_requested[0]:
                return

            if char_index[0] < len(current_line):
                full_text[0] += current_line[char_index[0]]
                text_widget.config(text=full_text[0])
                char_index[0] += 1
                splash.after(35, type_char)
            else:
                # После WARNING делаем текст красным
                if "WARNING: Suspicious presence detected." in current_line:
                    text_widget.config(fg="red")
                    warning_triggered[0] = True

                line_index[0] += 1
                splash.after(300, type_next_line)

        type_char()

    # ===== Final phase =====
    def show_final_phase():
        if skip_requested[0]:
            return

        text_widget.config(fg="lime")
        char_index = [0]

        def type_final():
            if skip_requested[0]:
                return

            if char_index[0] < len(final_message):
                full_text[0] += final_message[char_index[0]]
                text_widget.config(text=full_text[0])
                char_index[0] += 1
                splash.after(45, type_final)
            else:
                splash.after(2000, fade_out)

        type_final()

    # ===== Fade out =====
    def fade_out(alpha=1.0):
        if skip_requested[0]:
            return

        if alpha > 0:
            splash.attributes("-alpha", alpha)
            splash.after(50, fade_out, alpha - 0.05)
        else:
            splash.destroy()

    splash.after(700, type_next_line)

    return splash



def exit_app():
    root.destroy()


root = tk.Tk()
root.withdraw()
root.configure(bg="black")
root.attributes("-fullscreen", True)
block_esc(root)

sw = root.winfo_screenwidth()
sh = root.winfo_screenheight()
root.geometry(f"{sw}x{sh}+0+0")

play_music(BACKGROUND_MUSIC)

root.after(100, lambda: show_splash(root))
root.deiconify()
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

def lock_start_button():
    open_game_btn.config(
        state="disabled",
        fg="gray",
        text="ACCESS LOCKED"
    )

def unlock_start_button():
    open_game_btn.config(
        state="normal",
        fg="white",
        text="OPEN SECRET FILES"
    )

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

def start_game():
    global game_running
    if game_running:
        return

    game_running = True
    lock_start_button()
    show_password_window(root)
    
styled_button(
    content,
    "NEW GAME",
    command=start_new_game
).pack(pady=12)

load_game_btn = styled_button(
    content,
    "LOAD GAME",
    command=lambda: None
)

load_game_btn.config(
    state="disabled",
    fg="gray"
)

load_game_btn.pack(pady=12)
  
open_game_btn = styled_button(
    content,
    "OPEN SECRET FILES",
    command=lambda: game_state.start_game(show_password_window)
)
open_game_btn.pack(pady=12)

styled_button(
    content,
    "SYSTEM SETTINGS",
    command=lambda: show_settings(root)
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
    text="Version 0.2.5-alpha",
    fg="gray",
    bg="black",
    font=("Terminal", 10)
)
version_label.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-5)



root.mainloop()
