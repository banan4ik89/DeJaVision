import tkinter as tk
import random
import winsound
import os

from abebe.core.utils import block_esc, safe_destroy, get_exe_dir
from abebe.core.config import DATA_DIR, DEATH_IMAGE, HINTS


GIF_NAME = "app/abebe/laugh.gif"
SOUND_NAME = "app/abebe/laugh.wav"



def start_fake_hack(root):
    fake_scanning(root, lambda:
        fake_deleting(root, lambda:
            fake_permission(
                root,
                "Р”РѕСЃС‚СѓРї Рє РєР°РјРµСЂРµ",
                "РџСЂРёР»РѕР¶РµРЅРёРµ Р·Р°РїСЂР°С€РёРІР°РµС‚ РґРѕСЃС‚СѓРї Рє РєР°РјРµСЂРµ",
                lambda: fake_permission(
                    root,
                    "Р”РѕСЃС‚СѓРї Рє РјРёРєСЂРѕС„РѕРЅСѓ",
                    "РџСЂРёР»РѕР¶РµРЅРёРµ Р·Р°РїСЂР°С€РёРІР°РµС‚ РґРѕСЃС‚СѓРї Рє РјРёРєСЂРѕС„РѕРЅСѓ",
                    lambda: show_fake_ip(root)
                )
            )
        )
    )



def fake_scanning(root, next_step):
    win = fullscreen_black(root)
    tk.Label(
        win,
        text="Scanning system...\n[OK] RAM\n[OK] CPU\n[WARNING] Registry\n[CRITICAL] User data",
        fg="lime",
        bg="black",
        font=("Consolas", 16),
        justify="left"
    ).pack(anchor="nw", padx=20, pady=20)

    win.after(3000, lambda: (win.destroy(), next_step()))


def fake_deleting(root, next_step):
    win = fullscreen_black(root)

    label = tk.Label(
        win,
        text="Deleting files...\n0%",
        fg="red",
        bg="black",
        font=("Consolas", 18),
        justify="left"
    )
    label.pack(anchor="nw", padx=20, pady=20)

    progress = 0

    def update():
        nonlocal progress
        progress += random.randint(5, 15)
        progress = min(progress, 100)
        label.config(text=f"Deleting files...\n{progress}%")

        if progress < 100:
            win.after(400, update)
        else:
            win.after(1000, lambda: (win.destroy(), next_step()))

    update()


def fake_permission(root, title, text, next_step):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)
    win.geometry("360x160+500+300")

    tk.Label(win, text=title, font=("Arial", 12, "bold")).pack(pady=10)
    tk.Label(win, text=text).pack(pady=5)

    def approve():
        win.destroy()
        next_step()

    tk.Button(win, text="Р”Р°", width=10, command=approve).pack(side="left", padx=40, pady=20)
    tk.Button(win, text="Р”Р°", width=10, command=approve).pack(side="right", padx=40, pady=20)


def show_fake_ip(root):
    win = fullscreen_black(root)

    fake_ip = f"{random.randint(10,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"

    tk.Label(
        win,
        text=f"IP ADDRESS DETECTED:\n{fake_ip}\nLocation: UA, Kyiv",
        fg="red",
        bg="black",
        font=("Consolas", 20),
        justify="center"
    ).pack(expand=True)

    win.after(3000, lambda: (win.destroy(), show_hack_screen(root)))




def show_hack_screen(root):
    bg = tk.Toplevel(root)
    bg.overrideredirect(True)
    block_esc(bg)
    bg.configure(bg="red")
    bg.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")

    tk.Label(
        bg,
        text="вљ  РќРђРўРЈР РђР› РћР‘РќРђР РЈР–Р•Рќ вљ ",
        font=("Arial", 42, "bold"),
        fg="white",
        bg="red"
    ).pack(expand=True)

    error_windows = []

    def spawn_error():
        win = tk.Toplevel(bg)
        win.overrideredirect(True)
        block_esc(win)

        x = random.randint(0, root.winfo_screenwidth() - 320)
        y = random.randint(0, root.winfo_screenheight() - 140)
        win.geometry(f"300x120+{x}+{y}")
        win.configure(bg="lightgray")

        tk.Label(win, text="РћС€РёР±РєР° СЃРёСЃС‚РµРјС‹", font=("Arial", 10, "bold"), bg="lightgray").pack(anchor="w", padx=8)
        tk.Label(win, text=random.choice(HINTS), bg="lightgray", fg="gray").pack(pady=10)

        error_windows.append(win)

    def chaos():
        for _ in range(5):
            spawn_error()
        winsound.MessageBeep(winsound.MB_ICONHAND)
        bg.after(1200, chaos)

    chaos()

    def finish():
        for w in error_windows:
            safe_destroy(w)
        safe_destroy(bg)

        show_noise_transition(root, duration=350)
        root.after(350, lambda: show_gif_with_sound(root))


    bg.after(10000, finish)


