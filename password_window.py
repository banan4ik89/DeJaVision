import tkinter as tk
from tkinter import font
from PIL import Image, ImageTk
import os

from utils import block_esc, get_exe_dir
from config import *
from fake_hack import start_fake_hack
from good_end import show_good_end
from minigame_pinball import start_pinball
from background_music import play_music, stop_music, resume_music
from trust_system import TrustSystem
from abebe_watcher import AbebeWatcher
from hack_decoder import show_hack_decoder
from data.events.eye_watcher_event import EyeWatcherEvent
from abebe_confirm_exit import show_abebe_confirm
from game_state import exit_game_confirmed
from window_registry import register, unregister
from data.events.creeper_event import CreeperEvent
from secret_maze import start_secret_maze
from testing_maze import start_testing_maze
from tutor_maze import start_tutor_maze
import random
from city_maze import start_city_maze
from game_launcher import run_pygame_session

from trust_system import TrustSystem
from abebe_watcher import AbebeWatcher


# ===================== HISTORY (очищается при перезапуске) =====================
password_history = []


# ===================== DRAG =====================
def make_draggable(win, bar):
    def start(e):
        win.x = e.x
        win.y = e.y

    def move(e):
        win.geometry(f"+{e.x_root - win.x}+{e.y_root - win.y}")

    bar.bind("<Button-1>", start)
    bar.bind("<B1-Motion>", move)


# ===================== BASE STYLED WINDOW =====================
def create_styled_window(root, title_text, width=400, height=300):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg="black")
    block_esc(win)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    win.geometry(f"{width}x{height}+{sw//2 - width//2}+{sh//2 - height//2}")

    # 🔥 ВАЖНО — держать поверх root
    win.transient(root)
    win.lift()
    win.attributes("-topmost", True)
    win.after(100, lambda: win.attributes("-topmost", False))

    # TITLE BAR
    title_bar = tk.Frame(win, bg="#C0C0C0", height=28)
    title_bar.pack(fill="x", side="top")

    tk.Label(
        title_bar,
        text=title_text,
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 10)
    ).pack(side="left", padx=8)

    close_btn = tk.Label(
        title_bar,
        text=" ✕ ",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 12, "bold"),
        cursor="hand2"
    )
    close_btn.pack(side="right", padx=6)

    close_btn.bind(
        "<Button-1>",
        lambda e: show_abebe_confirm(
            root,
            on_yes=lambda: exit_game_confirmed(),
            on_no=lambda: None  # ничего не делаем
        )
    )
    close_btn.bind("<Enter>", lambda e: close_btn.config(bg="red", fg="white"))
    close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#C0C0C0", fg="black"))

    make_draggable(win, title_bar)

    content = tk.Frame(
        win,
        bg="black",
        highlightbackground="lime",
        highlightthickness=2
    )
    content.pack(expand=True, fill="both", padx=6, pady=6)

    return win, content



# ===================== HELP WINDOW =====================
def show_help_window(root):
    win, content = create_styled_window(root, "HELP.EXE", 420, 300)
    register(win)

    tk.Label(
        content,
        text="AVAILABLE COMMANDS",
        fg="lime",
        bg="black",
        font=("Terminal", 14)
    ).pack(pady=15)

    commands = [
        "!help - show commands",
        "!history - show password history",
        "!gallery - open gallery",
        "!abebe_watcher - restart watcher",
        "!info - show info.txt",
        "!dev - show developer info",
        "!reset - reset game (clear password history & watcher)",
        "!sound on/off - toggle background music",
        "!easteregg - show hidden image",
        "!tut - open tutor / training maze",
        "!city - open city maze",
    ]

    for cmd in commands:
        tk.Label(
            content,
            text=cmd,
            fg="white",
            bg="black",
            font=("Terminal", 12)
        ).pack(anchor="w", padx=20, pady=4)

# ===================== HISTORY WINDOW =====================
def show_history_window(root):
    win, content = create_styled_window(root, "HISTORY.LOG", 420, 300)
    register(win)
    tk.Label(
        content,
        text="ENTERED PASSWORDS",
        fg="lime",
        bg="black",
        font=("Terminal", 14)
    ).pack(pady=10)

    if not password_history:
        tk.Label(
            content,
            text="No passwords yet.",
            fg="gray",
            bg="black"
        ).pack()
        return

    for pwd in password_history:
        tk.Label(
            content,
            text=pwd,
            fg="white",
            bg="black",
            font=("Consolas", 12)
        ).pack(anchor="w", padx=20)

def show_hack_hint_window(root):
    win, content = create_styled_window(root, "HELPER.EXE", 300, 160)
    register(win)
    tk.Label(
        content,
        text="SYSTEM TIP",
        fg="lime",
        bg="black",
        font=("Terminal", 14)
    ).pack(pady=15)

    tk.Label(
        content,
        text="Type command:\n\n!hack",
        fg="white",
        bg="black",
        font=("Consolas", 12),
        justify="center"
    ).pack(pady=10)

