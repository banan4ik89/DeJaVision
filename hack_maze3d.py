import tkinter as tk
import math
import time
import os
import sys
from PIL import Image, ImageTk
# === НАСТРОЙКИ ===
FOV = math.pi / 3
NUM_RAYS = 320
MAX_DEPTH = 20
SPEED = 0.13
ROT_SPEED_KEYS = 0.08
ROT_SPEED_MOUSE = 0.002
TIME_LIMIT = 90

MINIMAP_SCALE = 14

MAP = [
    "####################",
    "#......#...........#",
    "#......#.....#.....#",
    "#..####.#.#####.##8#",
    "#..#........###....#",
    "#..#.#######.#.##..#",
    "#..#.....K...#.....#",
    "#..#####.#####.##88#",
    "#....P.#.....#....?#",
    "#......#.....#.....#",
    "#..######.#####.####",
    "#..#......#...#....#",
    "#..#......#...#....#",
    "#......#.....#.....#",
    "####################"
]

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_gif_frames(path):
    gif = Image.open(path)
    frames = []

    try:
        while True:
            frame = gif.copy().convert("RGBA")
            frames.append(frame)
            gif.seek(len(frames))
    except EOFError:
        pass

    return frames


def start_hack_maze(root, hack_window=None, on_success=lambda: None):
    win = tk.Toplevel(root)
    win.attributes("-fullscreen", True)
    win.attributes("-topmost", True)
    win.configure(bg="black")

    canvas = tk.Canvas(win, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    W = win.winfo_screenwidth()
    H = win.winfo_screenheight()

    player_x, player_y, player_angle = 2.5, 2.5, 0
    start_time = time.time()
    game_over = False
    has_key = False
    message = ""
    enemy_frames = load_gif_frames(resource_path("data/patrol.gif"))
    key_frames = load_gif_frames(resource_path("data/key.gif"))
    goal_frames = load_gif_frames(resource_path("data/whatthe.gif"))
    meto_frames = load_gif_frames(resource_path("data/metopear.gif"))
    gun_img_raw = Image.open(resource_path("data/gun.png")).convert("RGBA")
    gun_img = None
    meto_frame_index = 0
    meto_x = meto_y = None

    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "P":
                meto_x, meto_y = x + 0.5, y + 0.5
    # === состояние диалога ===
    dialog_active = False
    dialog_step = 0

    dialog_full_text = ""
    dialog_display_text = ""
    dialog_index = 0
    dialog_typing = False

    meto_triggered = False
    has_gun = False
    enemy_frame_index = 0
    key_frame_index = 0
    goal_frame_index = 0

    last_anim_time = time.time()
    ANIM_SPEED = 0.15

    sprite_cache = []

    # === поиск цели ===
    goal_x = goal_y = None
    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "?":
                goal_x, goal_y = x + 0.5, y + 0.5

    # === враг ===
    enemy = {
        "x": 10.5,
        "y": 6.5,
        "dir": 1,
        "min_x": 8.5,
        "max_x": 14.5
    }

    last_mouse_x = W // 2
    win.event_generate("<Motion>", warp=True, x=last_mouse_x, y=H//2)

    def is_wall(x, y):
        if x < 0 or y < 0 or int(y) >= len(MAP) or int(x) >= len(MAP[0]):
            return True
        cell = MAP[int(y)][int(x)]
        if cell == "8":
            return not has_key
        return cell == "#"
    
    def start_dialog_text(text):
        nonlocal dialog_full_text, dialog_display_text
        nonlocal dialog_index, dialog_typing

        dialog_full_text = text
        dialog_display_text = ""
        dialog_index = 0
        dialog_typing = True

    def draw_minimap():
        for y, row in enumerate(MAP):
            for x, c in enumerate(row):
                color = "#002200"
                if c == "#":
                    color = "#006600"
                elif c == "8":
                    color = "#00ff00" if has_key else "#004400"
                elif c == "K":
                    color = "#00ff00"
                elif c == "?":
                    color = "#00ff00"

                canvas.create_rectangle(
                    x * MINIMAP_SCALE,
                    y * MINIMAP_SCALE,
                    (x+1)*MINIMAP_SCALE,
                    (y+1)*MINIMAP_SCALE,
                    fill=color,
                    outline="#003300"
                )

        px = player_x * MINIMAP_SCALE
        py = player_y * MINIMAP_SCALE

        canvas.create_oval(px-4, py-4, px+4, py+4, fill="#00ff00")
        canvas.create_line(
            px, py,
            px + math.cos(player_angle)*15,
            py + math.sin(player_angle)*15,
            fill="#00ff00"
        )
        
        
    
    
    
    
    sprite_cache = []

    def render_sprite(frames, frame_index, world_x, world_y, scale, depth_buffer):
        dx = world_x - player_x
        dy = world_y - player_y
        dist = math.hypot(dx, dy)

        angle = math.atan2(dy, dx) - player_angle
        
        while angle > math.pi: angle -= 2*math.pi
        while angle < -math.pi: angle += 2*math.pi

        if abs(angle) > FOV / 2:
            return

        screen_x = (angle + FOV/2) / FOV * W
        ray = int(screen_x * NUM_RAYS / W)
        if ray < 0: ray = 0
        if ray >= NUM_RAYS: ray = NUM_RAYS - 1

    # проверка глубины
        if depth_buffer[ray] < dist:
            return

        size = max(1, int(H / dist * scale))
        frame = frames[frame_index]
        scaled = frame.resize((size, size), Image.NEAREST)
        tk_img = ImageTk.PhotoImage(scaled)
        sprite_cache.append(tk_img)
        canvas.create_image(screen_x, H//2, image=tk_img)

    def render_key(depth_buffer):
        for y, row in enumerate(MAP):
            for x, cell in enumerate(row):
                if cell == "K":

                    key_x = x + 0.5
                    key_y = y + 0.5

                    dx = key_x - player_x
                    dy = key_y - player_y
                    dist = math.hypot(dx, dy)

                    angle = math.atan2(dy, dx) - player_angle
                    if abs(angle) > FOV / 2:
                        continue

                    screen_x = (angle + FOV/2) / FOV * W
                    ray = int(screen_x * NUM_RAYS / W)

                    if ray < 0 or ray >= NUM_RAYS:
                        continue

                    if depth_buffer[ray] < dist:
                        continue

                    size = int(H / dist * 0.5)

                    frame = key_frames[key_frame_index]
                    scaled = frame.resize((size, size), Image.NEAREST)
                    tk_img = ImageTk.PhotoImage(scaled)

                    sprite_cache.append(tk_img)

                    canvas.create_image(screen_x, H//2, image=tk_img)
                    
    def render_enemy(depth_buffer):
        dx = enemy["x"] - player_x
        dy = enemy["y"] - player_y
        dist = math.hypot(dx, dy)

        angle = math.atan2(dy, dx) - player_angle
        if abs(angle) > FOV / 2:
            return

        screen_x = (angle + FOV/2) / FOV * W
        ray = int(screen_x * NUM_RAYS / W)
        if ray < 0 or ray >= NUM_RAYS:
            return

        if depth_buffer[ray] < dist:
            return

        size = int(H / dist * 0.6)

        frame = enemy_frames[enemy_frame_index]
        scaled = frame.resize((size, size), Image.NEAREST)
        tk_img = ImageTk.PhotoImage(scaled)

        sprite_cache.append(tk_img)

        canvas.create_image(screen_x, H//2, image=tk_img)

    def render_goal(depth_buffer):
        if goal_x is None:
            return

        dx = goal_x - player_x
        dy = goal_y - player_y
        dist = math.hypot(dx, dy)

        angle = math.atan2(dy, dx) - player_angle
        if abs(angle) > FOV / 2:
            return

        screen_x = (angle + FOV/2) / FOV * W
        ray = int(screen_x * NUM_RAYS / W)
        if ray < 0 or ray >= NUM_RAYS:
            return

        if depth_buffer[ray] < dist:
            return

        size = int(H / dist * 0.7)

        frame = goal_frames[goal_frame_index]
        scaled = frame.resize((size, size), Image.NEAREST)
        tk_img = ImageTk.PhotoImage(scaled)

        sprite_cache.append(tk_img)

        canvas.create_image(screen_x, H//2, image=tk_img)
        
    def close_dialog():
        nonlocal dialog_active, dialog_full_text
        nonlocal dialog_display_text, dialog_index, dialog_typing

        dialog_active = False
        dialog_full_text = ""
        dialog_display_text = ""
        dialog_index = 0
        dialog_typing = False

    def render():
        nonlocal game_over, has_key, message
        nonlocal enemy_frame_index, key_frame_index, goal_frame_index
        nonlocal last_anim_time, meto_frame_index
        nonlocal dialog_active, dialog_step, meto_triggered
        nonlocal has_gun, gun_img
        nonlocal dialog_full_text, dialog_display_text
        nonlocal dialog_index, dialog_typing
        if game_over:
            return

        if time.time() - last_anim_time > ANIM_SPEED:
            enemy_frame_index = (enemy_frame_index + 1) % len(enemy_frames)
            key_frame_index = (key_frame_index + 1) % len(key_frames)
            goal_frame_index = (goal_frame_index + 1) % len(goal_frames)

        # === анимация Meto-Pear ===
            if meto_frames:
                meto_frame_index = (meto_frame_index + 1) % len(meto_frames)

            last_anim_time = time.time()

        canvas.delete("all")
        sprite_cache.clear()
        depth_buffer = []
        
        # === печать текста ===
        if dialog_active and dialog_typing:
            if dialog_index < len(dialog_full_text):
                dialog_display_text += dialog_full_text[dialog_index]
                dialog_index += 1
            else:
                dialog_typing = False

    # === движение врага ===
        enemy["x"] += 0.03 * enemy["dir"]
        if enemy["x"] < enemy["min_x"] or enemy["x"] > enemy["max_x"]:
            enemy["dir"] *= -1

    # детект
        if math.hypot(player_x - enemy["x"], player_y - enemy["y"]) < 0.4:
            game_over = True
            canvas.create_text(W//2, H//2, fill="red",
                               font=("Consolas", 40), text="DETECTED")
            win.after(1200, win.destroy)
            return

    # === рейкастинг ===
        for r in range(NUM_RAYS):
            a = player_angle - FOV/2 + FOV*r/NUM_RAYS
            d = 0
            while d < MAX_DEPTH:
                d += 0.05
                tx = player_x + math.cos(a)*d
                ty = player_y + math.sin(a)*d
                if is_wall(tx, ty):
                    break
            depth_buffer.append(d)

            h = min(H, H/(d+0.1))
            g = int(255/(1+d*d*0.12))
            x = r * W / NUM_RAYS

            canvas.create_line(
                x, H/2-h/2,
                x, H/2+h/2,
                fill=f"#00{g:02x}00",
                width=W/NUM_RAYS+1
            )

    # === спрайты ===
        render_sprite(enemy_frames, enemy_frame_index, enemy["x"], enemy["y"], 0.6, depth_buffer)

        for y, row in enumerate(MAP):
            for x, cell in enumerate(row):
                if cell == "K":
                    render_sprite(key_frames, key_frame_index, x+0.5, y+0.5, 0.5, depth_buffer)

        if goal_x:
            render_sprite(goal_frames, goal_frame_index, goal_x, goal_y, 0.7, depth_buffer)

    # === Meto-Pear рендер ===
        if meto_x:
            render_sprite(meto_frames, meto_frame_index, meto_x, meto_y, 0.6, depth_buffer)

        draw_minimap()
        
        # === запуск диалога Meto-Pear ===
        if (meto_x and
            not meto_triggered and
            math.hypot(player_x - meto_x, player_y - meto_y) < 0.8):

            dialog_active = True
            dialog_step = 0
            start_dialog_text(
                "Hello! Im Meto-pear!\n"
                "Do you like pears?\n\n"
                "1) Yes\n"
                "2) No"
            )
            meto_triggered = True

    # === ключ ===
        if MAP[int(player_y)][int(player_x)] == "K":
            has_key = True
            message = "KEY ACQUIRED"
            row = MAP[int(player_y)]
            MAP[int(player_y)] = row.replace("K", ".")

    # === таймер ===
        remaining = max(0, TIME_LIMIT - int(time.time() - start_time))
        canvas.create_text(
            W//2, 20,
            fill="#00ff00",
            font=("Consolas", 16),
            text=f"W/S MOVE  A/D or MOUSE TURN  TIME {remaining}"
        )

        if remaining <= 0:
            game_over = True
            canvas.create_text(W//2, H//2, fill="red",
                               font=("Consolas", 40), text="ACCESS DENIED")
            win.after(1500, win.destroy)
            return

    # === победа ===
        if goal_x and int(player_x) == int(goal_x) and int(player_y) == int(goal_y):
            game_over = True
            canvas.create_text(W//2, H//2, fill="#00ff00",
                               font=("Consolas", 40), text="THEME UNLOCKED")
            win.after(1200, lambda: (win.destroy(), on_success()))
            return

        if message:
            canvas.create_text(W//2, 60,
                               fill="#00ff00",
                               font=("Consolas", 18),
                               text=message)
        if dialog_active:
            canvas.create_rectangle(
                W*0.1, H*0.65,
                W*0.9, H*0.9,
                fill="black",
                outline="#00ff00",
                width=3
            )

            canvas.create_text(
                W//2,
                int(H*0.775),
                text=dialog_display_text + (" █" if dialog_typing else ""),
                fill="#00ff00",
                font=("Consolas", 20),
                width=W*0.75
            )
            # === оружие в руках ===
        if has_gun:
            nonlocal gun_img
            if gun_img is None:
                scaled = gun_img_raw.resize((int(W*0.4), int(H*0.4)), Image.NEAREST)
                gun_img = ImageTk.PhotoImage(scaled)

            canvas.create_image(
                W//2,
                H - int(H*0.25),
                image=gun_img
            )

        

        win.after(16, render)


    def on_mouse(e):
        nonlocal player_angle, last_mouse_x
        dx = e.x - last_mouse_x
        player_angle += dx * ROT_SPEED_MOUSE
        last_mouse_x = e.x


    def key_press(e):
        nonlocal player_x, player_y, player_angle
        nonlocal dialog_active, dialog_step
        nonlocal has_gun, game_over

        if dialog_active:

            if dialog_step == 0:
                if e.char == "1":
                    dialog_step = 1
                    start_dialog_text(
                        "What exactly do you mean?\n\n"
                        "1) Iloveyou\n"
                        "2) I love eating them\n"
                        "3) Idk"
                    )
                elif e.char == "2":
                    win.destroy()

            elif dialog_step == 1:
                if e.char == "1":
                    start_dialog_text(
                        "Aww... Thats cute.. wait I`l give you a present"
                    )
                    has_gun = True
                    win.after(2500, close_dialog)

                elif e.char == "2":
                    start_dialog_text(
                        "What?! do you love it when we die and suffer?"
                    )
                    game_over = True
                    win.after(2000, win.destroy)

                elif e.char == "3":
                    start_dialog_text("Um.. OK")
                    win.after(1500, close_dialog)

            return

    # === движение ===
        if e.keysym == "w":
            nx = player_x + SPEED * math.cos(player_angle)
            ny = player_y + SPEED * math.sin(player_angle)
            if not is_wall(nx, ny):
                player_x, player_y = nx, ny

        elif e.keysym == "s":
            nx = player_x - SPEED * math.cos(player_angle)
            ny = player_y - SPEED * math.sin(player_angle)
            if not is_wall(nx, ny):
                player_x, player_y = nx, ny

        elif e.keysym == "a":
            player_angle -= ROT_SPEED_KEYS

        elif e.keysym == "d":
            player_angle += ROT_SPEED_KEYS

        elif e.keysym == "Escape":
            win.destroy()


    win.bind("<Key>", key_press)
    win.bind("<Motion>", on_mouse)

    render()