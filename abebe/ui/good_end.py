import tkinter as tk
import winsound
import os
import random

from abebe.core.utils import block_esc, get_exe_dir
from abebe.core.config import DATA_DIR, ARCHIVE_FILE
from abebe.core.background_music import resume_music


GIF_NAME = "app/abebe/goodendabebe.gif"
SOUND_NAME = "app/abebe/goodendabebe.wav"
DURATION = 8000



SUBTITLES = [
    (0, "Oh, congratulations."),
    (2000, "You are one of us after all."),
    (4200, "You may access the files."),
    (6200, "I know you are intruder.")
]



def type_text(label, text, color="white", speed=35):
    label.config(text="", fg=color)
    full_text = text + " в–€"

    def step(i=0):
        if not label.winfo_exists():
            return
        if i <= len(full_text):
            label.config(text=full_text[:i])
            label.after(speed, step, i + 1)

    step()


def open_archive():
    path = os.path.join(get_exe_dir(), DATA_DIR, ARCHIVE_FILE)
    if os.path.exists(path):
        os.startfile(path)


def show_good_end(root):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)
    win.configure(bg="black")

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    win.geometry(f"{sw}x{sh}+0+0")

    gif_path = os.path.join(get_exe_dir(), DATA_DIR, GIF_NAME)
    sound_path = os.path.join(get_exe_dir(), DATA_DIR, SOUND_NAME)

    
    title_bar = tk.Frame(win, bg="#C0C0C0", height=28)
    title_bar.pack(fill="x", side="top")

    tk.Label(
        title_bar,
        text="FILE_055_Congratulations_Abebe.MP4",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 10)
    ).pack(side="left", padx=8, pady=4)

    
    def close_scene():
        winsound.PlaySound(None, winsound.SND_PURGE)
        win.destroy()
        open_archive()
        resume_music()
        root.deiconify()

    
    close_btn = tk.Label(
        title_bar,
        text=" вњ• ",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 12, "bold"),
        cursor="hand2"
    )
    close_btn.pack(side="right", padx=6, pady=2)

    close_btn.bind("<Button-1>", lambda e: close_scene())
    close_btn.bind("<Enter>", lambda e: close_btn.config(bg="red", fg="white"))
    close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#C0C0C0", fg="black"))

    
    frames = []
    i = 0
    while True:
        try:
            frames.append(tk.PhotoImage(file=gif_path, format=f"gif -index {i}"))
            i += 1
        except:
            break

    gif_label = tk.Label(win, bg="black")
    gif_label.pack(expand=True)

    def animate(idx=0):
        if not win.winfo_exists():
            return
        gif_label.config(image=frames[idx])
        win.after(80, animate, (idx + 1) % len(frames))

    animate()

    
    subtitle_label = tk.Label(
        win,
        text="",
        fg="white",
        bg="black",
        font=("Terminal", 16),
        justify="center",
        wraplength=int(sw * 0.8),
        highlightbackground="white",
        highlightthickness=1
    )

    base_x = sw // 2
    base_y = int(sh * 0.75)
    subtitle_label.place(x=base_x, y=base_y, anchor="center")

    shake_job = None

    def stop_shake():
        nonlocal shake_job
        if shake_job:
            subtitle_label.after_cancel(shake_job)
            shake_job = None
        subtitle_label.place(x=base_x, y=base_y, anchor="center")

    def start_shake(intensity=7, speed=25):
        nonlocal shake_job

        def jitter():
            nonlocal shake_job
            dx = random.randint(-intensity, intensity)
            dy = random.randint(-intensity, intensity)
            subtitle_label.place(
                x=base_x + dx,
                y=base_y + dy,
                anchor="center"
            )
            shake_job = subtitle_label.after(speed, jitter)

        jitter()

    def play_subtitles(index=0):
        if not win.winfo_exists() or index >= len(SUBTITLES):
            return

        start_time, text = SUBTITLES[index]
        stop_shake()

        if text == "I know you are intruder.":
            type_text(subtitle_label, text, color="red", speed=28)
            start_shake()
        else:
            type_text(subtitle_label, text)

        if index + 1 < len(SUBTITLES):
            delay = SUBTITLES[index + 1][0] - start_time
        else:
            delay = DURATION - start_time

        win.after(delay, lambda: play_subtitles(index + 1))

    play_subtitles()

    
    if os.path.exists(sound_path):
        winsound.PlaySound(
            sound_path,
            winsound.SND_FILENAME | winsound.SND_ASYNC
        )

    
    win.after(DURATION, close_scene)

