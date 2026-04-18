import math
import os
import random
import sys
import time

import pygame
from PIL import Image

from abebe.entities.maze_entities import BOMB_SYMBOL, HEXAGAZE_SYMBOL, MANNEQUIN_SYMBOL
from abebe.maze.maze_pygame_common import (
    GAME_VIEW_H,
    GAME_VIEW_W,
    blit_game_view_upscaled,
    draw_boss_bar,
    draw_hud_base,
    make_font,
)
from abebe.maze.pause_menu import run_pause_menu
from abebe.maze.raycast_engine import NUM_RAYS, RaycastEngine, draw_floor_ceiling, pil_to_surface
from abebe.core.user_settings import (
    get_game_view_size,
    get_mouse_wheel_weapon_switch,
    get_show_debug_stats,
    get_show_fps,
    get_view_bob,
)
from abebe.core.utils import get_resource_path

SPEED = 0.17
GUN_BOTTOM_MARGIN = -14
MOUSE_SENSITIVITY = 0.0035

# Shared entity symbols are available for later MAP integration:
# BOMB_SYMBOL, MANNEQUIN_SYMBOL, HEXAGAZE_SYMBOL

MAP = [
    ".........###............",
    ".........#.#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    ".........#L#............",
    "##########.#############",
    "#........#..W.T........#",
    "#........####TT........#",
    "#......................#",
    "#..................E...#",
    "#......................#",
    "#........#.............#",
    "#........#.............#",
    "#........#.............#",
    "########################",
]

trigger_activated = False


def resource_path(relative_path):
    return get_resource_path(relative_path)


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


def is_wall(x, y):
    global trigger_activated
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


def get_floor_height(x, y):
    if x < 0 or y < 0:
        return 0.0
    if int(y) >= len(MAP):
        return 0.0
    if int(x) >= len(MAP[0]):
        return 0.0
    cell = MAP[int(y)][int(x)]
    if cell == "T":
        return 0.4
    if cell == "W":
        return 0.22
    return 0.0


