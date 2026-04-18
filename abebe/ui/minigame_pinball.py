import tkinter as tk
import random
import os

from abebe.core.utils import block_esc, get_exe_dir
from abebe.core.config import DATA_DIR

ALASTOR_WIN_IMG = "alastor_win.png"
VOX_WIN_IMG = "vox_win.png"


def start_pinball(root):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)
    win.geometry("420x260+480+280")

    tk.Label(win, text="РџРРќР‘РћР›: РђР»Р°СЃС‚РѕСЂ vs Р’РѕРєСЃ",
             font=("Arial", 14, "bold")).pack(pady=10)

    tk.Label(win, text="Р’С‹Р±РµСЂРё СЃС‚РѕСЂРѕРЅСѓ").pack(pady=5)

    def choose(player):
        win.destroy()
        game_window(root, player)

    tk.Button(win, text="РРіСЂР°С‚СЊ Р·Р° РђР»Р°СЃС‚РѕСЂР°",
              width=20, command=lambda: choose("alastor")).pack(pady=4)

    tk.Button(win, text="РРіСЂР°С‚СЊ Р·Р° Р’РѕРєСЃР°",
              width=20, command=lambda: choose("vox")).pack(pady=4)


def game_window(root, player):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)
    speed_by_round = [2000, 1900, 1700, 1500, 1350]
    button_speed = speed_by_round[0]


    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    win.geometry(f"{sw}x{sh}+0+0")

    round_num = 0
    player_score = 0
    enemy_score = 0

    info = tk.Label(
        win,
        text="РџРћР™РњРђР™ РљРќРћРџРљРЈ!",
        font=("Arial", 24, "bold"),
        fg="red"
    )
    info.pack(pady=20)

    score_label = tk.Label(
        win,
        text="",
        font=("Consolas", 14)
    )
    score_label.pack()

    btn = tk.Button(
        win,
        text="РћРўР‘РРўР¬ РЁРђР ",
        font=("Arial", 14, "bold")
    )

    btn.place(x=100, y=100)

    timer_label = tk.Label(
        win,
        text="Р’СЂРµРјСЏ: 3.0",
        font=("Consolas", 14),
        fg="red"
    )
    timer_label.pack(pady=10)

    update_id = None
    time_left = 3.0

    def update_score():
        score_label.config(
            text=f"Р Р°СѓРЅРґ {round_num}/5 | РўС‹: {player_score} | РџСЂРѕС‚РёРІРЅРёРє: {enemy_score}"
        )

    def move_button():
        if not win.winfo_exists():
            return

        x = random.randint(0, sw - 160)
        y = random.randint(100, sh - 100)

        btn.place(x=x, y=y)
        btn.lift()  

        win.after(button_speed, move_button)


    def countdown():
        nonlocal time_left
        time_left -= 0.1
        timer_label.config(text=f"Р’СЂРµРјСЏ: {time_left:.1f}")
        if time_left > 0:
            win.after(100, countdown)
        else:
            lose_round()

    def start_round():
        nonlocal time_left
        time_left = 3.0

        btn.place(x=100, y=100)
        btn.lift()

        move_button()
        countdown()


    def win_round():
        nonlocal player_score, round_num
        player_score += random.randint(5, 15)
        round_num += 1
        next_round()

    def lose_round():
        nonlocal enemy_score, round_num
        enemy_score += random.randint(3, 10)
        round_num += 1
        next_round()

    def next_round():
        nonlocal button_speed

        btn.place_forget()
        update_score()

        if round_num >= 5:
            win.after(500, lambda: finish_game(
                root, win, player_score, enemy_score
            ))
        else:
            button_speed = speed_by_round[round_num]
            win.after(800, start_round)


    btn.config(command=win_round)

    update_score()
    start_round()



def finish_game(root, game_win, player_score, enemy_score):
    game_win.destroy()

    if player_score >= enemy_score:
        winner = "alastor"
    else:
        winner = "vox"

    show_result(root, winner)


def show_result(root, winner):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    block_esc(win)

    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    win.geometry(f"{sw}x{sh}+0+0")

    canvas = tk.Canvas(win, bg="black")
    canvas.pack(fill="both", expand=True)

    img_name = ALASTOR_WIN_IMG if winner == "alastor" else VOX_WIN_IMG
    img_path = os.path.join(get_exe_dir(), DATA_DIR, img_name)
    img = tk.PhotoImage(file=img_path)
    canvas.create_image(sw // 2, sh // 2, image=img)
    win.image = img

    win.after(4000, win.destroy)

