import math
import random
import time

from PIL import Image


def load_mannequin_assets(resource_path, get_wav_duration):
    frames = []
    for frame_idx in range(1, 10):
        frame_path = resource_path(f"data/gifs/mannequin/mannequin{frame_idx}.png")
        frames.append(Image.open(frame_path).convert("RGBA"))
    sound_path = resource_path("data/gifs/mannequin/attackmannequin.wav")
    return {
        "frames": frames,
        "attack_sound_path": sound_path,
        "attack_duration": get_wav_duration(sound_path, fallback=1.0),
    }


def create_mannequin_state(map_data):
    spawn_x = None
    spawn_y = None

    if isinstance(map_data, dict) and map_data.get("mannequin_spawn"):
        spawn = map_data["mannequin_spawn"]
        spawn_x = float(spawn.get("x", 0.5))
        spawn_y = float(spawn.get("y", 0.5))

    runtime_layers = map_data.get("layers") if isinstance(map_data, dict) else None
    if spawn_x is None and runtime_layers:
        for layer in runtime_layers:
            for y, row in enumerate(layer):
                for x, cell in enumerate(row):
                    if isinstance(cell, dict) and cell.get("tile") == "mannequin":
                        spawn_x = x + 0.5 + float(cell.get("offset_x", 0.0))
                        spawn_y = y + 0.5 + float(cell.get("offset_y", 0.0))
                        break
                if spawn_x is not None:
                    break
            if spawn_x is not None:
                break
    else:
        for y, row in enumerate(map_data):
            for x, cell in enumerate(row):
                if cell == "M":
                    spawn_x = x + 0.5
                    spawn_y = y + 0.5
                    break
            if spawn_x is not None:
                break

    visited = set()
    if spawn_x is not None and spawn_y is not None:
        visited.add((int(spawn_x), int(spawn_y)))
    return {
        "x": spawn_x,
        "y": spawn_y,
        "health": 5,
        "max_health": 5,
        "alive": spawn_x is not None and spawn_y is not None,
        "mode": "search",
        "search_interval": 3.0,
        "next_search_move_at": time.time() + 3.0,
        "search_visited": visited,
        "observe_distance": 5,
        "hidden_active": False,
        "wait_duration": 3.0,
        "next_hidden_step_at": None,
        "notice_radius": 5.0,
        "shot_push_cooldown": 0.0,
        "last_seen_by_player": False,
        "restart_at": None,
    }


def get_directional_frame_index(target_x, target_y, player_x, player_y, frame_count):
    if target_x is None or target_y is None or frame_count <= 0:
        return 0
    viewer_angle = math.atan2(player_y - target_y, player_x - target_x)
    sector_size = (2 * math.pi) / frame_count
    return int((viewer_angle % (2 * math.pi)) / sector_size) % frame_count


def get_frame_index(state, player_x, player_y, frame_count):
    return get_directional_frame_index(state["x"], state["y"], player_x, player_y, frame_count)


def player_can_see(state, player_x, player_y, player_angle, has_line_of_sight):
    if not state["alive"] or state["x"] is None or state["y"] is None:
        return False
    dx = state["x"] - player_x
    dy = state["y"] - player_y
    angle_diff = math.atan2(dy, dx) - player_angle
    while angle_diff > math.pi:
        angle_diff -= 2 * math.pi
    while angle_diff < -math.pi:
        angle_diff += 2 * math.pi
    if abs(angle_diff) > math.radians(30):
        return False
    return has_line_of_sight(player_x, player_y, state["x"], state["y"])


def can_see_player(state, player_x, player_y, has_line_of_sight):
    if not state["alive"] or state["x"] is None or state["y"] is None:
        return False
    if math.hypot(state["x"] - player_x, state["y"] - player_y) > state["notice_radius"]:
        return False
    return has_line_of_sight(state["x"], state["y"], player_x, player_y)


def damage(state, amount):
    if not state["alive"]:
        return False
    state["health"] = max(0, state["health"] - amount)
    if state["health"] <= 0:
        state["alive"] = False
        return True
    return False