def wrap_angle(angle):
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def start_secret_maze(root=None):
    global trigger_activated
    game_view_w, game_view_h = get_game_view_size()
    bob_strength = get_view_bob()
    allow_wheel_switch = get_mouse_wheel_weapon_switch()
    pygame.init()
    info = pygame.display.Info()
    W, H = info.current_w, info.current_h
    screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN | pygame.DOUBLEBUF)
    game_surface = pygame.Surface((game_view_w, game_view_h))
    pygame.display.set_caption("THE_CICADA_PRISON")
    clock = pygame.time.Clock()
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    pygame.mouse.get_rel()

    font_hud = make_font(16)
    font_hud_big = make_font(18)
    font_clock = make_font(13, bold=True)
    font_slot = make_font(11)
    font_intro = make_font(42)
    font_boss = make_font(20)
    font_debug = make_font(14)

    intro_active = True
    intro_text = "SECRET CASE 1.1.5 /// THE_CICADA_PRISON"
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

    hud_start_time = time.time()
    player_spawn_x = 10.5
    player_spawn_y = 2.5
    player_start_cutscene_offset = 2.0
    player_x = player_spawn_x - player_start_cutscene_offset
    player_y = player_spawn_y
    player_z = get_floor_height(player_x, player_y)
    player_angle = 0.0

    gun_img_raw = Image.open(resource_path("data/gifs/hands/gun.png")).convert("RGBA")
    gunshoot_frames_raw = load_gif_frames(resource_path("data/gifs/hands/gunshoot.gif"))
    gunreload_frames_raw = load_gif_frames(resource_path("data/gifs/hands/gunreload.gif"))
    GUN_SCALE = 0.25

    hud_raw = Image.open(resource_path("data/hud.png")).convert("RGBA")
    HUD_SCALE_X = 3.8
    HUD_SCALE_Y = 3.2
    hud_w = int(128 * HUD_SCALE_X)
    hud_h = int(48 * HUD_SCALE_Y)
    hud_img = pil_to_surface(hud_raw.resize((hud_w, hud_h), Image.NEAREST))

    gunitem_raw = Image.open(resource_path("data/gunitem.png")).convert("RGBA")
    gunitem_raw = gunitem_raw.resize((40, 40), Image.NEAREST)
    gunitem_img = pil_to_surface(gunitem_raw)

    enemy_gifs = {
        "sitting": load_gif_frames(resource_path("data/gifs/cicada/cicadasitting.gif")),
        "getting_up": load_gif_frames(resource_path("data/gifs/cicada/cicadagettingup.gif")),
        "walking": load_gif_frames(resource_path("data/gifs/cicada/cicadawalking.gif")),
    }

    enemy_state = "sitting"
    enemy_frame_index = 0
    enemy_timer_start = None
    enemy_x = None
    enemy_y = None
    enemy_health = 100
    enemy_max_health = 100

    wall_tex = Image.open(resource_path("data/prison.png")).convert("RGB")
    TEX_SIZE = 32
    wall_tex = wall_tex.resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)
    texture_column_cache = {}
    ray_engine = RaycastEngine(game_surface, game_view_w, game_view_h, wall_tex, TEX_SIZE)

    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "E":
                enemy_x = x + 0.5
                enemy_y = y + 0.5
                break
        if enemy_x is not None:
            break

    lights = []
    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "L":
                lights.append((x + 0.5, y + 0.5))
    light_states = {}
    light_timers = {}
    for lx, ly in lights:
        light_states[(lx, ly)] = True
        light_timers[(lx, ly)] = time.time()

    keys = {"w": False, "s": False, "a": False, "d": False}
    selected_slot = 1
    ammo = 17
    max_ammo = 17
    reloading = False
    has_gun = True
    bob_phase = 0.0
    bob_offset = 0.0
    flash_timer = 0.0
    flash_duration = 0.08
    show_debug = get_show_debug_stats()
    fps_display = 0
    fps_timer = 0.0
    player_frozen = False
    freeze_end_time = 0.0

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

    gunshoot_animating = False
    gunshoot_frame_index = 0
    reload_anim_index = 0
    reload_anim_active = False
    shoot_acc = 0.0
    reload_acc = 0.0
    running = True
    next_action = None

    def build_gun_surface_from_pil(pil_frame):
        w, h = pil_frame.size
        new_w = int(game_view_w * GUN_SCALE)
        new_h = int(h * (new_w / w))
        return pil_to_surface(pil_frame.resize((new_w, new_h), Image.NEAREST))

    def shoot_gun():
        nonlocal gunshoot_animating, gunshoot_frame_index, ammo, flash_timer, reloading, enemy_health, shoot_acc
        if selected_slot != 1:
            return
        if not has_gun or gunshoot_animating or reloading:
            return
        if ammo <= 0:
            start_reload()
            return
        ammo -= 1
        flash_timer = flash_duration
        gunshoot_animating = True
        gunshoot_frame_index = 0
        shoot_acc = 0.0
        dx = enemy_x - player_x
        dy = enemy_y - player_y
        dist = math.hypot(dx, dy)
        angle_to_enemy = math.atan2(dy, dx)
        angle_diff = angle_to_enemy - player_angle
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        if abs(angle_diff) < 0.05 and dist < 8 and enemy_state == "walking":
            enemy_health -= 2

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
        fps_timer += delta
        if fps_timer > 0.2:
            fps_display = int(1.0 / delta) if delta > 0 else 0
            fps_timer = 0.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pause_action = run_pause_menu(screen, clock, root, W, H, title="Paused")
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    pygame.mouse.get_rel()
                    if pause_action == "restart":
                        next_action = "restart"
                        running = False
                    elif pause_action == "quit":
                        next_action = "quit"
                        running = False
                elif start_cutscene_active:
                    continue
                elif event.unicode in "12345":
                    selected_slot = int(event.unicode)
                elif event.key == pygame.K_r:
                    start_reload()
                elif event.key == pygame.K_f:
                    show_debug = not show_debug
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if start_cutscene_active:
                    continue
                if event.button == 1:
                    shoot_gun()
            elif event.type == pygame.MOUSEWHEEL:
                if start_cutscene_active or not allow_wheel_switch:
                    continue
                if event.y > 0:
                    selected_slot -= 1
                else:
                    selected_slot += 1
                if selected_slot < 1:
                    selected_slot = 5
                elif selected_slot > 5:
                    selected_slot = 1

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

            keys["w"] = keys["s"] = keys["a"] = keys["d"] = False
        else:
            k = pygame.key.get_pressed()
            keys["w"] = k[pygame.K_w]
            keys["s"] = k[pygame.K_s]
            keys["a"] = k[pygame.K_a]
            keys["d"] = k[pygame.K_d]

            mouse_dx, _mouse_dy = pygame.mouse.get_rel()
            player_angle = wrap_angle(player_angle + mouse_dx * MOUSE_SENSITIVITY)

        t = time.time()
        texture_column_cache.clear()

        for lk in light_states:
            if time.time() - light_timers[lk] > random.uniform(0.05, 0.3):
                light_timers[lk] = time.time()
                if random.random() < 0.2:
                    light_states[lk] = not light_states[lk]

        if trigger_activated and enemy_state == "sitting" and enemy_timer_start is None:
            enemy_timer_start = time.time()
        if enemy_timer_start:
            elapsed = time.time() - enemy_timer_start
            if elapsed >= 47 and enemy_state == "sitting":
                enemy_state = "getting_up"
                enemy_frame_index = 0

        if enemy_state == "walking":
            dx = player_x - enemy_x
            dy = player_y - enemy_y
            dist = math.hypot(dx, dy)
            if dist > 0.2:
                enemy_x += (dx / dist) * SPEED * 0.2
                enemy_y += (dy / dist) * SPEED * 0.2

        move_x = 0.0
        move_y = 0.0
        moving = False
        if player_frozen and time.time() > freeze_end_time:
            player_frozen = False

        if start_cutscene_active:
            move_x = 0.0
            move_y = 0.0
            moving = False
            bob_offset = 0
        elif not player_frozen and not intro_active:
            forward_x = math.cos(player_angle)
            forward_y = math.sin(player_angle)
            right_x = math.cos(player_angle + math.pi / 2)
            right_y = math.sin(player_angle + math.pi / 2)
            if keys["w"]:
                move_x += forward_x
                move_y += forward_y
            if keys["s"]:
                move_x -= forward_x
                move_y -= forward_y
            if keys["a"]:
                move_x -= right_x
                move_y -= right_y
            if keys["d"]:
                move_x += right_x
                move_y += right_y

            move_len = math.hypot(move_x, move_y)
            moving = move_len > 0.0
            if moving:
                move_x = (move_x / move_len) * SPEED
                move_y = (move_y / move_len) * SPEED

        nx = player_x + move_x
        ny = player_y + move_y
        if not is_wall(nx, player_y):
            player_x = nx
        if not is_wall(player_x, ny):
            player_y = ny

        player_z = get_floor_height(player_x, player_y)

        if moving:
            bob_phase += 0.25
            bob_offset = math.sin(bob_phase) * 10 * bob_strength
        else:
            bob_offset = 0

        cell = MAP[int(player_y)][int(player_x)]
        if cell == "T" and not trigger_activated:
            trigger_activated = True
            player_frozen = True
            freeze_end_time = time.time() + 47

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

        flash_ref = [flash_timer]
        draw_floor_ceiling(game_surface, game_view_w, game_view_h)
        sprite_cache = []
        depth_buffer = ray_engine.raycast_walls(
            player_x,
            player_y,
            player_z,
            player_angle,
            bob_offset,
            is_wall,
            lights,
            light_states,
            texture_column_cache,
            t,
            delta,
            flash_ref,
            flash_duration,
            floor_height_getter=get_floor_height,
        )
        flash_timer = flash_ref[0]

        frames = enemy_gifs[enemy_state]
        if int(time.time() * 8) % 2 == 0:
            enemy_frame_index += 1
        if enemy_frame_index >= len(frames):
            if enemy_state == "getting_up":
                enemy_state = "walking"
                enemy_frame_index = 0
            else:
                enemy_frame_index = 0

        sprite_width = int(game_view_w * 0.1)
        scale = sprite_width / frames[enemy_frame_index].width
        ray_engine.render_sprite(
            frames,
            enemy_frame_index,
            enemy_x,
            enemy_y,
            scale,
            depth_buffer,
            player_x,
            player_y,
            player_angle,
            bob_offset,
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
            door_sprite_scale = 1.12
            ray_engine.render_sprite(
                door_left_frames,
                door_frame_idx,
                left_sx,
                left_sy,
                door_sprite_scale,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
            )
            ray_engine.render_sprite(
                door_right_frames,
                door_frame_idx,
                right_sx,
                right_sy,
                door_sprite_scale,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
            )

        gun_y = game_view_h - GUN_BOTTOM_MARGIN - int(bob_offset * 0.35)
        if (not start_cutscene_active) and has_gun and selected_slot == 1:
            if reloading and reload_anim_active:
                pil_f = gunreload_frames_raw[min(reload_anim_index, len(gunreload_frames_raw) - 1)]
                gs = build_gun_surface_from_pil(pil_f)
            elif gunshoot_animating:
                pil_f = gunshoot_frames_raw[min(gunshoot_frame_index, len(gunshoot_frames_raw) - 1)]
                gs = build_gun_surface_from_pil(pil_f)
            else:
                gs = build_gun_surface_from_pil(gun_img_raw)
            game_surface.blit(gs, gs.get_rect(midbottom=(game_view_w // 2, gun_y)))

        blit_game_view_upscaled(game_surface, screen, W, H)

        hud_x = W - hud_w - 20
        hud_y = H - hud_h - 20
        draw_hud_base(
            screen,
            hud_img,
            hud_x,
            hud_y,
            hud_w,
            hud_h,
            font_hud,
            font_hud_big,
            font_clock,
            font_slot,
            ammo,
            max_ammo,
            hud_start_time,
            selected_slot,
            gunitem_img,
            True,
        )
        draw_boss_bar(screen, font_boss, enemy_state, enemy_health, enemy_max_health, W)

        pygame.draw.line(screen, (255, 255, 255), (W // 2 - 10, H // 2), (W // 2 + 10, H // 2), 2)
        pygame.draw.line(screen, (255, 255, 255), (W // 2, H // 2 - 10), (W // 2, H // 2 + 10), 2)

        if show_debug or get_show_fps():
            pygame.draw.rect(screen, (0, 0, 0), (5, 5, 220, 120), width=1)
            lines = [f"FPS: {fps_display}"]
            if show_debug:
                lines.extend(
                    [
                        f"RAYS: {game_view_w}",
                        f"SPRITES: {len(sprite_cache)}",
                        f"POS: {player_x:.2f} {player_y:.2f}",
                        f"ANGLE: {math.degrees(player_angle):.1f}",
                    ]
                )
            for i, line in enumerate(lines):
                screen.blit(font_debug.render(line, True, (0, 255, 0)), (10, 10 + i * 20))

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
                    try:
                        fintro = make_font(size)
                    except Exception:
                        fintro = font_intro
                    surf = fintro.render(shown, True, (0, 255, 136))
                    screen.blit(surf, (W // 2 - surf.get_width() // 2, H // 2 - surf.get_height() // 2))

        pygame.display.flip()

    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)
    pygame.quit()
    if next_action == "restart":
        return start_secret_maze(root)