import tkinter as tk
import winsound
import os
import threading

def show_iobey_audio(root):
    win, content = create_styled_window(root, "AUDIO_PLAYER.EXE", 360, 220)
    register(win)
    # держим окно поверх всего
    win.attributes("-topmost", True)

    tk.Label(
        content,
        text="SECURE AUDIO FILE",
        fg="lime",
        bg="black",
        font=("Terminal", 14)
    ).pack(pady=15)

    status = tk.Label(
        content,
        text="iobey98.wav",
        fg="white",
        bg="black",
        font=("Consolas", 11)
    )
    status.pack(pady=5)

    audio_path = os.path.join(get_exe_dir(), "data", "iobey98.wav")

    def play_audio():
        if not os.path.exists(audio_path):
            status.config(text="FILE NOT FOUND", fg="red")
            return

        stop_music()  # останавливаем фон
        status.config(text="PLAYING...", fg="lime")

        # ===== поток для звука =====
        def sound_thread():
            winsound.PlaySound(audio_path, winsound.SND_FILENAME)
            # После окончания звука
            root.after(100, stop_audio)

        threading.Thread(target=sound_thread, daemon=True).start()

    def stop_audio():
        winsound.PlaySound(None, winsound.SND_PURGE)  # остановка
        status.config(text="STOPPED", fg="gray")
        resume_music()  # возобновляем фон
        if win.winfo_exists():
            win.destroy()  # закрываем окно

    # ===== BUTTONS =====
    btn_frame = tk.Frame(content, bg="black")
    btn_frame.pack(pady=20)

    play_btn = tk.Button(
        btn_frame,
        text="▶ PLAY",
        command=play_audio,
        bg="black",
        fg="lime",
        activebackground="black",
        activeforeground="white",
        relief="ridge",
        width=10,
        cursor="hand2"
    )
    play_btn.pack(side="left", padx=10)

    stop_btn = tk.Button(
        btn_frame,
        text="■ STOP",
        command=stop_audio,
        bg="black",
        fg="white",
        activebackground="black",
        activeforeground="red",
        relief="ridge",
        width=10,
        cursor="hand2"
    )
    stop_btn.pack(side="left", padx=10)





# ===================== GALLERY WINDOW =====================
def show_gallery_window(root):
    win, content = create_styled_window(root, "GALLERY.EXE", 420, 320)
    register(win)
    tk.Label(
        content,
        text="FILE STORAGE",
        fg="lime",
        bg="black",
        font=("Terminal", 14)
    ).pack(pady=15)

    file_frame = tk.Frame(content, bg="black")
    file_frame.pack(pady=20)

    # Путь к папке data
    data_dir = os.path.join(get_exe_dir(), "data")
    img_path = os.path.join(data_dir, "death.png")

    # --- Открытие изображения в отдельном окне ---
    def open_image():
        if not os.path.exists(img_path):
            tk.messagebox.showerror("Error", f"File not found:\n{img_path}")
            return

        img_win, img_content = create_styled_window(root, "death.png", 600, 500)

        # Загружаем и масштабируем изображение
        img = Image.open(img_path)
        img.thumbnail((580, 480))  # сохраняем пропорции
        photo = ImageTk.PhotoImage(img)

        # Сохраняем ссылку на изображение, чтобы Tkinter его не удалил
        label = tk.Label(img_content, image=photo, bg="black")
        label.image = photo
        label.pack(expand=True, pady=10)

    # Кнопка-файл
    file_button = tk.Button(
        file_frame,
        width=10,
        height=5,
        command=open_image,
        bg="black",
        activebackground="black",
        relief="ridge",
        borderwidth=2,
        highlightbackground="lime",
        cursor="hand2"
    )
    file_button.pack()

    # Подпись под файлом
    tk.Label(
        file_frame,
        text="death.png",
        fg="white",
        bg="black",
        font=("Consolas", 11)
    ).pack(pady=6)


