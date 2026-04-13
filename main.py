# Project: Abebe Watcher(ABEBE_PROTOCOL)
# Author: Denis Kravchenko
# Started: Feb 10, 2026
# All assets, story, design, and main game logic by the author.
# Some helper code assisted by AI.

import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk
from utils import block_esc, get_exe_dir
from password_window import show_password_window
from intro import show_intro
from background_music import play_music
from config import BACKGROUND_MUSIC
from new_game_window import show_new_game_window
from settings_window import show_settings
import game_state

import time
from user_settings import load_settings

APP_SETTINGS = load_settings()
PANE_OS_DIR = Path(get_exe_dir()) / "data" / "PaneOS"
PANE_BG = "#c3c3c3"
PANE_BG_DARK = "#b8b8b8"
PANE_BORDER_DARK = "#808080"
PANE_TITLE = "#000080"
PANE_TEXT = "black"
PANE_TEXT_MUTED = "#4a4a4a"
PANE_ACTIVE = "#dcdcdc"
PREVIEW_TRANSPARENT = "#ff00ff"

game_running = False


def init_custom_cursor(root):
    normal_cursor = tk.PhotoImage(file=str(PANE_OS_DIR / "cursor.png"))
    click_cursor = tk.PhotoImage(file=str(PANE_OS_DIR / "click.png"))

    overlay = tk.Toplevel(root)
    overlay.overrideredirect(True)
    overlay.attributes("-topmost", True)
    overlay.configure(bg=PREVIEW_TRANSPARENT)
    overlay.wm_attributes("-transparentcolor", PREVIEW_TRANSPARENT)

    label = tk.Label(overlay, image=normal_cursor, bg=PREVIEW_TRANSPARENT, borderwidth=0, highlightthickness=0)
    label.pack()

    state = {"mode": "normal", "suppressed": False}

    def set_mode(mode):
        if state["mode"] == mode:
            return
        state["mode"] = mode
        label.config(image=click_cursor if mode == "click" else normal_cursor)
        label.image = click_cursor if mode == "click" else normal_cursor

    def move_cursor(event):
        if state["suppressed"]:
            overlay.withdraw()
            return
        overlay.geometry(f"+{event.x_root + 2}+{event.y_root + 1}")
        if not overlay.winfo_viewable():
            overlay.deiconify()

    def hide_cursor(_event=None):
        overlay.withdraw()

    def suppress_cursor():
        state["suppressed"] = True
        overlay.withdraw()

    def restore_cursor():
        state["suppressed"] = False

    def apply_hidden_cursor(widget):
        try:
            widget.configure(cursor="none")
        except tk.TclError:
            return
        for child in widget.winfo_children():
            apply_hidden_cursor(child)

    def register_click_widget(widget):
        try:
            widget.configure(cursor="none")
        except tk.TclError:
            pass
        widget.bind("<Enter>", lambda _e: set_mode("click"), add="+")
        widget.bind("<Leave>", lambda _e: set_mode("normal"), add="+")
        widget.bind("<Motion>", move_cursor, add="+")

    def register_click_canvas_item(canvas, item):
        canvas.tag_bind(item, "<Enter>", lambda _e: set_mode("click"), add="+")
        canvas.tag_bind(item, "<Leave>", lambda _e: set_mode("normal"), add="+")
        canvas.tag_bind(item, "<Motion>", move_cursor, add="+")

    root.bind_all("<Motion>", move_cursor, add="+")
    root.bind_all("<ButtonPress>", lambda _e: set_mode("click"), add="+")
    root.bind_all("<ButtonRelease>", lambda _e: set_mode("normal"), add="+")
    root.bind("<Leave>", hide_cursor, add="+")
    root.configure(cursor="none")
    overlay.withdraw()

    root._cursor_overlay = overlay
    root._cursor_api = {
        "apply_hidden_cursor": apply_hidden_cursor,
        "register_click_widget": register_click_widget,
        "register_click_canvas_item": register_click_canvas_item,
        "set_mode": set_mode,
        "move_cursor": move_cursor,
        "suppress_cursor": suppress_cursor,
        "restore_cursor": restore_cursor,
    }

def styled_button(parent, text, command, fg=PANE_TEXT):
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        font=("Terminal", 16),
        bg=PANE_BG,
        fg=fg,
        activebackground=PANE_ACTIVE,
        activeforeground=PANE_TEXT,
        relief="raised",
        borderwidth=2,
        width=34,
        height=2
    )

    btn.bind("<Enter>", lambda e: btn.config(bg=PANE_ACTIVE))
    btn.bind("<Leave>", lambda e: btn.config(bg=PANE_BG))
    return btn


