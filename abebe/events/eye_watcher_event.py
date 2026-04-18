import tkinter as tk
from abebe.core.utils import block_esc, get_resource_path


class EyeWatcherEvent:
    def __init__(
        self,
        root,
        trust_system,
        is_password_visible_cb,
        on_finish,
        watch_time=5000
    ):
        self.root = root
        self.trust = trust_system
        self.is_password_visible = is_password_visible_cb
        self.on_finish = on_finish
        self.watch_time = watch_time

        self.active = True
        self.current_frames = []
        self.anim_job = None

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        block_esc(self.win)

        self.win.configure(bg="black")
        self.win.geometry("240x240+600+220")

        self.label = tk.Label(self.win, bg="black")
        self.label.pack(expand=True)

        self.play_state("eye_watch.gif")

        # вЏ± Р·Р°РїСѓСЃРєР°РµРј РѕС‚СЃС‡С‘С‚
        self.win.after(self.watch_time, self.resolve_event)

    # ================= GIF =================

    def load_gif(self, name):
        path = get_resource_path("data", "app", "abebe", name)
        frames = []
        i = 0
        while True:
            try:
                frames.append(
                    tk.PhotoImage(file=path, format=f"gif -index {i}")
                )
                i += 1
            except:
                break
        return frames

    def play_gif(self, frames, delay=80):
        if self.anim_job:
            self.win.after_cancel(self.anim_job)

        self.current_frames = frames

        def animate(i=0):
            if not self.active:
                return
            self.label.config(image=frames[i])
            self.anim_job = self.win.after(
                delay, animate, (i + 1) % len(frames)
            )

        animate()

    def play_state(self, gif_name):
        frames = self.load_gif(gif_name)
        self.play_gif(frames)

    # ================= LOGIC =================

    def resolve_event(self):
        if not self.active:
            return

        if self.is_password_visible():
        # вќЊ РёРіСЂРѕРє РЅРµ СЃРєСЂС‹Р» РїР°СЂРѕР»СЊ
            self.trust.add_suspicion(20)

            self.play_state("eye_happy.gif")
            self.win.after(3000, self.finish)
        else:
        # вњ… РёРіСЂРѕРє СѓСЃРїРµР» СЃРєСЂС‹С‚СЊ
            self.play_state("eye_sad.gif")
            self.win.after(3000, self.finish)


    def finish(self):
        self.active = False
        if self.anim_job:
            self.win.after_cancel(self.anim_job)
        self.win.destroy()
        self.on_finish()

