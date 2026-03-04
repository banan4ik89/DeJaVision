
import tkinter as tk
import random
import string
from hack_maze3d import start_hack_maze


def make_draggable(win, bar):
    def start(e):
        win.x = e.x
        win.y = e.y

    def move(e):
        win.geometry(f"+{e.x_root - win.x}+{e.y_root - win.y}")

    bar.bind("<Button-1>", start)
    bar.bind("<B1-Motion>", move)



def show_hack_decoder(root, theme):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg="black")
    win.attributes("-topmost", True)
    win.geometry("440x300+480+300")

    
    title_bar = tk.Frame(win, bg="#C0C0C0", height=26)
    title_bar.pack(fill="x")

    tk.Label(
        title_bar,
        text="HACK_DECODER.EXE",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 10)
    ).pack(side="left", padx=8)

    close_btn = tk.Label(
        title_bar,
        text=" ✕ ",
        bg="#C0C0C0",
        fg="black",
        font=("Terminal", 10, "bold"),
        cursor="hand2"
    )
    close_btn.pack(side="right", padx=6)
    close_btn.bind("<Button-1>", lambda e: win.destroy())
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

    
    log = tk.Text(
        content,
        bg="black",
        fg="lime",
        font=("Consolas", 11),
        height=10,
        wrap="none",
        state="disabled",
        bd=0
    )
    log.pack(fill="both", expand=True, padx=10, pady=(10, 6))

    
    btn_frame = tk.Frame(content, bg="black")
    btn_frame.pack(fill="x", pady=(0, 8))

    
    noise_chars = string.ascii_uppercase + string.digits + "#@$%"
    phrases = [
        "Initializing decoder module...",
        "Bypassing security layer...",
        "Accessing encrypted memory...",
        "Reading protocol headers...",
        "Injecting override sequence...",
        "Decrypting data stream...",
        "Analyzing semantic patterns...",
        "Reconstructing password logic..."
    ]

    running = True

    def write(line):
        log.config(state="normal")
        log.insert("end", line + "\n")
        log.see("end")
        log.config(state="disabled")

    def spam_text():
        if not running or not win.winfo_exists():
            return

        if random.random() < 0.35:
            write(random.choice(phrases))
        else:
            noise = "".join(random.choice(noise_chars) for _ in range(32))
            write(noise)

        win.after(80, spam_text)

    spam_text()

    
    def decrypt():
        nonlocal running
        running = False
        decrypt_btn.destroy()
        write("Entering breach simulation...")

        def unlocked():
            show_password_theme()

        start_hack_maze(root, win, unlocked)

    

    decrypt_btn = tk.Button(
        btn_frame,
        text="DECRYPT",
        bg="black",
        fg="white",
        activeforeground="lime",
        relief="ridge",
        width=18,
        command=decrypt
    )
    decrypt_btn.pack()

    
    def show_password_theme():
        write("")
        write("PASSWORD_THEME IDENTIFIED:")
        write(f">>> {theme}")
        log.config(fg="red")
