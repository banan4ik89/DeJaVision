import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from background_music import apply_music_settings, resume_music, stop_music
from user_settings import DEFAULT_SETTINGS, PIXEL_PRESETS, load_settings, save_settings
from utils import get_exe_dir


PANE_OS_DIR = Path(get_exe_dir()) / "data" / "PaneOS"
WINDOW_SIZE = (760, 500)
WINDOW_IMAGE_SIZE = (WINDOW_SIZE[0], WINDOW_SIZE[1])
PANE_BG = "#c3c3c3"
PANE_BG_DARK = "#b8b8b8"
PANE_BORDER_DARK = "#808080"
PANE_BORDER_LIGHT = "#f4f4f4"
PANE_TITLE = "#000080"
PANE_TEXT = "black"
PANE_TEXT_MUTED = "#404040"
PANE_ACTIVE = "#dcdcdc"
TITLE_BAR_PADDING = 8
TITLE_BAR_Y = 8
TITLE_BAR_HEIGHT = 24
SHELL_X = 16
SHELL_TOP = 44
SHELL_BOTTOM_MARGIN = 16
PREVIEW_TRANSPARENT = "#ff00ff"


def make_draggable(win, bar):
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
        win.geometry(_geometry_string(win.winfo_width(), win.winfo_height(), x, y))

    bar.bind("<Button-1>", start)
    bar.bind("<B1-Motion>", move)
    bar.bind("<ButtonRelease-1>", finish)


def _geometry_string(width, height, x, y):
    return f"{int(round(width))}x{int(round(height))}+{int(round(x))}+{int(round(y))}"

def _section_button(parent, text, command):
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=("Terminal", 12),
        bg=PANE_BG,
        fg=PANE_TEXT,
        activebackground=PANE_ACTIVE,
        activeforeground=PANE_TEXT,
        relief="raised",
        borderwidth=2,
        anchor="w",
        padx=14,
        width=16,
    )


def _section_title(parent, text):
    tk.Label(
        parent,
        text=text,
        fg=PANE_TEXT,
        bg=PANE_BG,
        font=("Terminal", 16),
        anchor="w",
    ).pack(fill="x", pady=(6, 16))


def _value_label(parent, value):
    label = tk.Label(
        parent,
        text=value,
        fg=PANE_TEXT,
        bg=PANE_BG,
        font=("Terminal", 11),
        anchor="e",
        width=8,
    )
    label.pack(side="right")
    return label


def _slider_row(parent, title, initial_value, on_change, min_value=0, max_value=100, suffix="%", scale_length=320):
    row = tk.Frame(parent, bg=PANE_BG)
    row.pack(fill="x", pady=8)

    top = tk.Frame(row, bg=PANE_BG)
    top.pack(fill="x")
    tk.Label(
        top,
        text=title,
        fg=PANE_TEXT,
        bg=PANE_BG,
        font=("Terminal", 12),
        anchor="w",
    ).pack(side="left")
    value_label = _value_label(top, f"{int(round(initial_value))}{suffix}")

    def handle_change(raw_value):
        value = max(float(min_value), min(float(max_value), float(raw_value)))
        value_label.config(text=f"{int(round(value))}{suffix}")
        on_change(value)

    tk.Scale(
        row,
        from_=min_value,
        to=max_value,
        orient="horizontal",
        command=handle_change,
        showvalue=False,
        resolution=1,
        length=scale_length,
        troughcolor=PANE_BG_DARK,
        bg=PANE_BG,
        fg=PANE_TEXT,
        highlightthickness=0,
        activebackground=PANE_ACTIVE,
        font=("Terminal", 10),
    ).pack(anchor="w")
    row.children[list(row.children.keys())[-1]].set(initial_value)


