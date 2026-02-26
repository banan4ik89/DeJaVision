# abebe_watcher.py
import tkinter as tk
import random
import os

from utils import get_exe_dir
from config import DATA_DIR
from abebe_confirm_exit import show_abebe_confirm
from window_registry import register, unregister

# ===================== СОСТОЯНИЯ =====================
STATE_NEUTRAL = "neutral"
STATE_HAPPY = "happy"
STATE_ANGRY = "angry"

# ===================== ФАЙЛЫ GIF =====================
GIFS = {
    STATE_NEUTRAL: "abebe_neutral.gif",
    STATE_HAPPY: "abebe_happy.gif",
    STATE_ANGRY: "abebe_angry.gif"
}

# ===================== ДИАЛОГИ =====================
DIALOGS = {
    STATE_NEUTRAL: [
        "I am watching.",
        "Continue.",
        "Enter the code.",
        "I see you."
    ],
    STATE_HAPPY: [
        "Good. You understand.",
        "You are doing well.",
        "Think about the system.",
        "You are one of us."
    ],
    STATE_ANGRY: [
        "Do not lie to me.",
        "You make me nervous.",
        "Your words are suspicious.",
        "I am losing patience."
    ]
}


# ===================== УТИЛИТА ПЕРЕТАСКИВАНИЯ =====================
def make_draggable(win, bar):
    def start(e):
        win.x = e.x
        win.y = e.y

    def move(e):
        win.geometry(f"+{e.x_root - win.x}+{e.y_root - win.y}")

    bar.bind("<Button-1>", start)
    bar.bind("<B1-Motion>", move)


