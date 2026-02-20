
import tkinter as tk
from window_registry import register
from window_registry import unregister

def make_draggable(win, bar):
    def start(e):
        win.x = e.x
        win.y = e.y

    def move(e):
        win.geometry(f"+{e.x_root - win.x}+{e.y_root - win.y}")

    bar.bind("<Button-1>", start)
    bar.bind("<B1-Motion>", move)



class TrustSystem:
    def __init__(self, root):
        self.trust = 50
        self.suspicion = 0
        self.max_value = 100

        
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg="black")
        self.win.transient(root)
        self.win.lift()
        self.win.attributes("-topmost", True)

        self.win.geometry("320x140+30+520")

        
        title_bar = tk.Frame(self.win, bg="#C0C0C0", height=26)
        title_bar.pack(fill="x", side="top")

        tk.Label(
            title_bar,
            text="TRUST_MONITOR.EXE",
            bg="#C0C0C0",
            fg="black",
            font=("Terminal", 10)
        ).pack(side="left", padx=6)

        make_draggable(self.win, title_bar)

        
        content = tk.Frame(
            self.win,
            bg="black",
            highlightbackground="lime",
            highlightthickness=2
        )
        content.pack(expand=True, fill="both", padx=6, pady=6)

        
        trust_row = tk.Frame(content, bg="black")
        trust_row.pack(fill="x", pady=6)

        tk.Label(
            trust_row,
            text="TRUST",
            fg="lime",
            bg="black",
            font=("Terminal", 10)
        ).pack(side="left")

        self.trust_percent = tk.Label(
            trust_row,
            text="50%",
            fg="lime",
            bg="black",
            font=("Consolas", 10)
        )
        self.trust_percent.pack(side="right")

        self.trust_bar = tk.Canvas(
            content,
            height=14,
            bg="#111",
            highlightthickness=1,
            highlightbackground="lime"
        )
        self.trust_bar.pack(fill="x")

        
        susp_row = tk.Frame(content, bg="black")
        susp_row.pack(fill="x", pady=(10, 6))

        tk.Label(
            susp_row,
            text="SUSPICION",
            fg="red",
            bg="black",
            font=("Terminal", 10)
        ).pack(side="left")

        self.susp_percent = tk.Label(
            susp_row,
            text="0%",
            fg="red",
            bg="black",
            font=("Consolas", 10)
        )
        self.susp_percent.pack(side="right")

        self.susp_bar = tk.Canvas(
            content,
            height=14,
            bg="#111",
            highlightthickness=1,
            highlightbackground="red"
        )
        self.susp_bar.pack(fill="x")
        register(self.win)
        self.update_ui()

    

    def add_trust(self, value):
        self.trust += value
        self.suspicion -= value // 2
        self._clamp()
        self.update_ui()

    def add_suspicion(self, value):
        self.suspicion += value
        self.trust -= value // 2
        self._clamp()
        self.update_ui()

    def is_suspicious(self):
        return self.suspicion >= 99

    

    def update_ui(self):
        w = 280 

        self.trust_bar.delete("all")
        self.susp_bar.delete("all")

        self.trust_bar.create_rectangle(
            0, 0, w * (self.trust / 100), 14,
            fill="lime", outline=""
        )

        self.susp_bar.create_rectangle(
            0, 0, w * (self.suspicion / 100), 14,
            fill="red", outline=""
        )

        self.trust_percent.config(text=f"{self.trust}%")
        self.susp_percent.config(text=f"{self.suspicion}%")

    
    
    def _clamp(self):
        self.trust = max(0, min(self.max_value, self.trust))
        self.suspicion = max(0, min(self.max_value, self.suspicion))

    def destroy(self):
        if self.win.winfo_exists():
            unregister(self.win)
            self.win.destroy()