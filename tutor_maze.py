import math
import os
import random
import sys
import time
import wave

import pygame
from PIL import Image

from background_music import play_overlay_music, play_sound_effect, stop_overlay_music, update_music
from maze_pygame_common import GAME_VIEW_H, GAME_VIEW_W, blit_game_view_upscaled
from pause_menu import run_pause_menu
from raycast_engine import NUM_RAYS, RaycastEngine, draw_floor_ceiling, pil_to_surface
from statistics_window import StatisticsWindow
from elevator import Elevator
from user_settings import (
    get_flash_enabled,
    get_game_view_size,
    get_mouse_wheel_weapon_switch,
    get_show_debug_stats,
    get_show_fps,
    get_view_bob,
)

SPEED = 0.17
GUN_BOTTOM_MARGIN = -14
MOUSE_SENSITIVITY = 0.0035

MINIMAP_SCALE = 14

MAP = [
    ".........###............",
    "##########P#############",
    "#......................#",
    "#......................#",
    "#......................#",
    "#..................M...#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#......................#",
    "#.....................##",
    "#...................G.N#",
    "#.....................##",
    "#......................#",
    "#......................#",
    "########################",
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


def is_wall(x, y):
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


def wrap_angle(angle):
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


def get_wav_duration(path, fallback=1.0):
    try:
        with wave.open(path, "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if rate > 0:
                return frames / float(rate)
    except Exception:
        pass
    return fallback


def _make_font(size, bold=False):
    names = ("consolas", "couriernew", "courier", "lucidaconsole")
    for name in names:
        try:
            return pygame.font.SysFont(name, size, bold=bold)
        except Exception:
            continue
    return pygame.font.Font(None, size)


def start_tutor_maze(root=None):
    game_view_w, game_view_h = get_game_view_size()
    flash_enabled = get_flash_enabled()
    bob_strength = get_view_bob()
    allow_wheel_switch = get_mouse_wheel_weapon_switch()
    pygame.init()
    info = pygame.display.Info()
    W, H = info.current_w, info.current_h
    screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN | pygame.DOUBLEBUF)
    game_surface = pygame.Surface((game_view_w, game_view_h))
    pygame.display.set_caption("TRAINING_SIM")
    clock = pygame.time.Clock()
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    pygame.mouse.get_rel()

    font_title = _make_font(14, bold=True)
    font_hud = _make_font(16)
    font_hud_big = _make_font(18)
    font_clock = _make_font(13, bold=True)
    font_slot = _make_font(11)
    font_task = _make_font(18)
    font_intro = _make_font(42)
    font_boss = _make_font(20)
    font_debug = _make_font(14)

    intro_active = True
    intro_text = "CASE 0.0.0 /// TRAINING_SIM"
    intro_index = 0
    intro_start = time.time()
    intro_duration = 8
    pixel_size = 28
    pixel_grid = []
    for x in range(0, W, pixel_size):
        for y in range(0, H, pixel_size):
            pixel_grid.append([x, y, True])
    random.shuffle(pixel_grid)
    # Keep full pixel coordinates for the lift shake "fill" effect.
    pixel_grid_full = [(p[0], p[1]) for p in pixel_grid]
    pixel_grid = pixel_grid[:1200]
    fade_started = False

    hud_start_time = time.time()

    player_spawn_x = 10.5
    player_spawn_y = 2.5
    player_start_cutscene_offset = 2.0
    player_x = player_spawn_x - player_start_cutscene_offset
    player_y = player_spawn_y
    player_z = 0.0
    player_angle = 0.0
    start_door_anchor_x = player_x + math.cos(player_angle) * 0.62
    start_door_anchor_y = player_y + math.sin(player_angle) * 0.62

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

    TASK_ICON_SIZE = 44
    task_stub_src = Image.open(resource_path("data/unknown.png")).convert("RGBA")
    task_stub_img = pil_to_surface(task_stub_src.resize((TASK_ICON_SIZE, TASK_ICON_SIZE), Image.NEAREST))

    orb_textures = {
        "yellow": Image.open(resource_path("data/orbs/orb_yellow.png")).convert("RGBA"),
        "red": Image.open(resource_path("data/orbs/orb_red.png")).convert("RGBA"),
        "green": Image.open(resource_path("data/orbs/orb_green.png")).convert("RGBA"),
        "violet": Image.open(resource_path("data/orbs/orb_violet.png")).convert("RGBA"),
    }

    gunitem_raw = Image.open(resource_path("data/gunitem.png")).convert("RGBA")
    gunitem_raw = gunitem_raw.resize((40, 40), Image.NEAREST)
    gunitem_img = pil_to_surface(gunitem_raw)

    gun_pickup_img_src = Image.open(resource_path("data/unknown.png")).convert("RGBA")
    gun_pickup_frames = [gun_pickup_img_src]
    gun_pickup_scale = (int(game_view_w * 0.1)) / max(gun_pickup_img_src.width, 1)

    enemy_gifs = {
        "sitting": load_gif_frames(resource_path("data/gifs/cicada/cicadasitting.gif")),
        "getting_up": load_gif_frames(resource_path("data/gifs/cicada/cicadagettingup.gif")),
        "walking": load_gif_frames(resource_path("data/gifs/cicada/cicadawalking.gif")),
    }

    mannequin_frames = []
    for frame_idx in range(1, 10):
        frame_path = resource_path(f"data/gifs/mannequin/mannequin{frame_idx}.png")
        mannequin_frames.append(Image.open(frame_path).convert("RGBA"))
    mannequin_frame_index = 0
    mannequin_anim_acc = 0.0
    mannequin_x = None
    mannequin_y = None
    mannequin_health = 5
    mannequin_max_health = 5
    mannequin_alive = True
    mannequin_mode = "search"
    mannequin_search_interval = 3.0
    mannequin_next_search_move_at = time.time() + mannequin_search_interval
    mannequin_search_visited = set()
    mannequin_observe_distance = 5
    mannequin_hidden_active = False
    mannequin_wait_duration = 3.0
    mannequin_next_hidden_step_at = None
    mannequin_notice_radius = 5.0
    mannequin_shot_push_cooldown = 0.0
    mannequin_last_seen_by_player = False

    wall_tex = Image.open(resource_path("data/unknown.png")).convert("RGB")
    TEX_SIZE = 32
    wall_tex = wall_tex.resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)

    texture_column_cache = {}
    ray_engine = RaycastEngine(game_surface, game_view_w, game_view_h, wall_tex, TEX_SIZE)

    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "M":
                mannequin_x = x + 0.5
                mannequin_y = y + 0.5
                break
        if mannequin_x is not None:
            break
    if mannequin_x is not None and mannequin_y is not None:
        mannequin_search_visited.add((int(mannequin_x), int(mannequin_y)))
    mannequin_attack_sound_path = resource_path("data/gifs/mannequin/attackmannequin.wav")
    mannequin_attack_duration = get_wav_duration(mannequin_attack_sound_path, fallback=1.0)
    mannequin_restart_at = None

    lift_cells = []
    lift_tiles = set()
    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "N":
                lift_cells.append((x + 0.5, y + 0.5))
                lift_tiles.add((x, y))

    gun_pickups = []
    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            if c == "G":
                gun_pickups.append((x + 0.5, y + 0.5))

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

    orbs = [
        {"x": 5.5, "y": 5.5, "color": "yellow", "health": 20, "max_health": 20},
        {"x": 7.5, "y": 3.5, "color": "red", "health": 20, "max_health": 20},
        {"x": 9.5, "y": 6.5, "color": "green", "health": 20, "max_health": 20},
        {"x": 12.5, "y": 4.5, "color": "violet", "health": 20, "max_health": 20},
    ]

    keys = {"w": False, "s": False, "a": False, "d": False}
    selected_slot = 1
    ammo = 17
    max_ammo = 17
    reloading = False
    has_gun = False
    bob_phase = 0.0
    bob_offset = 0.0
    flash_timer = 0.0
    flash_duration = 0.08
    show_debug = get_show_debug_stats()
    last_frame_time = time.time()
    fps_display = 0
    fps_timer = 0.0
    
    # Statistics tracking
    total_shots_fired = 0
    total_shots_hit = 0  # Count of successful hits
    enemies_killed = 0  # Count of killed enemies

    gunshoot_animating = False
    gunshoot_frame_index = 0
    reload_anim_index = 0
    reload_anim_active = False
    shoot_acc = 0.0
    reload_acc = 0.0
    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, v))

    def _ease_out_cubic(x: float) -> float:
        x = _clamp01(x)
        return 1.0 - (1.0 - x) ** 3

    # Lift animation (symbol 'N')
    elevator_active = False
    elevator_start_time = 0.0
    elevator_from_angle = 0.0
    elevator_target_angle = 0.0
    elevator_close_t = 0.0
    elevator_transition_to_testing = False
    elevator_trigger_x = None
    elevator_trigger_y = None

    start_cutscene_active = True
    start_cutscene_started = False
    start_cutscene_start_time = 0.0
    start_cutscene_open_t = 0.0
    start_cutscene_close_t = 0.0

    # Elevator timeline (doors start closing immediately when elevator begins)
    # Rotation duration controls how fast camera turns.
    ELEV_ROT_DUR = 1.0
    ELEV_DOOR_CLOSE_DUR = 2.0  # doors approach each other for ~2s (reduced)
    ELEV_DOOR_HOLD_DUR = 2.0  # doors stay closed for a while (reduced)
    ELEV_SHAKE_DUR = 2.0  # shake/glitch + then transition (reduced)
    # Rotation overlaps with door closing, so total time is based on door+hold+shake.
    ELEV_TOTAL_DUR = ELEV_DOOR_CLOSE_DUR + ELEV_DOOR_HOLD_DUR + ELEV_SHAKE_DUR  # ~6 seconds total

    START_DOOR_OPEN_DUR = 0.55
    START_MOVE_DUR = 0.7
    START_DOOR_CLOSE_DUR = 0.45
    START_TOTAL_DUR = START_DOOR_OPEN_DUR + START_MOVE_DUR + START_DOOR_CLOSE_DUR

    # Statistics window
    stats_window_active = False
    elevator_enter_time = 0.0
    stats_font = _make_font(24)
    stats_font_small = _make_font(18)
    stats_animation_start = 0.0
    stats_window_y = 0.0
    stats_shake_offset = 0.0
    stats_float_offset_x = 0.0
    stats_float_offset_y = 0.0
    stats_float_time = 0.0
    
    # Statistics counting animation
    stats_counting_active = False
    stats_count_start = 0.0
    stats_flash_active = False
    stats_flash_start = 0.0
    stats_count_duration = 2.0  # Duration for counting animation
    stats_flash_duration = 0.3  # Duration for white flash
    stats_can_skip = False
    stats_completed = False
    
    # Post-flash icon animation
    stats_icon_active = False
    stats_icon_start = 0.0
    stats_icon_pulse_time = 0.0
    stats_icon_base_size = 48  # Increased from 32
    stats_icon_max_size = 72  # Increased from 48
    
    # Progress bar animation
    stats_progress_bar_target = 67  # Target percentage
    stats_progress_bar_current = 0.0

    door_left_tex = Image.open(resource_path("data/Lelevatordoor.png")).convert("RGBA")
    door_right_tex = Image.open(resource_path("data/Relevatordoor.png")).convert("RGBA")

    # Door frames are billboard sprites with dedicated left/right textures.
    DOOR_CLOSE_STEPS = 12
    DOOR_PIL_H = 64
    # Keep doors "thick" at the end; otherwise they become stripes.
    DOOR_PIL_W_MIN = 48
    DOOR_PIL_W_MAX = DOOR_PIL_H  # start open: roughly square
    door_left_frames = []
    door_right_frames = []
    for i in range(DOOR_CLOSE_STEPS):
        ct = i / max(1, DOOR_CLOSE_STEPS - 1)  # 0=open .. 1=closed
        # Make doors look like "closing panels": keep width mostly while moving,
        # and only start thinning near the very end. Otherwise they turn into stripes.
        ct_thin = _clamp01((ct - 0.65) / 0.35)
        w = int(DOOR_PIL_W_MAX * (1.0 - ct_thin) + DOOR_PIL_W_MIN * ct_thin)
        w = max(1, w)
        door_left_frames.append(door_left_tex.resize((w, DOOR_PIL_H), Image.NEAREST))
        door_right_frames.append(door_right_tex.resize((w, DOOR_PIL_H), Image.NEAREST))

    running = True

    def build_gun_surface_from_pil(pil_frame):
        w, h = pil_frame.size
        new_w = int(game_view_w * GUN_SCALE)
        new_h = int(h * (new_w / w))
        return pil_to_surface(pil_frame.resize((new_w, new_h), Image.NEAREST))

    def shoot_gun():
        nonlocal gunshoot_animating, gunshoot_frame_index, ammo, flash_timer, reloading, shoot_acc
        nonlocal total_shots_fired, total_shots_hit, enemies_killed
        nonlocal mannequin_health, mannequin_alive, mannequin_mode, mannequin_observe_distance
        nonlocal mannequin_hidden_active, mannequin_shot_push_cooldown, mannequin_next_hidden_step_at
        nonlocal mannequin_last_seen_by_player
        if selected_slot != 1:
            return
        if not has_gun or gunshoot_animating or reloading:
            return
        if ammo <= 0:
            start_reload()
            return
        ammo -= 1
        total_shots_fired += 1  # Increment shot counter
        flash_timer = flash_duration
        gunshoot_animating = True
        gunshoot_frame_index = 0
        shoot_acc = 0.0

        if mannequin_alive and mannequin_mode == "observe" and player_can_see_mannequin():
            dx = mannequin_x - player_x
            dy = mannequin_y - player_y
            dist = math.hypot(dx, dy)
            angle_to_mannequin = math.atan2(dy, dx)
            angle_diff = wrap_angle(angle_to_mannequin - player_angle)
            if abs(angle_diff) < 0.05 and dist < 8.5 and has_line_of_sight(player_x, player_y, mannequin_x, mannequin_y):
                mannequin_health -= 1
                total_shots_hit += 1
                mannequin_hidden_active = False
                mannequin_next_hidden_step_at = None
                mannequin_last_seen_by_player = True
                if mannequin_health <= 0:
                    mannequin_alive = False
                    enemies_killed += 1
                elif mannequin_shot_push_cooldown <= 0.0:
                    push_mannequin_back()
                    mannequin_shot_push_cooldown = 0.12

        # Check if cursor hits any orb
        for orb in orbs:
            dx = orb["x"] - player_x
            dy = orb["y"] - player_y
            dist = math.hypot(dx, dy)
            angle_to_orb = math.atan2(dy, dx)
            angle_diff = wrap_angle(angle_to_orb - player_angle)
            
            # Check if shot hits orb
            if abs(angle_diff) < 0.05 and dist < 8 and orb["health"] > 0:
                orb["health"] -= 10  # Deal 10 damage
                total_shots_hit += 1  # Increment hit counter
                print(f"Hit {orb['color']} orb! HP: {orb['health']}/{orb['max_health']}")  # Debug info
                if orb["health"] <= 0:
                    enemies_killed += 1  # Increment kill counter
                    print(f"{orb['color']} orb destroyed! Total kills: {enemies_killed}")  # Debug info

    def start_reload():
        nonlocal reloading, reload_anim_active, reload_anim_index, reload_acc, ammo
        if reloading or not has_gun:
            return
        reloading = True
        reload_anim_active = True
        reload_anim_index = 0
        reload_acc = 0.0

    # Fonts dictionary for statistics window
    fonts = {
        'title': _make_font(24),
        'small': _make_font(18),
        'main': _make_font(18)
    }

    # Elevator and statistics window instances
    elevator = Elevator(player_angle)
    stats = {
        'enemies_killed': 0,
        'total_shots_fired': 0,
        'total_shots_hit': 0
    }
    statistics_window = StatisticsWindow(W, H, 0, stats, fonts, resource_path)
    next_action = None

    def has_line_of_sight(x1, y1, x2, y2, step=0.1):
        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)
        if dist <= 0.01:
            return True
        steps = max(1, int(dist / step))
        for i in range(1, steps):
            px = x1 + dx * (i / steps)
            py = y1 + dy * (i / steps)
            if is_wall(px, py):
                return False
        return True

    def is_walkable_cell(cell_x, cell_y):
        if cell_x < 0 or cell_y < 0:
            return False
        if cell_y >= len(MAP) or cell_x >= len(MAP[0]):
            return False
        return MAP[cell_y][cell_x] != "#"

    def candidate_cells_around_player(preferred_dist, prefer_behind=False, require_los=True):
        back_x = -math.cos(player_angle)
        back_y = -math.sin(player_angle)
        for radius in range(preferred_dist, 0, -1):
            ring = []
            for cell_y in range(len(MAP)):
                for cell_x in range(len(MAP[0])):
                    if not is_walkable_cell(cell_x, cell_y):
                        continue
                    center_x = cell_x + 0.5
                    center_y = cell_y + 0.5
                    if math.hypot(center_x - player_x, center_y - player_y) < 0.75:
                        continue
                    actual_dist = math.hypot(center_x - player_x, center_y - player_y)
                    if abs(actual_dist - radius) > 0.75:
                        continue
                    if require_los and not has_line_of_sight(center_x, center_y, player_x, player_y):
                        continue
                    to_cell_x = center_x - player_x
                    to_cell_y = center_y - player_y
                    dot = 0.0
                    vec_len = math.hypot(to_cell_x, to_cell_y)
                    if vec_len > 0:
                        dot = (to_cell_x / vec_len) * back_x + (to_cell_y / vec_len) * back_y
                    current_offset = math.hypot(center_x - mannequin_x, center_y - mannequin_y) if mannequin_x is not None and mannequin_y is not None else 0.0
                    visibility_penalty = 0 if has_line_of_sight(center_x, center_y, player_x, player_y) else 1
                    ring.append((dot, abs(actual_dist - radius), visibility_penalty, -current_offset, center_x, center_y, radius))
            if ring:
                if prefer_behind:
                    ring.sort(key=lambda item: (-item[0], item[2], item[1], item[3]))
                else:
                    ring.sort(key=lambda item: (item[1], item[2], item[3], -item[0]))
                return ring
        return []

    def place_mannequin_for_observation(preferred_dist, prefer_behind=False):
        nonlocal mannequin_x, mannequin_y, mannequin_observe_distance
        ring = candidate_cells_around_player(preferred_dist, prefer_behind=prefer_behind, require_los=True)
        if not ring:
            return False
        _, _, _, _, mannequin_x, mannequin_y, used_radius = ring[0]
        mannequin_observe_distance = used_radius
        return True

    def place_mannequin_behind_player(preferred_dist):
        nonlocal mannequin_x, mannequin_y, mannequin_observe_distance
        ring = candidate_cells_around_player(preferred_dist, prefer_behind=True, require_los=False)
        if not ring:
            return False
        _, _, _, _, mannequin_x, mannequin_y, used_radius = ring[0]
        mannequin_observe_distance = used_radius
        return True

    def get_mannequin_frame_index():
        if mannequin_x is None or mannequin_y is None:
            return 0
        viewer_angle = math.atan2(player_y - mannequin_y, player_x - mannequin_x)
        sector_size = (2 * math.pi) / len(mannequin_frames)
        sector = int((viewer_angle % (2 * math.pi)) / sector_size) % len(mannequin_frames)
        return sector

    def player_can_see_mannequin():
        if not mannequin_alive or mannequin_x is None or mannequin_y is None:
            return False
        dx = mannequin_x - player_x
        dy = mannequin_y - player_y
        angle_diff = wrap_angle(math.atan2(dy, dx) - player_angle)
        if abs(angle_diff) > math.radians(30):
            return False
        return has_line_of_sight(player_x, player_y, mannequin_x, mannequin_y)

    def mannequin_can_see_player():
        if not mannequin_alive or mannequin_x is None or mannequin_y is None:
            return False
        if math.hypot(mannequin_x - player_x, mannequin_y - player_y) > mannequin_notice_radius:
            return False
        return has_line_of_sight(mannequin_x, mannequin_y, player_x, player_y)

    def move_mannequin_search():
        nonlocal mannequin_x, mannequin_y
        if mannequin_x is None or mannequin_y is None:
            return
        current_cell = (int(mannequin_x), int(mannequin_y))
        options = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx = current_cell[0] + dx
            ny = current_cell[1] + dy
            if not is_walkable_cell(nx, ny):
                continue
            score = 0
            if (nx, ny) not in mannequin_search_visited:
                score += 10
            score += random.random()
            player_dist = math.hypot((nx + 0.5) - player_x, (ny + 0.5) - player_y)
            score += min(player_dist, 6.0) * 0.15
            options.append((score, nx, ny))
        if not options:
            return
        options.sort(reverse=True)
        _, nx, ny = options[0]
        mannequin_x = nx + 0.5
        mannequin_y = ny + 0.5
        mannequin_search_visited.add((nx, ny))

    def switch_mannequin_to_observe():
        nonlocal mannequin_mode, mannequin_hidden_active, mannequin_next_hidden_step_at
        nonlocal mannequin_observe_distance, mannequin_last_seen_by_player
        mannequin_mode = "observe"
        mannequin_hidden_active = False
        mannequin_next_hidden_step_at = None
        mannequin_last_seen_by_player = False
        mannequin_observe_distance = min(5, max(1, mannequin_observe_distance))
        if not place_mannequin_for_observation(mannequin_observe_distance, prefer_behind=False):
            place_mannequin_for_observation(1, prefer_behind=False)

    def teleport_mannequin_behind(distance):
        nonlocal mannequin_observe_distance
        if place_mannequin_behind_player(distance):
            mannequin_observe_distance = distance
            return True
        for fallback_dist in range(distance - 1, 0, -1):
            if place_mannequin_behind_player(fallback_dist):
                mannequin_observe_distance = fallback_dist
                return True
        if place_mannequin_for_observation(distance, prefer_behind=False):
            return True
        for fallback_dist in range(distance - 1, 0, -1):
            if place_mannequin_for_observation(fallback_dist, prefer_behind=False):
                return True
        return False

    def update_mannequin(delta_time):
        nonlocal mannequin_mode, mannequin_hidden_active, mannequin_observe_distance
        nonlocal mannequin_shot_push_cooldown, mannequin_next_search_move_at, mannequin_next_hidden_step_at
        nonlocal running, next_action, mannequin_last_seen_by_player
        if not mannequin_alive or elevator_active or stats_window_active or intro_active or start_cutscene_active:
            return
        now = time.time()
        if mannequin_restart_at is not None:
            return
        mannequin_shot_push_cooldown = max(0.0, mannequin_shot_push_cooldown - delta_time)

        if mannequin_mode == "search":
            if mannequin_can_see_player():
                switch_mannequin_to_observe()
                return
            if now >= mannequin_next_search_move_at:
                move_mannequin_search()
                mannequin_next_search_move_at = now + mannequin_search_interval
                if mannequin_can_see_player():
                    switch_mannequin_to_observe()
            return

        visible_to_player = player_can_see_mannequin()
        if visible_to_player:
            mannequin_hidden_active = False
            mannequin_next_hidden_step_at = None
            mannequin_last_seen_by_player = True
            return

        if not mannequin_last_seen_by_player:
            if mannequin_hidden_active and mannequin_next_hidden_step_at is not None and now >= mannequin_next_hidden_step_at:
                next_distance = max(1, mannequin_observe_distance - 1)
                if teleport_mannequin_behind(next_distance):
                    mannequin_observe_distance = next_distance
                if mannequin_observe_distance <= 1:
                    trigger_mannequin_attack(now)
                    return
                mannequin_next_hidden_step_at = now + mannequin_wait_duration
            return

        mannequin_last_seen_by_player = False
        if not mannequin_hidden_active:
            next_distance = max(1, mannequin_observe_distance - 1)
            if teleport_mannequin_behind(next_distance):
                mannequin_observe_distance = next_distance
            if mannequin_observe_distance <= 1:
                trigger_mannequin_attack(now)
                return
            mannequin_hidden_active = True
            mannequin_next_hidden_step_at = now + mannequin_wait_duration
            return

        if mannequin_next_hidden_step_at is None:
            mannequin_next_hidden_step_at = now + mannequin_wait_duration
            return

        if now >= mannequin_next_hidden_step_at:
            next_distance = max(1, mannequin_observe_distance - 1)
            if teleport_mannequin_behind(next_distance):
                mannequin_observe_distance = next_distance
            if mannequin_observe_distance <= 1:
                trigger_mannequin_attack(now)
                return
            mannequin_next_hidden_step_at = now + mannequin_wait_duration

    def push_mannequin_back():
        nonlocal mannequin_x, mannequin_y, mannequin_observe_distance
        current_dist = math.hypot(mannequin_x - player_x, mannequin_y - player_y)
        target_dist = min(5, max(mannequin_observe_distance, int(round(current_dist)) + 1))
        ring = candidate_cells_around_player(target_dist, prefer_behind=True, require_los=False)
        if ring:
            _, _, _, _, next_x, next_y, used_radius = ring[0]
            next_dist = math.hypot(next_x - player_x, next_y - player_y)
            if next_dist >= current_dist - 0.01:
                mannequin_x = next_x
                mannequin_y = next_y
                mannequin_observe_distance = used_radius
                return

        ring = candidate_cells_around_player(target_dist, prefer_behind=False, require_los=True)
        if not ring:
            return
        _, _, _, _, next_x, next_y, used_radius = ring[0]
        next_dist = math.hypot(next_x - player_x, next_y - player_y)
        if next_dist < current_dist - 0.01:
            return
        mannequin_x = next_x
        mannequin_y = next_y
        mannequin_observe_distance = used_radius

    def trigger_mannequin_attack(now):
        nonlocal mannequin_restart_at
        if mannequin_restart_at is not None:
            return
        play_sound_effect(mannequin_attack_sound_path)
        mannequin_restart_at = now + max(0.2, mannequin_attack_duration)

    while running:
        delta = clock.tick(120) / 1000.0
        update_music(delta)
        if delta <= 0:
            delta = 1.0 / 60.0
        now = time.time()
        if mannequin_restart_at is not None and now >= mannequin_restart_at:
            next_action = "restart"
            running = False
            continue
        fps_timer += delta
        if fps_timer > 0.2:
            fps_display = int(1.0 / delta) if delta > 0 else 0
            fps_timer = 0.0
        last_frame_time = now

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
                    continue
                if stats_window_active:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        if stats_completed:
                            stop_overlay_music(fade_ms=900, restore_background=False)
                            elevator_transition_to_testing = True
                            running = False
                            stats_window_active = False
                            elevator_active = False  # Stop elevator only after OK
                    continue
                if mannequin_restart_at is not None:
                    continue
                # Allow movement only when elevator is not active and stats are not shown
                if elevator_active or start_cutscene_active:
                    continue
                elif event.unicode in "12345":
                    selected_slot = int(event.unicode)
                elif event.key == pygame.K_r:
                    start_reload()
                elif event.key == pygame.K_f:
                    show_debug = not show_debug
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if elevator_active or stats_window_active or start_cutscene_active:
                    if stats_window_active and stats_can_skip and not stats_completed:
                        # Skip animation with mouse click
                        stats_completed = True
                        if flash_enabled:
                            stats_flash_active = True
                            stats_flash_start = time.time()
                        else:
                            stats_flash_active = False
                            stats_icon_active = True
                            stats_icon_start = time.time()
                            stats_icon_pulse_time = 0.0
                        stats_counting_active = False
                    continue
                if mannequin_restart_at is not None:
                    continue
                if event.button == 1:
                    shoot_gun()
            elif event.type == pygame.MOUSEWHEEL:
                if elevator_active or stats_window_active or start_cutscene_active or mannequin_restart_at is not None or not allow_wheel_switch:
                    continue
                if event.y > 0:
                    selected_slot -= 1
                else:
                    selected_slot += 1
                if selected_slot < 1:
                    selected_slot = 5
                if selected_slot > 5:
                    selected_slot = 1

        if mannequin_restart_at is not None:
            bob_offset = 0
            move_x = 0.0
            move_y = 0.0
            moving = False
        elif start_cutscene_active:
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

            bob_offset = 0
            move_x = 0.0
            move_y = 0.0
            moving = False
        elif elevator_active:
            # Freeze player controls and drive the lift camera.
            elapsed = time.time() - elevator_start_time
            # Camera rotates for a short time; meanwhile doors start closing immediately.
            if elapsed < ELEV_ROT_DUR:
                ratio = elapsed / ELEV_ROT_DUR
                player_angle = elevator_from_angle + math.pi * _ease_out_cubic(ratio)
            else:
                player_angle = elevator_target_angle

            # Door closing starts immediately (t=0) and clamps at 1.0.
            elevator_close_t = _clamp01(elapsed / ELEV_DOOR_CLOSE_DUR)

            bob_offset = 0
            if elapsed >= ELEV_TOTAL_DUR and not stats_window_active:
                # Show statistics window instead of direct transition
                stats_window_active = True
                stats_animation_start = time.time()
                stats_counting_active = True
                stats_count_start = time.time()
                stats_can_skip = True
                # Don't stop elevator - keep the glitch effects going
                # elevator_active = False  # Keep this True to maintain shake/pixels
        else:
            k = pygame.key.get_pressed()
            keys["w"] = k[pygame.K_w]
            keys["s"] = k[pygame.K_s]
            keys["a"] = k[pygame.K_a]
            keys["d"] = k[pygame.K_d]

            move_x = 0.0
            move_y = 0.0
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

            mouse_dx = pygame.mouse.get_rel()[0]
            if mouse_dx:
                player_angle = wrap_angle(player_angle + mouse_dx * MOUSE_SENSITIVITY)

            # Trigger lift when player is inside 'N' tile.
            # Tile-based trigger is more stable than a distance radius.
            if (not intro_active) and lift_tiles and not elevator_active and not stats_window_active:
                tx = int(player_x)
                ty = int(player_y)
                if 0 <= ty < len(MAP) and 0 <= tx < len(MAP[0]) and MAP[ty][tx] == "N":
                    cutscene_forwardstep = 0.32
                    player_x -= math.cos(player_angle) * cutscene_forwardstep
                    player_y -= math.sin(player_angle) * cutscene_forwardstep
                    elevator_active = True
                    elevator_start_time = time.time()
                    elevator_enter_time = time.time() - hud_start_time  # Save time when player entered lift
                    elevator_from_angle = player_angle
                    elevator_target_angle = elevator_from_angle + math.pi
                    elevator_trigger_x = tx + 0.5
                    elevator_trigger_y = ty + 0.5
                    elevator_close_t = 0.0
                    play_overlay_music(resource_path("data/music/LocalCodepastElevator.wav"), fade_ms=1200)

            if elevator_active:
                # Start lift; skip movement for this frame.
                moving = False
                bob_offset = 0
                move_x = 0.0
                move_y = 0.0

        for lk in light_states:
            if time.time() - light_timers[lk] > random.uniform(0.05, 0.3):
                light_timers[lk] = time.time()
                if random.random() < 0.2:
                    light_states[lk] = not light_states[lk]

        if not elevator_active and not stats_window_active and not start_cutscene_active:
            nx = player_x + move_x
            ny = player_y + move_y
            tx = int(nx)
            ty = int(ny)
            in_bounds = 0 <= ty < len(MAP) and 0 <= tx < len(MAP[0])

            # If movement would put the player on 'N', start elevator right now.
            # This check is now handled above to prevent duplication

            cell = MAP[ty][tx] if in_bounds else "#"

            if cell != "#":
                player_x = nx
                player_y = ny
                # Лестницы убраны: символ 'L' теперь просто проходной пол,
                # высота камеры (player_z) не меняется.
                player_z = 0.0

                if not is_wall(nx, ny):
                    player_x = nx
                    player_y = ny

                if moving:
                    bob_phase += 0.25
                    bob_offset = math.sin(bob_phase) * 10 * bob_strength
                else:
                    bob_offset = 0

        cell = MAP[int(player_y)][int(player_x)]
        PICKUP_GUN_RADIUS = 0.55
        if gun_pickups:
            kept = []
            for gx, gy in gun_pickups:
                if math.hypot(player_x - gx, player_y - gy) < PICKUP_GUN_RADIUS:
                    has_gun = True
                else:
                    kept.append((gx, gy))
            gun_pickups = kept

        update_mannequin(delta)

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

        t = time.time()
        texture_column_cache.clear()
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
        )
        flash_timer = flash_ref[0]

        if mannequin_alive:
            mannequin_frame_index = get_mannequin_frame_index()
            ray_engine.render_sprite(
                mannequin_frames,
                mannequin_frame_index,
                mannequin_x,
                mannequin_y,
                0.85,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
            )

        for gx, gy in gun_pickups:
            ray_engine.render_sprite(
                gun_pickup_frames,
                0,
                gx,
                gy,
                gun_pickup_scale,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
            )
        for orb in orbs:
            # Only render orb if alive
            if orb["health"] > 0:
                ray_engine.render_orb(
                    orb,
                    orb_textures,
                    depth_buffer,
                    player_x,
                    player_y,
                    player_angle,
                    bob_offset,
                    sprite_cache,
                )

        # Render lift doors (billboard planes) during the whole elevator sequence.
        # We render even at elevator_close_t == 0 to avoid "nothing happens" frames.
        if start_cutscene_active:
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

            half_sep_open = 0.88
            half_sep_closed = 0.17
            half_sep = half_sep_open + (half_sep_closed - half_sep_open) * door_progress

            center_x = start_door_anchor_x
            center_y = start_door_anchor_y
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
        elif elevator_active:
            fwd_x = math.cos(player_angle)
            fwd_y = math.sin(player_angle)
            right_x = -fwd_y
            right_y = fwd_x

            # Make doors visibly slide in from the left/right edges and stop with a tiny gap.
            door_progress = _ease_out_cubic(elevator_close_t)
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

            door_frame_idx = int(elevator_close_t * (len(door_left_frames) - 1))
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

        if (not elevator_active) and (not start_cutscene_active) and has_gun and selected_slot == 1:
            if reloading and reload_anim_active:
                pil_f = gunreload_frames_raw[min(reload_anim_index, len(gunreload_frames_raw) - 1)]
                gs = build_gun_surface_from_pil(pil_f)
            elif gunshoot_animating:
                pil_f = gunshoot_frames_raw[min(gunshoot_frame_index, len(gunshoot_frames_raw) - 1)]
                gs = build_gun_surface_from_pil(pil_f)
            else:
                gs = build_gun_surface_from_pil(gun_img_raw)
            game_surface.blit(gs, gs.get_rect(midbottom=(game_view_w // 2, gun_y)))

        # Shake the view only after doors are closed and the hold phase ends.
        # Continue shaking while stats window is active
        if elevator_active or stats_window_active:
            if elevator_start_time > 0:
                elapsed = time.time() - elevator_start_time
            else:
                elapsed = 0
            # Start shaking immediately after doors are closed.
            shake_start = ELEV_DOOR_CLOSE_DUR
            if elapsed >= shake_start:
                # Let the "fill pixels" reach 100% right before teleport.
                shake_dur_effective = max(1e-6, ELEV_TOTAL_DUR - shake_start)
                ratio = _clamp01((elapsed - shake_start) / shake_dur_effective)
                if ratio >= 1.0 and stats_window_active:
                    # Keep maximum shake while stats window is active
                    ratio = 1.0
                shake_px = int(2 + ratio * 3)
                scaled = pygame.transform.scale(game_surface, (W, H))
                ox = random.randint(-shake_px, shake_px)
                oy = random.randint(-shake_px, shake_px)
                screen.blit(scaled, (ox, oy))

                # "Anti-intro" pixels: show pixels like intro glitch,
                # but fill the screen instead of disappearing.
                fill_ratio = _clamp01(ratio**0.35)  # faster fill
                if ratio >= 1.0 and stats_window_active:
                    # Keep full pixel coverage while stats window is active
                    fill_ratio = 1.0
                fill_count = int(len(pixel_grid_full) * fill_ratio)
                stride = 2 if fill_count > 900 else 1
                extra = int(160 * fill_ratio)
                for i in range(0, fill_count, stride):
                    x, y = pixel_grid_full[i]
                    shade = random.randint(0, 120) + extra
                    # Pygame requires 0..255 per channel.
                    shade = max(0, min(255, shade))
                    pygame.draw.rect(
                        screen,
                        (int(shade), int(shade), int(shade)),
                        (x + ox, y + oy, pixel_size, pixel_size),
                    )
            else:
                blit_game_view_upscaled(game_surface, screen, W, H)
        else:
            blit_game_view_upscaled(game_surface, screen, W, H)

        task_margin = 20
        task_pad = 10
        task_box_w = 340
        task_box_h = 92
        task_x1 = task_margin
        task_y1 = task_margin
        pygame.draw.rect(screen, (5, 8, 5), (task_x1, task_y1, task_box_w, task_box_h), width=2)
        screen.blit(font_title.render("TASK", True, (0, 255, 0)), (task_x1 + task_pad, task_y1 + task_pad))
        screen.blit(task_stub_img, (task_x1 + task_pad, task_y1 + 32))
        screen.blit(
            font_task.render("FIND A WEAPON", True, (0, 255, 0)),
            (task_x1 + task_pad + TASK_ICON_SIZE + 10, task_y1 + 32 + TASK_ICON_SIZE // 2 - 10),
        )

        hud_x = W - hud_w - 20
        hud_y = H - hud_h - 20
        screen.blit(hud_img, (hud_x, hud_y))
        screen.blit(font_hud.render("AMMO:", True, (0, 255, 0)), (hud_x + 26, hud_y + 28))
        screen.blit(font_hud_big.render(f"{ammo}/{max_ammo}", True, (0, 255, 0)), (hud_x + 23, hud_y + 48))

        hp_percent = 1.0
        max_blocks = 10
        filled_blocks = int(max_blocks * hp_percent)
        block_size = 10
        block_spacing = 3
        start_hp_x = hud_x + hud_w // 2 + 20
        start_hp_y = hud_y + 40
        for i in range(max_blocks):
            x = start_hp_x + i * (block_size + block_spacing)
            y = start_hp_y
            col = (255, 0, 0) if i < filled_blocks else (34, 0, 0)
            pygame.draw.rect(screen, col, (x, y, block_size, block_size), width=1)
        screen.blit(font_hud.render("HP:", True, (0, 255, 0)), (start_hp_x, start_hp_y - 10))

        elapsed = time.time() - hud_start_time
        minutes = int(elapsed // 60) % 60
        seconds = int(elapsed % 60)
        milliseconds = int((elapsed % 1) * 1000)
        time_text = f"{minutes:02}:{seconds:02}:{milliseconds:03}"
        clock_offset_x = 30
        clock_offset_y = hud_h - 55
        clock_width = 80
        clock_height = 28
        pygame.draw.rect(
            screen,
            (0, 0, 0),
            (hud_x + clock_offset_x, hud_y + clock_offset_y, clock_width, clock_height),
            width=2,
        )
        tsurf = font_clock.render(time_text, True, (0, 255, 0))
        screen.blit(
            tsurf,
            (
                hud_x + clock_offset_x + clock_width // 2 - tsurf.get_width() // 2,
                hud_y + clock_offset_y + clock_height // 2 - tsurf.get_height() // 2,
            ),
        )

        slot_size = 32
        slot_spacing = 6
        start_x = hud_x + hud_w // 2 - (2 * slot_size + 1.5 * slot_spacing)
        start_y = hud_y + hud_h - slot_size - 35
        for i in range(5):
            x = start_x + i * (slot_size + slot_spacing)
            y = start_y
            if (i + 1) == selected_slot:
                pygame.draw.rect(screen, (255, 255, 0), (x - 2, y - 2, slot_size + 4, slot_size + 4), width=2)
            pygame.draw.rect(screen, (102, 102, 102), (x, y, slot_size, slot_size), width=2)
            ns = font_slot.render(str(i + 1), True, (0, 255, 0))
            screen.blit(ns, (x + slot_size // 2 - ns.get_width() // 2, y + slot_size + 10))
        if has_gun:
            screen.blit(gunitem_img, gunitem_img.get_rect(center=(start_x + slot_size // 2, start_y + slot_size // 2)))

        if mannequin_alive and mannequin_mode == "observe" and player_can_see_mannequin():
            mannequin_bar_w = 140
            mannequin_bar_h = 16
            mannequin_bar_x = W // 2 - mannequin_bar_w // 2
            mannequin_bar_y = H // 2 - 90
            pygame.draw.rect(screen, (25, 0, 0), (mannequin_bar_x, mannequin_bar_y, mannequin_bar_w, mannequin_bar_h))
            fill_w = int(mannequin_bar_w * (mannequin_health / max(1, mannequin_max_health)))
            pygame.draw.rect(screen, (220, 40, 40), (mannequin_bar_x, mannequin_bar_y, fill_w, mannequin_bar_h))
            pygame.draw.rect(screen, (255, 255, 255), (mannequin_bar_x, mannequin_bar_y, mannequin_bar_w, mannequin_bar_h), width=2)
            label = font_hud.render("MANNEQUIN", True, (255, 255, 255))
            screen.blit(label, (W // 2 - label.get_width() // 2, mannequin_bar_y - 20))

        pygame.draw.line(screen, (255, 255, 255), (W // 2 - 10, H // 2), (W // 2 + 10, H // 2), 2)
        pygame.draw.line(screen, (255, 255, 255), (W // 2, H // 2 - 10), (W // 2, H // 2 + 10), 2)

        if show_debug or get_show_fps():
            pygame.draw.rect(screen, (0, 0, 0), (5, 5, 220, 120), width=1)
            dbg = [f"FPS: {fps_display}"]
            if show_debug:
                dbg.extend(
                    [
                        f"RAYS: {game_view_w}",
                        f"SPRITES: {len(sprite_cache)}",
                        f"POS: {player_x:.2f} {player_y:.2f}",
                        f"ANGLE: {math.degrees(player_angle):.1f}",
                        f"MANNEQUIN: {mannequin_mode} {mannequin_health}/{mannequin_max_health}",
                    ]
                )
            for i, line in enumerate(dbg):
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
                        fintro = _make_font(size)
                    except Exception:
                        fintro = font_intro
                    surf = fintro.render(shown, True, (0, 255, 136))
                    screen.blit(surf, (W // 2 - surf.get_width() // 2, H // 2 - surf.get_height() // 2))

        # Draw statistics window
        if stats_window_active:
            # Handle counting animation
            if stats_counting_active:
                count_elapsed = time.time() - stats_count_start
                if count_elapsed >= stats_count_duration:
                    stats_counting_active = False
                    stats_completed = True
                    if flash_enabled:
                        stats_flash_active = True
                        stats_flash_start = time.time()
                    else:
                        stats_flash_active = False
                        stats_icon_active = True
                        stats_icon_start = time.time()
                        stats_icon_pulse_time = 0.0
                    
            # Handle flash animation
            if stats_flash_active:
                flash_elapsed = time.time() - stats_flash_start
                if flash_elapsed >= stats_flash_duration:
                    stats_flash_active = False
                    stats_icon_active = True
                    stats_icon_start = time.time()
                    stats_icon_pulse_time = 0.0
            
            # Calculate window animation only if not already started
            if stats_animation_start == 0.0:
                stats_animation_start = time.time()
            
            anim_elapsed = time.time() - stats_animation_start
            anim_duration = 1.2  # Animation duration in seconds
            
            # Slide down animation (ease out cubic)
            slide_progress = _clamp01(anim_elapsed / anim_duration)
            slide_eased = _ease_out_cubic(slide_progress)
            
            # Shake effect (starts after slide is mostly complete)
            shake_intensity = 0.0
            if slide_progress > 0.3:  # Start shake earlier to sync with screen shake
                shake_progress = (slide_progress - 0.3) / 0.7  # Normalize to 0-1
                # Stronger shake to match the screen glitch effect
                shake_intensity = math.sin(shake_progress * math.pi * 4) * 5.0 * (1.0 - shake_progress * 0.5)
                stats_shake_offset = random.uniform(-shake_intensity, shake_intensity)
            
            # Floating movement effect (continuous smooth movement)
            stats_float_time += delta
            float_speed = 2.0  # Speed of floating
            float_amplitude_x = 3.0  # Horizontal floating amplitude
            float_amplitude_y = 2.0  # Vertical floating amplitude
            stats_float_offset_x = math.sin(stats_float_time * float_speed) * float_amplitude_x
            stats_float_offset_y = math.sin(stats_float_time * float_speed * 1.3 + math.pi/4) * float_amplitude_y
            
            # Window dimensions and position
            window_w = 500
            window_h = 400
            target_y = H // 2 - window_h // 2
            start_y = -window_h  # Start above screen
            
            # Calculate current Y position with animation and floating
            stats_window_y = start_y + (target_y - start_y) * slide_eased + stats_shake_offset + stats_float_offset_y
            window_x = W // 2 - window_w // 2 + stats_float_offset_x
            window_y = stats_window_y  # Make window_y available for icon animation
            
            # Only show window when pixels are appearing (sync with elevator glitch effect)
            # Use the saved elevator start time for consistent calculation
            if elevator_start_time > 0:
                elevator_elapsed = time.time() - elevator_start_time
                pixel_fill_ratio = 0.0
                # Show window when shake starts (same time as pixels)
                if elevator_elapsed >= (ELEV_DOOR_CLOSE_DUR + ELEV_DOOR_HOLD_DUR):
                    shake_start = ELEV_DOOR_CLOSE_DUR
                    shake_dur_effective = max(1e-6, ELEV_TOTAL_DUR - shake_start)
                    ratio = _clamp01((elevator_elapsed - shake_start) / shake_dur_effective)
                    pixel_fill_ratio = _clamp01(ratio**0.35)
                    # When stats window is active, keep full pixel coverage
                    if stats_window_active:
                        pixel_fill_ratio = 1.0
            else:
                pixel_fill_ratio = 1.0  # Fallback
            
            # Draw window when pixels start appearing (during the glitch effect)
            # Use lower threshold to appear earlier with the pixels
            if pixel_fill_ratio > 0.01 and slide_progress > 0.01:
                # White flash effect
                if flash_enabled and stats_flash_active:
                    flash_alpha = int(255 * (1.0 - (time.time() - stats_flash_start) / stats_flash_duration))
                    flash_surface = pygame.Surface((W, H))
                    flash_surface.set_alpha(flash_alpha)
                    flash_surface.fill((255, 255, 255))
                    screen.blit(flash_surface, (0, 0))
                
                # Darken background
                dark_surface = pygame.Surface((W, H))
                dark_surface.set_alpha(int(180 * slide_progress))
                dark_surface.fill((0, 0, 0))
                screen.blit(dark_surface, (0, 0))
                
                # Window border
                pygame.draw.rect(screen, (0, 255, 0), (window_x, stats_window_y, window_w, window_h), width=3)
                pygame.draw.rect(screen, (0, 0, 0), (window_x + 3, stats_window_y + 3, window_w - 6, window_h - 6))
                
                # Title
                title_text = "LEVEL COMPLETE"
                title_surf = stats_font.render(title_text, True, (0, 255, 0))
                screen.blit(title_surf, (window_x + window_w // 2 - title_surf.get_width() // 2, stats_window_y + 30))
                
                # Statistics with counting animation
                stats_y = stats_window_y + 80
                line_height = 35
                
                # Calculate animated values
                if stats_counting_active:
                    count_elapsed = time.time() - stats_count_start
                    count_progress = _clamp01(count_elapsed / stats_count_duration)
                    # Time entry animation
                    current_time = elevator_enter_time * count_progress
                    # Other stats animation
                    enemies_defeated = int(enemies_killed * count_progress)
                    items_collected = int(1 * count_progress)
                    shots_fired = int(total_shots_fired * count_progress)
                    shots_hit = int(total_shots_hit * count_progress)
                    accuracy = int((total_shots_hit / max(1, total_shots_fired)) * 100) * count_progress if total_shots_fired > 0 else 0
                    # Progress bar animation
                    stats_progress_bar_current = stats_progress_bar_target * count_progress
                else:
                    # Final values
                    current_time = elevator_enter_time
                    enemies_defeated = enemies_killed
                    items_collected = 1
                    shots_fired = total_shots_fired
                    shots_hit = total_shots_hit
                    accuracy = int((total_shots_hit / max(1, total_shots_fired)) * 100) if total_shots_fired > 0 else 0
                    count_elapsed = 0  # Define for consistency
                    stats_progress_bar_current = stats_progress_bar_target
                
                # Time entry
                entry_minutes = int(current_time // 60) % 60
                entry_seconds = int(current_time % 60)
                entry_milliseconds = int((current_time % 1) * 1000)
                entry_time_text = f"Entry Time: {entry_minutes:02}:{entry_seconds:02}:{entry_milliseconds:03}"
                entry_surf = stats_font_small.render(entry_time_text, True, (0, 255, 0))
                screen.blit(entry_surf, (window_x + 40, stats_y))
                
                # Other statistics with animation
                other_stats = [
                    f"Enemies Defeated: {enemies_defeated}",
                    f"Items Collected: {items_collected}",
                    f"Shots Fired: {shots_fired}",
                    f"Shots Hit: {shots_hit}",
                    f"Accuracy: {accuracy}%",
                    "Rank: TRAINEE"
                ]
                
                for i, stat_text in enumerate(other_stats):
                    stat_surf = stats_font_small.render(stat_text, True, (0, 255, 0))
                    screen.blit(stat_surf, (window_x + 40, stats_y + line_height * (i + 1)))
                
                # Progress bar (vertical, on the right side)
                progress_bar_x = window_x + window_w - 60
                progress_bar_y = stats_y + 10
                progress_bar_width = 20
                progress_bar_height = 160
                
                # Progress bar background
                pygame.draw.rect(screen, (50, 50, 50), (progress_bar_x, progress_bar_y, progress_bar_width, progress_bar_height))
                
                # Progress bar fill (animated)
                fill_height = int((stats_progress_bar_current / 100.0) * progress_bar_height)
                fill_y = progress_bar_y + progress_bar_height - fill_height  # Fill from bottom
                pygame.draw.rect(screen, (0, 255, 0), (progress_bar_x, fill_y, progress_bar_width, fill_height))
                
                # Progress bar border
                pygame.draw.rect(screen, (0, 255, 0), (progress_bar_x, progress_bar_y, progress_bar_width, progress_bar_height), width=2)
                
                # Percentage text above progress bar
                percent_text = f"{int(stats_progress_bar_current)}%"
                percent_surf = stats_font_small.render(percent_text, True, (0, 255, 0))
                screen.blit(percent_surf, (progress_bar_x + progress_bar_width // 2 - percent_surf.get_width() // 2, progress_bar_y - 25))
                
                # OK button (only show when completed)
                if stats_completed:
                    button_w = 120
                    button_h = 40
                    button_x = window_x + window_w // 2 - button_w // 2
                    button_y = stats_window_y + window_h - 70
                    
                    pygame.draw.rect(screen, (0, 255, 0), (button_x, button_y, button_w, button_h), width=2)
                    ok_text = "OK"
                    ok_surf = stats_font.render(ok_text, True, (0, 255, 0))
                    screen.blit(ok_surf, (button_x + button_w // 2 - ok_surf.get_width() // 2, button_y + button_h // 2 - ok_surf.get_height() // 2))
                    
                    # Instructions
                    inst_text = "Press ENTER or SPACE to continue"
                    inst_surf = stats_font_small.render(inst_text, True, (0, 255, 0))
                    screen.blit(inst_surf, (window_x + window_w // 2 - inst_surf.get_width() // 2, stats_window_y + window_h - 25))
                else:
                    # Skip instruction
                    inst_text = "Click to skip animation"
                    inst_surf = stats_font_small.render(inst_text, True, (0, 255, 0))
                    screen.blit(inst_surf, (window_x + window_w // 2 - inst_surf.get_width() // 2, stats_window_y + window_h - 25))
                
                # Post-flash icon animation (top-right corner, partially outside window)
                if stats_icon_active:
                    # Update pulse animation
                    stats_icon_pulse_time += delta
                    pulse_speed = 3.0  # Speed of pulsing
                    pulse_ratio = (math.sin(stats_icon_pulse_time * pulse_speed) + 1.0) / 2.0  # 0 to 1
                    current_size = int(stats_icon_base_size + (stats_icon_max_size - stats_icon_base_size) * pulse_ratio)
                    
                    # Position in top-right corner, partially outside window
                    # Move it further right and up so it extends beyond window bounds
                    icon_x = window_x + window_w - current_size // 2  # Half outside to the right
                    icon_y = window_y - current_size // 3  # Partially outside at top
                    
                    # Load and rotate the unknown image
                    try:
                        icon_img = Image.open(resource_path("data/unknown.png")).convert("RGBA")
                        # Rotate 45 degrees
                        icon_img = icon_img.rotate(45, expand=True)
                        # Resize to current size
                        icon_img = icon_img.resize((current_size, current_size), Image.NEAREST)
                        # Convert to pygame surface
                        icon_surface = pil_to_surface(icon_img)
                        # Draw with transparency
                        screen.blit(icon_surface, (icon_x, icon_y))
                    except Exception:
                        # Fallback: draw a simple rotated square
                        center_x = icon_x + current_size // 2
                        center_y = icon_y + current_size // 2
                        half_size = current_size // 2
                        # Calculate rotated corners
                        angle_rad = math.radians(45)
                        corners = []
                        for dx, dy in [(-half_size, -half_size), (half_size, -half_size), (half_size, half_size), (-half_size, half_size)]:
                            rot_x = dx * math.cos(angle_rad) - dy * math.sin(angle_rad)
                            rot_y = dx * math.sin(angle_rad) + dy * math.cos(angle_rad)
                            corners.append((center_x + rot_x, center_y + rot_y))
                        pygame.draw.polygon(screen, (0, 255, 0), corners, 2)

        pygame.display.flip()

    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)
    pygame.quit()

    if next_action == "restart":
        return start_tutor_maze(root)

    if elevator_transition_to_testing:
        # Switch scene: go to testing mode.
        from testing_maze import start_testing_maze
        start_testing_maze(root)


start_game = start_tutor_maze