def load_menu_icon(name, size=(64, 64)):
    image = Image.open(PANE_OS_DIR / name).convert("RGBA")
    return ImageTk.PhotoImage(image.resize(size, Image.NEAREST))


def create_desktop_file_icon(parent, icon_image, label_text, command, enabled=True):
    text_color = "#f5f5f5" if enabled else "#b5b5b5"
    icon_item = parent.create_image(0, 0, image=icon_image, anchor="n")
    text_shadow_item = parent.create_text(
        0,
        0,
        text=label_text,
        fill="#101010",
        font=("Terminal", 11, "bold"),
        justify="center",
        width=120,
        anchor="n",
    )
    text_item = parent.create_text(
        0,
        0,
        text=label_text,
        fill=text_color,
        font=("Terminal", 11, "bold"),
        justify="center",
        width=120,
        anchor="n",
    )
    hitbox_item = parent.create_rectangle(0, 0, 0, 0, outline="", fill="")

    state = {
        "enabled": enabled,
        "command": command,
        "icon_item": icon_item,
        "text_shadow_item": text_shadow_item,
        "text_item": text_item,
        "hitbox_item": hitbox_item,
        "image": icon_image,
        "label_text": label_text,
    }

    def on_click(_event=None):
        if state["enabled"]:
            state["command"]()

    for item in (icon_item, text_shadow_item, text_item, hitbox_item):
        parent.tag_bind(item, "<Button-1>", on_click, add="+")

    return state

def exit_game_confirmed():
    global game_running

    # Р·Р°РєСЂС‹РІР°РµРј Р’РЎР• Toplevel РѕРєРЅР°
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()

    game_running = False
    unlock_start_button()

def start_new_game():
    show_new_game_window(root)

def make_draggable(bar):
    win = bar.winfo_toplevel()
    drag_state = {"preview": None, "offset_x": 0, "offset_y": 0}

    def start(event):
        drag_state["offset_x"] = event.x
        drag_state["offset_y"] = event.y

        preview = tk.Toplevel(win)
        preview.overrideredirect(True)
        preview.attributes("-alpha", 0.35)
        preview.attributes("-topmost", True)
        preview.configure(bg=PREVIEW_TRANSPARENT)
        preview.wm_attributes("-transparentcolor", PREVIEW_TRANSPARENT)

        border = tk.Frame(preview, bg=PREVIEW_TRANSPARENT, highlightbackground="black", highlightthickness=2)
        border.pack(expand=True, fill="both")

        width = win.winfo_width()
        height = win.winfo_height()
        preview.geometry(f"{width}x{height}+{win.winfo_x()}+{win.winfo_y()}")
        drag_state["preview"] = preview

    def move(event):
        preview = drag_state["preview"]
        if preview is None:
            return
        x = event.x_root - drag_state["offset_x"]
        y = event.y_root - drag_state["offset_y"]
        preview.geometry(f"+{x}+{y}")

    def finish(event):
        preview = drag_state["preview"]
        if preview is None:
            return
        x = event.x_root - drag_state["offset_x"]
        y = event.y_root - drag_state["offset_y"]
        preview.destroy()
        drag_state["preview"] = None
        win.geometry(f"+{x}+{y}")

    bar.bind("<Button-1>", start)
    bar.bind("<B1-Motion>", move)
    bar.bind("<ButtonRelease-1>", finish)

