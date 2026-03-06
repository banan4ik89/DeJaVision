import tkinter as tk
import math
import time
import os
import sys
import winsound
from PIL import Image, ImageTk
from fake_hack import start_fake_hack

FOV = math.pi / 3
NUM_RAYS = 320
MAX_DEPTH = 20
SPEED = 0.13
ROT_SPEED_KEYS = 0.08

TIME_LIMIT = 90

MINIMAP_SCALE = 14

MAP = [
    "#S#####################",
    "#......#..............#",
    "#......#.....#........#",
    "#..#####..#####....##8#",
    "#..#.........#........#",
    "#..#.#########.##.....#",
    "#..#.....K...#.....####",
    "#..#####.#####.##88#",
    "#....P.#.....#...8?#",
    "#......#.....#...88#",
    "#..######.#####.####",
    "#..#......#...#....####",
    "#..#..##..#...#.......#",
    "#.....##......#.......#",
    "#######################"
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
    gunshoot_frames_raw = load_gif_frames(resource_path("data/gunshoot.gif"))
    gunshoot_frames = [ImageTk.PhotoImage(f.resize((int(W*0.4), int(H*0.4)), Image.NEAREST)) for f in gunshoot_frames_raw]
    gunshoot_animating = False
    gun_img = None
    orb_textures = {
        "yellow": Image.open(resource_path("data/orbs/orb_yellow.png")).convert("RGBA"),
        "red": Image.open(resource_path("data/orbs/orb_red.png")).convert("RGBA"),
        "green": Image.open(resource_path("data/orbs/orb_green.png")).convert("RGBA"),
        "violet": Image.open(resource_path("data/orbs/orb_violet.png")).convert("RGBA"),
    }
    eyewall_raw = Image.open(resource_path("data/eyewall.png")).convert("RGBA")
    meto_frame_index = 0
    meto_x = meto_y = None
    bob_phase = 0
    bob_offset = 0
    is_moving = False
    eye_event_active = False
    eye_event_triggered = False
    eye_event_end_time = 0
    show_debug = False
    last_frame_time = time.time()
    fps = 0
    gun_img = None
    GUN_SCALE = 0.25
    GUN_OFFSET_Y = 0.15
    ammo = 17
    max_ammo = 17 
    keys = {
        "w": False,
        "s": False,
        "a": False,
        "d": False
    }

    reloading = False
    gunreload_frames_raw = load_gif_frames(resource_path("data/gunreload.gif"))
    gunreload_frames = [ImageTk.PhotoImage(f.resize((int(W*0.4), int(H*0.4)), Image.NEAREST)) for f in gunreload_frames_raw]

    eye_zone_x = 14.5
    eye_zone_y = 7
    eye_zone_radius = 0.6

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
    
        # === орб-черви ===
    import random

    orbworms = []
    colors = list(orb_textures.keys())

    for i in range(4):
        length = random.randint(7, 9)

        orbworms.append({
            "x": -5.0 - i * 3,  # стартуют в разных местах
            "base_y": 1.5 + i * 1.5,  # выше уровня игрока
            "speed": 0.06 + random.random() * 0.02,
            "length": length,
            "color": colors[i],
            "start_delay": random.random() * 2.5,  # разное время старта
            "started": False
        })

    last_mouse_x = W // 2
    win.event_generate("<Motion>", warp=True, x=last_mouse_x, y=H//2)
    
    def shoot_gun():
        nonlocal gunshoot_animating, gun_img, ammo, reloading

        if not has_gun or gunshoot_animating or reloading:
            return

        if ammo <= 0:
            reload_gun()
            return

        ammo -= 1
        gunshoot_animating = True

        def animate(index=0):
            nonlocal gunshoot_animating, gun_img

        # если анимация закончилась
            if index >= len(gunshoot_frames_raw):
                gunshoot_animating = False

            # вернуть обычный пистолет
                w, h = gun_img_raw.size
                new_w = int(W * GUN_SCALE)
                scale = new_w / w
                new_h = int(h * scale)

                frame = gun_img_raw.resize((new_w, new_h), Image.NEAREST)
                gun_img = ImageTk.PhotoImage(frame)
                return

            frame = gunshoot_frames_raw[index].resize(
                (
                    int(W * GUN_SCALE),
                    int(gun_img_raw.height * (W * GUN_SCALE) / gun_img_raw.width)
                ),
                Image.NEAREST
            )

            gun_img = ImageTk.PhotoImage(frame)

            canvas.create_image(
                W // 2,
                H - int(H * GUN_OFFSET_Y) - int(bob_offset / 2),
                image=gun_img
            )

            win.after(50, animate, index + 1)

        animate()
        
    def reload_gun():
        nonlocal reloading, gun_img, ammo

        if reloading:
            return

        reloading = True

        def animate(index=0):
            nonlocal reloading, gun_img, ammo

            if index >= len(gunreload_frames):
                reloading = False
                ammo = max_ammo
                return

            frame = gunreload_frames_raw[index].resize(
                (int(W*GUN_SCALE),
                int(gun_img_raw.height * (W*GUN_SCALE)/gun_img_raw.width)),
                Image.NEAREST
            )

            gun_img = ImageTk.PhotoImage(frame)

            canvas.create_image(
                W // 2,
                H - int(H * GUN_OFFSET_Y) - int(bob_offset / 2),
                image=gun_img
            )

            win.after(60, animate, index + 1)

        animate()
    
    def trigger_fake_hack():
        canvas.create_text(W//2, H//2 + 60,
                           fill="white",
                           font=("Consolas", 18),
                           text="INTRUDER CONFIRMED")
        win.after(300, lambda: (win.destroy(), start_fake_hack(root)))

    def is_wall(x, y):
        if x < 0 or y < 0 or int(y) >= len(MAP) or int(x) >= len(MAP[0]):
            return True

        cell = MAP[int(y)][int(x)]

    # обычная дверь
        if cell == "8":
            return not has_key

    # секретная стена
        if cell == "S":
            if has_key and has_gun:
                return False
            return True

        return cell == "#"
    last_step_time = 0
    def play_step():
        winsound.PlaySound(
            resource_path("data/step.wav"),
            winsound.SND_FILENAME | winsound.SND_ASYNC
    )
    
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
                if c == "S":
                    continue
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
        if dist < 0.3:
            return

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

        size = int(H / dist * scale)

        if size > H:
            size = H
        frame = frames[frame_index]
        scaled = frame.resize((size, size), Image.NEAREST)
        tk_img = ImageTk.PhotoImage(scaled)
        sprite_cache.append(tk_img)
        canvas.create_image(screen_x, H//2 + bob_offset, image=tk_img)

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
        nonlocal show_debug, last_frame_time, fps
        nonlocal bob_phase, bob_offset, is_moving
        nonlocal game_over, has_key, message
        nonlocal enemy_frame_index, key_frame_index, goal_frame_index
        nonlocal last_anim_time, meto_frame_index
        nonlocal dialog_active, dialog_step, meto_triggered
        nonlocal has_gun, gun_img
        nonlocal dialog_full_text, dialog_display_text
        nonlocal dialog_index, dialog_typing
        nonlocal eye_event_active, eye_event_triggered, eye_event_end_time
        nonlocal player_x, player_y, player_angle
        if game_over:
            return
        
        current_time = time.time()
        delta = current_time - last_frame_time
        last_frame_time = current_time
        
        # === движение Doom style ===

        move_x = 0
        move_y = 0

        if keys["w"]:
            move_x += math.cos(player_angle) * SPEED
            move_y += math.sin(player_angle) * SPEED
            is_moving = True

        if keys["s"]:
            move_x -= math.cos(player_angle) * SPEED
            move_y -= math.sin(player_angle) * SPEED
            is_moving = True

        nx = player_x + move_x
        ny = player_y + move_y

        if not is_wall(nx, ny):
            player_x = nx
            player_y = ny

# поворот
        if keys["a"]:
            player_angle -= ROT_SPEED_KEYS

        if keys["d"]:
            player_angle += ROT_SPEED_KEYS

        if delta > 0:
            fps = int(1 / delta)

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
        
        # === ПОТОЛОК ===
        if eye_event_active:
            sky_color = "black"
            floor_color = "black"
        else:
            sky_color = "#87CEEB"
            floor_color = "#555555"

        canvas.create_rectangle(0, 0, W, H//2, fill=sky_color, outline="")
        canvas.create_rectangle(0, H//2, W, H, fill=floor_color, outline="")
        
        
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
            
        # === покачивание камеры ===
        if is_moving:
            bob_phase += 0.3
            bob_offset = math.sin(bob_phase) * 16          # вертикальное покачивание
            bob_side_offset = math.sin(bob_phase*0.6) * 8 # горизонтальное покачивание
        else:
            bob_offset = 0
            bob_side_offset = 0
            
        if (not eye_event_triggered and
            math.hypot(player_x - eye_zone_x, player_y - eye_zone_y) < eye_zone_radius):

            eye_event_active = True
            eye_event_triggered = True
            eye_event_end_time = time.time() + 4

        if eye_event_active and time.time() > eye_event_end_time:
            eye_event_active = False
        
        nonlocal last_step_time

        if is_moving:
            if time.time() - last_step_time > 0.4:
                play_step()
                last_step_time = time.time()
            
                # === движение орб-червей ===
        current_time = time.time()

        for worm in orbworms:

            # задержка старта
            if not worm["started"]:
                if current_time > worm["start_delay"]:
                    worm["started"] = True
                else:
                    continue

            worm["x"] += worm["speed"]

            if worm["x"] > len(MAP[0]) + 5:
                worm["x"] = -5
                worm["start_delay"] = current_time + random.random() * 3
                worm["started"] = False

    # детект
        if math.hypot(player_x - enemy["x"], player_y - enemy["y"]) < 0.4:
            game_over = True
            canvas.create_text(W//2, H//2, fill="red",
                               font=("Consolas", 40), text="DETECTED")
            win.after(1200, trigger_fake_hack)
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

            if eye_event_active:

                slice_width = int(W/NUM_RAYS)+2
                slice_height = int(h)

    # вырезаем вертикальный кусок из eyeball текстуры
                tex_w, tex_h = eyewall_raw.size
                tex_x = int((r / NUM_RAYS) * tex_w)

                column = eyewall_raw.crop((tex_x, 0, tex_x+1, tex_h))
                column = column.resize((slice_width, slice_height), Image.NEAREST)

                tk_col = ImageTk.PhotoImage(column)
                sprite_cache.append(tk_col)

                canvas.create_image(
                    x + bob_side_offset,
                    H/2 + bob_offset,
                    image=tk_col
                )

            else:
                canvas.create_line(
                    x + bob_side_offset,
                    H/2 - h/2 + bob_offset,
                    x + bob_side_offset,
                    H/2 + h/2 + bob_offset,
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
            
                # === рендер орб-червей ===
                # === рендер орб-червей (лесенка) ===
        for worm in orbworms:
            if not worm["started"]:
                continue

            texture = orb_textures[worm["color"]]

            for i in range(worm["length"]):
                # ближе друг к другу
                segment_x = worm["x"] - i * 0.09

                pattern = [0, -0.25, -0.5, -0.25]  # форма ступеньки

                phase = int(worm["x"] * 8)    # скорость анимации
                offset = pattern[(i + phase) % len(pattern)]

                segment_y = worm["base_y"] + math.sin(i * 0.6 + worm["x"] * 4) * 0.3

                render_sprite(
                    [texture],
                    0,
                    segment_x,
                    segment_y,
                    0.42,
                    depth_buffer
                )

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
            fill="#ff0000",
            font=("Terminal", 16),
            text=f"W/S MOVE  A/D or MOUSE TURN  TIME {remaining}"
        )

        if remaining <= 0:
            game_over = True
            canvas.create_text(W//2, H//2, fill="red",
                               font=("Terminal", 40), text="ACCESS DENIED")
            win.after(1500, trigger_fake_hack)
            return
        # === секретный телепорт ===
        if MAP[int(player_y)][int(player_x)] == "S":
            if has_key and has_gun:
                win.destroy()
                try:
                    from secret_maze import start_secret_maze
                    start_secret_maze(root)
                except:
                    print("Secret maze not found")
                return
        
    # === победа ===
        if goal_x and int(player_x) == int(goal_x) and int(player_y) == int(goal_y):
            game_over = True
            canvas.create_text(W//2, H//2, fill="#00ff00",
                               font=("Terminal", 40), text="THEME UNLOCKED")
            win.after(1200, lambda: (win.destroy(), on_success()))
            return

        if message:
            canvas.create_text(W//2, 60,
                               fill="#00ff00",
                               font=("Terminal", 18),
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
                font=("Terminal", 20),
                width=W*0.75
            )
            # === оружие в руках ===
          
        if has_gun:
            nonlocal gun_img
            if gun_img is None:
        # Масштабируем пистолет
                w, h = gun_img_raw.size
                new_w = int(W * GUN_SCALE)
                scale_factor = new_w / w
                new_h = int(h * scale_factor)
                gun_img_resized = gun_img_raw.resize((new_w, new_h), Image.NEAREST)
                gun_img = ImageTk.PhotoImage(gun_img_resized)

    # Рисуем оружие внизу, с учётом покачивания камеры
            canvas.create_image(
                W // 2,
                H - int(H * GUN_OFFSET_Y) - int(bob_offset / 2),
                image=gun_img
            )
            canvas.create_text(
                W - 120,
                H - 40,
                fill="#00ff00",
                font=("Terminal", 18),
                text=f"{ammo}/{max_ammo}"
            )


        is_moving = False
        
        if show_debug:
            canvas.create_rectangle(
                10, 10, 320, 100,
                fill="black",
                outline="#00ff00"
            )

            canvas.create_text(
                20, 25,
                anchor="nw",
                fill="#00ff00",
                font=("Consolas", 14),
                text=f"FPS: {fps}"
            )

            canvas.create_text(
                20, 45,
                anchor="nw",
                fill="#00ff00",
                font=("Consolas", 14),
                text=f"X: {player_x:.2f}"
            )

            canvas.create_text(
                20, 65,
                anchor="nw",
                fill="#00ff00",
                font=("Consolas", 14),
                text=f"Y: {player_y:.2f}"
            )

            canvas.create_text(
                20, 85,
                anchor="nw",
                fill="#00ff00",
                font=("Consolas", 14),
                text=f"ANGLE: {player_angle:.2f}"
            )
            
            # === прицел ===
        cross_size = 8
        cross_color = "#00ff00"

        canvas.create_line(
            W//2 - cross_size, H//2,
            W//2 + cross_size, H//2,
            fill=cross_color,
            width=2
        )

        canvas.create_line(
            W//2, H//2 - cross_size,
            W//2, H//2 + cross_size,
            fill=cross_color,
            width=2
        )

        win.after(16, render)

    def key_press(e):
        nonlocal dialog_active, dialog_step
        nonlocal has_gun, game_over
        nonlocal show_debug

        key = e.keysym.lower()

    # === диалог ===
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

    # === управление (только запись состояния клавиш) ===
        if key in keys:
            keys[key] = True

    # === debug ===
        if e.char == "=":
            show_debug = not show_debug
            
    def key_release(e):
        key = e.keysym.lower()
        if key in keys:
            keys[key] = False

    win.bind("<KeyPress>", key_press)
    win.bind("<KeyRelease>", key_release)
    win.bind("<Button-1>", lambda e: shoot_gun())
    
    
    

    render()