# ===================== КЛАСС ABEBE =====================
class AbebeWatcher:
    def __init__(self, root, trust_system):
        self.root = root
        self.trust_system = trust_system
        self.used_words = set()

        self.state = STATE_NEUTRAL
        self.frames = []
        self.frame_index = 0
        self.shake_job = None
        
        self.setup_topics()

        self._create_window()
        self._create_text_window()
        self._load_gif()
        self._animate()
        
    def exit_game(self):
        from game_state import exit_game_confirmed
        exit_game_confirmed()

    # ===================== ОКНО GIF =====================
    def _create_window(self):
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.configure(bg="black")
        self.win.attributes("-topmost", True)
        self.win.geometry("300x300+30+100")


        # TITLE BAR
        self.title_bar = tk.Frame(self.win, bg="#C0C0C0", height=24)
        self.title_bar.pack(fill="x", side="top")

        tk.Label(
            self.title_bar,
            text="ABEBE_WATCHER.EXE",
            bg="#C0C0C0",
            fg="black",
            font=("Terminal", 10)
        ).pack(side="left", padx=6)

        self.close_btn = tk.Label(
            self.title_bar,
            text=" ✕ ",
            bg="#C0C0C0",
            fg="black",
            font=("Terminal", 10, "bold"),
            cursor="hand2"
        )
        self.close_btn.pack(side="right", padx=4)
        self.close_btn.bind(
            "<Button-1>",
            lambda e: show_abebe_confirm(
                self.root,
                on_yes=self.exit_game,
                on_no=lambda: None
            )
        )
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(bg="red", fg="white"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(bg="#C0C0C0", fg="black"))

        make_draggable(self.win, self.title_bar)

        # GIF
        self.gif_label = tk.Label(self.win, bg="black")
        self.gif_label.pack(pady=10)

    # ===================== ОТДЕЛЬНОЕ ОКНО ТЕКСТА =====================
    def _create_text_window(self):
        self.text_win = tk.Toplevel(self.root)
        self.text_win.overrideredirect(True)
        self.text_win.configure(bg="black")
        self.text_win.attributes("-topmost", True)
        self.text_win.geometry("380x120+370+100")\
        

        # TITLE BAR
        self.text_title = tk.Frame(self.text_win, bg="#C0C0C0", height=24)
        self.text_title.pack(fill="x", side="top")

        tk.Label(
            self.text_title,
            text="ABEBE DIALOG",
            bg="#C0C0C0",
            fg="black",
            font=("Terminal", 10)
        ).pack(side="left", padx=6)

        self.text_close = tk.Label(
            self.text_title,
            text=" ✕ ",
            bg="#C0C0C0",
            fg="black",
            font=("Terminal", 10, "bold"),
            cursor="hand2"
        )
        self.text_close.pack(side="right", padx=4)
        self.text_close.bind(
            "<Button-1>",
            lambda e: show_abebe_confirm(
                self.root,
                on_yes=self.exit_game,
                on_no=lambda: None
            )
        )
        self.text_close.bind("<Enter>", lambda e: self.text_close.config(bg="red", fg="white"))
        self.text_close.bind("<Leave>", lambda e: self.text_close.config(bg="#C0C0C0", fg="black"))

        make_draggable(self.text_win, self.text_title)

        # LABEL
        self.text_label = tk.Label(
            self.text_win,
            text="",
            fg="white",
            bg="black",
            font=("Terminal", 16),
            wraplength=360,
            justify="center"
        )
        self.text_label.pack(padx=10, pady=10, anchor="center")

    # ===================== ЗАГРУЗКА GIF =====================
    def _load_gif(self):
        self.frames.clear()
        self.frame_index = 0
        gif_name = GIFS[self.state]
        gif_path = os.path.join(get_exe_dir(), DATA_DIR, gif_name)
        i = 0
        while True:
            try:
                frame = tk.PhotoImage(file=gif_path, format=f"gif -index {i}")
                self.frames.append(frame)
                i += 1
            except:
                break

    # ===================== АНИМАЦИЯ =====================
    def _animate(self):
        if not self.win.winfo_exists():
            return
        if self.frames:
            self.gif_label.config(image=self.frames[self.frame_index])
            self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.win.after(90, self._animate)

    # ===================== ОБНОВЛЕНИЕ СОСТОЯНИЯ =====================
    def update_state(self):
        if self.trust_system.is_suspicious():
            new_state = STATE_ANGRY
        elif self.trust_system.trust >= 70:
            new_state = STATE_HAPPY
        else:
            new_state = STATE_NEUTRAL

        if new_state != self.state:
            self.state = new_state
            self._load_gif()
            self.show_dialog()

    # ===================== ПОКАЗ ДИАЛОГА =====================
    def show_dialog(self, custom_text=None):
        self._stop_shake()
        text = custom_text if custom_text else random.choice(DIALOGS[self.state])
        self.text_label.config(text=text)
        if self.state == STATE_ANGRY:
            self._start_shake()

    # ===================== ЭФФЕКТ ДРОЖАНИЯ =====================
    def _start_shake(self, intensity=4, speed=40):
        def jitter():
            dx = random.randint(-intensity, intensity)
            dy = random.randint(-intensity, intensity)
            self.text_label.place(
                x=190 + dx,
                y=60 + dy,
                anchor="center"
            )
            self.shake_job = self.text_label.after(speed, jitter)

        self.text_label.place(x=190, y=60, anchor="center")
        jitter()

    def _stop_shake(self):
        if self.shake_job:
            self.text_label.after_cancel(self.shake_job)
            self.shake_job = None
        self.text_label.place_forget()
        self.text_label.pack(padx=10, pady=10, anchor="center")

    # ===================== ВНЕШНИЙ ВЫЗОВ =====================
    def setup_topics(self):
        self.topics = [
    {
        "name": "OFFICE",
        "good": [
            "employee", "report", "manager", "meeting", "system",
            "project", "deadline", "schedule", "document", "office",
            "department", "colleague", "contract", "presentation", "email",
            "task", "budget", "plan", "analysis", "workflow",
            "conference", "briefing", "summary", "note", "record",
            "archive", "file", "printer", "desk", "workspace",
            "policy", "strategy", "proposal", "review", "feedback",
            "performance", "promotion", "salary", "agreement", "client",
            "coffee",
            "customer", "support", "service", "administrator", "director",
            "assistant", "supervisor", "team", "corporate", "headquarters",
            "branch", "finance", "accounting", "invoice", "receipt",
            "procurement", "resource", "human_resources", "recruitment",
            "training", "orientation", "memo", "notice", "announcement",
            "compliance", "standard", "guideline", "procedure", "operations",
            "logistics", "inventory", "supply", "shipment", "delivery",
            "consultation", "appointment", "agenda", "minutes", "coordination"
        ],
        "bad": [
            "hack", "virus", "steal", "bypass", "root",
            "leak", "corrupt", "sabotage", "fraud", "blackmail",
            "destroy", "tamper", "exploit", "spy", "breach",
            "theft", "bribe", "scam", "collapse", "shutdown",
            "crash", "error", "failure", "misconduct", "violation",
            "lawsuit", "conflict", "strike", "boycott", "embezzle",
            "manipulate", "forge", "fake", "plagiarize", "abuse",
            "misuse", "expose", "disrupt", "overload", "infect",
            "override", "intrusion", "threat", "danger", "crisis"
        ]
    },
    {
        "name": "SECURITY",
        "good": [
            "password", "access", "confirm", "login", "verify",
            "authentication", "authorize", "secure", "protect", "shield",
            "encryption", "firewall", "clearance", "defense", "monitor",
            "identity", "code", "token", "checkpoint", "approval",
            "biometric", "scan", "fingerprint", "retina", "pin",
            "passcode", "validation", "credential", "certificate", "protocol",
            "safety", "alarm", "camera", "surveillance", "guard",
            "control", "restriction", "permission", "inspection", "screening",
            "lock", "key", "barrier", "gate", "authorization",
            "backup", "recovery", "integrity", "confidential", "privacy",
            "compliance", "audit", "tracking", "logging", "verification"
        ],
        "bad": [
            "intruder", "break", "exploit", "attack", "override",
            "crack", "disable", "threat", "danger", "breach",
            "hack", "spy", "force", "bypass", "steal",
            "tamper", "compromise", "infiltrate", "intercept", "violate",
            "trespass", "snoop", "eavesdrop", "smuggle", "leak",
            "fraud", "phishing", "malware", "virus", "worm",
            "trojan", "backdoor", "hijack", "spoof", "ddos",
            "blackout", "shutdown", "collapse", "corrupt", "manipulate",
            "override_code", "bruteforce", "decrypt", "expose", "surveil"
        ]
    },
    {
        "name": "PSYCHO",
        "good": [
            "friend", "help", "trust", "calm", "safe",
            "support", "care", "listen", "understand", "peace",
            "comfort", "hope", "kindness", "relax", "stable",
            "protect", "guide", "assist", "heal", "balance",
            "empathy", "respect", "love", "loyal", "bond",
            "together", "secure", "patience", "clarity", "focus",
            "control", "confidence", "courage", "strength", "faith",
            "recovery", "therapy", "growth", "accept", "forgive",
            "harmony", "mindful", "breathe", "supportive", "compassion"
        ],
        "bad": [
            "kill", "escape", "fear", "panic", "hide",
            "rage", "chaos", "madness", "paranoia", "scream",
            "threat", "violence", "danger", "anxiety", "nightmare",
            "hallucination", "breakdown", "despair", "isolate", "shock",
            "terror", "phobia", "trauma", "aggression", "delusion",
            "obsession", "compulsion", "insanity", "unstable", "collapse",
            "cry", "stress", "pressure", "guilt", "shame",
            "selfharm", "confusion", "distress", "darkness", "void"
        ]
    },
    {
        "name": "HACKER",
        "good": [
            "terminal", "protocol", "database", "server", "network",
            "script", "console", "cipher", "encrypt", "decrypt",
            "firewall", "packet", "node", "host", "interface",
            "command", "binary", "compile", "process", "system",
            "kernel", "shell", "socket", "router", "switch",
            "infrastructure", "cloud", "virtual", "container", "repository",
            "version", "git", "commit", "branch", "merge",
            "algorithm", "debug", "optimize", "framework", "library",
            "module", "runtime", "thread", "api", "endpoint",
            "cache", "bandwidth", "latency", "signal", "data"
        ],
        "bad": [
            "breach", "inject", "payload", "malware", "spyware",
            "exploit", "ddos", "phishing", "backdoor", "trojan",
            "worm", "keylogger", "ransomware", "crack", "leak",
            "spoof", "sniff", "botnet", "rootkit", "hijack",
            "overflow", "bruteforce", "zero_day", "trojan_dropper",
            "credential_dump", "session_hijack", "sql_injection",
            "xss", "mitm", "recon", "scan", "probe",
            "intrusion", "exfiltrate", "decrypt_attack", "spoofing",
            "cloaking", "obfuscate", "payload_exec", "privilege_escalation"
        ]
    },
    {
        "name": "PERSONAL",
        "good": [
            "name", "birthday", "city", "family", "home",
            "friend", "school", "memory", "photo", "pet",
            "address", "hobby", "dream", "future", "story",
            "profile", "identity", "background", "contact", "origin",
            "relative", "parent", "sibling", "child", "neighbor",
            "apartment", "country", "language", "tradition", "culture",
            "passport", "document", "biography", "history", "nickname",
            "relationship", "partner", "celebration", "holiday", "gift",
            "achievement", "goal", "experience", "journey", "moment"
        ],
        "bad": [
            "unknown", "fake", "lie", "mask", "stranger",
            "hidden", "secret", "alias", "imposter", "deceive",
            "anonymous", "mystery", "false", "suspicious", "shadow",
            "disguise", "traitor", "unknown_id", "mislead", "cover",
            "identity_theft", "fraud", "scam", "manipulate", "expose",
            "blackmail", "spy", "stalker", "threat", "danger",
            "erase", "delete", "fabricate", "conceal", "deny",
            "betray", "intruder", "unauthorized", "compromise", "fake_profile"
        ]
    }
]



        self.current_topic = random.choice(self.topics)
        
        
    def get_current_theme(self):
        return self.current_topic["name"]

    def on_user_input(self, text):
        text = text.lower()

    # инициализация тем
        if not hasattr(self, "topics"):
            self.setup_topics()
            self.show_dialog(f"Topic selected: {self.current_topic['name']}")

    # хранилище использованных слов
        if not hasattr(self, "used_words"):
            self.used_words = set()

        good = self.current_topic["good"]
        bad = self.current_topic["bad"]

        words = set(text.split())

        new_words = []
        repeated_words = []

        for w in words:
            if w in self.used_words:
                repeated_words.append(w)
            else:
                self.used_words.add(w)
                new_words.append(w)

    # штраф за повтор
        if repeated_words:
            self.trust_system.add_suspicion(2 * len(repeated_words))
            self.show_dialog("Repeated words detected. Ignored.")

        if not new_words:
            self.update_state()
            return

    # ----------- УЛУЧШЕННАЯ ЛОГИКА СОВПАДЕНИЙ -----------

        def normalize(word):
        # множественное число
            if word.endswith("s") and len(word) > 3:
                word = word[:-1]

        # -ing
            if word.endswith("ing") and len(word) > 4:
                base = word[:-3]
                if not base.endswith("e"):
                    base += "e"
                return base

        # -ed
            if word.endswith("ed") and len(word) > 3:
                base = word[:-2]
                if not base.endswith("e"):
                    base += "e"
                return base

            return word

        def matches(word, word_list):
            word_norm = normalize(word)

            for base in word_list:
                base_norm = normalize(base)

            # точное совпадение
                if word == base:
                    return True

            # совпадение после нормализации
                if word_norm == base:
                    return True

                if word == base_norm:
                    return True

                if word_norm == base_norm:
                    return True

            # частичное совпадение
                if word.startswith(base) or base.startswith(word):
                    return True

            return False

        good_match = any(matches(w, good) for w in new_words)
        bad_match = any(matches(w, bad) for w in new_words)

        if good_match:
            self.trust_system.add_trust(10)
            self.show_dialog("Accepted.")

        elif bad_match:
            self.trust_system.add_suspicion(15)
            self.show_dialog("Suspicious input detected.")

        else:
            self.trust_system.add_suspicion(4)
            self.show_dialog("Unknown response.")

        self.update_state()
    
    

    # ===================== ЗАКРЫТИЕ =====================
    def destroy(self):
        if self.win.winfo_exists():
            self.win.destroy()
        if self.text_win.winfo_exists():
            self.text_win.destroy()
            