def _candidate_cells_around_player(state, map_data, player_x, player_y, player_angle, preferred_dist,
                                   has_line_of_sight, is_walkable_cell, prefer_behind=False, require_los=True):
    back_x = -math.cos(player_angle)
    back_y = -math.sin(player_angle)
    for radius in range(preferred_dist, 0, -1):
        ring = []
        for cell_y in range(len(map_data)):
            for cell_x in range(len(map_data[0])):
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
                current_offset = 0.0
                if state["x"] is not None and state["y"] is not None:
                    current_offset = math.hypot(center_x - state["x"], center_y - state["y"])
                visibility_penalty = 0 if has_line_of_sight(center_x, center_y, player_x, player_y) else 1
                ring.append((dot, abs(actual_dist - radius), visibility_penalty, -current_offset, center_x, center_y, radius))
        if ring:
            if prefer_behind:
                ring.sort(key=lambda item: (-item[0], item[2], item[1], item[3]))
            else:
                ring.sort(key=lambda item: (item[1], item[2], item[3], -item[0]))
            return ring
    return []


def _place_for_observation(state, map_data, player_x, player_y, player_angle, preferred_dist,
                           has_line_of_sight, is_walkable_cell, prefer_behind=False):
    ring = _candidate_cells_around_player(
        state,
        map_data,
        player_x,
        player_y,
        player_angle,
        preferred_dist,
        has_line_of_sight,
        is_walkable_cell,
        prefer_behind=prefer_behind,
        require_los=not prefer_behind,
    )
    if not ring:
        return False
    _, _, _, _, state["x"], state["y"], used_radius = ring[0]
    state["observe_distance"] = used_radius
    return True


def _teleport_behind_player(state, map_data, player_x, player_y, player_angle, distance, has_line_of_sight, is_walkable_cell):
    if _place_for_observation(state, map_data, player_x, player_y, player_angle, distance, has_line_of_sight, is_walkable_cell, prefer_behind=True):
        state["observe_distance"] = distance
        return True
    for fallback_dist in range(distance - 1, 0, -1):
        if _place_for_observation(state, map_data, player_x, player_y, player_angle, fallback_dist, has_line_of_sight, is_walkable_cell, prefer_behind=True):
            state["observe_distance"] = fallback_dist
            return True
    if _place_for_observation(state, map_data, player_x, player_y, player_angle, distance, has_line_of_sight, is_walkable_cell, prefer_behind=False):
        return True
    for fallback_dist in range(distance - 1, 0, -1):
        if _place_for_observation(state, map_data, player_x, player_y, player_angle, fallback_dist, has_line_of_sight, is_walkable_cell, prefer_behind=False):
            return True
    return False


def push_back(state, map_data, player_x, player_y, player_angle, has_line_of_sight, is_walkable_cell):
    current_dist = math.hypot(state["x"] - player_x, state["y"] - player_y)
    target_dist = min(5, max(state["observe_distance"], int(round(current_dist)) + 1))
    ring = _candidate_cells_around_player(
        state,
        map_data,
        player_x,
        player_y,
        player_angle,
        target_dist,
        has_line_of_sight,
        is_walkable_cell,
        prefer_behind=True,
        require_los=False,
    )
    if ring:
        _, _, _, _, next_x, next_y, used_radius = ring[0]
        next_dist = math.hypot(next_x - player_x, next_y - player_y)
        if next_dist >= current_dist - 0.01:
            state["x"] = next_x
            state["y"] = next_y
            state["observe_distance"] = used_radius
            return

    ring = _candidate_cells_around_player(
        state,
        map_data,
        player_x,
        player_y,
        player_angle,
        target_dist,
        has_line_of_sight,
        is_walkable_cell,
        prefer_behind=False,
        require_los=True,
    )
    if not ring:
        return
    _, _, _, _, next_x, next_y, used_radius = ring[0]
    next_dist = math.hypot(next_x - player_x, next_y - player_y)
    if next_dist < current_dist - 0.01:
        return
    state["x"] = next_x
    state["y"] = next_y
    state["observe_distance"] = used_radius


