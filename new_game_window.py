import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

import testing_maze
from game_launcher import run_pygame_session
from settings_window import make_draggable
from user_settings import load_settings, save_settings
from utils import get_exe_dir


PANE_OS_DIR = Path(get_exe_dir()) / "data" / "PaneOS"
WINDOW_SIZE = (760, 500)
WINDOW_IMAGE_SIZE = (WINDOW_SIZE[0], WINDOW_SIZE[1])
PANE_BG = "#c3c3c3"
PANE_BG_DARK = "#b8b8b8"
PANE_BORDER_DARK = "#808080"
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


def _geometry_string(width, height, x, y):
    return f"{int(round(width))}x{int(round(height))}+{int(round(x))}+{int(round(y))}"


def _button(parent, text, command, width=26, state="normal", fg=PANE_TEXT):
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=("Terminal", 12),
        bg=PANE_BG,
        fg=fg,
        activebackground=PANE_ACTIVE,
        activeforeground=PANE_TEXT,
        relief="raised",
        borderwidth=2,
        width=width,
        state=state,
        anchor="w",
        padx=12,
    )


def _file_case_card(parent, filename, footer, command=None, locked=False):
    card_bg = PANE_BG if not locked else PANE_BG_DARK
    title_fg = PANE_TEXT if not locked else "#5f5f5f"
    footer_fg = PANE_TEXT_MUTED if not locked else "#6f6f6f"
    relief = "raised" if not locked else "sunken"

    card = tk.Frame(
        parent,
        bg=card_bg,
        relief=relief,
        borderwidth=2,
        highlightbackground=PANE_BORDER_DARK,
        highlightthickness=1,
    )

    if command is not None and not locked:
        def on_enter(_event):
            card.config(bg=PANE_ACTIVE)
            title.config(bg=PANE_ACTIVE)
            footer_bar.config(bg=PANE_TITLE)
            footer_label.config(bg=PANE_TITLE)

        def on_leave(_event):
            card.config(bg=PANE_BG)
            title.config(bg=PANE_BG)
            footer_bar.config(bg=PANE_BG_DARK)
            footer_label.config(bg=PANE_BG_DARK)

        def on_click(_event):
            command()

        for widget in (card,):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<ButtonRelease-1>", on_click)

    title = tk.Label(
        card,
        text=filename,
        fg=title_fg,
        bg=card_bg,
        font=("Terminal", 14),
        anchor="w",
        padx=14,
        pady=12,
    )
    title.pack(fill="x")

    footer_bar = tk.Frame(card, bg=PANE_BG_DARK if not locked else "#9a9a9a", height=26)
    footer_bar.pack(fill="x", side="bottom")
    footer_bar.pack_propagate(False)

    footer_label = tk.Label(
        footer_bar,
        text=footer,
        fg="white" if not locked else "#4f4f4f",
        bg=PANE_BG_DARK if not locked else "#9a9a9a",
        font=("Terminal", 10),
        anchor="w",
        padx=12,
    )
    footer_label.pack(fill="both", expand=True)

    if command is not None and not locked:
        for widget in (title, footer_bar, footer_label):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<ButtonRelease-1>", on_click)

    return card


def _save_slot_card(parent, slot, command):
    card = tk.Frame(
        parent,
        bg=PANE_BG_DARK,
        relief="raised",
        borderwidth=2,
        highlightbackground=PANE_BORDER_DARK,
        highlightthickness=1,
        width=180,
        height=180,
    )
    card.pack_propagate(False)

    def on_enter(_event):
        card.config(bg=PANE_ACTIVE)
        title.config(bg=PANE_ACTIVE)
        subtitle.config(bg=PANE_ACTIVE)

    def on_leave(_event):
        card.config(bg=PANE_BG_DARK)
        title.config(bg=PANE_BG_DARK)
        subtitle.config(bg=PANE_BG_DARK)

    def on_click(_event):
        command()

    title = tk.Label(
        card,
        text=f"SAVE {slot}",
        fg=PANE_TEXT,
        bg=PANE_BG_DARK,
        font=("Terminal", 18),
    )
    title.pack(pady=(34, 10))

    subtitle = tk.Label(
        card,
        text=f"slot_{slot:02}.sav",
        fg=PANE_TEXT_MUTED,
        bg=PANE_BG_DARK,
        font=("Terminal", 10),
    )
    subtitle.pack(pady=(0, 18))

    choose_btn = _button(card, "SELECT", lambda: command(), width=10)
    choose_btn.pack()

    for widget in (card, title, subtitle):
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
        widget.bind("<ButtonRelease-1>", on_click)

    return card


