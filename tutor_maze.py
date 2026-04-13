import math
import os
import random
import sys
import time
import wave
import copy

import pygame
from PIL import Image, ImageDraw

from background_music import play_overlay_music, play_sound_effect, stop_overlay_music, update_music
import bomb as bomb_logic
import hexagaze as hexagaze_logic
import mannequin as mannequin_logic
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
from utils import get_exe_dir

SPEED = 0.17
GUN_BOTTOM_MARGIN = -14
MOUSE_SENSITIVITY = 0.0035
HAND_SWAP_DURATION = 0.18

MINIMAP_SCALE = 14
DEJA_VU_MAX_CHARGE = 8.0
DEJA_VU_RECHARGE_DELAY = 1.5
DEJA_VU_FAST_CHARGE_CAP = 3.0
DEJA_VU_FAST_CHARGE_TIME = 9.0
DEJA_VU_SLOW_CHARGE_TIME = 21.0
DEJA_VU_MIN_ACTIVATION = 2.0
DEJA_VU_GHOST_INTERVAL = 0.08
DEJA_VU_RETURN_FADE = 0.75
DEJA_VU_GHOST_LIFETIME = 9.0
DEJA_VU_ENTER_FADE = 0.5
DEJA_VU_SPEED_BOOST = 1.18
PLAYER_MAX_HEALTH = 100
PUNCH_DAMAGE = 0.5
PUNCH_RANGE_CELLS = 1.0
PUNCH_AIM_TOLERANCE = 0.22
PUNCH_COOLDOWN = 0.75
HEXAGAZE_RADIUS_CELLS = 9
HEXAGAZE_RADIUS_MIN = 8
HEXAGAZE_RADIUS_MAX = 10
HEXAGAZE_CLOSE_SIGHT_RADIUS = 0.9
HEXAGAZE_FIRST_SHOT_DELAY = 0.3
HEXAGAZE_BURST_DELAY = 0.14
HEXAGAZE_BURST_SIZE = 3
HEXAGAZE_BURST_PAUSE = 1.0
HEXAGAZE_PROJECTILE_SPEED = 7.4
HEXAGAZE_PROJECTILE_DAMAGE = 10
HEXAGAZE_PLAYER_HIT_RADIUS = 0.34
HEXAGAZE_BLOCK_RADIUS = 0.42
HEXAGAZE_ENTRY_BURST_COUNT = 3
HEXAGAZE_ENTRY_BURST_SPEED = 10.8
HEXAGAZE_HOMING_TURN_RATE = 3.8
HEXAGAZE_SNAKE_TURN_RATE = 3.2
HEXAGAZE_SNAKE_WAVE_SPEED = 8.0
HEXAGAZE_SNAKE_WAVE_AMPLITUDE = 0.85
HEXAGAZE_ROLL_FRAME_TIME = 0.06
HEXAGAZE_ROLL_DURATION = 2.0
HEXAGAZE_POST_ATTACK_WAIT = 4.0

MAP = [
    ".........###...............",
    "##########P################",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "#.....................M...#",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "#........................##",
    "#.....................BG.N#",
    "#........................##",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "###########...............#",
    "#C........................#",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "#.........................#",
    "###########################",
]


def resource_path(relative_path):
    return os.path.join(get_exe_dir(), relative_path)


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


