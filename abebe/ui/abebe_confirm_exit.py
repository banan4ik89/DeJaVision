# abebe_confirm_exit.py
import tkinter as tk
import random
from abebe.core.utils import block_esc

_confirm_window = None

def show_abebe_confirm(root, on_yes, on_no=None):
    global _confirm_window

    # вњ… Р•РЎР›Р РЈР–Р• РћРўРљР Р«РўРћ вЂ” РќРР§Р•Р“Рћ РќР• РЎРћР—Р”РђРЃРњ
    if _confirm_window and _confirm_window.winfo_exists():
        _confirm_window.lift()
        return

    win = tk.Toplevel(root)
    _confirm_window = win

    # рџ”— РїСЂР°РІРёР»СЊРЅР°СЏ РїСЂРёРІСЏР·РєР°
    win.transient(root)
    win.overrideredirect(True)
    win.configure(bg="black")
    win.attributes("-topmost", True)
    block_esc(win)

    # ===== SIZE =====
    w, h = 480, 260
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    # ===== CLEANUP =====
    def cleanup():
        global _confirm_window
        _confirm_window = None
        if win.winfo_exists():
            win.destroy()

    def confirm():
        cleanup()
        on_yes()

    def cancel():
        cleanup()
        if on_no:
            on_no()

    win.protocol("WM_DELETE_WINDOW", cancel)

    # ===== TITLE BAR =====
    title = tk.Frame(win, bg="#C0C0C0", height=28)
    title.pack(fill="x")

    tk.Label(
        title,
        text="ABEBE_CONFIRM.EXE",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 11)
    ).pack(side="left", padx=10)

    close = tk.Label(
        title,
        text=" вњ• ",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 13, "bold"),
        cursor="hand2"
    )
    close.pack(side="right", padx=8)
    close.bind("<Button-1>", lambda e: cancel())

    # ===== CONTENT =====
    content = tk.Frame(
        win,
        bg="black",
        highlightbackground="red",
        highlightthickness=2
    )
    content.pack(expand=True, fill="both", padx=8, pady=8)

    tk.Label(
        content,
        text="YOU ARE TRYING TO EXIT.\n\nABEBE IS WATCHING.\n\nCONFIRM DECISION.",
        fg="red",
        bg="black",
        font=("Terminal", 15),
        justify="center",
        wraplength=420
    ).pack(pady=28)

    btn_frame = tk.Frame(content, bg="black")
    btn_frame.pack(pady=12)

    tk.Button(
        btn_frame,
        text="CONFIRM EXIT",
        width=18,
        height=2,
        font=("Terminal", 13, "bold"),
        bg="black",
        fg="red",
        relief="ridge",
        borderwidth=3,
        command=confirm
    ).pack(side="left", padx=14)

    tk.Button(
        btn_frame,
        text="STAY",
        width=18,
        height=2,
        font=("Terminal", 13, "bold"),
        bg="black",
        fg="lime",
        relief="ridge",
        borderwidth=3,
        command=cancel
    ).pack(side="right", padx=14)

    # ===== SHAKE =====
    def shake():
        if not win.winfo_exists():
            return
        x = win.winfo_x()
        y = win.winfo_y()
        win.geometry(f"+{x + random.randint(-3,3)}+{y + random.randint(-3,3)}")
        win.after(40, shake)

    shake()
