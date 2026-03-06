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
ROT_SPEED = 0.08

MINIMAP_SCALE = 14

MAP = [
".........####...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
".........#..#...........",
"##########..############",
"#........#..W.T........#",
"#........####TT........#",
"#........#.............#",
"#........#.........E...#",
"#........#.............#",
"#........#.............#",
"#........#.............#",
"#........#.............#",
"########################"
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

def is_wall(x,y):

    if x < 0 or y < 0:
        return True

    if int(y) >= len(MAP):
        return True

    if int(x) >= len(MAP[0]):
        return True

    cell = MAP[int(y)][int(x)]

    if cell == "#":
        return True

    if cell == "W" and trigger_activated:
        return True

    return False


def start_secret_maze(root):

    win = tk.Toplevel(root)
    win.attributes("-fullscreen", True)
    win.attributes("-topmost", True)
    win.configure(bg="black")

    canvas = tk.Canvas(win, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    W = win.winfo_screenwidth()
    H = win.winfo_screenheight()

    player_x = 10.5
    player_y = 2.5
    player_angle = 0
    
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
    global trigger_activated
    trigger_activated = False
    player_frozen = False
    freeze_end_time = 0
    sprite_resize_cache = {}
    reloading = False
    gunreload_frames_raw = load_gif_frames(resource_path("data/gunreload.gif"))
    gunreload_frames = [ImageTk.PhotoImage(f.resize((int(W*0.4), int(H*0.4)), Image.NEAREST)) for f in gunreload_frames_raw]

    keys = {"w":False,"s":False,"a":False,"d":False}

    gun_raw = Image.open("data/gun.png").convert("RGBA")

    gun_img = None
    
    ammo = 17
    max_ammo = 17
    shooting = False
    reloading = False
    has_gun = True

    bob_phase = 0
    bob_offset = 0

    last_frame_time = time.time()

    sprite_cache = []
    
      # примерные, можешь менять
    enemy_state = "sitting"  # состояния: sitting, getting_up, walking
    enemy_frame_index = 0
    enemy_timer_start = None

    enemy_gifs = {
        "sitting": load_gif_frames(resource_path("data/gifs/cicada/cicadasitting.gif")),
        "getting_up": load_gif_frames(resource_path("data/gifs/cicada/cicadagettingup.gif")),
        "walking": load_gif_frames(resource_path("data/gifs/cicada/cicadawalking.gif"))
    }
    enemy_img = None
    enemy_timer_start = None   # <-- здесь
    enemy_img = None
    enemy_x = None
    enemy_y = None

    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "E":
                enemy_x = x + 0.5
                enemy_y = y + 0.5
                break
        if enemy_x is not None:
            break

    def draw_minimap():

        for y,row in enumerate(MAP):
            for x,c in enumerate(row):

                color = "#002200"

                if c == "#":
                    color = "#006600"

                canvas.create_rectangle(
                    x*MINIMAP_SCALE,
                    y*MINIMAP_SCALE,
                    (x+1)*MINIMAP_SCALE,
                    (y+1)*MINIMAP_SCALE,
                    fill=color,
                    outline="#003300"
                )

        px = player_x * MINIMAP_SCALE
        py = player_y * MINIMAP_SCALE

        canvas.create_oval(px-4,py-4,px+4,py+4,fill="#00ff00")

        canvas.create_line(
            px,
            py,
            px+math.cos(player_angle)*15,
            py+math.sin(player_angle)*15,
            fill="#00ff00"
        )


    def render():

        nonlocal player_x,player_y,player_angle
        nonlocal bob_phase,bob_offset
        nonlocal last_frame_time
        nonlocal gun_img
        nonlocal player_frozen, freeze_end_time
        global trigger_activated
        
        
        


        now = time.time()
        t = time.time()
        delta = now - last_frame_time
        last_frame_time = now

        move_x = 0
        move_y = 0
        nonlocal enemy_x, enemy_y, enemy_state, enemy_frame_index, enemy_timer_start, enemy_img

# запускаем таймер 47 секунд после входа в триггер
        if trigger_activated and enemy_state == "sitting" and enemy_timer_start is None:
            enemy_timer_start = time.time()

# проверяем, прошло ли 47 секунд, чтобы начать getting_up
        if enemy_timer_start:
            elapsed = time.time() - enemy_timer_start
            if elapsed >= 47 and enemy_state == "sitting":
                enemy_state = "getting_up"
                enemy_frame_index = 0

# движение за игроком, если уже walking
        if enemy_state == "walking":
            dx = player_x - enemy_x
            dy = player_y - enemy_y
            dist = math.hypot(dx, dy)
            if dist > 0.2:  # дистанция, чтобы не наседал слишком близко
                enemy_x += (dx / dist) * SPEED * 0.5  # враг медленнее игрока
                enemy_y += (dy / dist) * SPEED * 0.5

# рисуем врага
        
        
        if trigger_activated and enemy_state == "sitting" and enemy_timer_start is None:
            enemy_timer_start = time.time()

        if enemy_timer_start:
            elapsed = time.time() - enemy_timer_start
            if elapsed >= 47 and enemy_state == "sitting":
                enemy_state = "getting_up"
                enemy_frame_index = 0

        moving = False
        if player_frozen:
            if time.time() > freeze_end_time:
                player_frozen = False

        if not player_frozen:

            if keys["w"]:
                move_x += math.cos(player_angle)*SPEED
                move_y += math.sin(player_angle)*SPEED
                moving = True

            if keys["s"]:
                move_x -= math.cos(player_angle)*SPEED
                move_y -= math.sin(player_angle)*SPEED
                moving = True

        nx = player_x + move_x
        ny = player_y + move_y

        if not is_wall(nx,ny):
            player_x = nx
            player_y = ny

        if keys["a"]:
            player_angle -= ROT_SPEED

        if keys["d"]:
            player_angle += ROT_SPEED

        if moving:
            bob_phase += 0.3
            bob_offset = math.sin(bob_phase)*16
        else:
            bob_offset = 0
            
        cell = MAP[int(player_y)][int(player_x)]

        if cell == "T" and not trigger_activated:
            trigger_activated = True
            player_frozen = True
            freeze_end_time = time.time() + 47

        canvas.delete("all")
        sprite_cache.clear()
        depth_buffer = []

        canvas.create_rectangle(0,0,W,H//2,fill="#87CEEB",outline="")
        canvas.create_rectangle(0,H//2,W,H,fill="#555555",outline="")

        for r in range(NUM_RAYS):

            ray_angle = player_angle - FOV/2 + FOV*r/NUM_RAYS

            depth = 0

            while depth < MAX_DEPTH:

                depth += 0.05

                tx = player_x + math.cos(ray_angle)*depth
                ty = player_y + math.sin(ray_angle)*depth

                if is_wall(tx,ty):
                    break

            depth_buffer.append(depth)

            wall_height = min(H, H/(depth+0.1))

            pulse = math.sin(t*2 + r*0.05) * 15

            shade = int(90/(1+depth*depth*0.1) + pulse)

            shade = max(30, min(120, shade))

            x = r*W/NUM_RAYS
            shade = int(120/(1+depth*depth*0.1))
            shade = max(40, shade)

            canvas.create_line(
                x,
                H/2-wall_height/2 + bob_offset,
                x,
                H/2+wall_height/2 + bob_offset,

                fill=f"#{shade:02x}{shade:02x}{shade:02x}",
                width=W/NUM_RAYS+1
            )
            
        frames = enemy_gifs[enemy_state]

# увеличение индекса кадра
        enemy_frame_index += 1

# проверка на конец анимации
        if enemy_frame_index >= len(frames):
            if enemy_state == "getting_up":
                enemy_state = "walking"
                enemy_frame_index = 0
            else:
                enemy_frame_index = 0  # зацикливаем для других состояний

# кадр спрайта
        frame = frames[enemy_frame_index]

# правильное масштабирование
        sprite_width = int(W * 0.1)  # ширина на экране
        scale = sprite_width / frame.width
        sprite_height = int(frame.height * scale)  # сохраняем пропорции

        render_sprite(
            frames,
            enemy_frame_index,
            enemy_x,
            enemy_y,
            scale,          # используем масштаб
            depth_buffer
        )

        # draw_minimap()
        

        if gun_img is None:

            w,h = gun_raw.size

            new_w = int(W*0.25)

            scale = new_w/w

            new_h = int(h*scale)

            gun = gun_raw.resize((new_w,new_h),Image.NEAREST)

            gun_img = ImageTk.PhotoImage(gun)

        canvas.create_image(
            W//2,
            H - int(H*0.15) - int(bob_offset/2),
            image=gun_img
        )

        canvas.create_text(
            W//2,
            20,
            fill="#ff0000",
            font=("Terminal",16),
            text="W/S MOVE   A/D TURN"
        )
        canvas.create_text(
            W-120,
            40,
            fill="white",
            font=("Terminal",16),
            text=f"AMMO {ammo}/{max_ammo}"
        )

        win.after(16,render)
    
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
        
    
    def render_sprite(frames, frame_index, sx, sy, scale, depth_buffer):
        dx = sx - player_x
        dy = sy - player_y

        dist = math.hypot(dx, dy)

        angle = math.atan2(dy, dx) - player_angle

        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi

        if abs(angle) > FOV / 2:
            return

        screen_x = (angle + FOV / 2) / FOV * W

        frame = frames[frame_index]

        sprite_height = int(H / (dist + 0.0001) * scale)
        sprite_height = min(sprite_height, H * 2)

        sprite_width = int(sprite_height * frame.width / frame.height)

    # округляем размер чтобы уменьшить количество resize
        key = (frame_index, sprite_width, sprite_height)

        if key not in sprite_resize_cache:
            img = frame.resize((sprite_width, sprite_height), Image.NEAREST)
            sprite_resize_cache[key] = ImageTk.PhotoImage(img)

        img = sprite_resize_cache[key]

        x1 = screen_x - sprite_width // 2
        y1 = H // 2 - sprite_height // 2 + bob_offset

        ray = int(screen_x / W * NUM_RAYS)

        if 0 <= ray < len(depth_buffer):
            if depth_buffer[ray] < dist:
                return

        canvas.create_image(x1, y1, image=img, anchor="nw")

        sprite_cache.append(img)
        
    def open_debug():

        dbg = tk.Toplevel(win)
        dbg.title("DEBUG")

        tk.Label(dbg, text="Secret Maze Debug").pack()

        tk.Label(dbg, text=f"Ammo: {ammo}").pack()

        tk.Button(
            dbg,
            text="Give Ammo",
            command=lambda: give_ammo()
        ).pack()

    def give_ammo():
        nonlocal ammo
        ammo = max_ammo

    def key_down(e):

        k = e.keysym.lower()

        if k in keys:
            keys[k] = True
        if k == "r":
            reload_gun()

        if k == "=":
            open_debug()


    def key_up(e):

        k = e.keysym.lower()

        if k in keys:
            keys[k] = False


    win.bind("<KeyPress>",key_down)
    win.bind("<KeyRelease>",key_up)
    win.bind("<Button-1>", lambda e: shoot_gun())

    render()