GIF_SUBTITLES = [
    (0,    "Ha...", False),
    (800,  "Ha...", False),
    (1600, "Ha...", False),
    (2400, "Ha...", False),
    (3200, "Ha...", False),
    (4300, "Fuck you...", True),
    (4600, "iobey98", True)
]

def shake_label(label, base_x, base_y, intensity=3, speed=35):
    def jitter():
        if not label.winfo_exists():
            return
        dx = random.randint(-intensity, intensity)
        dy = random.randint(-intensity, intensity)
        label.place_configure(x=base_x + dx, y=base_y + dy)
        label.after(speed, jitter)

    jitter()


def type_text(label, text, color="white", speed=40):
    label.config(text="", fg=color)
    full_text = text + " в–€"

    def step(i=0):
        if not label.winfo_exists():
            return
        if i <= len(full_text):
            label.config(text=full_text[:i])
            label.after(speed, step, i + 1)

    step()




def show_gif_with_sound(root, duration=5000):
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
        text="FILE_056_FUCK_YOU_Abebe.MP4",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 10)
    ).pack(side="left", padx=8, pady=4)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    win.geometry(f"{sw}x{sh}+0+0")

    gif_path = os.path.join(get_exe_dir(), DATA_DIR, GIF_NAME)
    sound_path = os.path.join(get_exe_dir(), DATA_DIR, SOUND_NAME)

    
    frames = []
    i = 0
    while True:
        try:
            frames.append(
                tk.PhotoImage(file=gif_path, format=f"gif -index {i}")
            )
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
        font=("Terminal", 18),
        justify="center",
        wraplength=int(sw * 0.75),
        highlightbackground="white",
        highlightthickness=1
    )
    base_x = sw // 2
    base_y = int(sh * 0.78)

    subtitle_label.place(
        x=base_x,
        y=base_y,
        anchor="center"
    )


    def play_subtitles(index=0):
        if not win.winfo_exists():
            return
        if index >= len(GIF_SUBTITLES):
            return

        start_time, text, is_red = GIF_SUBTITLES[index]

        if is_red:
            type_text(subtitle_label, text, color="red", speed=30)
            shake_label(subtitle_label, base_x, base_y, intensity=6, speed=25)
        else:
            type_text(subtitle_label, text, color="white", speed=45)
            shake_label(subtitle_label, base_x, base_y, intensity=2, speed=45)

        if index + 1 < len(GIF_SUBTITLES):
            next_time = GIF_SUBTITLES[index + 1][0]
            delay = next_time - start_time
        else:
            delay = duration - start_time

        win.after(delay, lambda: play_subtitles(index + 1))


    play_subtitles()

    
    if os.path.exists(sound_path):
        winsound.PlaySound(
            sound_path,
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP
        )

    
    def end():
        winsound.PlaySound(None, winsound.SND_PURGE)
        win.destroy()
        show_death_screen(root)

    win.after(duration, end)





def show_death_screen(root):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)
    win.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")

    canvas = tk.Canvas(win, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    img = tk.PhotoImage(
        file=os.path.join(get_exe_dir(), DATA_DIR, DEATH_IMAGE)
    )
    canvas.create_image(
        root.winfo_screenwidth() // 2,
        root.winfo_screenheight() // 2,
        image=img
    )
    canvas.image = img

    win.after(5000, root.destroy)




def fullscreen_black(root):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)
    win.configure(bg="black")
    win.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    return win

def show_black_transition(root, duration=200):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)
    win.configure(bg="black")
    win.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")

    win.after(duration, win.destroy)

def show_noise_transition(root, duration=1500, density=9820):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    win.geometry(f"{sw}x{sh}+0+0")

    canvas = tk.Canvas(win, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    def draw_noise():
        canvas.delete("all")
        for _ in range(density):
            x = random.randint(0, sw)
            y = random.randint(0, sh)
            size = random.randint(1, 3)
            color = random.choice(("white", "gray", "#888888"))
            canvas.create_rectangle(
                x, y, x + size, y + size,
                fill=color, outline=color
            )

    def animate():
        if not win.winfo_exists():
            return
        draw_noise()
        win.after(50, animate)

    animate()
    win.after(duration, win.destroy)