def get_floor_height(x, y):
    if x < 0 or y < 0:
        return 0.0
    if int(y) >= len(MAP):
        return 0.0
    if int(x) >= len(MAP[0]):
        return 0.0
    cell = MAP[int(y)][int(x)]
    if cell == "N":
        return 0.45
    if cell in {"B", "G", "C", "M"}:
        return 0.2
    if cell == "P":
        return 0.3
    return 0.0


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


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def generate_hexagaze_blind_offsets(radius):
    candidates = []
    for ox in range(-radius, radius + 1):
        for oy in range(-radius, radius + 1):
            if ox == 0 and oy == 0:
                continue
            dist = math.hypot(ox, oy)
            if 1.0 <= dist <= radius + 0.01:
                candidates.append((ox, oy))
    random.shuffle(candidates)
    blind_count = max(6, min(len(candidates), radius * 3))
    return candidates[:blind_count]


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
    player_z = get_floor_height(player_x, player_y)
    player_angle = 0.0
    start_door_anchor_x = player_x + math.cos(player_angle) * 0.62
    start_door_anchor_y = player_y + math.sin(player_angle) * 0.62

    gun_img_raw = Image.open(resource_path("data/gifs/hands/gun.png")).convert("RGBA")
    gunshoot_frames_raw = load_gif_frames(resource_path("data/gifs/hands/gunshoot.gif"))
    gunreload_frames_raw = load_gif_frames(resource_path("data/gifs/hands/gunreload.gif"))
    punch_img_raw = Image.open(resource_path("data/gifs/hands/punch.png")).convert("RGBA")
    left_punch_frames_raw = load_gif_frames(resource_path("data/gifs/hands/LPunch.gif"))
    right_punch_frames_raw = load_gif_frames(resource_path("data/gifs/hands/RPunch.gif"))
    bomb_assets = bomb_logic.load_bomb_assets(resource_path, game_view_w, pil_to_surface)
    bomb_icon_raw = bomb_assets["bomb_icon_raw"]
    bombon_frames_raw = bomb_assets["bombon_frames_raw"]
    boom_frames_raw = bomb_assets["boom_frames_raw"]
    boom_sound_path = bomb_assets["boom_sound_path"]
    activator_img_raw = bomb_assets["activator_img_raw"]
    activatorclick_frames_raw = bomb_assets["activatorclick_frames_raw"]

    GUN_SCALE = 0.25
    PUNCH_SCALE = 0.38
    PUNCH_WIDTH_MULT = 1.28
    PUNCH_HEIGHT_MULT = 1.30

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

    deja_vu_ghost_frames = []
    for alpha in (255, 210, 165, 120, 80, 45):
        ghost_frame = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
        ghost_draw = ImageDraw.Draw(ghost_frame)
        ghost_draw.ellipse((2, 2, 22, 22), fill=(120, 255, 240, max(10, alpha // 5)))
        ghost_draw.ellipse((6, 6, 18, 18), fill=(170, 255, 250, max(20, alpha // 2)))
        ghost_draw.ellipse((9, 9, 15, 15), fill=(240, 255, 255, alpha))
        deja_vu_ghost_frames.append(ghost_frame)

    gunitem_raw = Image.open(resource_path("data/gunitem.png")).convert("RGBA")
    gunitem_raw = gunitem_raw.resize((40, 40), Image.NEAREST)
    gunitem_img = pil_to_surface(gunitem_raw)
    bombitem_img = bomb_assets["bombitem_img"]
    activatoritem_img = bomb_assets["activatoritem_img"]

    gun_pickup_img_src = Image.open(resource_path("data/unknown.png")).convert("RGBA")
    gun_pickup_frames = [gun_pickup_img_src]
    gun_pickup_scale = (int(game_view_w * 0.1)) / max(gun_pickup_img_src.width, 1)
    bomb_pickup_frames = bomb_assets["bomb_pickup_frames"]
    bomb_pickup_scale = bomb_assets["bomb_pickup_scale"]
    target_marker_frames = bomb_assets["target_marker_frames"]

    hexagaze_assets = hexagaze_logic.load_hexagaze_assets(resource_path)
    hexagaze_frames = hexagaze_assets["frames"]
    hexagaze_roll_animations = hexagaze_assets["roll_animations"]
    hexagaze_roll_durations = hexagaze_assets["roll_durations"]
    sentry_danger_frames = hexagaze_assets["danger_frames"]
    sentry_safe_frames = hexagaze_assets["safe_frames"]

    enemy_gifs = {
        "sitting": load_gif_frames(resource_path("data/gifs/cicada/cicadasitting.gif")),
        "getting_up": load_gif_frames(resource_path("data/gifs/cicada/cicadagettingup.gif")),
        "walking": load_gif_frames(resource_path("data/gifs/cicada/cicadawalking.gif")),
    }

    mannequin_assets = mannequin_logic.load_mannequin_assets(resource_path, get_wav_duration)
    mannequin_frames = mannequin_assets["frames"]
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

    mannequin_state = mannequin_logic.create_mannequin_state(MAP)
    mannequin_x = mannequin_state["x"]
    mannequin_y = mannequin_state["y"]
    mannequin_search_visited = set(mannequin_state["search_visited"])
    mannequin_attack_sound_path = mannequin_assets["attack_sound_path"]
    mannequin_attack_duration = mannequin_assets["attack_duration"]
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

    bomb_pickups = bomb_logic.collect_bomb_pickups(MAP)

    orb_cycle = ["red", "violet", "yellow", "green"]
    sentries = hexagaze_logic.collect_sentries(MAP, HEXAGAZE_RADIUS_MIN, HEXAGAZE_RADIUS_MAX, orb_cycle)
    sentry_projectiles = []
    hexagaze_config = {
        "radius_cells": HEXAGAZE_RADIUS_CELLS,
        "close_sight_radius": HEXAGAZE_CLOSE_SIGHT_RADIUS,
        "roll_durations": hexagaze_roll_durations,
        "roll_duration": HEXAGAZE_ROLL_DURATION,
        "burst_size": HEXAGAZE_BURST_SIZE,
        "first_shot_delay": HEXAGAZE_FIRST_SHOT_DELAY,
        "burst_delay": HEXAGAZE_BURST_DELAY,
        "post_attack_wait": HEXAGAZE_POST_ATTACK_WAIT,
        "projectile_speed": HEXAGAZE_PROJECTILE_SPEED,
        "player_hit_radius": HEXAGAZE_PLAYER_HIT_RADIUS,
        "projectile_damage": HEXAGAZE_PROJECTILE_DAMAGE,
        "entry_burst_count": HEXAGAZE_ENTRY_BURST_COUNT,
        "entry_burst_speed": HEXAGAZE_ENTRY_BURST_SPEED,
        "homing_turn_rate": HEXAGAZE_HOMING_TURN_RATE,
        "snake_turn_rate": HEXAGAZE_SNAKE_TURN_RATE,
        "snake_wave_speed": HEXAGAZE_SNAKE_WAVE_SPEED,
        "snake_wave_amplitude": HEXAGAZE_SNAKE_WAVE_AMPLITUDE,
        "orb_cycle": orb_cycle,
    }

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
    player_health = PLAYER_MAX_HEALTH
    player_restart_at = None
    ammo = 17
    max_ammo = 17
    reloading = False
    has_gun = False
    slot2_item = None
    placed_bombs = []
    active_explosions = []
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
    activator_click_animating = False
    activator_click_frame_index = 0
    activator_click_acc = 0.0
    bomb_world_frame_index = 0
    bomb_world_anim_acc = 0.0
    hand_target_item_id = None
    hand_previous_item_id = None
    hand_swap_progress = 1.0
    hand_swap_active = False
    shoot_acc = 0.0
    reload_acc = 0.0
    punch_animating = False
    punch_frame_index = 0
    punch_acc = 0.0
    punch_side = "left"
    next_punch_time = 0.0
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

    def build_hand_surface_from_pil(pil_frame, item_id=None):
        w, h = pil_frame.size
        hand_scale = PUNCH_SCALE if item_id == "fists" else GUN_SCALE
        new_w = int(game_view_w * hand_scale)
        new_h = int(h * (new_w / w))
        if item_id == "fists":
            new_w = int(new_w * PUNCH_WIDTH_MULT)
            new_h = int(new_h * PUNCH_HEIGHT_MULT)
        return pil_to_surface(pil_frame.resize((new_w, new_h), Image.NEAREST))

    def get_hand_pil_for_item(item_id):
        if item_id == "gun":
            if reloading and reload_anim_active:
                return gunreload_frames_raw[min(reload_anim_index, len(gunreload_frames_raw) - 1)]
            if gunshoot_animating:
                return gunshoot_frames_raw[min(gunshoot_frame_index, len(gunshoot_frames_raw) - 1)]
            return gun_img_raw
        if item_id == "fists":
            if punch_animating:
                frames = right_punch_frames_raw if punch_side == "right" else left_punch_frames_raw
                return frames[min(punch_frame_index, len(frames) - 1)]
            return punch_img_raw
        if item_id in {"bomb", "activator"}:
            return bomb_logic.get_hand_pil(item_id, bomb_assets, activator_click_animating, activator_click_frame_index)
        return None

    def get_selected_inventory_item_id():
        if selected_slot == 1 and has_gun:
            return "gun"
        if selected_slot == 2 and slot2_item == "bomb":
            return "bomb"
        if selected_slot == 2 and slot2_item == "activator":
            return "activator"
        return None

    def get_current_hand_item_id():
        if elevator_active or start_cutscene_active:
            return None
        return get_selected_inventory_item_id() or "fists"

    def update_hand_swap(delta_time):
        nonlocal hand_target_item_id, hand_previous_item_id, hand_swap_progress, hand_swap_active
        target_item_id = get_current_hand_item_id()
        if target_item_id != hand_target_item_id:
            hand_previous_item_id = hand_target_item_id
            hand_target_item_id = target_item_id
            if hand_previous_item_id != hand_target_item_id:
                hand_swap_progress = 0.0
                hand_swap_active = True
        if hand_swap_active:
            hand_swap_progress += delta_time / max(0.001, HAND_SWAP_DURATION)
            if hand_swap_progress >= 1.0:
                hand_swap_progress = 1.0
                hand_swap_active = False
                hand_previous_item_id = None

    def get_targeted_floor_cell(max_distance=3.2, step=0.03):
        return bomb_logic.get_targeted_floor_cell(
            player_x,
            player_y,
            player_angle,
            is_wall,
            placed_bombs,
            max_distance=max_distance,
            step=step,
        )

    def place_bomb():
        nonlocal slot2_item
        slot2_item, _ = bomb_logic.place_bomb(
            selected_slot,
            slot2_item,
            placed_bombs,
            player_x,
            player_y,
            player_angle,
            is_wall,
        )

    def spawn_bomb_explosion(cell):
        bomb_logic.spawn_bomb_explosion(active_explosions, boom_sound_path, cell)

    def damage_player(amount, now_value):
        nonlocal player_health
        if player_restart_at is not None:
            return
        player_health = max(0, player_health - amount)
        if player_health <= 0:
            trigger_player_death(now_value)

    def sync_mannequin_state_to_module():
        mannequin_state["x"] = mannequin_x
        mannequin_state["y"] = mannequin_y
        mannequin_state["health"] = mannequin_health
        mannequin_state["max_health"] = mannequin_max_health
        mannequin_state["alive"] = mannequin_alive
        mannequin_state["mode"] = mannequin_mode
        mannequin_state["next_search_move_at"] = mannequin_next_search_move_at
        mannequin_state["search_visited"] = set(mannequin_search_visited)
        mannequin_state["observe_distance"] = mannequin_observe_distance
        mannequin_state["hidden_active"] = mannequin_hidden_active
        mannequin_state["next_hidden_step_at"] = mannequin_next_hidden_step_at
        mannequin_state["notice_radius"] = mannequin_notice_radius
        mannequin_state["shot_push_cooldown"] = mannequin_shot_push_cooldown
        mannequin_state["last_seen_by_player"] = mannequin_last_seen_by_player
        mannequin_state["restart_at"] = mannequin_restart_at

    def sync_mannequin_state_from_module():
        nonlocal mannequin_x, mannequin_y, mannequin_health, mannequin_max_health, mannequin_alive, mannequin_mode
        nonlocal mannequin_next_search_move_at, mannequin_search_visited, mannequin_observe_distance
        nonlocal mannequin_hidden_active, mannequin_next_hidden_step_at, mannequin_notice_radius
        nonlocal mannequin_shot_push_cooldown, mannequin_last_seen_by_player, mannequin_restart_at
        mannequin_x = mannequin_state["x"]
        mannequin_y = mannequin_state["y"]
        mannequin_health = mannequin_state["health"]
        mannequin_max_health = mannequin_state["max_health"]
        mannequin_alive = mannequin_state["alive"]
        mannequin_mode = mannequin_state["mode"]
        mannequin_next_search_move_at = mannequin_state["next_search_move_at"]
        mannequin_search_visited = set(mannequin_state["search_visited"])
        mannequin_observe_distance = mannequin_state["observe_distance"]
        mannequin_hidden_active = mannequin_state["hidden_active"]
        mannequin_next_hidden_step_at = mannequin_state["next_hidden_step_at"]
        mannequin_notice_radius = mannequin_state["notice_radius"]
        mannequin_shot_push_cooldown = mannequin_state["shot_push_cooldown"]
        mannequin_last_seen_by_player = mannequin_state["last_seen_by_player"]
        mannequin_restart_at = mannequin_state["restart_at"]

    def damage_mannequin(amount):
        nonlocal enemies_killed
        sync_mannequin_state_to_module()
        killed = mannequin_logic.damage(mannequin_state, amount)
        sync_mannequin_state_from_module()
        if killed:
            enemies_killed += 1

    def damage_mannequin_from_player_attack(amount, register_shot_hit=False):
        nonlocal total_shots_hit, enemies_killed
        nonlocal mannequin_health, mannequin_alive, mannequin_hidden_active
        nonlocal mannequin_next_hidden_step_at, mannequin_last_seen_by_player, mannequin_shot_push_cooldown
        if not mannequin_alive:
            return False
        mannequin_health = max(0, mannequin_health - amount)
        if register_shot_hit:
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
        return True

    def try_damage_target_under_cursor(amount, max_distance_cells):
        nonlocal enemies_killed
        best_target = None
        best_dist = float("inf")

        if mannequin_alive and mannequin_x is not None and mannequin_y is not None:
            dx = mannequin_x - player_x
            dy = mannequin_y - player_y
            dist = math.hypot(dx, dy)
            angle_diff = wrap_angle(math.atan2(dy, dx) - player_angle)
            if (
                dist <= max_distance_cells
                and abs(angle_diff) <= PUNCH_AIM_TOLERANCE
                and has_line_of_sight(player_x, player_y, mannequin_x, mannequin_y)
            ):
                best_target = ("mannequin", None)
                best_dist = dist

        for orb_index, orb in enumerate(orbs):
            if orb["health"] <= 0:
                continue
            dx = orb["x"] - player_x
            dy = orb["y"] - player_y
            dist = math.hypot(dx, dy)
            angle_diff = wrap_angle(math.atan2(dy, dx) - player_angle)
            if (
                dist <= max_distance_cells
                and abs(angle_diff) <= PUNCH_AIM_TOLERANCE
                and has_line_of_sight(player_x, player_y, orb["x"], orb["y"])
                and dist < best_dist
            ):
                best_target = ("orb", orb_index)
                best_dist = dist

        for sentry_index, sentry in enumerate(sentries):
            if sentry["health"] <= 0:
                continue
            dx = sentry["x"] - player_x
            dy = sentry["y"] - player_y
            dist = math.hypot(dx, dy)
            angle_diff = wrap_angle(math.atan2(dy, dx) - player_angle)
            if (
                dist <= max_distance_cells
                and abs(angle_diff) <= PUNCH_AIM_TOLERANCE
                and has_line_of_sight(player_x, player_y, sentry["x"], sentry["y"])
                and dist < best_dist
            ):
                best_target = ("sentry", sentry_index)
                best_dist = dist

        if best_target is None:
            return False

        target_kind, target_index = best_target
        if target_kind == "mannequin":
            damage_mannequin_from_player_attack(amount)
            return True
        if target_kind == "orb":
            orb = orbs[target_index]
            previous_health = orb["health"]
            orb["health"] = max(0, orb["health"] - amount)
            if previous_health > 0 and orb["health"] <= 0:
                enemies_killed += 1
            return True

        sentry = sentries[target_index]
        previous_health = sentry["health"]
        sentry["health"] = max(0, sentry["health"] - amount)
        if previous_health > 0 and sentry["health"] <= 0:
            sentry["burst_shots_left"] = 0
            enemies_killed += 1
        return True

    def damage_entities_in_bomb_area(center_cell, radius_cells, now_value):
        nonlocal enemies_killed
        min_x = center_cell[0] - radius_cells
        max_x = center_cell[0] + radius_cells
        min_y = center_cell[1] - radius_cells
        max_y = center_cell[1] + radius_cells

        player_cell = (int(player_x), int(player_y))
        if min_x <= player_cell[0] <= max_x and min_y <= player_cell[1] <= max_y:
            damage_player(5, now_value)

        mannequin_cell = (int(mannequin_x), int(mannequin_y)) if mannequin_x is not None and mannequin_y is not None else None
        if mannequin_cell is not None and min_x <= mannequin_cell[0] <= max_x and min_y <= mannequin_cell[1] <= max_y:
            damage_mannequin(5)

        for orb in orbs:
            if orb["health"] <= 0:
                continue
            orb_cell = (int(orb["x"]), int(orb["y"]))
            if min_x <= orb_cell[0] <= max_x and min_y <= orb_cell[1] <= max_y:
                orb["health"] = max(0, orb["health"] - 5)
                if orb["health"] <= 0:
                    enemies_killed += 1

        for sentry in sentries:
            if sentry["health"] <= 0:
                continue
            sentry_cell = (int(sentry["x"]), int(sentry["y"]))
            if min_x <= sentry_cell[0] <= max_x and min_y <= sentry_cell[1] <= max_y:
                sentry["health"] = max(0, sentry["health"] - 5)
                if sentry["health"] <= 0:
                    sentry["burst_shots_left"] = 0
                    enemies_killed += 1

    def detonate_bomb_at_cell(cell, radius_cells, now_value):
        return bomb_logic.detonate_bomb_at_cell(
            placed_bombs,
            active_explosions,
            boom_sound_path,
            cell,
            radius_cells,
            now_value,
            damage_entities_in_bomb_area,
        )

    def update_bomb_system(delta_time, now_value):
        nonlocal bomb_world_anim_acc, bomb_world_frame_index
        nonlocal activator_click_animating, activator_click_frame_index, activator_click_acc
        mannequin_cell = (int(mannequin_x), int(mannequin_y)) if mannequin_x is not None and mannequin_y is not None else None
        bomb_update = bomb_logic.update_bomb_system(
            placed_bombs,
            active_explosions,
            bomb_assets,
            delta_time,
            now_value,
            (int(player_x), int(player_y)),
            mannequin_cell,
            mannequin_alive,
            damage_entities_in_bomb_area,
            bomb_world_frame_index,
            bomb_world_anim_acc,
            activator_click_animating,
            activator_click_frame_index,
            activator_click_acc,
        )
        bomb_world_frame_index = bomb_update["bomb_world_frame_index"]
        bomb_world_anim_acc = bomb_update["bomb_world_anim_acc"]
        activator_click_animating = bomb_update["activator_click_animating"]
        activator_click_frame_index = bomb_update["activator_click_frame_index"]
        activator_click_acc = bomb_update["activator_click_acc"]

    def trigger_activator():
        nonlocal activator_click_animating, activator_click_frame_index, activator_click_acc
        activator_click_animating, activator_click_frame_index, activator_click_acc, _ = bomb_logic.trigger_activator(
            selected_slot,
            slot2_item,
            placed_bombs,
            activator_click_animating,
            time.time(),
        )

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
                damage_mannequin_from_player_attack(1, register_shot_hit=True)

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

        for sentry in sentries:
            if sentry["health"] <= 0:
                continue
            dx = sentry["x"] - player_x
            dy = sentry["y"] - player_y
            dist = math.hypot(dx, dy)
            angle_to_sentry = math.atan2(dy, dx)
            angle_diff = wrap_angle(angle_to_sentry - player_angle)
            if abs(angle_diff) < 0.05 and dist < 10 and has_line_of_sight(player_x, player_y, sentry["x"], sentry["y"]):
                sentry["health"] -= 1
                total_shots_hit += 1
                if sentry["health"] <= 0:
                    sentry["health"] = 0
                    sentry["burst_shots_left"] = 0
                    enemies_killed += 1
                break

    def start_reload():
        nonlocal reloading, reload_anim_active, reload_anim_index, reload_acc, ammo
        if reloading or not has_gun:
            return
        reloading = True
        reload_anim_active = True
        reload_anim_index = 0
        reload_acc = 0.0

    def punch_with_fists(mouse_button):
        nonlocal punch_animating, punch_frame_index, punch_acc, punch_side, next_punch_time
        if get_current_hand_item_id() != "fists":
            return
        now_value = time.time()
        if now_value < next_punch_time:
            return
        next_punch_time = now_value + PUNCH_COOLDOWN
        punch_side = "right" if mouse_button == 3 else "left"
        punch_animating = True
        punch_frame_index = 0
        punch_acc = 0.0
        try_damage_target_under_cursor(PUNCH_DAMAGE, PUNCH_RANGE_CELLS)

    def use_selected_item(mouse_button):
        selected_item_id = get_selected_inventory_item_id()
        if selected_item_id is None:
            if mouse_button in (1, 3):
                punch_with_fists(mouse_button)
            return
        if mouse_button != 1:
            return
        if selected_slot == 1:
            shoot_gun()
        elif selected_slot == 2:
            if slot2_item == "bomb":
                place_bomb()
            elif slot2_item == "activator":
                trigger_activator()

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

    deja_vu_active = False
    deja_vu_started_at = 0.0
    deja_vu_charge = DEJA_VU_MAX_CHARGE
    deja_vu_recharge_available_at = 0.0
    deja_vu_snapshot = None
    deja_vu_ghost_trail = []
    deja_vu_ghost_acc = 0.0
    deja_vu_return_started_at = None
    deja_vu_active_budget = 0.0

    def deja_vu_available():
        return (
            not deja_vu_active
            and not intro_active
            and not elevator_active
            and not stats_window_active
            and not start_cutscene_active
            and mannequin_restart_at is None
            and deja_vu_charge >= DEJA_VU_MIN_ACTIVATION
        )

    def capture_deja_vu_snapshot():
        return {
            "player_x": player_x,
            "player_y": player_y,
            "player_z": player_z,
            "player_angle": player_angle,
            "player_health": player_health,
            "player_restart_at": player_restart_at,
            "selected_slot": selected_slot,
            "ammo": ammo,
            "max_ammo": max_ammo,
            "reloading": reloading,
            "has_gun": has_gun,
            "slot2_item": slot2_item,
            "bob_phase": bob_phase,
            "bob_offset": bob_offset,
            "flash_timer": flash_timer,
            "gunshoot_animating": gunshoot_animating,
            "gunshoot_frame_index": gunshoot_frame_index,
            "reload_anim_index": reload_anim_index,
            "reload_anim_active": reload_anim_active,
            "activator_click_animating": activator_click_animating,
            "activator_click_frame_index": activator_click_frame_index,
            "activator_click_acc": activator_click_acc,
            "bomb_world_frame_index": bomb_world_frame_index,
            "bomb_world_anim_acc": bomb_world_anim_acc,
            "hand_target_item_id": hand_target_item_id,
            "hand_previous_item_id": hand_previous_item_id,
            "hand_swap_progress": hand_swap_progress,
            "hand_swap_active": hand_swap_active,
            "shoot_acc": shoot_acc,
            "reload_acc": reload_acc,
            "punch_animating": punch_animating,
            "punch_frame_index": punch_frame_index,
            "punch_acc": punch_acc,
            "punch_side": punch_side,
            "next_punch_time": next_punch_time,
            "total_shots_fired": total_shots_fired,
            "total_shots_hit": total_shots_hit,
            "enemies_killed": enemies_killed,
            "gun_pickups": list(gun_pickups),
            "bomb_pickups": list(bomb_pickups),
            "placed_bombs": copy.deepcopy(placed_bombs),
            "active_explosions": copy.deepcopy(active_explosions),
            "orbs": copy.deepcopy(orbs),
            "sentries": copy.deepcopy(sentries),
            "sentry_projectiles": copy.deepcopy(sentry_projectiles),
            "light_states": dict(light_states),
            "light_timers": dict(light_timers),
            "mannequin_x": mannequin_x,
            "mannequin_y": mannequin_y,
            "mannequin_health": mannequin_health,
            "mannequin_alive": mannequin_alive,
            "mannequin_mode": mannequin_mode,
            "mannequin_next_search_move_at": mannequin_next_search_move_at,
            "mannequin_search_visited": set(mannequin_search_visited),
            "mannequin_observe_distance": mannequin_observe_distance,
            "mannequin_hidden_active": mannequin_hidden_active,
            "mannequin_next_hidden_step_at": mannequin_next_hidden_step_at,
            "mannequin_shot_push_cooldown": mannequin_shot_push_cooldown,
            "mannequin_last_seen_by_player": mannequin_last_seen_by_player,
            "mannequin_restart_at": mannequin_restart_at,
        }

    def restore_deja_vu_snapshot(snapshot):
        nonlocal player_x, player_y, player_z, player_angle, player_health, player_restart_at
        nonlocal selected_slot, ammo, max_ammo, reloading, has_gun, slot2_item
        nonlocal bob_phase, bob_offset, flash_timer
        nonlocal gunshoot_animating, gunshoot_frame_index, reload_anim_index, reload_anim_active
        nonlocal activator_click_animating, activator_click_frame_index, activator_click_acc
        nonlocal bomb_world_frame_index, bomb_world_anim_acc
        nonlocal hand_target_item_id, hand_previous_item_id, hand_swap_progress, hand_swap_active
        nonlocal shoot_acc, reload_acc, punch_animating, punch_frame_index, punch_acc, punch_side, next_punch_time
        nonlocal total_shots_fired, total_shots_hit, enemies_killed
        nonlocal gun_pickups, bomb_pickups, placed_bombs, active_explosions, orbs, sentries, sentry_projectiles, light_states, light_timers
        nonlocal mannequin_x, mannequin_y, mannequin_health, mannequin_alive, mannequin_mode
        nonlocal mannequin_next_search_move_at, mannequin_search_visited, mannequin_observe_distance
        nonlocal mannequin_hidden_active, mannequin_next_hidden_step_at
        nonlocal mannequin_shot_push_cooldown, mannequin_last_seen_by_player, mannequin_restart_at

        player_x = snapshot["player_x"]
        player_y = snapshot["player_y"]
        player_z = snapshot["player_z"]
        player_angle = snapshot["player_angle"]
        player_health = snapshot["player_health"]
        player_restart_at = snapshot["player_restart_at"]
        selected_slot = snapshot["selected_slot"]
        ammo = snapshot["ammo"]
        max_ammo = snapshot["max_ammo"]
        reloading = snapshot["reloading"]
        has_gun = snapshot["has_gun"]
        slot2_item = snapshot["slot2_item"]
        bob_phase = snapshot["bob_phase"]
        bob_offset = snapshot["bob_offset"]
        flash_timer = snapshot["flash_timer"]
        gunshoot_animating = snapshot["gunshoot_animating"]
        gunshoot_frame_index = snapshot["gunshoot_frame_index"]
        reload_anim_index = snapshot["reload_anim_index"]
        reload_anim_active = snapshot["reload_anim_active"]
        activator_click_animating = snapshot["activator_click_animating"]
        activator_click_frame_index = snapshot["activator_click_frame_index"]
        activator_click_acc = snapshot["activator_click_acc"]
        bomb_world_frame_index = snapshot["bomb_world_frame_index"]
        bomb_world_anim_acc = snapshot["bomb_world_anim_acc"]
        hand_target_item_id = snapshot["hand_target_item_id"]
        hand_previous_item_id = snapshot["hand_previous_item_id"]
        hand_swap_progress = snapshot["hand_swap_progress"]
        hand_swap_active = snapshot["hand_swap_active"]
        shoot_acc = snapshot["shoot_acc"]
        reload_acc = snapshot["reload_acc"]
        punch_animating = snapshot["punch_animating"]
        punch_frame_index = snapshot["punch_frame_index"]
        punch_acc = snapshot["punch_acc"]
        punch_side = snapshot["punch_side"]
        next_punch_time = snapshot["next_punch_time"]
        total_shots_fired = snapshot["total_shots_fired"]
        total_shots_hit = snapshot["total_shots_hit"]
        enemies_killed = snapshot["enemies_killed"]
        gun_pickups = list(snapshot["gun_pickups"])
        bomb_pickups = list(snapshot["bomb_pickups"])
        placed_bombs = copy.deepcopy(snapshot["placed_bombs"])
        active_explosions = copy.deepcopy(snapshot["active_explosions"])
        orbs = copy.deepcopy(snapshot["orbs"])
        sentries = copy.deepcopy(snapshot["sentries"])
        sentry_projectiles = copy.deepcopy(snapshot["sentry_projectiles"])
        light_states = dict(snapshot["light_states"])
        light_timers = dict(snapshot["light_timers"])
        mannequin_x = snapshot["mannequin_x"]
        mannequin_y = snapshot["mannequin_y"]
        mannequin_health = snapshot["mannequin_health"]
        mannequin_alive = snapshot["mannequin_alive"]
        mannequin_mode = snapshot["mannequin_mode"]
        mannequin_next_search_move_at = snapshot["mannequin_next_search_move_at"]
        mannequin_search_visited = set(snapshot["mannequin_search_visited"])
        mannequin_observe_distance = snapshot["mannequin_observe_distance"]
        mannequin_hidden_active = snapshot["mannequin_hidden_active"]
        mannequin_next_hidden_step_at = snapshot["mannequin_next_hidden_step_at"]
        mannequin_shot_push_cooldown = snapshot["mannequin_shot_push_cooldown"]
        mannequin_last_seen_by_player = snapshot["mannequin_last_seen_by_player"]
        mannequin_restart_at = snapshot["mannequin_restart_at"]

    def activate_deja_vu():
        nonlocal deja_vu_active, deja_vu_started_at, deja_vu_snapshot, deja_vu_active_budget
        nonlocal deja_vu_ghost_trail, deja_vu_ghost_acc, deja_vu_return_started_at
        if not deja_vu_available():
            return
        now_local = time.time()
        deja_vu_snapshot = capture_deja_vu_snapshot()
        deja_vu_active = True
        deja_vu_started_at = now_local
        deja_vu_active_budget = deja_vu_charge
        deja_vu_ghost_trail = [{"x": player_x, "y": player_y, "spawned_at": now_local}]
        deja_vu_ghost_acc = 0.0
        deja_vu_return_started_at = None

    def finish_deja_vu():
        nonlocal deja_vu_active, deja_vu_snapshot, deja_vu_ghost_acc, deja_vu_return_started_at
        nonlocal deja_vu_active_budget, deja_vu_charge, deja_vu_recharge_available_at
        if deja_vu_snapshot is None:
            deja_vu_active = False
            return
        elapsed = max(0.0, time.time() - deja_vu_started_at)
        deja_vu_charge = max(0.0, min(DEJA_VU_MAX_CHARGE, deja_vu_active_budget - elapsed))
        deja_vu_recharge_available_at = time.time() + DEJA_VU_RECHARGE_DELAY
        restore_deja_vu_snapshot(deja_vu_snapshot)
        deja_vu_active = False
        deja_vu_snapshot = None
        deja_vu_ghost_acc = 0.0
        deja_vu_active_budget = 0.0
        deja_vu_return_started_at = time.time()

    def update_deja_vu(delta_time):
        nonlocal deja_vu_ghost_acc, deja_vu_ghost_trail, deja_vu_charge
        now_local = time.time()
        deja_vu_ghost_trail = [
            point for point in deja_vu_ghost_trail
            if now_local - point["spawned_at"] < DEJA_VU_GHOST_LIFETIME
        ]
        if not deja_vu_active and now_local >= deja_vu_recharge_available_at and deja_vu_charge < DEJA_VU_MAX_CHARGE:
            fast_rate = DEJA_VU_FAST_CHARGE_CAP / DEJA_VU_FAST_CHARGE_TIME
            slow_charge_amount = max(0.0, DEJA_VU_MAX_CHARGE - DEJA_VU_FAST_CHARGE_CAP)
            slow_rate = slow_charge_amount / DEJA_VU_SLOW_CHARGE_TIME if slow_charge_amount > 0 else fast_rate
            recharge_left = max(0.0, delta_time)

            if deja_vu_charge < DEJA_VU_FAST_CHARGE_CAP and recharge_left > 0.0:
                fast_missing = DEJA_VU_FAST_CHARGE_CAP - deja_vu_charge
                fast_gain = min(fast_missing, recharge_left * fast_rate)
                deja_vu_charge += fast_gain
                recharge_left -= fast_gain / fast_rate

            if deja_vu_charge >= DEJA_VU_FAST_CHARGE_CAP and recharge_left > 0.0:
                deja_vu_charge = min(DEJA_VU_MAX_CHARGE, deja_vu_charge + recharge_left * slow_rate)
        if not deja_vu_active:
            return
        deja_vu_ghost_acc += delta_time
        if deja_vu_ghost_acc >= DEJA_VU_GHOST_INTERVAL:
            deja_vu_ghost_acc = 0.0
            if (
                not deja_vu_ghost_trail
                or math.hypot(player_x - deja_vu_ghost_trail[-1]["x"], player_y - deja_vu_ghost_trail[-1]["y"]) > 0.08
            ):
                deja_vu_ghost_trail.append({"x": player_x, "y": player_y, "spawned_at": now_local})
        if now_local - deja_vu_started_at >= deja_vu_active_budget:
            finish_deja_vu()

    def get_deja_vu_visual_mix(now_value):
        if deja_vu_active:
            return _clamp01((now_value - deja_vu_started_at) / DEJA_VU_ENTER_FADE)
        if deja_vu_return_started_at is not None:
            return 1.0 - _clamp01((now_value - deja_vu_return_started_at) / DEJA_VU_RETURN_FADE)
        return 0.0

    def get_deja_vu_speed_multiplier(now_value):
        return 1.0 + (DEJA_VU_SPEED_BOOST - 1.0) * get_deja_vu_visual_mix(now_value)

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

    def restart_pending():
        return mannequin_restart_at is not None or player_restart_at is not None

    def trigger_player_death(now_value):
        nonlocal player_restart_at
        if player_restart_at is None:
            player_restart_at = now_value + 0.35

    def build_sentry_visible_cells(sentry):
        hexagaze_logic.build_visible_cells(sentry, MAP, has_line_of_sight)

    def is_blocked_by_sentry(x_pos, y_pos):
        return hexagaze_logic.is_blocked_by_sentry(sentries, x_pos, y_pos, HEXAGAZE_BLOCK_RADIUS)

    def player_in_sentry_sight(sentry):
        if sentry["health"] <= 0:
            return False
        if math.hypot(player_x - sentry["x"], player_y - sentry["y"]) <= HEXAGAZE_CLOSE_SIGHT_RADIUS:
            return has_line_of_sight(sentry["x"], sentry["y"], player_x, player_y)
        player_cell = (int(player_x), int(player_y))
        return player_cell in sentry["visible_cells"] and has_line_of_sight(sentry["x"], sentry["y"], player_x, player_y)

    def player_in_sentry_radius(sentry):
        if sentry["health"] <= 0:
            return False
        radius = float(sentry.get("vision_radius", HEXAGAZE_RADIUS_CELLS))
        return math.hypot(player_x - sentry["x"], player_y - sentry["y"]) <= radius + 0.01

    def queue_next_hexagaze_roll(sentry, now_local):
        roll_name = random.choice(("roll1", "roll2", "roll4"))
        roll_duration = hexagaze_roll_durations.get(roll_name, HEXAGAZE_ROLL_DURATION)
        sentry["queued_roll"] = roll_name
        sentry["roll_started_at"] = now_local
        sentry["roll_visible_until"] = now_local + roll_duration
        if roll_name == "roll1":
            sentry["queued_attack_kind"] = "homing"
            sentry["queued_attack_shots"] = 1
        elif roll_name == "roll2":
            sentry["queued_attack_kind"] = "snake"
            sentry["queued_attack_shots"] = 2
        else:
            sentry["queued_attack_kind"] = "normal"
            sentry["queued_attack_shots"] = 4
        sentry["cooldown_until"] = now_local + roll_duration

    def start_sentry_burst(sentry, now_local):
        sentry["burst_shots_left"] = max(1, int(sentry.get("queued_attack_shots", HEXAGAZE_BURST_SIZE)))
        sentry["burst_shots_fired"] = 0
        sentry["next_shot_at"] = now_local + HEXAGAZE_FIRST_SHOT_DELAY
        sentry["queued_roll"] = None
        sentry["roll_visible_until"] = 0.0
        sentry["attack_cycle_id"] += 1
        sentry["current_cycle_id"] = sentry["attack_cycle_id"]

    def spawn_sentry_projectile(sentry, attack_kind=None, base_angle=None, speed_override=None):
        color = orb_cycle[sentry["orb_cycle_index"] % len(orb_cycle)]
        sentry["orb_cycle_index"] += 1
        angle = base_angle if base_angle is not None else math.atan2(player_y - sentry["y"], player_x - sentry["x"])
        sentry["facing_angle"] = angle
        attack_kind = attack_kind or sentry.get("queued_attack_kind", "normal")
        shot_index = sentry.get("burst_shots_fired", 0)
        wave_direction = 0
        wave_phase = 0.0
        if attack_kind == "snake":
            wave_direction = -1 if shot_index % 2 == 0 else 1
            wave_phase = shot_index * math.pi
        projectile_speed = speed_override if speed_override is not None else HEXAGAZE_PROJECTILE_SPEED
        sentry_projectiles.append(
            {
                "x": sentry["x"] + math.cos(angle) * 0.38,
                "y": sentry["y"] + math.sin(angle) * 0.38,
                "vx": math.cos(angle) * projectile_speed,
                "vy": math.sin(angle) * projectile_speed,
                "color": color,
                "kind": attack_kind,
                "wave_direction": wave_direction,
                "wave_phase": wave_phase,
                "age": 0.0,
                "owner_cell": (sentry["cell_x"], sentry["cell_y"]),
                "cycle_id": sentry.get("current_cycle_id", 0),
            }
        )

    def launch_hexagaze_entry_burst(sentry, now_local):
        sentry["queued_roll"] = None
        sentry["roll_visible_until"] = 0.0
        sentry["burst_shots_left"] = 0
        sentry["waiting_for_hit"] = False
        sentry["waiting_until"] = now_local + HEXAGAZE_POST_ATTACK_WAIT
        sentry["attack_cycle_id"] += 1
        sentry["current_cycle_id"] = sentry["attack_cycle_id"]
        base_angle = math.atan2(player_y - sentry["y"], player_x - sentry["x"])
        for _ in range(HEXAGAZE_ENTRY_BURST_COUNT):
            spawn_sentry_projectile(
                sentry,
                attack_kind="fast",
                base_angle=base_angle,
                speed_override=HEXAGAZE_ENTRY_BURST_SPEED,
            )

    def update_sentries(delta_time):
        hexagaze_logic.update_sentries(
            sentries,
            sentry_projectiles,
            delta_time,
            time.time(),
            player_x,
            player_y,
            is_wall,
            has_line_of_sight,
            elevator_active or stats_window_active or intro_active or start_cutscene_active or restart_pending(),
            damage_player,
            hexagaze_config,
        )

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

    def get_directional_frame_index(target_x, target_y, frames):
        if target_x is None or target_y is None or not frames:
            return 0
        viewer_angle = math.atan2(player_y - target_y, player_x - target_x)
        sector_size = (2 * math.pi) / len(frames)
        sector = int((viewer_angle % (2 * math.pi)) / sector_size) % len(frames)
        return sector

    def get_mannequin_frame_index():
        sync_mannequin_state_to_module()
        return mannequin_logic.get_frame_index(mannequin_state, player_x, player_y, len(mannequin_frames))

    def get_hexagaze_frame_index(hexagaze):
        return hexagaze_logic.get_frame_index(hexagaze, player_x, player_y, len(hexagaze_frames))

    def get_hexagaze_roll_frame_index(hexagaze, frames, now_value):
        return hexagaze_logic.get_roll_frame_index(hexagaze, frames, now_value, HEXAGAZE_ROLL_FRAME_TIME)

    def player_can_see_mannequin():
        sync_mannequin_state_to_module()
        return mannequin_logic.player_can_see(mannequin_state, player_x, player_y, player_angle, has_line_of_sight)

    def mannequin_can_see_player():
        sync_mannequin_state_to_module()
        return mannequin_logic.can_see_player(mannequin_state, player_x, player_y, has_line_of_sight)

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
        sync_mannequin_state_to_module()
        mannequin_logic.update_state(
            mannequin_state,
            MAP,
            delta_time,
            time.time(),
            player_x,
            player_y,
            player_angle,
            has_line_of_sight,
            is_walkable_cell,
            elevator_active or stats_window_active or intro_active or start_cutscene_active,
            trigger_mannequin_attack,
        )
        sync_mannequin_state_from_module()

    def push_mannequin_back():
        sync_mannequin_state_to_module()
        mannequin_logic.push_back(mannequin_state, MAP, player_x, player_y, player_angle, has_line_of_sight, is_walkable_cell)
        sync_mannequin_state_from_module()

    def trigger_mannequin_attack(now):
        nonlocal mannequin_restart_at
        if mannequin_restart_at is not None:
            return
        play_sound_effect(mannequin_attack_sound_path)
        mannequin_restart_at = now + max(0.2, mannequin_attack_duration)

    for sentry in sentries:
        build_sentry_visible_cells(sentry)

    while running:
        delta = clock.tick(120) / 1000.0
        update_music(delta)
        if delta <= 0:
            delta = 1.0 / 60.0
        now = time.time()
        deja_vu_visual_mix = get_deja_vu_visual_mix(now)
        deja_vu_speed_multiplier = get_deja_vu_speed_multiplier(now)
        if not deja_vu_active and (
            (mannequin_restart_at is not None and now >= mannequin_restart_at)
            or (player_restart_at is not None and now >= player_restart_at)
        ):
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
                if restart_pending():
                    continue
                # Allow movement only when elevator is not active and stats are not shown
                if elevator_active or start_cutscene_active:
                    continue
                elif event.unicode in "12345":
                    selected_slot = int(event.unicode)
                elif event.key == pygame.K_v:
                    activate_deja_vu()
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
                if restart_pending():
                    continue
                if event.button in (1, 3):
                    use_selected_item(event.button)
            elif event.type == pygame.MOUSEWHEEL:
                if elevator_active or stats_window_active or start_cutscene_active or restart_pending() or not allow_wheel_switch:
                    continue
                if event.y > 0:
                    selected_slot -= 1
                else:
                    selected_slot += 1
                if selected_slot < 1:
                    selected_slot = 5
                if selected_slot > 5:
                    selected_slot = 1

        if restart_pending():
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
                current_speed = SPEED * deja_vu_speed_multiplier
                move_x = (move_x / move_len) * current_speed
                move_y = (move_y / move_len) * current_speed

            mouse_dx, _mouse_dy = pygame.mouse.get_rel()
            if mouse_dx:
                player_angle = wrap_angle(player_angle + mouse_dx * MOUSE_SENSITIVITY)

            # Trigger lift when player is inside 'N' tile.
            # Tile-based trigger is more stable than a distance radius.
            if (not intro_active) and lift_tiles and not elevator_active and not stats_window_active and not deja_vu_active:
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

            if not is_wall(nx, player_y) and not is_blocked_by_sentry(nx, player_y):
                player_x = nx
            if not is_wall(player_x, ny) and not is_blocked_by_sentry(player_x, ny):
                player_y = ny

            player_z = get_floor_height(player_x, player_y)

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
        if bomb_pickups:
            bomb_pickups, picked_bomb = bomb_logic.pickup_bombs(bomb_pickups, player_x, player_y, PICKUP_GUN_RADIUS)
            if picked_bomb:
                slot2_item = "bomb"
                if selected_slot == 2 and activator_click_animating:
                    activator_click_animating = False
                    activator_click_frame_index = 0
                    activator_click_acc = 0.0

        update_mannequin(delta)
        update_sentries(delta)
        update_deja_vu(delta)
        update_bomb_system(delta, time.time())
        update_hand_swap(delta)

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

        punch_frame_time = 0.05
        if punch_animating:
            punch_acc += delta
            frames = right_punch_frames_raw if punch_side == "right" else left_punch_frames_raw
            while punch_acc >= punch_frame_time and punch_animating:
                punch_acc -= punch_frame_time
                punch_frame_index += 1
                if punch_frame_index >= len(frames):
                    punch_animating = False
                    punch_frame_index = 0

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
            floor_height_getter=get_floor_height,
        )
        flash_timer = flash_ref[0]

        if deja_vu_active:
            for sentry in sentries:
                if sentry["health"] <= 0:
                    continue
                safe_cells = sentry["zone_cells"] - sentry["visible_cells"]
                for cell_x, cell_y in safe_cells:
                    ray_engine.render_sprite(
                        sentry_safe_frames,
                        0,
                        cell_x + 0.5,
                        cell_y + 0.5,
                        0.18,
                        depth_buffer,
                        player_x,
                        player_y,
                        player_angle,
                        bob_offset,
                        sprite_cache,
                        vertical_anchor="floor",
                    )
                for cell_x, cell_y in sentry["visible_cells"]:
                    ray_engine.render_sprite(
                        sentry_danger_frames,
                        0,
                        cell_x + 0.5,
                        cell_y + 0.5,
                        0.18,
                        depth_buffer,
                        player_x,
                        player_y,
                        player_angle,
                        bob_offset,
                        sprite_cache,
                        vertical_anchor="floor",
                    )

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
        for bx, by in bomb_pickups:
            ray_engine.render_sprite(
                bomb_pickup_frames,
                0,
                bx,
                by,
                bomb_pickup_scale,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
            )
        if selected_slot == 2 and slot2_item == "bomb":
            target_cell = get_targeted_floor_cell()
            if target_cell is not None:
                ray_engine.render_sprite(
                    target_marker_frames,
                    0,
                    target_cell[0] + 0.5,
                    target_cell[1] + 0.5,
                    0.20,
                    depth_buffer,
                    player_x,
                    player_y,
                    player_angle,
                    bob_offset,
                    sprite_cache,
                    vertical_anchor="floor",
                )
        for bomb in placed_bombs:
            ray_engine.render_sprite(
                bombon_frames_raw,
                bomb_world_frame_index,
                bomb["x"],
                bomb["y"],
                0.34,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
                vertical_anchor="floor",
            )
        for explosion in active_explosions:
            frame_index = min(explosion["frame_index"], len(boom_frames_raw) - 1)
            ray_engine.render_sprite(
                boom_frames_raw,
                frame_index,
                explosion["x"],
                explosion["y"] + 0.12,
                0.90,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
                vertical_anchor="floor",
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

        for sentry in sentries:
            if sentry["health"] <= 0:
                continue
            roll_name = sentry.get("queued_roll")
            roll_frames = hexagaze_roll_animations.get(roll_name) if roll_name else None
            if roll_frames and sentry["burst_shots_left"] <= 0 and now < sentry.get("roll_visible_until", 0.0):
                render_frames = roll_frames
                render_frame_index = get_hexagaze_roll_frame_index(sentry, roll_frames, now)
            else:
                render_frames = hexagaze_frames
                render_frame_index = get_hexagaze_frame_index(sentry)
            ray_engine.render_sprite(
                render_frames,
                render_frame_index,
                sentry["x"],
                sentry["y"],
                0.55,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
            )

        for projectile in sentry_projectiles:
            ray_engine.render_sprite(
                [orb_textures[projectile["color"]]],
                0,
                projectile["x"],
                projectile["y"],
                0.12,
                depth_buffer,
                player_x,
                player_y,
                player_angle,
                bob_offset,
                sprite_cache,
            )

        ghost_now = time.time()
        for ghost_point in deja_vu_ghost_trail:
            life_ratio = 1.0 - ((ghost_now - ghost_point["spawned_at"]) / DEJA_VU_GHOST_LIFETIME)
            if life_ratio <= 0.0:
                continue
            frame_index = min(
                len(deja_vu_ghost_frames) - 1,
                int((1.0 - life_ratio) * len(deja_vu_ghost_frames)),
            )
            ghost_scale = 0.085 + life_ratio * 0.03
            ray_engine.render_sprite(
                deja_vu_ghost_frames,
                frame_index,
                ghost_point["x"],
                ghost_point["y"],
                ghost_scale,
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
        if (not elevator_active) and (not start_cutscene_active):
            hand_slide_distance = int(game_view_h * 0.58)
            hand_swap_eased = _ease_out_cubic(hand_swap_progress)
            if hand_swap_active and hand_previous_item_id is not None:
                previous_pil = get_hand_pil_for_item(hand_previous_item_id)
                if previous_pil is not None:
                    previous_surface = build_hand_surface_from_pil(previous_pil, hand_previous_item_id)
                    previous_y = gun_y + int(hand_slide_distance * hand_swap_eased)
                    game_surface.blit(previous_surface, previous_surface.get_rect(midbottom=(game_view_w // 2, previous_y)))

            current_pil = get_hand_pil_for_item(hand_target_item_id)
            if current_pil is not None:
                current_surface = build_hand_surface_from_pil(current_pil, hand_target_item_id)
                current_y = gun_y
                if hand_swap_active:
                    current_y = gun_y + int(hand_slide_distance * (1.0 - hand_swap_eased))
                game_surface.blit(current_surface, current_surface.get_rect(midbottom=(game_view_w // 2, current_y)))

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

        if deja_vu_visual_mix > 0.001:
            ghost_surface = screen.copy()
            ghost_surface.set_alpha(int(24 + 36 * deja_vu_visual_mix))
            ghost_shift = max(1, int(2 + 4 * deja_vu_visual_mix))
            screen.blit(ghost_surface, (ghost_shift, 0))
            screen.blit(ghost_surface, (-ghost_shift, 0))

        if deja_vu_active:
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((28, 90, 96, int(20 + 32 * deja_vu_visual_mix)))
            screen.blit(overlay, (0, 0))

            pulse = (math.sin((time.time() - deja_vu_started_at) * 8.0) + 1.0) * 0.5
            vignette_alpha = int((26 + pulse * 42) * deja_vu_visual_mix)
            frame_surface = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.rect(frame_surface, (120, 255, 235, vignette_alpha), (10, 10, W - 20, H - 20), width=3)
            screen.blit(frame_surface, (0, 0))

        if deja_vu_return_started_at is not None:
            rewind_progress = (time.time() - deja_vu_return_started_at) / DEJA_VU_RETURN_FADE
            if rewind_progress >= 1.0:
                deja_vu_return_started_at = None
            else:
                collapse_radius = int((1.0 - rewind_progress) * min(W, H) * 0.35)
                collapse_surface = pygame.Surface((W, H), pygame.SRCALPHA)
                pygame.draw.circle(
                    collapse_surface,
                    (200, 255, 245, int(110 * (1.0 - rewind_progress))),
                    (W // 2, H // 2),
                    max(12, collapse_radius),
                    width=max(2, int(10 * (1.0 - rewind_progress) + 2)),
                )
                screen.blit(collapse_surface, (0, 0))
                rewind_surface = pygame.Surface((W, H), pygame.SRCALPHA)
                rewind_surface.fill((210, 255, 250, int(170 * (1.0 - rewind_progress))))
                screen.blit(rewind_surface, (0, 0))

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

        hp_percent = player_health / max(1, PLAYER_MAX_HEALTH)
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

        deja_now = time.time()
        if deja_vu_active:
            deja_display_charge = max(0.0, deja_vu_active_budget - (deja_now - deja_vu_started_at))
        else:
            deja_display_charge = deja_vu_charge
        deja_ready = deja_display_charge >= DEJA_VU_MIN_ACTIVATION
        if deja_vu_active:
            deja_state = f"{deja_display_charge:04.1f}s"
            deja_color = (120, 255, 235)
        elif deja_ready and deja_vu_available():
            deja_state = f"{deja_display_charge:04.1f}s"
            deja_color = (120, 255, 235)
        else:
            if deja_now < deja_vu_recharge_available_at:
                deja_state = f"WAIT {max(0.0, deja_vu_recharge_available_at - deja_now):03.1f}s"
            else:
                deja_state = f"{deja_display_charge:04.1f}s"
            deja_color = (110, 130, 130)
        deja_box = pygame.Rect(hud_x - 220, hud_y + 20, 190, 56)
        pygame.draw.rect(screen, (0, 18, 18), deja_box)
        pygame.draw.rect(screen, deja_color, deja_box, width=2)
        screen.blit(font_hud.render("DEJA VU [V]", True, deja_color), (deja_box.x + 12, deja_box.y + 6))
        screen.blit(font_hud_big.render(deja_state, True, deja_color), (deja_box.x + 12, deja_box.y + 26))
        charge_fill_w = int((deja_box.width - 24) * (deja_display_charge / DEJA_VU_MAX_CHARGE))
        pygame.draw.rect(screen, (20, 40, 40), (deja_box.x + 12, deja_box.y + deja_box.height - 10, deja_box.width - 24, 4))
        pygame.draw.rect(screen, deja_color, (deja_box.x + 12, deja_box.y + deja_box.height - 10, charge_fill_w, 4))

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
        if slot2_item == "bomb":
            screen.blit(
                bombitem_img,
                bombitem_img.get_rect(center=(start_x + (slot_size + slot_spacing) + slot_size // 2, start_y + slot_size // 2)),
            )
        elif slot2_item == "activator":
            screen.blit(
                activatoritem_img,
                activatoritem_img.get_rect(center=(start_x + (slot_size + slot_spacing) + slot_size // 2, start_y + slot_size // 2)),
            )

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