def show_splash(root):
    splash = tk.Toplevel(root)
    splash.configure(bg="black")
    splash.attributes("-fullscreen", True)
    splash.attributes("-alpha", 1.0)
    splash.config(cursor="none")
    root.config(cursor="none")
    cursor_api = getattr(root, "_cursor_api", None)
    if cursor_api is not None:
        cursor_api["suppress_cursor"]()

    splash.lift()
    splash.attributes("-topmost", True)
    splash.after(10, lambda: splash.attributes("-topmost", False))

    skip_requested = [False]
    interaction_enabled = [False]
    signed_enough = [False]
    drawing_state = {"active": False, "last_x": None, "last_y": None, "ink": 0.0}

    def skip_splash(event=None):
        if not skip_requested[0]:
            skip_requested[0] = True
            root.config(cursor="")
            if cursor_api is not None:
                cursor_api["restore_cursor"]()
            splash.destroy()

    splash.bind("<Escape>", skip_splash)
    splash.focus_set()

    game_state.init_game_state(root, open_game_btn)

    def fade_out(alpha=1.0):
        if skip_requested[0]:
            return

        if alpha > 0:
            splash.attributes("-alpha", alpha)
            splash.after(50, fade_out, alpha - 0.05)
        else:
            root.config(cursor="")
            if cursor_api is not None:
                cursor_api["restore_cursor"]()
            splash.destroy()

    hands_dir = Path(get_exe_dir()) / "data" / "gifs" / "hands"
    left_source = Image.open(hands_dir / "LPen.png")
    right_source = Image.open(hands_dir / "RPen.png")
    contract_source = Image.open(hands_dir / "Contract.png")

    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    center_x = sw // 2
    center_y = sh // 2

    contract_w = max(320, int(sw * 0.22))
    contract_h = int(contract_w * (contract_source.height / contract_source.width))
    hand_h = int(contract_h * 0.31)

    def make_photo(image, target_h):
        target_w = int(target_h * (image.width / image.height))
        resized = image.resize((target_w, target_h), Image.NEAREST)
        return ImageTk.PhotoImage(resized), target_w

    left_photo, left_w = make_photo(left_source, hand_h)
    right_photo, right_w = make_photo(right_source, hand_h)
    contract_photo = ImageTk.PhotoImage(contract_source.resize((contract_w, contract_h), Image.NEAREST))
    splash._splash_images = (left_photo, right_photo, contract_photo)

    canvas = tk.Canvas(splash, bg="black", highlightthickness=0, bd=0, cursor="none")
    canvas.pack(fill="both", expand=True)

    spacing = int(contract_w * 0.16)
    left_x = center_x - (contract_w // 2) - spacing - (left_w // 2)
    right_x = center_x + (contract_w // 2) + spacing + (right_w // 2)
    hand_y = center_y + 6
    intro_jitter_job = [None]
    pen_motion = {"target_x": right_x, "target_y": hand_y, "current_x": right_x, "current_y": hand_y, "tick": 0}

    contract_item = canvas.create_image(center_x, center_y, image=contract_photo, state="hidden")
    left_item = canvas.create_image(left_x, hand_y, image=left_photo, state="hidden")
    right_item = canvas.create_image(right_x, hand_y, image=right_photo, state="hidden")

    title_box = canvas.create_rectangle(
        center_x - 170,
        max(34, sh // 10) - 24,
        center_x + 170,
        max(34, sh // 10) + 24,
        fill="#c3c3c3",
        outline="#808080",
        width=3,
        state="hidden",
    )
    title_item = canvas.create_text(
        center_x,
        max(64, sh // 9),
        text="SIGN THE CONTRACT",
        fill="black",
        font=("Terminal", 20),
        state="hidden",
    )

    sign_left = center_x - int(contract_w * 0.16)
    sign_right = center_x + int(contract_w * 0.42)
    sign_top = center_y + int(contract_h * 0.35)
    sign_bottom = center_y + int(contract_h * 0.47)
    sign_box = canvas.create_rectangle(
        sign_left,
        sign_top,
        sign_right,
        sign_bottom,
        outline="#5f5f5f",
        dash=(5, 3),
        width=2,
        state="hidden",
    )
    hint_item = canvas.create_text(
        center_x,
        sh - 42,
        text="Hold left mouse button and sign inside the box",
        fill="#d0d0d0",
        font=("Terminal", 14),
        state="hidden",
    )

    def reveal_contract():
        if skip_requested[0]:
            return
        canvas.itemconfigure(contract_item, state="normal")
        splash.after(320, reveal_left)

    def reveal_left():
        if skip_requested[0]:
            return
        canvas.itemconfigure(left_item, state="normal")
        splash.after(320, reveal_right)

    def reveal_right():
        if skip_requested[0]:
            return
        canvas.itemconfigure(right_item, state="normal")
        pen_motion["current_x"] = right_x + 40
        pen_motion["current_y"] = hand_y + 14
        pen_motion["target_x"] = right_x
        pen_motion["target_y"] = hand_y
        canvas.coords(right_item, pen_motion["current_x"], pen_motion["current_y"])

        def settle(step=0):
            if skip_requested[0]:
                return
            progress = min(step / 12, 1.0)
            current_x = (right_x + 40) - int(40 * progress)
            current_y = (hand_y + 14) - int(14 * progress)
            pen_motion["current_x"] = current_x
            pen_motion["current_y"] = current_y
            pen_motion["target_x"] = current_x
            pen_motion["target_y"] = current_y
            canvas.coords(right_item, current_x, current_y)
            if progress < 1.0:
                splash.after(55, lambda: settle(step + 1))
            else:
                start_intro_jitter()
                splash.after(420, enable_signing)

        settle()

    def start_intro_jitter():
        if skip_requested[0] or interaction_enabled[0]:
            return

        phase = {"tick": 0}

        def jitter():
            if skip_requested[0] or interaction_enabled[0]:
                return
            phase["tick"] += 1
            dx = -1 if phase["tick"] % 2 == 0 else 1
            dy = 0.5 if phase["tick"] % 3 == 0 else -0.5
            canvas.coords(right_item, right_x + dx, hand_y + dy)
            intro_jitter_job[0] = splash.after(95, jitter)

        jitter()

    def is_in_sign_area(x, y):
        return sign_left <= x <= sign_right and sign_top <= y <= sign_bottom

    def maybe_finish():
        if signed_enough[0] or drawing_state["ink"] < 180:
            return
        signed_enough[0] = True
        canvas.itemconfigure(hint_item, text="CONTRACT ACCEPTED", fill="white")
        splash.after(700, fade_out)

    pen_anchor_offset_x = -90
    pen_anchor_offset_y = -60

    def move_pen(x, y):
        if skip_requested[0]:
            return
        pen_motion["target_x"] = x - pen_anchor_offset_x
        pen_motion["target_y"] = y + pen_anchor_offset_y
        canvas.tag_raise(right_item)

    def animate_pen():
        if skip_requested[0]:
            return
        pen_motion["tick"] += 1
        pen_motion["current_x"] = pen_motion["target_x"]
        pen_motion["current_y"] = pen_motion["target_y"]
        jitter_x = -0.6 if pen_motion["tick"] % 2 == 0 else 0.6
        jitter_y = 0.45 if pen_motion["tick"] % 3 == 0 else -0.45
        canvas.coords(
            right_item,
            pen_motion["current_x"] + jitter_x,
            pen_motion["current_y"] + jitter_y,
        )
        canvas.tag_raise(right_item)
        splash.after(16, animate_pen)

    def on_motion(event):
        if not interaction_enabled[0]:
            return
        move_pen(event.x, event.y)
        if drawing_state["active"] and drawing_state["last_x"] is not None and is_in_sign_area(event.x, event.y):
            last_x = drawing_state["last_x"]
            last_y = drawing_state["last_y"]
            canvas.create_line(last_x, last_y, event.x, event.y, fill="#111111", width=2, capstyle=tk.ROUND, smooth=True)
            canvas.tag_raise(right_item)
            drawing_state["ink"] += abs(event.x - last_x) + abs(event.y - last_y)
        drawing_state["last_x"] = event.x
        drawing_state["last_y"] = event.y

    def on_press(event):
        if not interaction_enabled[0]:
            return
        drawing_state["active"] = is_in_sign_area(event.x, event.y)
        drawing_state["last_x"] = event.x
        drawing_state["last_y"] = event.y
        move_pen(event.x, event.y)

    def on_release(_event):
        if drawing_state["active"]:
            maybe_finish()
        drawing_state["active"] = False
        drawing_state["last_x"] = None
        drawing_state["last_y"] = None

    def enable_signing():
        if skip_requested[0]:
            return
        if intro_jitter_job[0] is not None:
            splash.after_cancel(intro_jitter_job[0])
            intro_jitter_job[0] = None
        interaction_enabled[0] = True
        pen_motion["target_x"] = pen_motion["current_x"]
        pen_motion["target_y"] = pen_motion["current_y"]
        canvas.itemconfigure(title_box, state="normal")
        canvas.itemconfigure(title_item, state="normal")
        canvas.itemconfigure(sign_box, state="normal")
        canvas.itemconfigure(hint_item, state="normal")

    canvas.bind("<Motion>", on_motion)
    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<ButtonRelease-1>", on_release)
    splash.after(16, animate_pen)

    splash.after(450, reveal_contract)

    return splash

def exit_app():
    root.destroy()


root = tk.Tk()
root.withdraw()
root.configure(bg=PANE_BG)
root.attributes("-fullscreen", APP_SETTINGS["fullscreen"])
block_esc(root)
init_custom_cursor(root)

sw = root.winfo_screenwidth()
sh = root.winfo_screenheight()
root.geometry(f"{sw}x{sh}+0+0")

if APP_SETTINGS["music_enabled"]:
    play_music(BACKGROUND_MUSIC)

root.after(100, lambda: show_splash(root))
root.deiconify()
desktop_wallpaper_source = Image.open(PANE_OS_DIR / "SMILE.png")
start_button_source = Image.open(PANE_OS_DIR / "start.png")
close_idle = tk.PhotoImage(file=str(PANE_OS_DIR / "close1.png"))
close_hover = tk.PhotoImage(file=str(PANE_OS_DIR / "close2.png"))
close_pressed = tk.PhotoImage(file=str(PANE_OS_DIR / "close3.png"))
root._ui_sprites = (close_idle, close_hover, close_pressed)

title_bar = tk.Frame(root, bg=PANE_TITLE, height=26)
title_bar.pack(fill="x", side="top")

make_draggable(title_bar)

tk.Label(
    title_bar,
    text="SECURE_SYSTEM.EXE",
    bg=PANE_TITLE,
    fg="white",
    font=("Terminal", 10)
).pack(side="left", padx=8, pady=4)

close_btn = tk.Label(
    title_bar,
    image=close_idle,
    bg=PANE_TITLE,
    borderwidth=0,
    highlightthickness=0,
    cursor="hand2"
)
close_btn.pack(side="right", padx=6, pady=4)

def set_close_sprite(sprite):
    close_btn.config(image=sprite)
    close_btn.image = sprite

close_btn.bind("<Enter>", lambda e: set_close_sprite(close_hover))
close_btn.bind("<Leave>", lambda e: set_close_sprite(close_idle))
close_btn.bind("<ButtonPress-1>", lambda e: set_close_sprite(close_pressed))

def release_close(event):
    hovered = 0 <= event.x < close_btn.winfo_width() and 0 <= event.y < close_btn.winfo_height()
    set_close_sprite(close_hover if hovered else close_idle)
    if hovered:
        exit_app()

close_btn.bind("<ButtonRelease-1>", release_close)

def lock_start_button():
    open_game_btn["enabled"] = False
    desktop_canvas.itemconfigure(open_game_btn["text_shadow_item"], text="secret_files.locked")
    desktop_canvas.itemconfigure(open_game_btn["text_item"], fill="#b5b5b5", text="secret_files.locked")

def unlock_start_button():
    open_game_btn["enabled"] = True
    desktop_canvas.itemconfigure(open_game_btn["text_shadow_item"], text="secret_files/")
    desktop_canvas.itemconfigure(open_game_btn["text_item"], fill="#f5f5f5", text="secret_files/")

desktop = tk.Frame(root, bg=PANE_BG)
desktop.pack(expand=True, fill="both")

desktop_canvas = tk.Canvas(desktop, bg=PANE_BG, highlightthickness=0, borderwidth=0)
desktop_canvas.pack(expand=True, fill="both")

wallpaper_item = desktop_canvas.create_image(0, 0, anchor="nw")
title_item = desktop_canvas.create_text(0, 0, text="Abebe Protocol", fill=PANE_TEXT, font=("Terminal", 56))
credit_item = desktop_canvas.create_text(0, 0, text="Made by Mr. Banandee", fill=PANE_TEXT_MUTED, font=("Terminal", 10))
auth_item = desktop_canvas.create_text(0, 0, text="AUTHORIZED ACCESS ONLY", fill=PANE_TEXT_MUTED, font=("Terminal", 14))

icon_my_computer = load_menu_icon("mycomputer.png")
icon_exe = load_menu_icon("exefile.png")
icon_settings = load_menu_icon("settingfile.png")
icon_folder = load_menu_icon("folder.png")
icon_data = load_menu_icon("datafile.png")

def start_game():
    global game_running
    if game_running:
        return

    game_running = True
    lock_start_button()
    show_password_window(root)
    
new_game_btn = create_desktop_file_icon(
    desktop_canvas,
    icon_exe,
    "ABEBE_PROTOCOL.exe",
    command=start_new_game
)

load_game_btn = create_desktop_file_icon(
    desktop_canvas,
    icon_data,
    "save_data.bin",
    command=lambda: None,
    enabled=False
)

open_game_btn = create_desktop_file_icon(
    desktop_canvas,
    icon_folder,
    "secret_files/",
    command=lambda: game_state.start_game(show_password_window)
)

settings_btn = create_desktop_file_icon(
    desktop_canvas,
    icon_settings,
    "system_settings.ini",
    command=lambda: show_settings(root)
)

intro_btn = create_desktop_file_icon(
    desktop_canvas,
    icon_my_computer,
    "my_computer.lnk",
    command=lambda: show_intro(root)
)

exit_btn = create_desktop_file_icon(
    desktop_canvas,
    icon_exe,
    "shutdown.exe",
    command=exit_app
)

desktop_icons = [
    new_game_btn,
    load_game_btn,
    open_game_btn,
    settings_btn,
    intro_btn,
    exit_btn,
]

version_label = tk.Label(
    desktop_canvas,
    text="Version 0.2.5-alpha",
    fg=PANE_TEXT_MUTED,
    bg=PANE_BG,
    font=("Terminal", 10)
)
version_window = desktop_canvas.create_window(0, 0, window=version_label, anchor="se")

def update_desktop_layout(event):
    wallpaper = ImageTk.PhotoImage(desktop_wallpaper_source.resize((event.width, event.height), Image.NEAREST))
    start_img = ImageTk.PhotoImage(start_button_source.copy())
    root._wallpaper_image = wallpaper
    root._start_button_image = start_img
    desktop_canvas.itemconfigure(wallpaper_item, image=wallpaper)
    center_x = event.width // 2
    top_y = max(120, (event.height // 2) - 300)
    desktop_canvas.coords(title_item, center_x, top_y)
    desktop_canvas.coords(credit_item, center_x, top_y + 78)
    desktop_canvas.coords(auth_item, center_x, top_y + 118)
    row_y = top_y + 210
    icon_spacing = 138
    start_x = center_x - ((len(desktop_icons) - 1) * icon_spacing) // 2
    for index, icon in enumerate(desktop_icons):
        icon_x = start_x + (index * icon_spacing)
        icon_y = row_y
        text_y = icon_y + 76
        desktop_canvas.coords(icon["icon_item"], icon_x, icon_y)
        desktop_canvas.coords(icon["text_shadow_item"], icon_x + 1, text_y + 1)
        desktop_canvas.coords(icon["text_item"], icon_x, text_y)
        bbox = desktop_canvas.bbox(icon["text_item"])
        if bbox is None:
            bbox = (icon_x - 60, text_y, icon_x + 60, text_y + 24)
        left = min(icon_x - 36, bbox[0] - 6)
        top = icon_y - 4
        right = max(icon_x + 36, bbox[2] + 6)
        bottom = bbox[3] + 6
        desktop_canvas.coords(icon["hitbox_item"], left, top, right, bottom)
    desktop_canvas.coords(version_window, event.width - 14, event.height - 8)
    start_placeholder.config(image=start_img)
    start_placeholder.image = start_img

desktop_canvas.bind("<Configure>", update_desktop_layout)

taskbar = tk.Frame(root, bg=PANE_BG_DARK, height=34, highlightbackground=PANE_BORDER_DARK, highlightthickness=1)
taskbar.pack(fill="x", side="bottom")
taskbar.pack_propagate(False)

start_placeholder = tk.Label(
    taskbar,
    bg=PANE_BG,
    fg=PANE_TEXT,
    relief="raised",
    borderwidth=2,
)
start_placeholder.pack(side="left", padx=8, pady=4)

taskbar_tasks = tk.Frame(taskbar, bg=PANE_BG_DARK)
taskbar_tasks.pack(side="left", fill="y", padx=4)
root._taskbar_tasks = taskbar_tasks

task_placeholder = tk.Label(
    taskbar_tasks,
    text=" ",
    bg=PANE_BG,
    fg=PANE_TEXT,
    width=16,
    relief="sunken",
    borderwidth=2,
)
task_placeholder.pack(side="left", padx=4, pady=4)

clock_box = tk.Frame(taskbar, bg=PANE_BG, relief="sunken", borderwidth=2)
clock_box.pack(side="right", padx=8, pady=4)

tk.Label(
    clock_box,
    text="2066 02 29",
    bg=PANE_BG,
    fg=PANE_TEXT,
    font=("Terminal", 10),
).pack(side="left", padx=(8, 6), pady=2)

tk.Label(
    clock_box,
    text="13:44",
    bg=PANE_BG,
    fg=PANE_TEXT,
    font=("Terminal", 10),
).pack(side="left", padx=(0, 8), pady=2)

root._cursor_api["apply_hidden_cursor"](root)
for clickable in (
    close_btn,
    start_placeholder,
    task_placeholder,
):
    root._cursor_api["register_click_widget"](clickable)

for icon in desktop_icons:
    root._cursor_api["register_click_canvas_item"](desktop_canvas, icon["hitbox_item"])



root.mainloop()