def show_settings(root):
    existing = getattr(root, "_settings_window", None)
    if existing is not None and existing.winfo_exists():
        if getattr(existing, "_is_hidden", False):
            existing.deiconify()
            existing._is_hidden = False
        existing.lift()
        return

    current_settings = load_settings()

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg=PANE_BG)
    win.attributes("-topmost", True)
    final_x = 420
    final_y = 220
    win.geometry(_geometry_string(WINDOW_SIZE[0], WINDOW_SIZE[1], final_x, final_y))
    root._settings_window = win
    win._is_hidden = False
    win._is_maximized = False
    win._normal_geometry = win.geometry()

    window_bg_source = Image.open(PANE_OS_DIR / "wondiw.png")
    close_idle = tk.PhotoImage(file=str(PANE_OS_DIR / "close1.png"))
    close_hover = tk.PhotoImage(file=str(PANE_OS_DIR / "close2.png"))
    close_pressed = tk.PhotoImage(file=str(PANE_OS_DIR / "close3.png"))
    minimize_idle = tk.PhotoImage(file=str(PANE_OS_DIR / "minimaze1.png"))
    minimize_hover = tk.PhotoImage(file=str(PANE_OS_DIR / "minimaze2.png"))
    minimize_pressed = tk.PhotoImage(file=str(PANE_OS_DIR / "minimaze3.png"))
    maximize_idle = tk.PhotoImage(file=str(PANE_OS_DIR / "maximize1.png"))
    maximize_hover = tk.PhotoImage(file=str(PANE_OS_DIR / "maximize2.png"))
    maximize_pressed = tk.PhotoImage(file=str(PANE_OS_DIR / "maximize3.png"))
    settings_icon = tk.PhotoImage(file=str(PANE_OS_DIR / "settings.png"))

    def render_background(width, height):
        image = window_bg_source.resize((width, height), Image.NEAREST)
        win._window_bg = ImageTk.PhotoImage(image)
        background.config(image=win._window_bg)

    background = tk.Label(win, borderwidth=0, highlightthickness=0)
    background.place(x=0, y=0, relwidth=1, relheight=1)
    render_background(*WINDOW_IMAGE_SIZE)

    title_bar = tk.Frame(win, bg=PANE_TITLE, height=24)
    title_bar.place(x=TITLE_BAR_PADDING, y=TITLE_BAR_Y, width=WINDOW_SIZE[0] - 16, height=TITLE_BAR_HEIGHT)

    tk.Label(
        title_bar,
        text="SYSTEM_SETTINGS.EXE",
        bg=PANE_TITLE,
        fg="white",
        font=("Terminal", 10),
    ).pack(side="left", padx=6)

    def set_sprite(widget, sprite):
        widget.config(image=sprite)
        widget.image = sprite

    def bind_sprite_button(widget, sprites, on_click):
        idle, hover, pressed = sprites
        set_sprite(widget, idle)
        widget.bind("<Enter>", lambda _: set_sprite(widget, hover))
        widget.bind("<Leave>", lambda _: set_sprite(widget, idle))
        widget.bind("<ButtonPress-1>", lambda _: set_sprite(widget, pressed))

        def release(event):
            hovered = 0 <= event.x < widget.winfo_width() and 0 <= event.y < widget.winfo_height()
            set_sprite(widget, hover if hovered else idle)
            if hovered:
                on_click()

        widget.bind("<ButtonRelease-1>", release)

    close_btn = tk.Label(
        title_bar,
        bg=PANE_TITLE,
        borderwidth=0,
        highlightthickness=0,
        cursor="hand2",
    )
    close_btn.pack(side="right", padx=4, pady=4)

    maximize_btn = tk.Label(
        title_bar,
        bg=PANE_TITLE,
        borderwidth=0,
        highlightthickness=0,
        cursor="hand2",
    )
    maximize_btn.pack(side="right", padx=(0, 2), pady=4)

    minimize_btn = tk.Label(
        title_bar,
        bg=PANE_TITLE,
        borderwidth=0,
        highlightthickness=0,
        cursor="hand2",
    )
    minimize_btn.pack(side="right", padx=(0, 2), pady=4)

    def close_settings():
        if hasattr(win, "_taskbar_button") and win._taskbar_button.winfo_exists():
            win._taskbar_button.destroy()
        root._settings_window = None
        if window_bg_source:
            window_bg_source.close()
        if win.winfo_exists():
            win.destroy()

    def restore_from_taskbar():
        if not win.winfo_exists():
            return
        if win._is_hidden:
            win.deiconify()
            win._is_hidden = False
        win.lift()

    def minimize_settings():
        win._is_hidden = True
        win.withdraw()

    def apply_layout(width, height):
        render_background(width, height)
        title_bar.place(x=TITLE_BAR_PADDING, y=TITLE_BAR_Y, width=width - (TITLE_BAR_PADDING * 2), height=TITLE_BAR_HEIGHT)
        shell.place(x=SHELL_X, y=SHELL_TOP, width=width - (SHELL_X * 2), height=height - SHELL_TOP - SHELL_BOTTOM_MARGIN)

    def maximize_settings():
        if not win._is_maximized:
            win._normal_geometry = win.geometry()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            win.geometry(f"{width}x{height}+0+0")
            win._is_maximized = True
            apply_layout(width, height)
        else:
            win.geometry(win._normal_geometry)
            win._is_maximized = False
            win.update_idletasks()
            apply_layout(win.winfo_width(), win.winfo_height())
        win.lift()

    bind_sprite_button(minimize_btn, (minimize_idle, minimize_hover, minimize_pressed), minimize_settings)
    bind_sprite_button(maximize_btn, (maximize_idle, maximize_hover, maximize_pressed), maximize_settings)
    bind_sprite_button(close_btn, (close_idle, close_hover, close_pressed), close_settings)

    make_draggable(win, title_bar)

    shell = tk.Frame(win, bg=PANE_BG, borderwidth=0, highlightthickness=0)
    shell.place(x=SHELL_X, y=SHELL_TOP, width=WINDOW_SIZE[0] - 32, height=WINDOW_SIZE[1] - 60)

    nav = tk.Frame(shell, bg=PANE_BG_DARK, width=190, highlightbackground=PANE_BORDER_DARK, highlightthickness=1)
    nav.pack(side="left", fill="y", padx=(0, 8), pady=8)
    nav.pack_propagate(False)

    body = tk.Frame(shell, bg=PANE_BG)
    body.pack(side="left", expand=True, fill="both", padx=(0, 8), pady=8)

    tk.Label(
        nav,
        text="SECTIONS",
        fg=PANE_TEXT,
        bg=PANE_BG_DARK,
        font=("Terminal", 14),
    ).pack(anchor="w", padx=14, pady=(16, 18))

    section_frames = {}

    def update_music_toggle(settings):
        if settings["music_enabled"]:
            resume_music()
        else:
            stop_music()

    def on_master_change(value):
        save_settings({"master_volume": value / 100.0})
        apply_music_settings()

    def on_sfx_change(value):
        save_settings({"sfx_volume": value / 100.0})

    def on_music_change(value):
        music_on.set(True)
        save_settings({"music_volume": value / 100.0, "music_enabled": True})
        apply_music_settings()

    graphics = tk.Frame(body, bg=PANE_BG)
    section_frames["Graphics"] = graphics
    _section_title(graphics, "Graphics")

    fullscreen_var = tk.BooleanVar(value=current_settings["fullscreen"])

    def toggle_fullscreen():
        enabled = fullscreen_var.get()
        save_settings({"fullscreen": enabled})
        root.attributes("-fullscreen", enabled)

    tk.Checkbutton(
        graphics,
        text="Fullscreen",
        variable=fullscreen_var,
        command=toggle_fullscreen,
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 16))

    tk.Label(
        graphics,
        text="Pixel Resolution",
        fg=PANE_TEXT,
        bg=PANE_BG,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w")

    pixel_preset = tk.StringVar(value=current_settings["pixel_preset"])

    def apply_pixel_preset(*_args):
        save_settings({"pixel_preset": pixel_preset.get()})

    pixel_menu = tk.OptionMenu(graphics, pixel_preset, *PIXEL_PRESETS.keys())
    pixel_menu.config(
        font=("Terminal", 11),
        bg=PANE_BG,
        fg=PANE_TEXT,
        activebackground=PANE_ACTIVE,
        activeforeground=PANE_TEXT,
        highlightthickness=1,
        highlightbackground=PANE_BORDER_DARK,
        relief="raised",
        bd=2,
        width=28,
    )
    pixel_menu["menu"].config(
        bg=PANE_BG,
        fg=PANE_TEXT,
        activebackground=PANE_ACTIVE,
        activeforeground=PANE_TEXT,
        font=("Terminal", 11),
    )
    pixel_menu.pack(anchor="w", pady=(6, 18))
    pixel_preset.trace_add("write", apply_pixel_preset)

    _slider_row(
        graphics,
        "Brightness",
        current_settings["brightness"] * 100,
        lambda value: save_settings({"brightness": value / 100.0}),
    )

    _slider_row(
        graphics,
        "View Bob",
        current_settings["view_bob"] * 100,
        lambda value: save_settings({"view_bob": value / 100.0}),
        min_value=0,
        max_value=150,
    )

    _slider_row(
        graphics,
        "FOV",
        current_settings["fov_degrees"],
        lambda value: save_settings({"fov_degrees": value}),
        min_value=45,
        max_value=110,
        suffix=" deg",
    )

    tk.Label(
        graphics,
        text="Brightness affects the in-game 3D scene.",
        fg=PANE_TEXT_MUTED,
        bg=PANE_BG,
        font=("Terminal", 10),
        anchor="w",
    ).pack(fill="x", pady=(10, 0))

    audio = tk.Frame(body, bg=PANE_BG)
    section_frames["Audio"] = audio
    _section_title(audio, "Audio")

    music_on = tk.BooleanVar(value=current_settings["music_enabled"])

    def toggle_music_enabled():
        enabled = music_on.get()
        save_settings({"music_enabled": enabled})
        if enabled:
            resume_music()
        else:
            stop_music()

    tk.Checkbutton(
        audio,
        text="Music Enabled",
        variable=music_on,
        command=toggle_music_enabled,
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 12))

    _slider_row(audio, "Master", current_settings["master_volume"] * 100, on_master_change)
    _slider_row(audio, "Sound Effects", current_settings["sfx_volume"] * 100, on_sfx_change)
    _slider_row(audio, "Music", current_settings["music_volume"] * 100, on_music_change)

    tk.Label(
        audio,
        text="Master affects music and step sounds. Sound Effects affects hack maze steps.",
        fg=PANE_TEXT_MUTED,
        bg=PANE_BG,
        font=("Terminal", 10),
        anchor="w",
        justify="left",
    ).pack(fill="x", pady=(12, 0))

    general = tk.Frame(body, bg=PANE_BG)
    section_frames["General"] = general
    _section_title(general, "General")

    flash_var = tk.BooleanVar(value=current_settings["flash_enabled"])
    wheel_switch_var = tk.BooleanVar(value=current_settings["mouse_wheel_weapon_switch"])
    impact_particles_var = tk.BooleanVar(value=current_settings["impact_particles_enabled"])
    bullet_marks_var = tk.BooleanVar(value=current_settings["bullet_marks_enabled"])
    screen_effects_var = tk.BooleanVar(value=current_settings["screen_effects_enabled"])
    rear_culling_var = tk.BooleanVar(value=current_settings["rear_world_culling_enabled"])
    show_fps_var = tk.BooleanVar(value=current_settings["show_fps"])
    show_debug_var = tk.BooleanVar(value=current_settings["show_debug_stats"])

    def toggle_flash():
        save_settings({"flash_enabled": flash_var.get()})

    tk.Checkbutton(
        general,
        text="Flash",
        variable=flash_var,
        command=toggle_flash,
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 10))

    tk.Checkbutton(
        general,
        text="Mouse Wheel Weapon Switch",
        variable=wheel_switch_var,
        command=lambda: save_settings({"mouse_wheel_weapon_switch": wheel_switch_var.get()}),
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 10))

    tk.Checkbutton(
        general,
        text="Impact Particles",
        variable=impact_particles_var,
        command=lambda: save_settings({"impact_particles_enabled": impact_particles_var.get()}),
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 10))

    tk.Checkbutton(
        general,
        text="Bullet Marks",
        variable=bullet_marks_var,
        command=lambda: save_settings({"bullet_marks_enabled": bullet_marks_var.get()}),
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 10))

    tk.Checkbutton(
        general,
        text="Screen Effects",
        variable=screen_effects_var,
        command=lambda: save_settings({"screen_effects_enabled": screen_effects_var.get()}),
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 10))

    tk.Checkbutton(
        general,
        text="Rear World Culling",
        variable=rear_culling_var,
        command=lambda: save_settings({"rear_world_culling_enabled": rear_culling_var.get()}),
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 10))

    tk.Checkbutton(
        general,
        text="Show FPS",
        variable=show_fps_var,
        command=lambda: save_settings({"show_fps": show_fps_var.get()}),
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 10))

    tk.Checkbutton(
        general,
        text="Show Debug Stats",
        variable=show_debug_var,
        command=lambda: save_settings({"show_debug_stats": show_debug_var.get()}),
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 12),
        anchor="w",
    ).pack(anchor="w", pady=(0, 10))

    tk.Label(
        general,
        text="Controls the white flash in the level statistics screen.",
        fg=PANE_TEXT_MUTED,
        bg=PANE_BG,
        font=("Terminal", 10),
        anchor="w",
        justify="left",
    ).pack(fill="x", pady=(0, 20))

    current_slot_label = tk.Label(
        general,
        text="",
        fg=PANE_TEXT,
        bg=PANE_BG,
        font=("Terminal", 12),
        anchor="w",
    )
    current_slot_label.pack(fill="x", pady=(0, 8))

    def refresh_slot_label():
        selected_slot = load_settings().get("selected_save_slot")
        if selected_slot in (1, 2, 3):
            current_slot_label.config(text=f"Current Save Slot: SAVE {selected_slot}")
        else:
            current_slot_label.config(text="Current Save Slot: NOT SELECTED")

    def set_new_game_slot(slot):
        save_settings({
            "selected_save_slot": slot,
            "new_game_slot_prompt_seen": True,
        })
        refresh_slot_label()

    slot_button_row = tk.Frame(general, bg=PANE_BG)
    slot_button_row.pack(anchor="w", pady=(0, 12))

    for slot in (1, 2, 3):
        tk.Button(
            slot_button_row,
            text=f"SAVE {slot}",
            command=lambda value=slot: set_new_game_slot(value),
            font=("Terminal", 11),
            bg=PANE_BG,
            fg=PANE_TEXT,
            activebackground=PANE_ACTIVE,
            activeforeground=PANE_TEXT,
            relief="raised",
            bd=2,
            width=9,
        ).pack(side="left", padx=(0, 8))

    tk.Label(
        general,
        text="Choose another save slot for NEW GAME without resetting everything.",
        fg=PANE_TEXT_MUTED,
        bg=PANE_BG,
        font=("Terminal", 10),
        anchor="w",
        justify="left",
    ).pack(fill="x", pady=(0, 16))

    def reset_to_defaults():
        save_settings(DEFAULT_SETTINGS.copy())
        root.attributes("-fullscreen", DEFAULT_SETTINGS["fullscreen"])
        apply_music_settings()
        if DEFAULT_SETTINGS["music_enabled"]:
            resume_music()
        else:
            stop_music()
        win.destroy()
        show_settings(root)

    tk.Button(
        general,
        text="RESET TO DEFAULTS",
        command=reset_to_defaults,
        font=("Terminal", 12),
        bg=PANE_BG,
        fg=PANE_TEXT,
        activebackground=PANE_ACTIVE,
        activeforeground=PANE_TEXT,
        relief="raised",
        bd=2,
        width=22,
    ).pack(anchor="w", pady=10)

    def reset_new_game_slot():
        save_settings({
            "selected_save_slot": None,
            "new_game_slot_prompt_seen": False,
        })
        refresh_slot_label()

    tk.Button(
        general,
        text="RESET NEW GAME SLOT",
        command=reset_new_game_slot,
        font=("Terminal", 12),
        bg=PANE_BG,
        fg=PANE_TEXT,
        activebackground=PANE_ACTIVE,
        activeforeground=PANE_TEXT,
        relief="raised",
        bd=2,
        width=22,
    ).pack(anchor="w", pady=(0, 8))

    tk.Label(
        general,
        text="Lets you choose a save slot again the next time you press NEW GAME.",
        fg=PANE_TEXT_MUTED,
        bg=PANE_BG,
        font=("Terminal", 10),
        anchor="w",
        justify="left",
    ).pack(fill="x", pady=(0, 10))

    refresh_slot_label()

    active_btn = {"widget": None}

    def show_section(name):
        for frame in section_frames.values():
            frame.pack_forget()
        section_frames[name].pack(expand=True, fill="both")
        if active_btn["widget"] is not None:
            active_btn["widget"].config(fg=PANE_TEXT, bg=PANE_BG, relief="raised")
        btn = nav_buttons[name]
        btn.config(fg=PANE_TEXT, bg=PANE_ACTIVE, relief="sunken")
        active_btn["widget"] = btn

    nav_buttons = {}
    for section_name in ("Graphics", "Audio", "General"):
        btn = _section_button(nav, section_name, lambda n=section_name: show_section(n))
        btn.pack(fill="x", padx=10, pady=4)
        nav_buttons[section_name] = btn

    taskbar_tasks = getattr(root, "_taskbar_tasks", None)
    if taskbar_tasks is not None:
        task_button = tk.Label(
            taskbar_tasks,
            image=settings_icon,
            bg=PANE_BG,
            relief="sunken",
            borderwidth=2,
            cursor="hand2",
            width=24,
        )
        task_button.image = settings_icon
        task_button.pack(side="left", padx=4, pady=4)
        task_button.bind("<Button-1>", lambda _: restore_from_taskbar())
        win._taskbar_button = task_button

    cursor_api = getattr(root, "_cursor_api", None)
    if cursor_api is not None:
        cursor_api["apply_hidden_cursor"](win)
        clickable_widgets = [close_btn, maximize_btn, minimize_btn]
        clickable_widgets.extend(nav_buttons.values())
        clickable_widgets.append(task_button if taskbar_tasks is not None else None)

        def collect_clickables(widget):
            if isinstance(widget, (tk.Button, tk.Checkbutton, tk.Scale, tk.Menubutton)):
                clickable_widgets.append(widget)
            for child in widget.winfo_children():
                collect_clickables(child)

        collect_clickables(body)
        for widget in clickable_widgets:
            if widget is not None:
                cursor_api["register_click_widget"](widget)

    win.protocol("WM_DELETE_WINDOW", close_settings)
    show_section("Graphics")
