import time
import tkinter as tk


LOADING_BG = "#05070c"
LOADING_PANEL = "#0d1420"
LOADING_BORDER = "#6ed3ff"
LOADING_TEXT = "#dff6ff"
LOADING_MUTED = "#86a6ba"


def _create_loading_overlay(root):
    overlay = tk.Toplevel(root)
    overlay.overrideredirect(True)
    overlay.configure(bg=LOADING_BG)
    overlay.attributes("-topmost", True)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    overlay.geometry(f"{screen_w}x{screen_h}+0+0")

    container = tk.Frame(
        overlay,
        bg=LOADING_BG,
        highlightthickness=0,
        borderwidth=0,
    )
    container.place(relx=0.5, rely=0.5, anchor="center")

    panel = tk.Frame(
        container,
        bg=LOADING_PANEL,
        highlightbackground=LOADING_BORDER,
        highlightthickness=2,
        borderwidth=0,
    )
    panel.pack()

    tk.Label(
        panel,
        text="ABEBE WATCHER",
        bg=LOADING_PANEL,
        fg=LOADING_BORDER,
        font=("Terminal", 22),
        padx=56,
        pady=28,
    ).pack()

    tk.Label(
        panel,
        text="Loading 3D level...",
        bg=LOADING_PANEL,
        fg=LOADING_TEXT,
        font=("Terminal", 18),
        padx=56,
    ).pack()

    tk.Label(
        panel,
        text="Preparing OpenGL renderer, textures, audio and entities",
        bg=LOADING_PANEL,
        fg=LOADING_MUTED,
        font=("Terminal", 12),
        padx=56,
    ).pack(pady=(10, 8))

    progress_outer = tk.Frame(
        panel,
        bg=LOADING_PANEL,
        highlightbackground=LOADING_BORDER,
        highlightthickness=1,
        borderwidth=0,
        width=420,
        height=16,
    )
    progress_outer.pack(padx=56, pady=(12, 30))
    progress_outer.pack_propagate(False)

    progress_fill = tk.Frame(progress_outer, bg=LOADING_BORDER, width=210, height=14, borderwidth=0)
    progress_fill.place(x=1, y=1)

    overlay.update_idletasks()
    overlay.lift()
    overlay.focus_force()
    overlay.update()
    return overlay


def run_pygame_session(root, callback, *args, **kwargs):
    if root is None:
        return callback(*args, **kwargs)

    hidden_windows = []
    loading_overlay = None
    overlay_closed = False

    def hide_window(window):
        try:
            if not window.winfo_exists():
                return
            previous_state = window.state()
            if previous_state == "withdrawn":
                return
            previous_alpha = window.attributes("-alpha")
            hidden_windows.append((window, previous_alpha, previous_state))
            window.attributes("-alpha", 0.0)
        except tk.TclError:
            pass

    try:
        loading_overlay = _create_loading_overlay(root)

        hide_window(root)
        for child in root.winfo_children():
            if isinstance(child, tk.Toplevel) and child is not loading_overlay:
                hide_window(child)

        root.update_idletasks()
        root.update()

        # First make Tk fully invisible, then iconify it so it does not stay
        # around as a second visible window when pygame goes fullscreen.
        for window, _previous_alpha, previous_state in hidden_windows:
            try:
                if not window.winfo_exists():
                    continue
                if previous_state != "iconic":
                    window.iconify()
            except tk.TclError:
                pass

        root.update_idletasks()
        root.update()

        # Give Windows a tiny moment to paint the loading overlay and apply
        # the minimized state before pygame switches into fullscreen OpenGL.
        time.sleep(0.08)
        if loading_overlay is not None:
            try:
                if loading_overlay.winfo_exists():
                    loading_overlay.destroy()
                overlay_closed = True
            except tk.TclError:
                pass
        return callback(*args, **kwargs)
    finally:
        if loading_overlay is not None and not overlay_closed:
            try:
                if loading_overlay.winfo_exists():
                    loading_overlay.destroy()
            except tk.TclError:
                pass
        for window, previous_alpha, previous_state in hidden_windows:
            try:
                if window.winfo_exists():
                    if previous_state != "iconic" and window.state() == "iconic":
                        window.deiconify()
                    window.attributes("-alpha", previous_alpha)
            except tk.TclError:
                pass
        try:
            if root.winfo_exists():
                root.lift()
                root.focus_force()
        except tk.TclError:
            pass
