import math
import os
import random
import sys
import time

import pygame
from PIL import Image

from background_music import play_sound_effect
from fake_hack import start_fake_hack
from maze_pygame_common import GAME_VIEW_H, GAME_VIEW_W, blit_game_view_upscaled
from pause_menu import run_pause_menu
from raycast_engine import (
    NUM_RAYS,
    draw_sky_floor_split,
    pil_to_surface,
    raycast_step_sampling_walls,
    render_sprite_hack_square,
)
from user_settings import get_fov_radians, get_game_view_size, get_show_debug_stats, get_show_fps, get_view_bob

MAX_DEPTH = 20
RAY_STEP = 0.05
SPEED = 0.052
TURN_SMOOTH = 26.0
ROT_RATE = 3.6
ROT_SUBSTEPS = 8
GUN_BOTTOM_MARGIN = -14
TIME_LIMIT = 90

MAP_TEMPLATE = [
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
    "#######################",
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
    game_view_w, game_view_h = get_game_view_size()
    num_rays = game_view_w
    bob_strength = get_view_bob()
    pygame.init()
    info = pygame.display.Info()
    W, H = info.current_w, info.current_h
    screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN | pygame.DOUBLEBUF)
    game_surface = pygame.Surface((game_view_w, game_view_h))
    pygame.display.set_caption("HACK MAZE")
    clock = pygame.time.Clock()

    font_ui = pygame.font.SysFont("consolas", 16)
    font_ui_big = pygame.font.SysFont("consolas", 40)
    font_dialog = pygame.font.SysFont("consolas", 20)
    font_dbg = pygame.font.SysFont("consolas", 14)
    font_intro = pygame.font.SysFont("consolas", 42)

    MAP_ROWS = list(MAP_TEMPLATE)

    def is_wall(x, y):
        if x < 0 or y < 0 or int(y) >= len(MAP_ROWS) or int(x) >= len(MAP_ROWS[0]):
            return True
        cell = MAP_ROWS[int(y)][int(x)]
        if cell == "8":
            return not has_key
        if cell == "S":
            if has_key and has_gun:
                return False
            return True
        return cell == "#"

    intro_active = True
    intro_text = "CASE H.0.1 /// HACK_MAZE"
    intro_index = 0
    intro_start = time.time()
    intro_duration = 8
    pixel_size = 28
    pixel_grid = []
    for x in range(0, W, pixel_size):
        for y in range(0, H, pixel_size):
            pixel_grid.append([x, y, True])
    random.shuffle(pixel_grid)
    pixel_grid = pixel_grid[:1200]
    fade_started = False

    player_spawn_x, player_spawn_y = 2.5, 2.5
    player_start_cutscene_offset = 2.0
    player_x = player_spawn_x - player_start_cutscene_offset
    player_y = player_spawn_y
    player_angle = 0.0
    start_time = time.time()
    game_over = False
    has_key = False
    message = ""
    enemy_frames = load_gif_frames(resource_path("data/patrol.gif"))
    key_frames = load_gif_frames(resource_path("data/key.gif"))
    goal_frames = load_gif_frames(resource_path("data/whatthe.gif"))
    meto_frames = load_gif_frames(resource_path("data/metopear.gif"))
    gun_img_raw = Image.open(resource_path("data/gifs/hands/gun.png")).convert("RGBA")
    gunshoot_frames_raw = load_gif_frames(resource_path("data/gifs/hands/gunshoot.gif"))
    gunreload_frames_raw = load_gif_frames(resource_path("data/gifs/hands/gunreload.gif"))

    GUN_SCALE = 0.25
    orb_textures = {
        "yellow": Image.open(resource_path("data/orbs/orb_yellow.png")).convert("RGBA"),
        "red": Image.open(resource_path("data/orbs/orb_red.png")).convert("RGBA"),
        "green": Image.open(resource_path("data/orbs/orb_green.png")).convert("RGBA"),
        "violet": Image.open(resource_path("data/orbs/orb_violet.png")).convert("RGBA"),
    }
    eyewall_raw = Image.open(resource_path("data/eyewall.png")).convert("RGBA")

    meto_frame_index = 0
    meto_x = meto_y = None
    for y, row in enumerate(MAP_ROWS):
        for x, c in enumerate(row):
            if c == "P":
                meto_x, meto_y = x + 0.5, y + 0.5

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

    goal_x = goal_y = None
    for y, row in enumerate(MAP_ROWS):
        for x, c in enumerate(row):
            if c == "?":
                goal_x, goal_y = x + 0.5, y + 0.5

    enemy = {"x": 10.5, "y": 6.5, "dir": 1, "min_x": 8.5, "max_x": 14.5}

    orbworms = []
    colors = list(orb_textures.keys())
    for i in range(4):
        length = random.randint(7, 9)
        orbworms.append(
            {
                "x": -5.0 - i * 3,
                "base_y": 1.5 + i * 1.5,
                "speed": 0.06 + random.random() * 0.02,
                "length": length,
                "color": colors[i],
                "start_delay": random.random() * 2.5,
                "started": False,
            }
        )

    eye_zone_x = 14.5
    eye_zone_y = 7
    eye_zone_radius = 0.6
    eye_event_active = False
    eye_event_triggered = False
    eye_event_end_time = 0.0

    keys = {"w": False, "s": False, "a": False, "d": False}
    ammo = 17
    max_ammo = 17
    reloading = False
    gunshoot_animating = False
    gunshoot_frame_index = 0
    reload_anim_index = 0
    reload_anim_active = False
    shoot_acc = 0.0
    reload_acc = 0.0
    show_debug = get_show_debug_stats()
    last_frame_time = time.time()
    fps = 0
    last_step_time = 0.0

    bob_phase = 0.0
    turn_smooth = 0.0
    bob_offset = 0.0
    bob_side_offset = 0.0

    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, v))

    def _ease_out_cubic(x: float) -> float:
        x = _clamp01(x)
        return 1.0 - (1.0 - x) ** 3

    start_cutscene_active = True
    start_cutscene_started = False
    start_cutscene_start_time = 0.0
    start_cutscene_open_t = 0.0
    start_cutscene_close_t = 0.0
    START_DOOR_OPEN_DUR = 0.55
    START_MOVE_DUR = 0.7
    START_DOOR_CLOSE_DUR = 0.45
    START_TOTAL_DUR = START_DOOR_OPEN_DUR + START_MOVE_DUR + START_DOOR_CLOSE_DUR

    door_left_tex = Image.open(resource_path("data/Lelevatordoor.png")).convert("RGBA")
    door_right_tex = Image.open(resource_path("data/Relevatordoor.png")).convert("RGBA")
    DOOR_CLOSE_STEPS = 12
    DOOR_PIL_H = 64
    DOOR_PIL_W_MIN = 48
    DOOR_PIL_W_MAX = DOOR_PIL_H
    door_left_frames = []
    door_right_frames = []
    for i in range(DOOR_CLOSE_STEPS):
        ct = i / max(1, DOOR_CLOSE_STEPS - 1)
        ct_thin = _clamp01((ct - 0.65) / 0.35)
        w = int(DOOR_PIL_W_MAX * (1.0 - ct_thin) + DOOR_PIL_W_MIN * ct_thin)
        w = max(1, w)
        door_left_frames.append(door_left_tex.resize((w, DOOR_PIL_H), Image.NEAREST))
        door_right_frames.append(door_right_tex.resize((w, DOOR_PIL_H), Image.NEAREST))

    pending_action = None
    pending_until = 0.0
    dialog_close_until = 0.0
    caught_by_enemy = False

    running = True
    next_action = None

    def build_gun_surface(pil_img):
        w, h = pil_img.size
        nw = int(game_view_w * GUN_SCALE)
        nh = int(h * (nw / w))
        return pil_to_surface(pil_img.resize((nw, nh), Image.NEAREST))

    def play_step():
        play_sound_effect(resource_path("data/step.wav"))

    def start_dialog_text(text):
        nonlocal dialog_full_text, dialog_display_text, dialog_index, dialog_typing
        dialog_full_text = text
        dialog_display_text = ""
        dialog_index = 0
        dialog_typing = True

    def close_dialog():
        nonlocal dialog_active, dialog_full_text, dialog_display_text, dialog_index, dialog_typing
        dialog_active = False
        dialog_full_text = ""
        dialog_display_text = ""
        dialog_index = 0
        dialog_typing = False

    def shoot_gun():
        nonlocal gunshoot_animating, gunshoot_frame_index, ammo, reloading, shoot_acc
        if not has_gun or gunshoot_animating or reloading:
            return
        if ammo <= 0:
            start_reload()
            return
        ammo -= 1
        gunshoot_animating = True
        gunshoot_frame_index = 0
        shoot_acc = 0.0

    def start_reload():
        nonlocal reloading, reload_anim_active, reload_anim_index, reload_acc
        if reloading or not has_gun:
            return
        reloading = True
        reload_anim_active = True
        reload_anim_index = 0
        reload_acc = 0.0

    while running:
        delta = clock.tick(120) / 1000.0
        if delta <= 0:
            delta = 1.0 / 60.0
        current_time = time.time()
        last_frame_time = current_time
        if intro_active or start_cutscene_active:
            start_time += delta

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pause_action = run_pause_menu(screen, clock, root, W, H, title="Paused")
                    if pause_action == "restart":
                        next_action = "restart"
                        running = False
                    elif pause_action == "quit":
                        next_action = "quit"
                        running = False
                    continue
                elif dialog_active:
                    ch = event.unicode
                    if dialog_step == 0:
                        if ch == "1":
                            dialog_step = 1
                            start_dialog_text(
                                "What exactly do you mean?\n\n"
                                "1) Iloveyou\n"
                                "2) I love eating them\n"
                                "3) Idk"
                            )
                        elif ch == "2":
                            running = False
                    elif dialog_step == 1:
                        if ch == "1":
                            start_dialog_text("Aww... Thats cute.. wait I`l give you a present")
                            has_gun = True
                            dialog_close_until = time.time() + 2.5
                        elif ch == "2":
                            start_dialog_text("What?! do you love it when we die and suffer?")
                            game_over = True
                            pending_action = "quit_delayed"
                            pending_until = time.time() + 2.0
                        elif ch == "3":
                            start_dialog_text("Um.. OK")
                            dialog_close_until = time.time() + 1.5
                elif start_cutscene_active or intro_active:
                    continue
                elif event.key == pygame.K_r and not dialog_active:
                    start_reload()
                elif event.unicode == "=":
                    show_debug = not show_debug
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if start_cutscene_active or intro_active:
                    continue
                if event.button == 1:
                    shoot_gun()

        if dialog_close_until and time.time() >= dialog_close_until:
            dialog_close_until = 0.0
            close_dialog()

        if pending_action == "quit_delayed" and time.time() >= pending_until:
            pygame.quit()
            return

        if pending_action == "fake_hack" and time.time() >= pending_until:
            pygame.quit()
            start_fake_hack(root)
            return

        if pending_action == "secret" and time.time() >= pending_until:
            from secret_maze import start_secret_maze

            pygame.quit()
            start_secret_maze(root)
            return

        if pending_action == "success" and time.time() >= pending_until:
            pygame.quit()
            on_success()
            return

        k = pygame.key.get_pressed()
        keys["w"] = k[pygame.K_w]
        keys["s"] = k[pygame.K_s]
        keys["a"] = k[pygame.K_a]
        keys["d"] = k[pygame.K_d]

        if start_cutscene_active:
            if (not intro_active) and not start_cutscene_started:
                start_cutscene_started = True
                start_cutscene_start_time = time.time()

            elapsed = max(0.0, time.time() - start_cutscene_start_time) if start_cutscene_started else 0.0
            start_cutscene_open_t = 0.0
            start_cutscene_close_t = 0.0

            if elapsed < START_DOOR_OPEN_DUR:
                start_cutscene_open_t = _clamp01(elapsed / START_DOOR_OPEN_DUR)
            elif elapsed < START_DOOR_OPEN_DUR + START_MOVE_DUR:
                start_cutscene_open_t = 1.0
                move_ratio = _ease_out_cubic((elapsed - START_DOOR_OPEN_DUR) / START_MOVE_DUR)
                player_x = player_spawn_x - player_start_cutscene_offset + player_start_cutscene_offset * move_ratio
                player_y = player_spawn_y
            elif elapsed < START_TOTAL_DUR:
                start_cutscene_open_t = 1.0
                start_cutscene_close_t = _clamp01((elapsed - START_DOOR_OPEN_DUR - START_MOVE_DUR) / START_DOOR_CLOSE_DUR)
                player_x = player_spawn_x + 0.02
                player_y = player_spawn_y
            else:
                player_x = player_spawn_x
                player_y = player_spawn_y
                start_cutscene_active = False
                start_cutscene_open_t = 0.0
                start_cutscene_close_t = 1.0

            bob_offset = 0.0
            bob_side_offset = 0.0
            keys["w"] = keys["s"] = keys["a"] = keys["d"] = False

        elif not game_over and not pending_action:
            move_x = 0.0
            move_y = 0.0
            is_moving = False
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

            want_turn = 0.0
            if keys["a"]:
                want_turn -= 1.0
            if keys["d"]:
                want_turn += 1.0
            ds = delta / ROT_SUBSTEPS
            for _ in range(ROT_SUBSTEPS):
                turn_smooth += (want_turn - turn_smooth) * min(1.0, TURN_SMOOTH * ds)
                player_angle += turn_smooth * ROT_RATE * ds

            if delta > 0:
                fps = int(1 / delta)

            if time.time() - last_anim_time > ANIM_SPEED:
                enemy_frame_index = (enemy_frame_index + 1) % len(enemy_frames)
                key_frame_index = (key_frame_index + 1) % len(key_frames)
                goal_frame_index = (goal_frame_index + 1) % len(goal_frames)
                if meto_frames:
                    meto_frame_index = (meto_frame_index + 1) % len(meto_frames)
                last_anim_time = time.time()

            enemy["x"] += 0.03 * enemy["dir"]
            if enemy["x"] < enemy["min_x"] or enemy["x"] > enemy["max_x"]:
                enemy["dir"] *= -1

            if is_moving:
                bob_phase += 0.25
                bob_offset = math.sin(bob_phase) * 10 * bob_strength
                bob_side_offset = math.sin(bob_phase * 0.6) * 4 * bob_strength
            else:
                bob_offset = 0.0
                bob_side_offset = 0.0

            if not eye_event_triggered and math.hypot(player_x - eye_zone_x, player_y - eye_zone_y) < eye_zone_radius:
                eye_event_active = True
                eye_event_triggered = True
                eye_event_end_time = time.time() + 4
            if eye_event_active and time.time() > eye_event_end_time:
                eye_event_active = False

            if is_moving and time.time() - last_step_time > 0.4:
                play_step()
                last_step_time = time.time()

            for worm in orbworms:
                if not worm["started"]:
                    if current_time > worm["start_delay"]:
                        worm["started"] = True
                    else:
                        continue
                worm["x"] += worm["speed"]
                if worm["x"] > len(MAP_ROWS[0]) + 5:
                    worm["x"] = -5
                    worm["start_delay"] = current_time + random.random() * 3
                    worm["started"] = False

            if math.hypot(player_x - enemy["x"], player_y - enemy["y"]) < 0.4:
                game_over = True
                caught_by_enemy = True
                pending_action = "fake_hack"
                pending_until = time.time() + 1.2

            if MAP_ROWS[int(player_y)][int(player_x)] == "K":
                has_key = True
                message = "KEY ACQUIRED"
                py, px = int(player_y), int(player_x)
                row = MAP_ROWS[py]
                MAP_ROWS[py] = row[:px] + "." + row[px + 1 :]

            remaining = max(0, TIME_LIMIT - int(time.time() - start_time))
            if remaining <= 0:
                game_over = True
                caught_by_enemy = False
                pending_action = "fake_hack"
                pending_until = time.time() + 1.5

            if MAP_ROWS[int(player_y)][int(player_x)] == "S" and has_key and has_gun:
                game_over = True
                pending_action = "secret"
                pending_until = time.time() + 0.05

            if goal_x and int(player_x) == int(goal_x) and int(player_y) == int(goal_y):
                game_over = True
                pending_action = "success"
                pending_until = time.time() + 1.2

            if meto_x and not meto_triggered and math.hypot(player_x - meto_x, player_y - meto_y) < 0.8:
                dialog_active = True
                dialog_step = 0
                start_dialog_text("Hello! Im Meto-pear!\nDo you like pears?\n\n1) Yes\n2) No")
                meto_triggered = True

        if dialog_active and dialog_typing:
            if dialog_index < len(dialog_full_text):
                dialog_display_text += dialog_full_text[dialog_index]
                dialog_index += 1
            else:
                dialog_typing = False

        shoot_frame_time = 0.05
        if gunshoot_animating:
            shoot_acc += delta
            while shoot_acc >= shoot_frame_time and gunshoot_animating:
                shoot_acc -= shoot_frame_time
                gunshoot_frame_index += 1
                if gunshoot_frame_index >= len(gunshoot_frames_raw):
                    gunshoot_animating = False
                    gunshoot_frame_index = 0

        reload_frame_time = 0.06
        if reload_anim_active and reloading:
            reload_acc += delta
            while reload_acc >= reload_frame_time and reloading:
                reload_acc -= reload_frame_time
                reload_anim_index += 1
                if reload_anim_index >= len(gunreload_frames_raw):
                    reloading = False
                    reload_anim_active = False
                    reload_anim_index = 0
                    ammo = max_ammo

        sprite_cache = []
        if eye_event_active:
            sky_color = "black"
            floor_color = "black"
        else:
            sky_color = "#87CEEB"
            floor_color = "#555555"
        draw_sky_floor_split(game_surface, game_view_w, game_view_h, sky_color, floor_color)

        current_fov = get_fov_radians()
        depth_buffer = raycast_step_sampling_walls(
            game_surface,
            game_view_w,
            game_view_h,
            num_rays,
            current_fov,
            MAX_DEPTH,
            RAY_STEP,
            player_x,
            player_y,
            player_angle,
            bob_offset,
            bob_side_offset,
            is_wall,
            eye_event_active,
            eyewall_raw,
            sprite_cache,
        )

        render_sprite_hack_square(
            game_surface,
            game_view_w,
            game_view_h,
            num_rays,
            current_fov,
            player_x,
            player_y,
            player_angle,
            bob_offset,
            enemy_frames,
            enemy_frame_index,
            enemy["x"],
            enemy["y"],
            0.6,
            depth_buffer,
            sprite_cache,
        )

        for y, row in enumerate(MAP_ROWS):
            for x, cell in enumerate(row):
                if cell == "K":
                    render_sprite_hack_square(
                        game_surface,
                        game_view_w,
                        game_view_h,
                        num_rays,
                        current_fov,
                        player_x,
                        player_y,
                        player_angle,
                        bob_offset,
                        key_frames,
                        key_frame_index,
                        x + 0.5,
                        y + 0.5,
                        0.5,
                        depth_buffer,
                        sprite_cache,
                    )

        if goal_x:
            render_sprite_hack_square(
                game_surface,
                game_view_w,
                game_view_h,
                num_rays,
                current_fov,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                goal_frames,
                goal_frame_index,
                goal_x,
                goal_y,
                0.7,
                depth_buffer,
                sprite_cache,
            )

        if meto_x:
            render_sprite_hack_square(
                game_surface,
                game_view_w,
                game_view_h,
                num_rays,
                current_fov,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                meto_frames,
                meto_frame_index,
                meto_x,
                meto_y,
                0.6,
                depth_buffer,
                sprite_cache,
            )

        for worm in orbworms:
            if not worm["started"]:
                continue
            texture = orb_textures[worm["color"]]
            for i in range(worm["length"]):
                segment_x = worm["x"] - i * 0.09
                segment_y = worm["base_y"] + math.sin(i * 0.6 + worm["x"] * 4) * 0.3
                render_sprite_hack_square(
                    game_surface,
                    game_view_w,
                    game_view_h,
                    num_rays,
                    current_fov,
                    player_x,
                    player_y,
                    player_angle,
                    bob_offset,
                    [texture],
                    0,
                    segment_x,
                    segment_y,
                    0.42,
                    depth_buffer,
                    sprite_cache,
                )

        if start_cutscene_active:
            if start_cutscene_open_t < 1.0:
                door_progress = 1.0 - _ease_out_cubic(start_cutscene_open_t)
            elif start_cutscene_close_t > 0.0:
                door_progress = _ease_out_cubic(start_cutscene_close_t)
            else:
                door_progress = 0.0

            fwd_x = math.cos(player_angle)
            fwd_y = math.sin(player_angle)
            right_x = -fwd_y
            right_y = fwd_x
            door_front_dist_open = 0.92
            door_front_dist_closed = 0.62
            door_front_dist = door_front_dist_open + (door_front_dist_closed - door_front_dist_open) * door_progress
            half_sep_open = 0.88
            half_sep_closed = 0.17
            half_sep = half_sep_open + (half_sep_closed - half_sep_open) * door_progress
            center_x = player_x + fwd_x * door_front_dist
            center_y = player_y + fwd_y * door_front_dist
            left_sx = center_x - right_x * half_sep
            left_sy = center_y - right_y * half_sep
            right_sx = center_x + right_x * half_sep
            right_sy = center_y + right_y * half_sep
            door_frame_idx = int(_clamp01(door_progress) * (len(door_left_frames) - 1))
            render_sprite_hack_square(
                game_surface,
                game_view_w,
                game_view_h,
                num_rays,
                current_fov,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                door_left_frames,
                door_frame_idx,
                left_sx,
                left_sy,
                1.12,
                depth_buffer,
                sprite_cache,
            )
            render_sprite_hack_square(
                game_surface,
                game_view_w,
                game_view_h,
                num_rays,
                current_fov,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                door_right_frames,
                door_frame_idx,
                right_sx,
                right_sy,
                1.12,
                depth_buffer,
                sprite_cache,
            )

        if (not start_cutscene_active) and has_gun:
            gs = build_gun_surface(gun_img_raw)
            if gunshoot_animating:
                fi = min(gunshoot_frame_index, len(gunshoot_frames_raw) - 1)
                gs = build_gun_surface(gunshoot_frames_raw[fi])
            elif reloading and reload_anim_active:
                fi = min(reload_anim_index, len(gunreload_frames_raw) - 1)
                gs = build_gun_surface(gunreload_frames_raw[fi])
            gun_y = game_view_h - GUN_BOTTOM_MARGIN - int(bob_offset * 0.35)
            game_surface.blit(gs, gs.get_rect(midbottom=(game_view_w // 2, gun_y)))

        blit_game_view_upscaled(game_surface, screen, W, H)

        remaining = max(0, TIME_LIMIT - int(time.time() - start_time))
        screen.blit(
            font_ui.render(f"W/S MOVE  A/D TURN  TIME {remaining}", True, (255, 0, 0)),
            (W // 2 - 200, 20),
        )

        if message:
            screen.blit(font_ui.render(message, True, (0, 255, 0)), (W // 2 - 80, 60))

        if dialog_active:
            pygame.draw.rect(screen, (0, 0, 0), (int(W * 0.1), int(H * 0.65), int(W * 0.8), int(H * 0.25)), width=3)
            lines = (dialog_display_text + (" █" if dialog_typing else "")).split("\n")
            yy = int(H * 0.68)
            for line in lines:
                screen.blit(font_dialog.render(line, True, (0, 255, 0)), (W // 2 - 280, yy))
                yy += 24

        if has_gun:
            screen.blit(font_ui.render(f"{ammo}/{max_ammo}", True, (0, 255, 0)), (W - 120, H - 40))

        cross_size = 8
        pygame.draw.line(screen, (0, 255, 0), (W // 2 - cross_size, H // 2), (W // 2 + cross_size, H // 2), 2)
        pygame.draw.line(screen, (0, 255, 0), (W // 2, H // 2 - cross_size), (W // 2, H // 2 + cross_size), 2)

        if show_debug or get_show_fps():
            pygame.draw.rect(screen, (0, 0, 0), (10, 10, 320, 100), width=1)
            lines = [f"FPS: {fps}"]
            if show_debug:
                lines.extend(
                    [
                        f"X: {player_x:.2f}",
                        f"Y: {player_y:.2f}",
                        f"ANGLE: {player_angle:.2f}",
                    ]
                )
            for i, line in enumerate(lines):
                screen.blit(font_dbg.render(line, True, (0, 255, 0)), (20, 25 + i * 20))

        if game_over and pending_action == "fake_hack" and time.time() < pending_until:
            msg = "DETECTED" if caught_by_enemy else "ACCESS DENIED"
            surf = font_ui_big.render(msg, True, (255, 0, 0))
            screen.blit(surf, (W // 2 - surf.get_width() // 2, H // 2 - 40))
        if game_over and pending_action == "success" and time.time() < pending_until:
            surf = font_ui_big.render("THEME UNLOCKED", True, (0, 255, 0))
            screen.blit(surf, (W // 2 - surf.get_width() // 2, H // 2 - 40))

        if intro_active:
            progress = (time.time() - intro_start) / intro_duration
            if progress >= 1:
                intro_active = False
            else:
                for p in pixel_grid:
                    x, y, active = p
                    if active and random.random() < progress * 0.2:
                        p[2] = False
                    if p[2]:
                        shade = random.randint(0, 120)
                        pygame.draw.rect(screen, (shade, shade, shade), (x, y, pixel_size, pixel_size))
            if intro_active:
                if intro_index < len(intro_text):
                    intro_index += 1
                shown = intro_text[:intro_index]
                if intro_index >= len(intro_text):
                    fade_started = True
                size = 42
                if fade_started:
                    fade_time = max(0, time.time() - intro_start - 2)
                    remain_ratio = max(0, 1 - fade_time * 0.25)
                    visible_len = int(len(shown) * remain_ratio)
                    shown = shown[:visible_len]
                    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@!?$%"
                    glitched = ""
                    for c in shown:
                        if random.random() < 0.15 * fade_time:
                            glitched += random.choice(chars)
                        else:
                            glitched += c
                    shown = glitched
                    size = int(42 * remain_ratio)
                    if size <= 6 or visible_len <= 0:
                        intro_active = False
                if intro_active and size > 6:
                    surf = font_intro.render(shown, True, (0, 255, 136))
                    screen.blit(surf, (W // 2 - surf.get_width() // 2, H // 2 - surf.get_height() // 2))

        pygame.display.flip()

    pygame.quit()
    if next_action == "restart":
        return start_hack_maze(root, hack_window=hack_window, on_success=on_success)
