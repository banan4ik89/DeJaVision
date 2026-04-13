# creeper_event.py
import tkinter as tk
import random

from utils import block_esc
from window_registry import register, unregister


class CreeperEvent:
    def __init__(self, root, trust_system):
        self.root = root
        self.trust_system = trust_system

        self.total_clicks = random.randint(8, 15)
        self.current_click = 0

        self.required_button = None  # "LMB" or "RMB"
        self.win = None
        self.label = None

        self._create_window()
        self._next_stage()

    # ===================== WINDOW =====================
    def _create_window(self):
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.configure(bg="black")
        self.win.attributes("-topmost", True)
        block_esc(self.win)

        w, h = 420, 140
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = random.randint(50, sw - w - 50)
        y = random.randint(80, sh - h - 80)
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        register(self.win)

        # TITLE BAR
        title = tk.Frame(self.win, bg="#C0C0C0", height=26)
        title.pack(fill="x")

        tk.Label(
            title,
            text="NOTCREEPER.EXE",
            bg="#C0C0C0",
            fg="black",
            font=("Terminal", 10)
        ).pack(side="left", padx=8)

        # CONTENT
        content = tk.Frame(
            self.win,
            bg="black",
            highlightbackground="white",
            highlightthickness=1
        )
        content.pack(expand=True, fill="both", padx=6, pady=6)

        self.label = tk.Label(
            content,
            text="",
            font=("Terminal", 15),
            bg="black",
            fg="red",
            justify="center",
            wraplength=380
        )
        self.label.pack(expand=True)

        # BINDINGS
        self.win.bind("<Button-1>", lambda e: self._handle_click("LMB"))
        self.win.bind("<Button-3>", lambda e: self._handle_click("RMB"))

    # ===================== STAGES =====================
    def _next_stage(self):
        if self.current_click >= self.total_clicks:
            self._success()
            return

        self.current_click += 1

        # random requirement
        if random.random() < 0.5:
            self.required_button = "LMB"
            color = "blue"
        else:
            self.required_button = "RMB"
            color = "red"

        self.label.config(
            fg=color,
            text="I’m not the creeper, catch me if you can!"
        )

        self._move_window()

    # ===================== INPUT =====================
    def _handle_click(self, button):
   
        self._move_window()

        if button == self.required_button:

            self.trust_system.add_trust(3)
            self._next_stage()
        else:

            self.trust_system.add_suspicion(3)

    # ===================== MOVE =====================
    def _move_window(self):
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()

        x = random.randint(30, sw - w - 30)
        y = random.randint(60, sh - h - 60)
        self.win.geometry(f"+{x}+{y}")

    # ===================== END =====================
    def _success(self):
        self.trust_system.add_trust(6)
        self.trust_system.add_suspicion(-8)

        self.label.config(
            fg="lime",
            text="You caught me."
        )

        self.win.after(800, self.destroy)

    def destroy(self):
        if self.win and self.win.winfo_exists():
            unregister(self.win)
            self.win.destroy()