# ===================== PASSWORD WINDOW =====================
def show_password_window(root):
    global password_history

    win, content = create_styled_window(root, "PASSWORD_CHECK.EXE", 360, 300)
    register(win)
    trust = TrustSystem(root)
    abebe = AbebeWatcher(root, trust)
    current_theme = abebe.get_current_theme()
    
    
    tk.Label(
        content,
        text="ENTER PASSWORD",
        fg="white",
        bg="black",
        font=("Terminal", 14)
    ).pack(pady=10)

    
    entry_frame = tk.Frame(content, bg="black")
    entry_frame.pack(pady=5)

    entry = tk.Entry(
        entry_frame,
        show="*",
        font=("Consolas", 14),
        bg="black",
        fg="lime",
        insertbackground="lime",
        relief="flat",
        highlightthickness=2,
        highlightbackground="lime",
        highlightcolor="lime",
        width=18
    )
    entry.pack(side="left")
    

    
    show_password = False

    def toggle_password():
        nonlocal show_password, eye_event_active

    # 👁 игрок пытается ПОКАЗАТЬ пароль
        if show_password and not eye_event_active and can_trigger_eye_event():
            eye_event_active = True

            def on_eye_finish():
                nonlocal eye_event_active
                eye_event_active = False

            EyeWatcherEvent(
                root=root,
                trust_system=trust,
                is_password_visible_cb=lambda: show_password,
                on_finish=on_eye_finish
            )

    # обычное поведение кнопки
        show_password = not show_password
        entry.config(show="" if show_password else "*")
        eye_btn.config(text="🚫" if show_password else "👁")


    eye_btn = tk.Button(
        entry_frame,
        text="👁",
        command=toggle_password,
        bg="black",
        fg="lime",
        activebackground="black",
        activeforeground="white",
        relief="flat",
        font=("Consolas", 14),
        cursor="hand2"
    )
    eye_btn.pack(side="left", padx=6)
    
    def show_hint():
        show_hack_hint_window(root)

    hint_btn = tk.Button(
        entry_frame,
        text="?",
        command=show_hint,
        bg="black",
        fg="yellow",
        activebackground="black",
        activeforeground="lime",
        relief="flat",
        font=("Terminal", 14, "bold"),
        cursor="hand2",
        width=2
    )
    hint_btn.pack(side="left", padx=4)


    
    status_label = tk.Label(
        content,
        text="",
        fg="red",
        bg="black",
        font=("Consolas", 10)
    )
    status_label.pack()
    status_clear_job = None


    f = font.Font(overstrike=1)
    tk.Label(content, text="пароль: 1401", font=f, fg="gray", bg="black").pack()
    tk.Label(content, text="новый пароль: 12525", fg="gray", bg="black").pack()

    PASSWORD_ACTIONS = {
        "1401": start_fake_hack,
        "12525": show_good_end,
        "iobey98": show_iobey_audio
    }
    
    def can_trigger_eye_event():
        return trust.trust >= 70 and random.random() < 1.0
    eye_event_active = False
    
    def clear_status():
        nonlocal status_clear_job
        status_label.config(text="")
        status_clear_job = None

    
    def show_status(text, color="red", timeout=5000):
        nonlocal status_clear_job

    # отменяем предыдущий таймер
        if status_clear_job:
            win.after_cancel(status_clear_job)
            status_clear_job = None

        status_label.config(text=text, fg=color)

    # автоочистка
        status_clear_job = win.after(timeout, clear_status)
        
    last_submit_time = 0
    SUBMIT_COOLDOWN = 700  # миллисекунды
    
    def unlock_confirm(delay=500):
        win.after(delay, lambda: confirm_btn.config(state="normal"))


    def check():
        nonlocal abebe, eye_event_active
        confirm_btn.config(state="disabled")
        clear_status()

        pwd = entry.get().strip()
        
        import string
        import time
        nonlocal last_submit_time

        now = int(time.time() * 1000)
        if now - last_submit_time < SUBMIT_COOLDOWN:
            show_status("Please wait...")
            unlock_confirm()
            return

        last_submit_time = now

        if not (1 <= len(pwd) <= 18):
            show_status("Input length must be 1–18 characters.")
            unlock_confirm()
            return



        if not pwd:
            show_status(text="Empty input is not allowed.")
            entry.delete(0, tk.END)
            unlock_confirm()
            return


        if " " in pwd:
            show_status(text="Spaces are not allowed.")
            entry.delete(0, tk.END)
            unlock_confirm()
            return


        allowed_chars = string.ascii_letters + string.digits + string.punctuation

        if any(c not in allowed_chars for c in pwd):
            show_status(text="Invalid characters detected.")
            entry.delete(0, tk.END)
            unlock_confirm()
            return

        
        

        
        if pwd.startswith("!"):
            confirm_btn.config(state="normal")

            if pwd == "!help":
                show_help_window(root)
            elif pwd == "!history":
                show_history_window(root)
            elif pwd == "!gallery":
                show_gallery_window(root)
            elif pwd == "!abebe_watcher":
                abebe.destroy()
                abebe = AbebeWatcher(root, trust)
            elif pwd == "!info":
                info_path = os.path.join(get_exe_dir(), "info.txt")
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        info_text = f.read()
                    info_win, info_content = create_styled_window(root, "INFO.TXT", 400, 300)
                    text_widget = tk.Text(info_content, bg="black", fg="lime", font=("Consolas", 12), wrap="word")
                    text_widget.insert("1.0", info_text)
                    text_widget.config(state="disabled")
                    text_widget.pack(expand=True, fill="both", padx=5, pady=5)
                else:
                    status_label.config(text="info.txt not found")

            # ===== DEV =====
            elif pwd == "!dev":
                dev_win, dev_content = create_styled_window(root, "DEV.INFO", 400, 300)
                tk.Label(dev_content, text=f"Password History:\n{password_history}", fg="lime", bg="black", font=("Consolas", 12), justify="left").pack(padx=10, pady=10)
                tk.Label(dev_content, text=f"Trust Level: {trust.level}", fg="lime", bg="black", font=("Consolas", 12)).pack(padx=10, pady=5)

            # ===== RESET =====
            elif pwd == "!reset":
                password_history.clear()
                trust.trust = 50
                trust.suspicion = 0
                trust.update_ui()
                abebe.destroy()
                abebe = AbebeWatcher(root, trust)
                show_status("System reset completed.", color="lime")

            elif pwd =="!sec":
                run_pygame_session(root, start_secret_maze, root)
            elif pwd =="!test":
                run_pygame_session(root, start_testing_maze, root)
            elif pwd == "!tut":
                run_pygame_session(root, start_tutor_maze, root)
            elif pwd == "!city":
                run_pygame_session(root, start_city_maze, root)

            elif pwd == "!summonnotcreep":
                CreeperEvent(root, trust)

            
            elif pwd == "!hack":
                show_hack_decoder(root, abebe.get_current_theme())
                
            elif pwd == "!summon_eye":
                nonlocal eye_event_active
                if not eye_event_active:
                    eye_event_active = True

                    def on_eye_finish():
                        nonlocal eye_event_active
                        eye_event_active = False

        # Запускаем EyeWatcher без условий
                    EyeWatcherEvent(
                        root=root,
                        trust_system=trust,
                        is_password_visible_cb=lambda: show_password,
                        on_finish=on_eye_finish,
                        watch_time=3000
                    )

                show_status("EyeWatcher summoned!", color="lime")





            # ===== SOUND =====
            elif pwd.startswith("!sound"):
                args = pwd.split()
                if len(args) > 1 and args[1].lower() == "off":
                    stop_music()
                    status_label.config(text="Music turned OFF")
                elif len(args) > 1 and args[1].lower() == "on":
                    resume_music()
                    status_label.config(text="Music turned ON")
                else:
                    status_label.config(text="Usage: !sound on/off")
            
                        # ===== SECRET INCIDENT WINDOW =====
            elif pwd == "!12340":
                incident_path = os.path.join(get_exe_dir(), "data", "12340.txt")
                if os.path.exists(incident_path):
                    with open(incident_path, "r", encoding="utf-8") as f:
                        incident_text = f.read()
                    incident_win, incident_content = create_styled_window(root, "1230.TXT", 400, 300)
                    text_widget = tk.Text(incident_content, bg="black", fg="lime", font=("Consolas", 12), wrap="word")
                    text_widget.insert("1.0", incident_text)
                    text_widget.config(state="disabled")
                    text_widget.pack(expand=True, fill="both", padx=5, pady=5)
                else:
                    status_label.config(text="12340.txt not found")

            # ===== EASTER EGG =====
            elif pwd == "!easteregg":
                egg_path = os.path.join(get_exe_dir(), "data", "easteregg.png")
                if os.path.exists(egg_path):
                    egg_win, egg_content = create_styled_window(root, "EASTER EGG", 500, 400)
                    img = Image.open(egg_path)
                    img.thumbnail((480, 380))
                    photo = ImageTk.PhotoImage(img)
                    label = tk.Label(egg_content, image=photo, bg="black")
                    label.image = photo
                    label.pack(expand=True, pady=10)
                else:
                    status_label.config(text="easteregg.png not found")

            entry.delete(0, tk.END)
            unlock_confirm()
            return
            

        # ===== История паролей =====
        password_history.append(pwd)
        
        abebe.on_user_input(pwd)

        # ===== Проверка на подозрительность =====
        if trust.is_suspicious():
            abebe.destroy()
            win.destroy()
            start_fake_hack(root)
            return
        
        

        # ===== Правильные пароли =====
        if pwd in PASSWORD_ACTIONS:
            abebe.destroy()
            win.destroy()
            PASSWORD_ACTIONS[pwd](root)
            return

        # ===== Неверный пароль =====
        

        def unlock():
            confirm_btn.config(state="normal")
            entry.delete(0, tk.END)
            status_label.config(text="")

        win.after(3000, unlock)

    # ===================== CONFIRM BUTTON =====================
    confirm_btn = tk.Button(
        content,
        text="ENTER",
        command=check,
        bg="black",
        fg="white",
        activebackground="black",
        activeforeground="lime",
        relief="ridge",
        width=16
    )
    confirm_btn.pack(pady=15)