def show_new_game_window(root):
    existing = getattr(root, "_new_game_window", None)
    if existing is not None and existing.winfo_exists():
        if getattr(existing, "_is_hidden", False):
            existing.deiconify()
            existing._is_hidden = False
        existing.lift()
        return

    settings = load_settings()

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg=PANE_BG)
    win.attributes("-topmost", True)
    win.geometry(_geometry_string(WINDOW_SIZE[0], WINDOW_SIZE[1], 460, 240))
    root._new_game_window = win
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
    taskbar_icon = tk.PhotoImage(file=str(PANE_OS_DIR / "settings.png"))

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
        text="NEW_GAME.EXE",
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

    close_btn = tk.Label(title_bar, bg=PANE_TITLE, borderwidth=0, highlightthickness=0, cursor="hand2")
    close_btn.pack(side="right", padx=4, pady=4)
    maximize_btn = tk.Label(title_bar, bg=PANE_TITLE, borderwidth=0, highlightthickness=0, cursor="hand2")
    maximize_btn.pack(side="right", padx=(0, 2), pady=4)
    minimize_btn = tk.Label(title_bar, bg=PANE_TITLE, borderwidth=0, highlightthickness=0, cursor="hand2")
    minimize_btn.pack(side="right", padx=(0, 2), pady=4)

    def close_window():
        if hasattr(win, "_taskbar_button") and win._taskbar_button.winfo_exists():
            win._taskbar_button.destroy()
        root._new_game_window = None
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

    def minimize_window():
        win._is_hidden = True
        win.withdraw()

    def apply_layout(width, height):
        render_background(width, height)
        title_bar.place(x=TITLE_BAR_PADDING, y=TITLE_BAR_Y, width=width - (TITLE_BAR_PADDING * 2), height=TITLE_BAR_HEIGHT)
        shell.place(x=SHELL_X, y=SHELL_TOP, width=width - (SHELL_X * 2), height=height - SHELL_TOP - SHELL_BOTTOM_MARGIN)

    def maximize_window():
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

    bind_sprite_button(minimize_btn, (minimize_idle, minimize_hover, minimize_pressed), minimize_window)
    bind_sprite_button(maximize_btn, (maximize_idle, maximize_hover, maximize_pressed), maximize_window)
    bind_sprite_button(close_btn, (close_idle, close_hover, close_pressed), close_window)

    make_draggable(win, title_bar)

    shell = tk.Frame(win, bg=PANE_BG, borderwidth=0, highlightthickness=0)
    shell.place(x=SHELL_X, y=SHELL_TOP, width=WINDOW_SIZE[0] - 32, height=WINDOW_SIZE[1] - 60)

    content = tk.Frame(shell, bg=PANE_BG)
    content.pack(expand=True, fill="both", padx=12, pady=12)

    top_status = tk.Label(
        content,
        text="",
        fg=PANE_TEXT_MUTED,
        bg=PANE_BG,
        font=("Terminal", 10),
        anchor="w",
    )
    top_status.pack(fill="x", pady=(0, 12))

    body = tk.Frame(content, bg=PANE_BG_DARK, highlightbackground=PANE_BORDER_DARK, highlightthickness=1)
    body.pack(expand=True, fill="both")

    current_view = {"frame": None}
    cursor_api = getattr(root, "_cursor_api", None)

    def register_clickables(widget):
        if cursor_api is None:
            return
        if isinstance(widget, (tk.Button, tk.Label, tk.Checkbutton, tk.Scale, tk.Menubutton)):
            cursor_api["register_click_widget"](widget)
        for child in widget.winfo_children():
            register_clickables(child)

    def swap_body(frame):
        if current_view["frame"] is not None:
            current_view["frame"].destroy()
        current_view["frame"] = frame
        frame.pack(expand=True, fill="both", padx=18, pady=18)
        register_clickables(frame)

    def show_case_list():
        latest_settings = load_settings()
        slot = latest_settings.get("selected_save_slot")
        top_status.config(text=f"Selected save slot: SAVE {slot}" if slot else "Selected save slot: NONE")

        frame = tk.Frame(body, bg=PANE_BG)
        tk.Label(
            frame,
            text="CASE DIRECTORY",
            fg=PANE_TEXT,
            bg=PANE_BG,
            font=("Terminal", 18),
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        tk.Label(
            frame,
            text="Available investigations are listed below. Only the tutorial is currently unlocked.",
            fg=PANE_TEXT_MUTED,
            bg=PANE_BG,
            font=("Terminal", 10),
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(0, 18))

        list_outer = tk.Frame(frame, bg=PANE_BG_DARK, highlightbackground=PANE_BORDER_DARK, highlightthickness=1)
        list_outer.pack(fill="both", expand=True)

        case_canvas = tk.Canvas(
            list_outer,
            bg=PANE_BG,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=18,
        )
        case_canvas.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_outer, orient="vertical", command=case_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        case_canvas.configure(yscrollcommand=scrollbar.set)

        list_wrap = tk.Frame(case_canvas, bg=PANE_BG)
        canvas_window = case_canvas.create_window((0, 0), window=list_wrap, anchor="nw")

        def refresh_scroll_region(_event=None):
            case_canvas.configure(scrollregion=case_canvas.bbox("all"))
            case_canvas.itemconfigure(canvas_window, width=case_canvas.winfo_width())

        def on_mousewheel(event):
            step = -1 if event.delta > 0 else 1
            case_canvas.yview_scroll(step, "units")

        list_wrap.bind("<Configure>", refresh_scroll_region)
        case_canvas.bind("<Configure>", refresh_scroll_region)
        for widget in (case_canvas, list_wrap):
            widget.bind("<MouseWheel>", on_mousewheel)

        case_entries = [
            ("case_0.0.0_tutorial.abebe", "case 0.0.0 // Tutorial", False),
            ("case_0.0.1_archive.abebe", "case ???", True),
            ("case_0.0.2_signal.abebe", "case ???", True),
            ("case_0.0.3_memory.abebe", "case ???", True),
            ("case_0.0.4_access.abebe", "case ???", True),
            ("case_0.0.5_void.abebe", "case ???", True),
            ("case_0.0.6_watcher.abebe", "case ???", True),
        ]

        for filename, footer, locked in case_entries:
            _file_case_card(
                list_wrap,
                filename,
                footer,
                command=None if locked else lambda: run_pygame_session(root, testing_maze.start_game, root),
                locked=locked,
            ).pack(fill="x", pady=(0, 12))

        tk.Label(
            frame,
            text="The locked cases will open later.",
            fg=PANE_TEXT_MUTED,
            bg=PANE_BG,
            font=("Terminal", 10),
            anchor="w",
        ).pack(fill="x", pady=(10, 0))

        swap_body(frame)

    def select_slot(slot):
        save_settings({
            "selected_save_slot": slot,
            "new_game_slot_prompt_seen": True,
        })
        show_case_list()

    def show_slot_picker():
        top_status.config(text="Select where your progress will be saved. This window appears only once until reset in settings.")

        frame = tk.Frame(body, bg=PANE_BG)
        tk.Label(
            frame,
            text="SELECT SAVE SLOT",
            fg=PANE_TEXT,
            bg=PANE_BG,
            font=("Terminal", 18),
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        tk.Label(
            frame,
            text="Choose one of three save slots for the new game.",
            fg=PANE_TEXT_MUTED,
            bg=PANE_BG,
            font=("Terminal", 10),
            anchor="w",
        ).pack(fill="x", pady=(0, 18))

        slots_row = tk.Frame(frame, bg=PANE_BG)
        slots_row.pack(fill="x", pady=(8, 0))

        for slot in (1, 2, 3):
            _save_slot_card(
                slots_row,
                slot,
                lambda value=slot: select_slot(value),
            ).pack(side="left", expand=True, padx=8)

        swap_body(frame)

    taskbar_tasks = getattr(root, "_taskbar_tasks", None)
    if taskbar_tasks is not None:
        task_button = tk.Label(
            taskbar_tasks,
            image=taskbar_icon,
            bg=PANE_BG,
            relief="sunken",
            borderwidth=2,
            cursor="hand2",
            width=24,
        )
        task_button.image = taskbar_icon
        task_button.pack(side="left", padx=4, pady=4)
        task_button.bind("<Button-1>", lambda _: restore_from_taskbar())
        win._taskbar_button = task_button

    if cursor_api is not None:
        cursor_api["apply_hidden_cursor"](win)

        register_clickables(title_bar)
        if taskbar_tasks is not None:
            cursor_api["register_click_widget"](task_button)

    win.protocol("WM_DELETE_WINDOW", close_window)

    if settings.get("new_game_slot_prompt_seen") and settings.get("selected_save_slot") in (1, 2, 3):
        show_case_list()
    else:
        show_slot_picker()
