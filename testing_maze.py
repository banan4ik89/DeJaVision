import tkinter as tk
import math
import time
import os
import random
import sys
import winsound
from PIL import Image, ImageTk
from fake_hack import start_fake_hack

FOV = math.pi / 3
NUM_RAYS = 80
MAX_DEPTH = 10
MAX_RENDER_DIST = 25


SPEED = 0.42
ROT_SPEED = 0.11

MINIMAP_SCALE = 14

MAP = [
".........###............",
"##########P#############",
"#......................#",
"#......................#",
"#......................#",
"#..................E...#",
"#......................#",
"#......................#",
"#......................#",
"#......................#",
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

    return False


def start_testing_maze(root):

    win = tk.Toplevel(root)
    win.attributes("-fullscreen", True)
    win.attributes("-topmost", True)
    win.configure(bg="black")

    canvas = tk.Canvas(win, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    intro_active = True
    intro_text = "CASE ??? /// TESTING"
    intro_index = 0
    intro_start = time.time()
    pixel_glitch = True
    intro_duration = 6
    pixel_size = 28
    pixel_grid = []
    random.shuffle(pixel_grid)
    pixel_grid = pixel_grid[:1200]
    text_alpha = 255
    fade_started = False

    hud_start_time = time.time()

    W = win.winfo_screenwidth()
    H = win.winfo_screenheight()

    player_x = 10.5
    player_y = 2.5
    player_z = 0.0
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
    hud_raw = Image.open(resource_path("data/hud.png")).convert("RGBA")

    HUD_SCALE_X = 3.8   # шире
    HUD_SCALE_Y = 3.2   # чуть ниже

    hud_w = int(128 * HUD_SCALE_X)
    hud_h = int(48 * HUD_SCALE_Y)

    hud_img = ImageTk.PhotoImage(
        hud_raw.resize((hud_w, hud_h), Image.NEAREST)
    )
    game_start_time = time.time()
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
    fps_display = 0
    fps_timer = 0
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
    selected_slot = 1
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
    
    
    enemy_state = "sitting"
    enemy_frame_index = 0
    enemy_timer_start = None
    gunitem_raw = Image.open(resource_path("data/gunitem.png")).convert("RGBA")
    gunitem_raw = gunitem_raw.resize((40,40), Image.NEAREST)
    gunitem_img = ImageTk.PhotoImage(gunitem_raw)

    enemy_gifs = {
        "sitting": load_gif_frames(resource_path("data/gifs/cicada/cicadasitting.gif")),
        "getting_up": load_gif_frames(resource_path("data/gifs/cicada/cicadagettingup.gif")),
        "walking": load_gif_frames(resource_path("data/gifs/cicada/cicadawalking.gif"))
    }
    enemy_img = None
    enemy_timer_start = None 
    enemy_img = None
    enemy_x = None
    enemy_y = None
    enemy_health = 100
    enemy_max_health = 100
    wall_tex = Image.open(resource_path("data/prison.png")).convert("RGB")
    flash_timer = 0 
    flash_duration = 0.08 

    TEX_SIZE = 32
    wall_tex = wall_tex.resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)

    texture_column_cache = {}
    
    for x in range(0, W, pixel_size):
        for y in range(0, H, pixel_size):
            pixel_grid.append([x, y, True])

    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "E":
                enemy_x = x + 0.5
                enemy_y = y + 0.5
                break
        if enemy_x is not None:
            break
        
    lights = []

    for y,row in enumerate(MAP):
        for x,c in enumerate(row):
            if c == "L":
                lights.append((x+0.5,y+0.5))
                
    light_states = {}
    light_timers = {}

    for lx,ly in lights:
        light_states[(lx,ly)] = True
        light_timers[(lx,ly)] = time.time()

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
        
    def draw_pixel_decode():

        nonlocal pixel_grid, intro_active

        progress = (time.time() - intro_start) / intro_duration

        if progress >= 1:
            intro_active = False
            return

        for p in pixel_grid:

            x, y, active = p

        
            if active and random.random() < progress * 0.2:
                p[2] = False

            if p[2]:

                shade = random.randint(0, 120)

                canvas.create_rectangle(
                    x, y,
                    x + pixel_size,
                    y + pixel_size,
                    fill=f"#{shade:02x}{shade:02x}{shade:02x}",
                    outline=""
                )
    
    
            
    def draw_intro_text():
        nonlocal intro_index, intro_active, fade_started

        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@!?$%"

        elapsed = time.time() - intro_start

        # появление текста
        if intro_index < len(intro_text):
            intro_index += 1

        shown = intro_text[:intro_index]

        # запускаем fade после полной печати
        if intro_index >= len(intro_text):
            fade_started = True

        if fade_started:
            fade_time = elapsed - 2  # небольшая пауза перед исчезновением
            fade_time = max(0, fade_time)

            # 🔥 СКОЛЬКО СИМВОЛОВ ОСТАЁТСЯ
            remain_ratio = max(0, 1 - fade_time * 0.25)
            visible_len = int(len(shown) * remain_ratio)

            shown = shown[:visible_len]

            # 🔥 мягкий глитч
            glitched = ""
            for c in shown:
                if random.random() < 0.15 * fade_time:
                    glitched += random.choice(chars)
                else:
                    glitched += c

            shown = glitched

            # 🔥 плавное уменьшение размера
            size = int(42 * remain_ratio)

            if size <= 6 or visible_len <= 0:
                intro_active = False
                return

        else:
            size = 42

        canvas.create_text(
            W//2,
            H//2,
            text=shown,
            fill="#00ff88",
            font=("Terminal", size)
        )


    def render():
        nonlocal flash_timer, flash_duration
        nonlocal player_x,player_y,player_z,player_angle
        nonlocal bob_phase,bob_offset
        nonlocal last_frame_time
        nonlocal gun_img
        nonlocal fps_timer, fps_display
        
        
        


        now = time.time()
        t = time.time()
        delta = now - last_frame_time
        last_frame_time = now
        if delta > 0:
            fps = int(1 / delta)
            
        fps_timer += delta
            
        if fps_timer > 0.2:
            fps_display = int(fps)
            fps_timer = 0
        texture_column_cache.clear()

        move_x = 0
        move_y = 0
        
        nonlocal enemy_x, enemy_y, enemy_state, enemy_frame_index, enemy_timer_start, enemy_img
        
        

        for key in light_states:

            if time.time() - light_timers[key] > random.uniform(0.05,0.3):

                light_timers[key] = time.time()

                if random.random() < 0.2:
                    light_states[key] = not light_states[key]

        moving = False

        nx = player_x + move_x
        ny = player_y + move_y
        cell = MAP[int(ny)][int(nx)]

        if cell != "#":
            player_x = nx
            player_y = ny

            if cell == "L":
                player_z += 0.2 * delta
                player_z = min(player_z, 1.0)  # ограничение (чтобы не улетал в космос)
            else:
                player_z -= 0.3 * delta
                if player_z < 0:
                    player_z = 0

            steps = max(1, int(player_z * 5))

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


        canvas.delete("all")
        
        # --- РЕНДЕР ПОЛА И ПОТОЛКА ---  

# Настройки
        ceiling_base = 120
        floor_base = 120
        num_steps = 60  # чем больше, тем плавнее градиент

        # Потолок (ближе ярче, дальше темнее)
        for i in range(num_steps):
            y1 = int(i * (H//2) / num_steps)
            y2 = int((i+1) * (H//2) / num_steps)
            dist_ratio = i / num_steps
            fog = 1 - dist_ratio  # инвертируем для потолка
            shade = int(ceiling_base * fog)
            shade = max(15, min(shade, 220))
            color = f"#{shade:02x}{shade:02x}{shade:02x}"
            canvas.create_rectangle(0, y1, W, y2, fill=color, outline="")

        # Пол (ближе светлее, дальше темнее)
        for i in range(num_steps):
            y1 = H//2 + int(i * (H//2) / num_steps)
            y2 = H//2 + int((i+1) * (H//2) / num_steps)

            dist_ratio = i / num_steps  # 0 = далеко, 1 = близко
            fog = dist_ratio            # теперь всё логично

            shade = int(floor_base * fog)
            shade = max(15, min(shade, 220))

            color = f"#{shade:02x}{shade:02x}{shade:02x}"

            canvas.create_rectangle(0, y1, W, y2, fill=color, outline="")
        
        sprite_cache.clear()
        depth_buffer = []

        # --- ПОТОЛОК ---
        # --- ПОТОЛОК ---
        
        
        for r in range(NUM_RAYS):

            ray_angle = player_angle - FOV/2 + FOV*r/NUM_RAYS

            # позиция в сетке
            map_x = int(player_x)
            map_y = int(player_y)

            ray_dir_x = math.cos(ray_angle)
            ray_dir_y = math.sin(ray_angle)

            delta_dist_x = abs(1 / ray_dir_x) if ray_dir_x != 0 else 1e30
            delta_dist_y = abs(1 / ray_dir_y) if ray_dir_y != 0 else 1e30

# шаг
            if ray_dir_x < 0:
                step_x = -1
                side_dist_x = (player_x - map_x) * delta_dist_x
            else:
                step_x = 1
                side_dist_x = (map_x + 1.0 - player_x) * delta_dist_x

            if ray_dir_y < 0:
                step_y = -1
                side_dist_y = (player_y - map_y) * delta_dist_y
            else:
                step_y = 1
                side_dist_y = (map_y + 1.0 - player_y) * delta_dist_y

            hit = False
            side = 0
            steps = 0

            while not hit and steps < 50:
                steps += 1

                if side_dist_x < side_dist_y:
                    side_dist_x += delta_dist_x
                    map_x += step_x
                    side = 0
                else:
                    side_dist_y += delta_dist_y
                    map_y += step_y
                    side = 1

                if is_wall(map_x, map_y):
                    hit = True

# расстояние до стены
           # расстояние до стены
            if side == 0:
                depth = (map_x - player_x + (1 - step_x) / 2) / ray_dir_x
            else:
                depth = (map_y - player_y + (1 - step_y) / 2) / ray_dir_y

            # корректируем угол для эффекта fish-eye
            depth *= math.cos(ray_angle - player_angle)

            # новая проверка: если стена дальше MAX_RENDER_DIST — пропускаем
            if depth > MAX_RENDER_DIST:
                depth_buffer.append(None)
                continue

            depth_buffer.append(depth)

# точка удара
            hit_x = player_x + ray_dir_x * depth
            hit_y = player_y + ray_dir_y * depth
            if depth is None:
                depth_buffer.append(None)
                continue

            # вычисляем угол до стены
            angle_from_player = math.atan2(hit_y - player_y, hit_x - player_x) - player_angle
            while angle_from_player > math.pi:
                angle_from_player -= 2 * math.pi
            while angle_from_player < -math.pi:
                angle_from_player += 2 * math.pi

            # если стена сзади игрока — пропускаем
            if abs(angle_from_player) > FOV / 2:
                depth_buffer.append(None)
                continue
            light_boost = 0

            for lx,ly in lights:

                if not light_states[(lx,ly)]:
                    continue

                dist_light = math.hypot(hit_x - lx, hit_y - ly)

                if dist_light < 4:

                    light_boost += (1/(dist_light+0.2)) * 120
            
            

            wall_height = min(H, H/(depth+0.1))

            pulse = math.sin(t*2 + r*0.05) * 15

            shade = int(90/(1+depth*depth*0.1) + pulse)

            shade = max(30, min(120, shade))
            
            if flash_timer > 0:
                shade = min(255, shade + int(100 * (flash_timer / flash_duration)))  # увеличиваем яркость
                flash_timer -= delta  # уменьшаем таймер

            

            x = r*W/NUM_RAYS
            # туман (чем дальше стена — тем темнее)
            FOG_DIST = 7

            fog = min((depth / FOG_DIST) ** 1.5, 1)

            base = 150

            shade = int(base * (1 - fog))

            shade += int(light_boost * (1 - fog))

            shade = max(10, min(220, shade))

            shade = max(15, min(220, shade))

            line_x = int(r * W / NUM_RAYS)
            ray_width = math.ceil(W / NUM_RAYS)

            wall_x = hit_x - math.floor(hit_x)
            wall_y = hit_y - math.floor(hit_y)

            if side == 0:
                wall_x = hit_y
            else:
                wall_x = hit_x

            wall_x -= math.floor(wall_x)

            tex_x = int(wall_x * TEX_SIZE)
            wall_x -= math.floor(wall_x)
            tex_x = int(wall_x * TEX_SIZE)

            from PIL import ImageEnhance

            key = (tex_x, int(wall_height))  # сначала ключ!

            if key not in texture_column_cache:
                enhancer = ImageEnhance.Brightness(wall_tex.crop((tex_x, 0, tex_x+1, TEX_SIZE)))
                column = enhancer.enhance(shade / 255)
                column = column.resize((int(W/NUM_RAYS)+2, int(wall_height)), Image.NEAREST)
                texture_column_cache[key] = ImageTk.PhotoImage(column)

            img = texture_column_cache[key]

            if key not in texture_column_cache:

                column = wall_tex.crop((tex_x, 0, tex_x+1, TEX_SIZE))

                column = column.resize(
                    (int(W/NUM_RAYS)+2, int(wall_height)),
                    Image.NEAREST
                )

                texture_column_cache[key] = ImageTk.PhotoImage(column)

            img = texture_column_cache[key]

            # рисуем стену с эффектом ступеней
            for s in range(steps):
                y_pos = int(H/2 - wall_height/2 - (player_z - s*0.2)*30 + bob_offset)
                
                # добавляем небольшой сдвиг, чтобы нижний край стены заходил в пол
                y_pos = max(0, min(y_pos, H - 1))  # верх не выше 0, низ не ниже H-1
                
                canvas.create_image(
                    line_x,
                    y_pos,
                    image=img,
                    anchor="nw"
                )
            # базовый оттенок стены
            base = 150
            fog = min((depth / FOG_DIST) ** 1.5, 1)
            shade = int(base * (1 - fog))

            # свет от ламп
            shade += int(light_boost * (1 - fog))

            # пульсация и flash
            pulse = math.sin(t*2 + r*0.05) * 15
            shade += int(pulse)

            if flash_timer > 0:
                shade = min(255, shade + int(100 * (flash_timer / flash_duration)))
                flash_timer -= delta

            # ограничиваем диапазон
            shade = max(15, min(255, shade))
        frames = enemy_gifs[enemy_state]

# увеличение индекса кадра
        if int(time.time() * 8) % 2 == 0:
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

        if selected_slot == 1:
            canvas.create_image(
                W//2,
                H - int(H*0.15) - int(bob_offset/2),
                image=gun_img
            )
        
        # === HUD IMAGE ===

        hud_x = W - hud_w - 20
        hud_y = H - hud_h - 20

        canvas.create_image(
            hud_x,
            hud_y,
            image=hud_img,
            anchor="nw"
        )
        # AMMO
        canvas.create_text(
            hud_x + 26,
            hud_y + 28,
            text="AMMO:",
            fill="#00ff00",
            font=("Terminal", 16),
            anchor="w"
        )

        canvas.create_text(
            hud_x + 23,
            hud_y + 48,
            text=f"{ammo}/{max_ammo}",
            fill="#00ff00",
            font=("Terminal", 18),
            anchor="w"
        )

        # HP кубики
        hp_percent = 1.0  # тут можно поставить enemy_health/max_health если для игрока
        max_blocks = 10
        filled_blocks = int(max_blocks * hp_percent)

        block_size = 10
        block_spacing = 3

        start_hp_x = hud_x + hud_w//2 + 20 # ближе к центру
        start_hp_y = hud_y + 40

        for i in range(max_blocks):
            x = start_hp_x + i * (block_size + block_spacing)
            y = start_hp_y

            color = "red" if i < filled_blocks else "#220000"

            canvas.create_rectangle(
                x, y,
                x + block_size,
                y + block_size,
                fill=color,
                outline="#00ff00"
            )

        canvas.create_text(
            start_hp_x,
            start_hp_y - 10,
            text="HP:",
            fill="#00ff00",
            font=("Terminal", 16),
            anchor="w"
        )
        # === ЧАСЫ НА HUD ===
        # === ЧАСЫ НА HUD ===
        elapsed = time.time() - hud_start_time  # время с начала игры
        minutes = int(elapsed // 60) % 60
        seconds = int(elapsed % 60)
        milliseconds = int((elapsed % 1) * 1000)
        time_text = f"{minutes:02}:{seconds:02}:{milliseconds:03}"

        # позиция часов относительно HUD
        clock_offset_x = 30
        clock_offset_y = hud_h - 55

        # фон часов внутри HUD
        clock_width = 80
        clock_height = 28
        canvas.create_rectangle(
            hud_x + clock_offset_x,
            hud_y + clock_offset_y,
            hud_x + clock_offset_x + clock_width,
            hud_y + clock_offset_y + clock_height,
            fill="#000000",
            outline="#00ff00",
            width=2
        )

        # текст часов
        canvas.create_text(
            hud_x + clock_offset_x + clock_width // 2,
            hud_y + clock_offset_y + clock_height // 2,
            text=time_text,
            fill="#00ff00",
            font=("Terminal", 13, "bold"),
            anchor="center"
        )

        # === СЛОТЫ В HUD (компактнее) ===
        slot_size = 32
        slot_spacing = 6   # ближе друг к другу

        # переносим ближе к центру HUD
        start_x = hud_x + hud_w//2 - (2*slot_size + 1.5*slot_spacing)  # чтобы 5 слотов по центру HUD
        start_y = hud_y + hud_h - slot_size - 35

        for i in range(5):
            x = start_x + i * (slot_size + slot_spacing)
            y = start_y

            # выделение выбранного
            if (i + 1) == selected_slot:
                canvas.create_rectangle(
                    x-2, y-2,
                    x+slot_size+2, y+slot_size+2,
                    outline="yellow",
                    width=2
                )

            canvas.create_rectangle(
                x, y,
                x + slot_size,
                y + slot_size,
                outline="#00ff00",
                width=2,
                fill="#666666"
            )

            # номер слота
            canvas.create_text(
                x + slot_size//2,
                y + slot_size + 10,
                text=str(i+1),
                fill="#00ff00",
                font=("Terminal", 11)
            )

        # Иконка предмета
        canvas.create_image(
            start_x + slot_size//2,
            start_y + slot_size//2,
            image=gunitem_img
        )
        
        # рисуем HP босса
        if enemy_state == "walking":

            bar_width = 400
            bar_height = 25

            x = W//2 - bar_width//2
            y = 40

    # фон
            canvas.create_rectangle(
                x, y,
                x + bar_width,
                y + bar_height,
                fill="#330000",
                outline="white"
            )

    # HP
            hp_ratio = enemy_health / enemy_max_health

            canvas.create_rectangle(
                x, y,
                x + bar_width * hp_ratio,
                y + bar_height,
                fill="red",
                outline=""
            )

    # имя босса
            canvas.create_text(
                W//2,
                y - 15,
                text="Dr. Hale",
                fill="white",
                font=("Terminal",20)
            )
        # прицел
        canvas.create_line(W//2-10, H//2, W//2+10, H//2, fill="white", width=2)
        canvas.create_line(W//2, H//2-10, W//2, H//2+10, fill="white", width=2)
        if show_debug:

            canvas.create_rectangle(
                5,5,
                220,120,
                fill="#000000",
                outline="#00ff00"
            )

            canvas.create_text(
                10,10,
                anchor="nw",
                fill="#00ff00",
                font=("Terminal",14),
                text=f"FPS: {fps_display}"
            )

            canvas.create_text(
                10,30,
                anchor="nw",
                fill="#00ff00",
                font=("Terminal",14),
                text=f"RAYS: {NUM_RAYS}"
            )

            canvas.create_text(
                10,50,
                anchor="nw",
                fill="#00ff00",
                font=("Terminal",14),
                text=f"SPRITES: {len(sprite_cache)}"
            )

            canvas.create_text(
                10,70,
                anchor="nw",
                fill="#00ff00",
                font=("Terminal",14),
                text=f"POS: {player_x:.2f} {player_y:.2f}"
            )

            canvas.create_text(
                10,90,
                anchor="nw",
                fill="#00ff00",
                font=("Terminal",14),
                text=f"ANGLE: {math.degrees(player_angle):.1f}"
            )
        
        if intro_active:
            draw_pixel_decode()
            draw_intro_text()
        win.after(16,render)
    
    def shoot_gun():
        nonlocal gunshoot_animating, gun_img, ammo, reloading
        nonlocal enemy_health, selected_slot
        if selected_slot != 1:
            return

        if not has_gun or gunshoot_animating or reloading:
            return

        if ammo <= 0:
            reload_gun()
            return

        ammo -= 1
        flash_timer = flash_duration

        # проверка попадания во врага
        dx = enemy_x - player_x
        dy = enemy_y - player_y
        dist = math.hypot(dx, dy)
        angle_to_enemy = math.atan2(dy, dx)
        angle_diff = angle_to_enemy - player_angle

        while angle_diff > math.pi:
            angle_diff -= 2*math.pi
        while angle_diff < -math.pi:
            angle_diff += 2*math.pi

        if abs(angle_diff) < 0.05 and dist < 8 and enemy_state == "walking":
            enemy_health -= 2

        # анимация выстрела
        def animate(index=0):
            nonlocal gunshoot_animating, gun_img

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
                (int(W * GUN_SCALE),
                int(gun_img_raw.height * (W * GUN_SCALE) / gun_img_raw.width)),
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

    # ограничиваем минимальное расстояние, чтобы спрайт не стал огромным
        if dist < 0.5:
            dist = 0.5

        angle = math.atan2(dy, dx) - player_angle
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi

        if abs(angle) > FOV / 2:
            return

        screen_x = (angle + FOV / 2) / FOV * W

        frame = frames[frame_index]

    # вычисляем размер спрайта на экране
        sprite_height = int(H / (dist + 0.0001) * scale)

    # лимитируем максимальный размер, чтобы не падал FPS
        max_sprite_size = 1500
        if sprite_height > max_sprite_size:
            sprite_height = max_sprite_size

        sprite_width = int(sprite_height * frame.width / frame.height)

    # создаем ключ для кэша
        key = (frame_index, sprite_width, sprite_height)

    # если такой спрайт уже есть в кэше — используем его
        if key not in sprite_resize_cache:
            img = frame.resize((sprite_width, sprite_height), Image.NEAREST)
            sprite_resize_cache[key] = ImageTk.PhotoImage(img)

        img = sprite_resize_cache[key]

        x1 = screen_x - sprite_width // 2
        y1 = H // 2 - sprite_height // 2 + bob_offset

        ray = int(screen_x / W * NUM_RAYS)
        if 0 <= ray < len(depth_buffer):
            if depth_buffer[ray] is not None and depth_buffer[ray] < dist:
                return

        canvas.create_image(x1, y1, image=img, anchor="nw")

        sprite_cache.append(img)
        
    def render_light(x,y,depth_buffer):

        dx = x - player_x
        dy = y - player_y

        dist = math.hypot(dx,dy)

        angle = math.atan2(dy,dx) - player_angle

        if abs(angle) > FOV/2:
            return

        screen_x = (angle + FOV/2) / FOV * W

        size = int(H/(dist+0.1)*0.2)

        canvas.create_oval(
            screen_x-size,
            H//2-size,
            screen_x+size,
            H//2+size,
            fill="#ffaa33",
            outline=""
        )
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
        nonlocal selected_slot

        k = e.keysym.lower()

        if k in keys:
            keys[k] = True
        if k == "r":
            reload_gun()

        if k == "f":
            nonlocal show_debug
            show_debug = not show_debug
            
        if k in ["1","2","3","4","5"]:
            selected_slot = int(k)

    def key_up(e):

        k = e.keysym.lower()

        if k in keys:
            keys[k] = False


    win.bind("<KeyPress>",key_down)
    win.bind("<KeyRelease>",key_up)
    win.bind("<Button-1>", lambda e: shoot_gun())
    def mouse_wheel(e):
        nonlocal selected_slot

        if e.delta > 0:
            selected_slot -= 1
        else:
            selected_slot += 1

        if selected_slot < 1:
            selected_slot = 5
        if selected_slot > 5:
            selected_slot = 1

    win.bind("<MouseWheel>", mouse_wheel)

    render()