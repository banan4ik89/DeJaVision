import tkinter as tk
import random


def make_draggable(win, bar):
    def start(e):
        win.x = e.x
        win.y = e.y

    def move(e):
        win.geometry(f"+{e.x_root - win.x}+{e.y_root - win.y}")

    bar.bind("<Button-1>", start)
    bar.bind("<B1-Motion>", move)



class DialogSystem:
    def __init__(self, root, title="ABEBE_WATCHER.EXE"):
        self.root = root
        self.state = "neutral"
        self.shake_job = None

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg="black")
        self.win.attributes("-topmost", True)

        w, h = 420, 240
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self.win.geometry(f"{w}x{h}+{sw//2 + 200}+{sh//2 - 120}")

        
        self.title_bar = tk.Frame(self.win, bg="#C0C0C0", height=26)
        self.title_bar.pack(fill="x", side="top")

        tk.Label(
            self.title_bar,
            text=title,
            bg="#C0C0C0",
            fg="black",
            font=("Terminal", 10)
        ).pack(side="left", padx=8)

        self.close_btn = tk.Label(
            self.title_bar,
            text=" ✕ ",
            bg="#C0C0C0",
            fg="black",
            font=("Terminal", 12, "bold"),
            cursor="hand2"
        )
        self.close_btn.pack(side="right", padx=6)

        self.close_btn.bind("<Button-1>", lambda e: self.destroy())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(bg="red", fg="white"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(bg="#C0C0C0", fg="black"))

        make_draggable(self.win, self.title_bar)

        
        self.content = tk.Frame(
            self.win,
            bg="black",
            highlightbackground="lime",
            highlightthickness=1
        )
        self.content.pack(expand=True, fill="both", padx=6, pady=6)

        self.text_label = tk.Label(
            self.content,
            text="...",
            fg="white",
            bg="black",
            font=("Terminal", 12),
            justify="left",
            wraplength=380,
            anchor="nw"
        )
        self.text_label.pack(padx=10, pady=10, anchor="nw")

    
    def set_state(self, state):
        self.state = state

        if state == "neutral":
            self.text_label.config(fg="white")
            self.stop_shake()

        elif state == "happy":
            self.text_label.config(fg="lime")
            self.stop_shake()

        elif state == "angry":
            self.text_label.config(fg="red")
            self.start_shake()

    
    def show(self, text):
        prefix = {
            "neutral": "[SYS] ",
            "happy": "[OK] ",
            "angry": "[WARNING] "
        }

        self.text_label.config(text=prefix[self.state] + text)

    
    def start_shake(self):
        if self.shake_job:
            return

        def shake():
            if self.state != "angry":
                self.stop_shake()
                return

            x = self.win.winfo_x()
            y = self.win.winfo_y()
            dx = random.randint(-2, 2)
            dy = random.randint(-2, 2)
            self.win.geometry(f"+{x + dx}+{y + dy}")

            self.shake_job = self.win.after(40, shake)

        shake()

    def stop_shake(self):
        if self.shake_job:
            self.win.after_cancel(self.shake_job)
            self.shake_job = None

    
    def destroy(self):
        self.stop_shake()
        self.win.destroy()