def update_state(state, map_data, delta_time, now_value, player_x, player_y, player_angle, has_line_of_sight,
                 is_walkable_cell, blocked, on_attack):
    if not state["alive"] or state["x"] is None or state["y"] is None or blocked:
        return
    if state["restart_at"] is not None:
        return
    state["shot_push_cooldown"] = max(0.0, state["shot_push_cooldown"] - delta_time)

    if state["mode"] == "search":
        if can_see_player(state, player_x, player_y, has_line_of_sight):
            state["mode"] = "observe"
            state["hidden_active"] = False
            state["next_hidden_step_at"] = None
            state["last_seen_by_player"] = False
            state["observe_distance"] = min(5, max(1, state["observe_distance"]))
            if not _place_for_observation(state, map_data, player_x, player_y, player_angle, state["observe_distance"], has_line_of_sight, is_walkable_cell, prefer_behind=False):
                _place_for_observation(state, map_data, player_x, player_y, player_angle, 1, has_line_of_sight, is_walkable_cell, prefer_behind=False)
            return

        if now_value >= state["next_search_move_at"]:
            current_cell = (int(state["x"]), int(state["y"]))
            options = []
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx = current_cell[0] + dx
                ny = current_cell[1] + dy
                if not is_walkable_cell(nx, ny):
                    continue
                score = 0
                if (nx, ny) not in state["search_visited"]:
                    score += 10
                score += random.random()
                player_dist = math.hypot((nx + 0.5) - player_x, (ny + 0.5) - player_y)
                score += min(player_dist, 6.0) * 0.15
                options.append((score, nx, ny))
            if options:
                options.sort(reverse=True)
                _, nx, ny = options[0]
                state["x"] = nx + 0.5
                state["y"] = ny + 0.5
                state["search_visited"].add((nx, ny))
            state["next_search_move_at"] = now_value + state["search_interval"]
            if can_see_player(state, player_x, player_y, has_line_of_sight):
                state["mode"] = "observe"
                state["hidden_active"] = False
                state["next_hidden_step_at"] = None
                state["last_seen_by_player"] = False
        return

    visible_to_player = player_can_see(state, player_x, player_y, player_angle, has_line_of_sight)
    if visible_to_player:
        state["hidden_active"] = False
        state["next_hidden_step_at"] = None
        state["last_seen_by_player"] = True
        return

    if not state["last_seen_by_player"]:
        if state["hidden_active"] and state["next_hidden_step_at"] is not None and now_value >= state["next_hidden_step_at"]:
            next_distance = max(1, state["observe_distance"] - 1)
            if _teleport_behind_player(state, map_data, player_x, player_y, player_angle, next_distance, has_line_of_sight, is_walkable_cell):
                state["observe_distance"] = next_distance
            if state["observe_distance"] <= 1:
                on_attack(now_value)
                return
            state["next_hidden_step_at"] = now_value + state["wait_duration"]
        return

    state["last_seen_by_player"] = False
    if not state["hidden_active"]:
        next_distance = max(1, state["observe_distance"] - 1)
        if _teleport_behind_player(state, map_data, player_x, player_y, player_angle, next_distance, has_line_of_sight, is_walkable_cell):
            state["observe_distance"] = next_distance
        if state["observe_distance"] <= 1:
            on_attack(now_value)
            return
        state["hidden_active"] = True
        state["next_hidden_step_at"] = now_value + state["wait_duration"]
        return

    if state["next_hidden_step_at"] is None:
        state["next_hidden_step_at"] = now_value + state["wait_duration"]
        return

    if now_value >= state["next_hidden_step_at"]:
        next_distance = max(1, state["observe_distance"] - 1)
        if _teleport_behind_player(state, map_data, player_x, player_y, player_angle, next_distance, has_line_of_sight, is_walkable_cell):
            state["observe_distance"] = next_distance
        if state["observe_distance"] <= 1:
            on_attack(now_value)
            return
        state["next_hidden_step_at"] = now_value + state["wait_duration"]
