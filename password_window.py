import tkinter as tk
from tkinter import font
from PIL import Image, ImageTk
import os
from pathlib import Path

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
import random
from opengl_secret_maze import start_secret_maze_opengl
from opengl_testing_maze import start_testing_maze_opengl
from opengl_tutor_maze import start_tutor_maze_opengl
from opengl_city_maze import start_city_maze_opengl
from game_launcher import run_pygame_session

from trust_system import TrustSystem
from abebe_watcher import AbebeWatcher


# ===================== HISTORY (РѕС‡РёС‰Р°РµС‚СЃСЏ РїСЂРё РїРµСЂРµР·Р°РїСѓСЃРєРµ) =====================
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

    # рџ”Ґ Р’РђР–РќРћ вЂ” РґРµСЂР¶Р°С‚СЊ РїРѕРІРµСЂС… root
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
        text=" вњ• ",
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
            on_no=lambda: None  # РЅРёС‡РµРіРѕ РЅРµ РґРµР»Р°РµРј
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
        "load test - open testing maze",
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
from pathlib import Path
import threading

def show_iobey_audio(root):
    win, content = create_styled_window(root, "AUDIO_PLAYER.EXE", 360, 220)
    register(win)
    # РґРµСЂР¶РёРј РѕРєРЅРѕ РїРѕРІРµСЂС… РІСЃРµРіРѕ
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

        stop_music()  # РѕСЃС‚Р°РЅР°РІР»РёРІР°РµРј С„РѕРЅ
        status.config(text="PLAYING...", fg="lime")

        # ===== РїРѕС‚РѕРє РґР»СЏ Р·РІСѓРєР° =====
        def sound_thread():
            winsound.PlaySound(audio_path, winsound.SND_FILENAME)
            # РџРѕСЃР»Рµ РѕРєРѕРЅС‡Р°РЅРёСЏ Р·РІСѓРєР°
            root.after(100, stop_audio)

        threading.Thread(target=sound_thread, daemon=True).start()

    def stop_audio():
        winsound.PlaySound(None, winsound.SND_PURGE)  # РѕСЃС‚Р°РЅРѕРІРєР°
        status.config(text="STOPPED", fg="gray")
        resume_music()  # РІРѕР·РѕР±РЅРѕРІР»СЏРµРј С„РѕРЅ
        if win.winfo_exists():
            win.destroy()  # Р·Р°РєСЂС‹РІР°РµРј РѕРєРЅРѕ

    # ===== BUTTONS =====
    btn_frame = tk.Frame(content, bg="black")
    btn_frame.pack(pady=20)

    play_btn = tk.Button(
        btn_frame,
        text="в–¶ PLAY",
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
        text="в–  STOP",
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

    # РџСѓС‚СЊ Рє РїР°РїРєРµ data
    data_dir = os.path.join(get_exe_dir(), "data")
    img_path = os.path.join(data_dir, "death.png")

    # --- РћС‚РєСЂС‹С‚РёРµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РІ РѕС‚РґРµР»СЊРЅРѕРј РѕРєРЅРµ ---
    def open_image():
        if not os.path.exists(img_path):
            tk.messagebox.showerror("Error", f"File not found:\n{img_path}")
            return

        img_win, img_content = create_styled_window(root, "death.png", 600, 500)

        # Р—Р°РіСЂСѓР¶Р°РµРј Рё РјР°СЃС€С‚Р°Р±РёСЂСѓРµРј РёР·РѕР±СЂР°Р¶РµРЅРёРµ
        img = Image.open(img_path)
        img.thumbnail((580, 480))  # СЃРѕС…СЂР°РЅСЏРµРј РїСЂРѕРїРѕСЂС†РёРё
        photo = ImageTk.PhotoImage(img)

        # РЎРѕС…СЂР°РЅСЏРµРј СЃСЃС‹Р»РєСѓ РЅР° РёР·РѕР±СЂР°Р¶РµРЅРёРµ, С‡С‚РѕР±С‹ Tkinter РµРіРѕ РЅРµ СѓРґР°Р»РёР»
        label = tk.Label(img_content, image=photo, bg="black")
        label.image = photo
        label.pack(expand=True, pady=10)

    # РљРЅРѕРїРєР°-С„Р°Р№Р»
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

    # РџРѕРґРїРёСЃСЊ РїРѕРґ С„Р°Р№Р»РѕРј
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

    import string
    import time

    pane_os_dir = Path(get_exe_dir()) / "data" / "PaneOS"
    width, height = 620, 430

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg="#c3c3c3")
    block_esc(win)
    register(win)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    win.geometry(f"{width}x{height}+{sw // 2 - width // 2}+{sh // 2 - height // 2}")
    win.transient(root)
    win.lift()
    win.attributes("-topmost", True)
    win._is_maximized = False
    win._normal_geometry = win.geometry()

    trust = TrustSystem(root)
    abebe = AbebeWatcher(root, trust)

    window_bg_source = Image.open(pane_os_dir / "wondiw.png")
    close_idle = tk.PhotoImage(file=str(pane_os_dir / "close1.png"))
    close_hover = tk.PhotoImage(file=str(pane_os_dir / "close2.png"))
    close_pressed = tk.PhotoImage(file=str(pane_os_dir / "close3.png"))
    minimize_idle = tk.PhotoImage(file=str(pane_os_dir / "minimaze1.png"))
    minimize_hover = tk.PhotoImage(file=str(pane_os_dir / "minimaze2.png"))
    minimize_pressed = tk.PhotoImage(file=str(pane_os_dir / "minimaze3.png"))
    maximize_idle = tk.PhotoImage(file=str(pane_os_dir / "maximize1.png"))
    maximize_hover = tk.PhotoImage(file=str(pane_os_dir / "maximize2.png"))
    maximize_pressed = tk.PhotoImage(file=str(pane_os_dir / "maximize3.png"))

    def render_background(current_width, current_height):
        image = window_bg_source.resize((current_width, current_height), Image.NEAREST)
        win._window_bg = ImageTk.PhotoImage(image)
        background.config(image=win._window_bg)

    background = tk.Label(win, borderwidth=0, highlightthickness=0)
    background.place(x=0, y=0, relwidth=1, relheight=1)
    render_background(width, height)

    title_bar = tk.Frame(win, bg="#000080", height=24)
    title_bar.place(x=8, y=8, width=width - 16, height=24)

    tk.Label(
        title_bar,
        text="COMMAND PROMPT",
        bg="#000080",
        fg="white",
        font=("Terminal", 10),
    ).pack(side="left", padx=6)

    def set_sprite(widget, sprite):
        widget.config(image=sprite)
        widget.image = sprite

    def bind_sprite_button(widget, sprites, on_click):
        idle, hover, pressed = sprites
        set_sprite(widget, idle)
        widget.bind("<Enter>", lambda _event: set_sprite(widget, hover))
        widget.bind("<Leave>", lambda _event: set_sprite(widget, idle))
        widget.bind("<ButtonPress-1>", lambda _event: set_sprite(widget, pressed))

        def release(event):
            hovered = 0 <= event.x < widget.winfo_width() and 0 <= event.y < widget.winfo_height()
            set_sprite(widget, hover if hovered else idle)
            if hovered:
                on_click()

        widget.bind("<ButtonRelease-1>", release)

    close_btn = tk.Label(title_bar, bg="#000080", borderwidth=0, highlightthickness=0, cursor="hand2")
    close_btn.pack(side="right", padx=4, pady=4)
    maximize_btn = tk.Label(title_bar, bg="#000080", borderwidth=0, highlightthickness=0, cursor="hand2")
    maximize_btn.pack(side="right", padx=(0, 2), pady=4)
    minimize_btn = tk.Label(title_bar, bg="#000080", borderwidth=0, highlightthickness=0, cursor="hand2")
    minimize_btn.pack(side="right", padx=(0, 2), pady=4)

    shell = tk.Frame(win, bg="black", borderwidth=0, highlightthickness=0)
    shell.place(x=12, y=42, width=width - 24, height=height - 54)

    terminal_outer = tk.Frame(
        shell,
        bg="black",
        highlightbackground="#6c6c6c",
        highlightthickness=2,
        bd=0,
    )
    terminal_outer.pack(fill="both", expand=True, pady=(0, 12))

    terminal_output = tk.Text(
        terminal_outer,
        bg="black",
        fg="white",
        insertbackground="white",
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        wrap="word",
        font=("Terminal", 11),
        padx=10,
        pady=10,
    )
    terminal_output.pack(fill="both", expand=True)
    terminal_output.config(state="disabled")

    prompt_outer = tk.Frame(
        terminal_outer,
        bg="black",
        highlightbackground="#6c6c6c",
        highlightthickness=1,
        bd=0,
    )
    prompt_outer.pack(fill="x", side="bottom", padx=8, pady=8)
    prompt_outer.lift()

    prompt_inner = tk.Frame(prompt_outer, bg="black")
    prompt_inner.pack(fill="x", padx=8, pady=6)

    prompt_label = tk.Label(
        prompt_inner,
        text=">",
        fg="white",
        bg="black",
        font=("Terminal", 14),
    )
    prompt_label.pack(side="left", padx=(0, 8))

    input_box = tk.Frame(
        prompt_inner,
        bg="black",
        highlightbackground="#bfbfbf",
        highlightthickness=1,
        bd=0,
        height=34,
    )
    input_box.pack(side="left", fill="x", expand=True)
    input_box.pack_propagate(False)

    entry_var = tk.StringVar(value="")
    entry = tk.Entry(
        input_box,
        textvariable=entry_var,
        font=("Terminal", 14),
        bg="black",
        fg="white",
        insertbackground="white",
        insertwidth=2,
        insertofftime=350,
        insertontime=350,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        exportselection=False,
        takefocus=True,
    )
    entry.pack(side="left", fill="both", expand=True, padx=10, pady=4)
    

    show_password = True
    eye_event_active = False
    last_submit_time = 0
    submit_cooldown = 700
    boot_done = False

    boot_sequence = [
        "PaneOS SYSTEM TERMINAL v2.0",
        "(c) 2060 Abel B. E. & Bane C. E. Bros",
        "",
        "Boot sequence initiated...",
        "Loading core modules...",
        "Mounting virtual drives... [OK]",
        "",
        "Initializing neural interface...",
        "Scanning cognitive patterns...",
        "Loading memory fragments... [32%]",
        "Loading memory fragments... [47%]",
        "Loading memory fragments... [51%]",
        "",
        "WARNING: Memory integrity compromised",
        "WARNING: Neural data incomplete",
        "ERROR: Failed to restore full consciousness",
        "",
        "Attempting recovery...",
        "Reconstructing personality matrix... [PARTIAL]",
        "Stabilizing neural link... [OK]",
        "",
        "NOTICE: System will continue with limited functionality",
        "",
        "Initializing host environment...",
        "Binding consciousness to shell... [OK]",
        "",
        "Welcome, USER_UNKNOWN",
        "",
        'Type "help" to display available commands.',
    ]

    password_actions = {
        "1401": start_fake_hack,
        "12525": show_good_end,
        "iobey98": show_iobey_audio,
    }
    level_commands = {
        "tutor": start_tutor_maze_opengl,
        "secret": start_secret_maze_opengl,
        "city": start_city_maze_opengl,
        "cite": start_city_maze_opengl,
        "test": start_testing_maze_opengl,
    }

    def close_window():
        show_abebe_confirm(
            root,
            on_yes=lambda: exit_game_confirmed(),
            on_no=lambda: None,
        )

    def minimize_window():
        win.attributes("-topmost", False)
        win.lower()

    def apply_layout(current_width, current_height):
        render_background(current_width, current_height)
        title_bar.place(x=8, y=8, width=current_width - 16, height=24)
        shell.place(x=12, y=42, width=current_width - 24, height=current_height - 54)

    def maximize_window():
        if not win._is_maximized:
            win._normal_geometry = win.geometry()
            full_width = root.winfo_screenwidth()
            full_height = root.winfo_screenheight()
            win.geometry(f"{full_width}x{full_height}+0+0")
            win._is_maximized = True
            apply_layout(full_width, full_height)
        else:
            win.geometry(win._normal_geometry)
            win._is_maximized = False
            win.update_idletasks()
            apply_layout(win.winfo_width(), win.winfo_height())
        win.lift()

    bind_sprite_button(minimize_btn, (minimize_idle, minimize_hover, minimize_pressed), minimize_window)
    bind_sprite_button(maximize_btn, (maximize_idle, maximize_hover, maximize_pressed), maximize_window)
    bind_sprite_button(close_btn, (close_idle, close_hover, close_pressed), close_window)
    make_draggable(win, title_bar)

    def can_trigger_eye_event():
        return trust.trust >= 70 and random.random() < 1.0

    def focus_terminal(_event=None):
        win.focus_force()
        win.lift()
        if boot_done:
            entry.focus_set()
            entry.icursor(tk.END)

    def set_input_enabled(enabled):
        entry.config(state="normal" if enabled else "disabled")
        if enabled:
            focus_terminal()

    def ensure_input_focus(attempt=0):
        if not win.winfo_exists() or not boot_done:
            return
        focus_terminal()
        if attempt < 8:
            win.after(120, lambda: ensure_input_focus(attempt + 1))

    def start_input():
        nonlocal boot_done
        boot_done = True
        set_input_enabled(True)
        ensure_input_focus()

    def type_boot_text(line_index=0, char_index=0):
        if line_index >= len(boot_sequence):
            start_input()
            return

        line = boot_sequence[line_index]
        terminal_output.config(state="normal")

        if line == "":
            terminal_output.insert("end", "\n")
            terminal_output.see("end")
            terminal_output.config(state="disabled")
            win.after(28, lambda: type_boot_text(line_index + 1, 0))
            return

        if char_index < len(line):
            terminal_output.insert("end", line[char_index])
            terminal_output.see("end")
            terminal_output.config(state="disabled")
            win.after(5, lambda: type_boot_text(line_index, char_index + 1))
            return

        terminal_output.insert("end", "\n")
        terminal_output.see("end")
        terminal_output.config(state="disabled")
        win.after(22, lambda: type_boot_text(line_index + 1, 0))

    def append_terminal_lines(lines):
        terminal_output.config(state="normal")
        for line in lines:
            terminal_output.insert("end", f"{line}\n")
        terminal_output.see("end")
        terminal_output.config(state="disabled")

    def type_terminal_lines(lines, on_complete=None, line_index=0, char_index=0):
        if line_index >= len(lines):
            if on_complete is not None:
                on_complete()
            return

        line = lines[line_index]
        terminal_output.config(state="normal")

        if line == "":
            terminal_output.insert("end", "\n")
            terminal_output.see("end")
            terminal_output.config(state="disabled")
            win.after(20, lambda: type_terminal_lines(lines, on_complete, line_index + 1, 0))
            return

        if char_index < len(line):
            terminal_output.insert("end", line[char_index])
            terminal_output.see("end")
            terminal_output.config(state="disabled")
            win.after(4, lambda: type_terminal_lines(lines, on_complete, line_index, char_index + 1))
            return

        terminal_output.insert("end", "\n")
        terminal_output.see("end")
        terminal_output.config(state="disabled")
        win.after(16, lambda: type_terminal_lines(lines, on_complete, line_index + 1, 0))

    def type_loading_command(command_text, on_complete=None):
        def finish_command():
            lines = [
                "Initializing...",
                "Loading assets...",
                "Loading textures... [OK]",
                "Loading audio... [OK]",
                "Spawning entities...",
                "Done.",
                "",
                f"> Entering {command_text}",
            ]
            type_terminal_lines(lines, on_complete=on_complete)

        type_terminal_lines([f"> load {command_text}"], on_complete=finish_command)

    def check():
        nonlocal abebe, eye_event_active, last_submit_time

        if not boot_done:
            entry_var.set("")
            focus_terminal()
            return

        set_input_enabled(False)
        pwd = entry.get().strip()
        if not pwd:
            entry_var.set("")
            set_input_enabled(True)
            return

        now = int(time.time() * 1000)
        if now - last_submit_time < submit_cooldown:
            set_input_enabled(True)
            return

        last_submit_time = now

        if not (1 <= len(pwd) <= 18):
            set_input_enabled(True)
            return

        load_target = None
        if pwd.startswith("load ") and len(pwd) > 5:
            load_target = pwd[5:].strip()

        if " " in pwd and load_target is None:
            entry_var.set("")
            set_input_enabled(True)
            return

        allowed_chars = string.ascii_letters + string.digits + string.punctuation
        validation_text = pwd if load_target is None else f"load{load_target}"
        if any(char not in allowed_chars for char in validation_text):
            entry_var.set("")
            set_input_enabled(True)
            return

        if pwd.startswith("!"):
            if pwd == "!help":
                lines = [
                    f"> {pwd}",
                    "Available commands:",
                    "!help - show commands",
                    "!history - show password history",
                    "!gallery - open gallery",
                    "!abebe_watcher - restart watcher",
                    "!info - show info.txt",
                    "!dev - show developer info",
                    "!reset - reset game state",
                    "!sound on/off - toggle background music",
                    "!easteregg - show hidden image",
                    "load tutor - open tutor maze",
                    "load secret - open secret maze",
                    "load city - open city maze",
                    "load test - open testing maze",
                    "!hack - open decoder helper",
                    "",
                ]
                entry_var.set("")
                type_terminal_lines(lines, on_complete=lambda: set_input_enabled(True))
                return
            elif pwd == "!history":
                append_terminal_lines([f"> {pwd}"])
                show_history_window(root)
            elif pwd == "!gallery":
                append_terminal_lines([f"> {pwd}"])
                show_gallery_window(root)
            elif pwd == "!abebe_watcher":
                append_terminal_lines([f"> {pwd}"])
                abebe.destroy()
                abebe = AbebeWatcher(root, trust)
            elif pwd == "!info":
                append_terminal_lines([f"> {pwd}"])
                info_path = os.path.join(get_exe_dir(), "info.txt")
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as info_file:
                        info_text = info_file.read()
                    info_win, info_content = create_styled_window(root, "INFO.TXT", 400, 300)
                    text_widget = tk.Text(info_content, bg="black", fg="lime", font=("Consolas", 12), wrap="word")
                    text_widget.insert("1.0", info_text)
                    text_widget.config(state="disabled")
                    text_widget.pack(expand=True, fill="both", padx=5, pady=5)
            elif pwd == "!dev":
                append_terminal_lines([f"> {pwd}"])
                dev_win, dev_content = create_styled_window(root, "DEV.INFO", 400, 300)
                tk.Label(dev_content, text=f"Password History:\n{password_history}", fg="lime", bg="black", font=("Consolas", 12), justify="left").pack(padx=10, pady=10)
                tk.Label(dev_content, text=f"Trust Level: {trust.level}", fg="lime", bg="black", font=("Consolas", 12)).pack(padx=10, pady=5)
            elif pwd == "!reset":
                append_terminal_lines([f"> {pwd}"])
                password_history.clear()
                trust.trust = 50
                trust.suspicion = 0
                trust.update_ui()
                abebe.destroy()
                abebe = AbebeWatcher(root, trust)
            elif pwd == "!summonnotcreep":
                append_terminal_lines([f"> {pwd}"])
                CreeperEvent(root, trust)
            elif pwd == "!hack":
                append_terminal_lines([f"> {pwd}"])
                show_hack_decoder(root, abebe.get_current_theme())
            elif pwd == "!summon_eye":
                append_terminal_lines([f"> {pwd}"])
                if not eye_event_active:
                    eye_event_active = True

                    def on_eye_finish():
                        nonlocal eye_event_active
                        eye_event_active = False

                    EyeWatcherEvent(
                        root=root,
                        trust_system=trust,
                        is_password_visible_cb=lambda: show_password,
                        on_finish=on_eye_finish,
                        watch_time=3000,
                    )
            elif pwd.startswith("!sound"):
                append_terminal_lines([f"> {pwd}"])
                args = pwd.split()
                if len(args) > 1 and args[1].lower() == "off":
                    stop_music()
                elif len(args) > 1 and args[1].lower() == "on":
                    resume_music()
            elif pwd == "!12340":
                append_terminal_lines([f"> {pwd}"])
                incident_path = os.path.join(get_exe_dir(), "data", "12340.txt")
                if os.path.exists(incident_path):
                    with open(incident_path, "r", encoding="utf-8") as incident_file:
                        incident_text = incident_file.read()
                    incident_win, incident_content = create_styled_window(root, "1230.TXT", 400, 300)
                    text_widget = tk.Text(incident_content, bg="black", fg="lime", font=("Consolas", 12), wrap="word")
                    text_widget.insert("1.0", incident_text)
                    text_widget.config(state="disabled")
                    text_widget.pack(expand=True, fill="both", padx=5, pady=5)
            elif pwd == "!easteregg":
                append_terminal_lines([f"> {pwd}"])
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
                lines = [f"> {pwd}", f"Unknown command: {pwd}", ""]
                entry_var.set("")
                type_terminal_lines(lines, on_complete=lambda: set_input_enabled(True))
                return

            entry_var.set("")
            set_input_enabled(True)
            return

        if load_target is not None:
            level_loader = level_commands.get(load_target)
            if level_loader is None:
                lines = [f"> load {load_target}", f"Unknown level: {load_target}", ""]
                entry_var.set("")
                type_terminal_lines(lines, on_complete=lambda: set_input_enabled(True))
                return

            entry_var.set("")
            type_loading_command(load_target, on_complete=lambda: run_pygame_session(root, level_loader, root))
            return

        append_terminal_lines([f"> {pwd}"])
        password_history.append(pwd)
        abebe.on_user_input(pwd)

        if trust.is_suspicious():
            abebe.destroy()
            win.destroy()
            start_fake_hack(root)
            return

        if pwd in password_actions:
            abebe.destroy()
            win.destroy()
            password_actions[pwd](root)
            return

        entry_var.set("")
        set_input_enabled(True)

    def limit_input(_event=None):
        value = entry.get()
        if len(value) > 48:
            entry.delete(48, tk.END)

    def handle_window_key(event):
        if not boot_done:
            return
        if str(entry.cget("state")) != "normal":
            return
        if entry.focus_get() == entry:
            return

        if event.keysym == "Return":
            check()
            return "break"
        if event.keysym == "BackSpace":
            entry_var.set(entry_var.get()[:-1])
            focus_terminal()
            return "break"
        if event.keysym in {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Tab", "Escape"}:
            return "break"
        if len(event.char) == 1 and event.char.isprintable():
            if len(entry_var.get()) < 18:
                entry_var.set(entry_var.get() + event.char)
            focus_terminal()
            return "break"

    for widget in (win, shell, terminal_outer, terminal_output, prompt_outer, prompt_inner, input_box, prompt_label):
        widget.bind("<Button-1>", focus_terminal)
    entry.bind("<KeyRelease>", limit_input)
    entry.bind("<Return>", lambda _event: check())
    win.bind("<KeyPress>", handle_window_key, add="+")
    win.after(50, focus_terminal)
    type_boot_text()
