import copy
import math

from PIL import Image, ImageDraw

from abebe.core.background_music import play_sound_effect


def load_gif_frames(path):
    gif = Image.open(path)
    frames = []
    try:
        while True:
            frames.append(gif.copy().convert("RGBA"))
            gif.seek(len(frames))
    except EOFError:
        pass
    return frames


def load_bomb_assets(resource_path, game_view_w, pil_to_surface):
    bomb_icon_raw = Image.open(resource_path("data/gifs/bomb/bombicon.png")).convert("RGBA")
    bombon_frames_raw = load_gif_frames(resource_path("data/gifs/bomb/bombon.gif"))
    boom_frames_raw = load_gif_frames(resource_path("data/gifs/bomb/boom.gif"))
    activator_img_raw = Image.open(resource_path("data/gifs/hands/activator.png")).convert("RGBA")
    activatorclick_frames_raw = load_gif_frames(resource_path("data/gifs/hands/activatorclick.gif"))
    activatoricon_raw = Image.open(resource_path("data/gifs/hands/activatoricon.png")).convert("RGBA")

    bombitem_img = pil_to_surface(bomb_icon_raw.resize((40, 40), Image.NEAREST))
    activatoritem_img = pil_to_surface(activatoricon_raw.resize((40, 40), Image.NEAREST))

    target_marker_frame = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    target_marker_draw = ImageDraw.Draw(target_marker_frame)
    target_marker_draw.rectangle((2, 2, 29, 29), outline=(255, 235, 80, 230), width=2)
    target_marker_draw.rectangle((9, 9, 22, 22), outline=(255, 170, 40, 180), width=1)

    return {
        "bomb_icon_raw": bomb_icon_raw,
        "bombon_frames_raw": bombon_frames_raw,
        "boom_frames_raw": boom_frames_raw,
        "boom_sound_path": resource_path("data/gifs/bomb/boom.mp3"),
        "activator_img_raw": activator_img_raw,
        "activatorclick_frames_raw": activatorclick_frames_raw,
        "bombitem_img": bombitem_img,
        "activatoritem_img": activatoritem_img,
        "bomb_pickup_frames": [bomb_icon_raw],
        "bomb_pickup_scale": (int(game_view_w * 0.1)) / max(bomb_icon_raw.width, 1),
        "target_marker_frames": [target_marker_frame],
    }


def collect_bomb_pickups(map_data, symbol="B"):
    if isinstance(map_data, dict) and map_data.get("bomb_pickups") is not None:
        return list(map_data.get("bomb_pickups", []))
    pickups = []
    for y, row in enumerate(map_data):
        for x, cell in enumerate(row):
            if cell == symbol:
                pickups.append((x + 0.5, y + 0.5))
    return pickups


def capture_snapshot(bomb_pickups, placed_bombs, active_explosions, bomb_world_frame_index, bomb_world_anim_acc,
                     activator_click_animating, activator_click_frame_index, activator_click_acc):
    return {
        "bomb_pickups": list(bomb_pickups),
        "placed_bombs": copy.deepcopy(placed_bombs),
        "active_explosions": copy.deepcopy(active_explosions),
        "bomb_world_frame_index": bomb_world_frame_index,
        "bomb_world_anim_acc": bomb_world_anim_acc,
        "activator_click_animating": activator_click_animating,
        "activator_click_frame_index": activator_click_frame_index,
        "activator_click_acc": activator_click_acc,
    }


def get_targeted_floor_cell(player_x, player_y, player_angle, is_wall, placed_bombs, max_distance=3.2, step=0.03):
    ray_x = math.cos(player_angle)
    ray_y = math.sin(player_angle)
    player_cell = (int(player_x), int(player_y))
    last_open_cell = None
    distance = 0.35
    while distance <= max_distance:
        sample_x = player_x + ray_x * distance
        sample_y = player_y + ray_y * distance
        cell_x = int(sample_x)
        cell_y = int(sample_y)
        if is_wall(cell_x, cell_y):
            break
        if (cell_x, cell_y) != player_cell:
            last_open_cell = (cell_x, cell_y)
        distance += step
    if last_open_cell is None:
        return None
    if any(bomb["cell"] == last_open_cell for bomb in placed_bombs):
        return None
    return last_open_cell


def place_bomb(selected_slot, slot2_item, placed_bombs, player_x, player_y, player_angle, is_wall):
    if selected_slot != 2 or slot2_item != "bomb":
        return slot2_item, False
    target_cell = get_targeted_floor_cell(player_x, player_y, player_angle, is_wall, placed_bombs)
    if target_cell is None:
        return slot2_item, False
    placed_bombs.append(
        {
            "cell": target_cell,
            "x": target_cell[0] + 0.5,
            "y": target_cell[1] + 0.5,
        }
    )
    return "activator", True


