# abebe_confirm_exit.py
import tkinter as tk
import random
from utils import block_esc

def show_abebe_confirm(root, on_yes, on_no=None):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg="black")
    win.attributes("-topmost", True)
    block_esc(win)

    # ===== SIZE (увеличили) =====
    w, h = 480, 260
    win.geometry(f"{w}x{h}+0+0")
    win.update_idletasks()

    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()

    x = (sw - w) // 2
    y = (sh - h) // 2

    win.geometry(f"{w}x{h}+{x}+{y}")

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
        text=" ✕ ",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 13, "bold"),
        cursor="hand2"
    )
    close.pack(side="right", padx=8)

    # ===== callbacks (нужны ДО bind) =====
    def confirm():
        win.destroy()
        on_yes()

    def cancel():
        win.destroy()
        if on_no:
            on_no()

    close.bind("<Button-1>", lambda e: cancel())

    # ===== CONTENT =====
    content = tk.Frame(
        win,
        bg="black",
        highlightbackground="red",
        highlightthickness=2
    )
    content.pack(expand=True, fill="both", padx=8, pady=8)

    label = tk.Label(
        content,
        text="YOU ARE TRYING TO EXIT.\n\nABEBE IS WATCHING.\n\nCONFIRM DECISION.",
        fg="red",
        bg="black",
        font=("Terminal", 15),
        justify="center",
        wraplength=420
    )
    label.pack(pady=28)

    btn_frame = tk.Frame(content, bg="black")
    btn_frame.pack(pady=12)

    # ===== BIGGER BUTTONS =====
    yes = tk.Button(
        btn_frame,
        text="CONFIRM EXIT",
        width=18,
        height=2,
        font=("Terminal", 13, "bold"),
        bg="black",
        fg="red",
        activeforeground="white",
        activebackground="black",
        relief="ridge",
        borderwidth=3,
        cursor="hand2",
        command=confirm
    )
    yes.pack(side="left", padx=14)

    no = tk.Button(
        btn_frame,
        text="STAY",
        width=18,
        height=2,
        font=("Terminal", 13, "bold"),
        bg="black",
        fg="lime",
        activeforeground="white",
        activebackground="black",
        relief="ridge",
        borderwidth=3,
        cursor="hand2",
        command=cancel
    )
    no.pack(side="right", padx=14)

    # ===== SHAKE =====
    def shake():
        if not win.winfo_exists():
            return
        x = win.winfo_x()
        y = win.winfo_y()
        dx = random.randint(-3, 3)
        dy = random.randint(-3, 3)
        win.geometry(f"+{x+dx}+{y+dy}")
        win.after(40, shake)

    shake()