def trigger_activator(selected_slot, slot2_item, placed_bombs, activator_click_animating, now_value):
    if selected_slot != 2 or slot2_item != "activator" or not placed_bombs or activator_click_animating:
        return activator_click_animating, 0, 0.0, False
    for bomb in placed_bombs:
        if bomb.get("trigger_at") is None:
            bomb["trigger_at"] = now_value + 1.0
            break
    return True, 0, 0.0, True


def pickup_bombs(bomb_pickups, player_x, player_y, pickup_radius):
    kept = []
    picked = False
    for bx, by in bomb_pickups:
        if math.hypot(player_x - bx, player_y - by) < pickup_radius:
            picked = True
        else:
            kept.append((bx, by))
    return kept, picked


def spawn_bomb_explosion(active_explosions, boom_sound_path, cell):
    play_sound_effect(boom_sound_path)
    active_explosions.append(
        {
            "cell": cell,
            "x": cell[0] + 0.5,
            "y": cell[1] + 0.5,
            "frame_index": 0,
            "acc": 0.0,
        }
    )


def detonate_bomb_at_cell(placed_bombs, active_explosions, boom_sound_path, cell, radius_cells, now_value, damage_callback):
    kept_bombs = []
    bomb_removed = False
    for bomb in placed_bombs:
        if (not bomb_removed) and bomb["cell"] == cell:
            bomb_removed = True
            continue
        kept_bombs.append(bomb)
    if not bomb_removed:
        return False
    placed_bombs[:] = kept_bombs
    spawn_bomb_explosion(active_explosions, boom_sound_path, cell)
    if damage_callback is not None:
        damage_callback(cell, radius_cells, now_value)
    return True


def update_bomb_system(placed_bombs, active_explosions, bomb_assets, delta_time, now_value, player_cell, mannequin_cell,
                       mannequin_alive, damage_callback, bomb_world_frame_index, bomb_world_anim_acc,
                       activator_click_animating, activator_click_frame_index, activator_click_acc):
    if placed_bombs:
        for bomb in list(placed_bombs):
            if bomb.get("trigger_at") is not None and now_value >= bomb["trigger_at"]:
                detonate_bomb_at_cell(placed_bombs, active_explosions, bomb_assets["boom_sound_path"], bomb["cell"], 1, now_value, damage_callback)
                continue
            if mannequin_alive and mannequin_cell == bomb["cell"]:
                detonate_bomb_at_cell(placed_bombs, active_explosions, bomb_assets["boom_sound_path"], bomb["cell"], 0, now_value, damage_callback)
                continue
            if player_cell == bomb["cell"]:
                detonate_bomb_at_cell(placed_bombs, active_explosions, bomb_assets["boom_sound_path"], bomb["cell"], 0, now_value, damage_callback)
                continue

    bomb_frame_time = 0.08
    if placed_bombs:
        bomb_world_anim_acc += delta_time
        while bomb_world_anim_acc >= bomb_frame_time:
            bomb_world_anim_acc -= bomb_frame_time
            bomb_world_frame_index = (bomb_world_frame_index + 1) % max(1, len(bomb_assets["bombon_frames_raw"]))
    else:
        bomb_world_anim_acc = 0.0
        bomb_world_frame_index = 0

    activator_frame_time = 0.05
    if activator_click_animating:
        activator_click_acc += delta_time
        while activator_click_acc >= activator_frame_time and activator_click_animating:
            activator_click_acc -= activator_frame_time
            activator_click_frame_index += 1
            if activator_click_frame_index >= len(bomb_assets["activatorclick_frames_raw"]):
                activator_click_animating = False
                activator_click_frame_index = 0
                activator_click_acc = 0.0

    explosion_frame_time = 0.06
    kept_explosions = []
    for explosion in active_explosions:
        explosion["acc"] += delta_time
        while explosion["acc"] >= explosion_frame_time:
            explosion["acc"] -= explosion_frame_time
            explosion["frame_index"] += 1
        if explosion["frame_index"] < len(bomb_assets["boom_frames_raw"]):
            kept_explosions.append(explosion)
    active_explosions[:] = kept_explosions

    return {
        "bomb_world_frame_index": bomb_world_frame_index,
        "bomb_world_anim_acc": bomb_world_anim_acc,
        "activator_click_animating": activator_click_animating,
        "activator_click_frame_index": activator_click_frame_index,
        "activator_click_acc": activator_click_acc,
    }


def get_hand_pil(slot2_item, bomb_assets, activator_click_animating, activator_click_frame_index):
    if slot2_item == "bomb":
        return bomb_assets["bomb_icon_raw"]
    if slot2_item == "activator":
        if activator_click_animating:
            frames = bomb_assets["activatorclick_frames_raw"]
            return frames[min(activator_click_frame_index, len(frames) - 1)]
        return bomb_assets["activator_img_raw"]
    return None

