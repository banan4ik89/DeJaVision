import math
import random

from PIL import Image, ImageDraw

from bomb import load_gif_frames


def load_hexagaze_assets(resource_path):
    frames = []
    for frame_idx in range(1, 13):
        frame_path = resource_path(f"data/gifs/hexagaze/Hexagaze{frame_idx}.png")
        frames.append(Image.open(frame_path).convert("RGBA"))

    roll_animations = {
        "roll1": load_gif_frames(resource_path("data/gifs/hexagaze/roll1.gif")),
        "roll2": load_gif_frames(resource_path("data/gifs/hexagaze/roll2.gif")),
        "roll4": load_gif_frames(resource_path("data/gifs/hexagaze/roll4.gif")),
    }

    danger_frame = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
    danger_draw = ImageDraw.Draw(danger_frame)
    danger_draw.rectangle((2, 2, 26, 26), fill=(255, 50, 50, 92), outline=(255, 120, 120, 165), width=2)

    safe_frame = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
    safe_draw = ImageDraw.Draw(safe_frame)
    safe_draw.rectangle((2, 2, 26, 26), fill=(40, 200, 80, 76), outline=(110, 255, 150, 145), width=2)

    return {
        "frames": frames,
        "roll_animations": roll_animations,
        "roll_durations": {
            name: max(2.0, len(anim_frames) * 0.06)
            for name, anim_frames in roll_animations.items()
        },
        "danger_frames": [danger_frame],
        "safe_frames": [safe_frame],
    }


def generate_blind_offsets(radius):
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


def collect_sentries(map_data, radius_min, radius_max, orb_cycle):
    sentries = []
    for y, row in enumerate(map_data):
        for x, cell in enumerate(row):
            if cell != "C":
                continue
            vision_radius = random.randint(radius_min, radius_max)
            sentries.append(
                {
                    "x": x + 0.5,
                    "y": y + 0.5,
                    "cell_x": x,
                    "cell_y": y,
                    "health": 10,
                    "max_health": 10,
                    "facing_angle": 0.0,
                    "burst_shots_left": 0,
                    "burst_shots_fired": 0,
                    "next_shot_at": 0.0,
                    "cooldown_until": 0.0,
                    "queued_roll": None,
                    "queued_attack_kind": "normal",
                    "queued_attack_shots": 3,
                    "roll_started_at": 0.0,
                    "roll_visible_until": 0.0,
                    "waiting_until": 0.0,
                    "waiting_for_hit": False,
                    "attack_cycle_id": 0,
                    "current_cycle_id": 0,
                    "player_in_radius_last": False,
                    "vision_radius": vision_radius,
                    "blind_offsets": generate_blind_offsets(vision_radius),
                    "zone_cells": set(),
                    "visible_cells": set(),
                    "orb_cycle_index": (x * 3 + y) % len(orb_cycle),
                }
            )
    return sentries


def build_visible_cells(sentry, map_data, has_line_of_sight):
    zone_cells = set()
    visible = set()
    radius = int(sentry.get("vision_radius", 7))
    blocked = {(sentry["cell_x"] + ox, sentry["cell_y"] + oy) for ox, oy in sentry["blind_offsets"]}
    for cell_y in range(max(0, sentry["cell_y"] - radius), min(len(map_data), sentry["cell_y"] + radius + 1)):
        for cell_x in range(max(0, sentry["cell_x"] - radius), min(len(map_data[0]), sentry["cell_x"] + radius + 1)):
            if (cell_x, cell_y) == (sentry["cell_x"], sentry["cell_y"]):
                continue
            if map_data[cell_y][cell_x] == "#":
                continue
            if math.hypot(cell_x - sentry["cell_x"], cell_y - sentry["cell_y"]) > radius + 0.01:
                continue
            zone_cells.add((cell_x, cell_y))
            if (cell_x, cell_y) in blocked:
                continue
            center_x = cell_x + 0.5
            center_y = cell_y + 0.5
            if has_line_of_sight(sentry["x"], sentry["y"], center_x, center_y):
                visible.add((cell_x, cell_y))
    sentry["zone_cells"] = zone_cells
    sentry["visible_cells"] = visible


def is_blocked_by_sentry(sentries, x_pos, y_pos, block_radius):
    for sentry in sentries:
        if sentry["health"] <= 0:
            continue
        if math.hypot(x_pos - sentry["x"], y_pos - sentry["y"]) < block_radius:
            return True
    return False


def get_directional_frame_index(target_x, target_y, player_x, player_y, frame_count):
    if frame_count <= 0:
        return 0
    viewer_angle = math.atan2(player_y - target_y, player_x - target_x)
    sector_size = (2 * math.pi) / frame_count
    return int((viewer_angle % (2 * math.pi)) / sector_size) % frame_count


def get_frame_index(sentry, player_x, player_y, frame_count):
    return get_directional_frame_index(sentry["x"], sentry["y"], player_x, player_y, frame_count)


def get_roll_frame_index(sentry, frames, now_value, frame_time):
    if not frames:
        return 0
    elapsed = max(0.0, now_value - sentry.get("roll_started_at", now_value))
    return int(elapsed / frame_time) % len(frames)


def update_sentries(sentries, sentry_projectiles, delta_time, now_value, player_x, player_y, is_wall, has_line_of_sight,
                    blocked, damage_player, config):
    def wrap_angle(angle):
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle

    def player_in_sight(sentry):
        if sentry["health"] <= 0:
            return False
        if math.hypot(player_x - sentry["x"], player_y - sentry["y"]) <= config.get("close_sight_radius", 0.9):
            return has_line_of_sight(sentry["x"], sentry["y"], player_x, player_y)
        player_cell = (int(player_x), int(player_y))
        return player_cell in sentry["visible_cells"] and has_line_of_sight(sentry["x"], sentry["y"], player_x, player_y)

    def player_in_radius(sentry):
        if sentry["health"] <= 0:
            return False
        radius = float(sentry.get("vision_radius", config["radius_cells"]))
        return math.hypot(player_x - sentry["x"], player_y - sentry["y"]) <= radius + 0.01

    def queue_next_roll(sentry):
        roll_name = random.choice(("roll1", "roll2", "roll4"))
        roll_duration = config["roll_durations"].get(roll_name, config["roll_duration"])
        sentry["queued_roll"] = roll_name
        sentry["roll_started_at"] = now_value
        sentry["roll_visible_until"] = now_value + roll_duration
        if roll_name == "roll1":
            sentry["queued_attack_kind"] = "homing"
            sentry["queued_attack_shots"] = 1
        elif roll_name == "roll2":
            sentry["queued_attack_kind"] = "snake"
            sentry["queued_attack_shots"] = 2
        else:
            sentry["queued_attack_kind"] = "normal"
            sentry["queued_attack_shots"] = 4
        sentry["cooldown_until"] = now_value + roll_duration

    def start_burst(sentry):
        sentry["burst_shots_left"] = max(1, int(sentry.get("queued_attack_shots", config["burst_size"])))
        sentry["burst_shots_fired"] = 0
        sentry["next_shot_at"] = now_value + config["first_shot_delay"]
        sentry["queued_roll"] = None
        sentry["roll_visible_until"] = 0.0
        sentry["attack_cycle_id"] += 1
        sentry["current_cycle_id"] = sentry["attack_cycle_id"]

    def spawn_projectile(sentry, attack_kind=None, base_angle=None, speed_override=None):
        color = config["orb_cycle"][sentry["orb_cycle_index"] % len(config["orb_cycle"])]
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
        projectile_speed = speed_override if speed_override is not None else config["projectile_speed"]
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

    def launch_entry_burst(sentry):
        sentry["queued_roll"] = None
        sentry["roll_visible_until"] = 0.0
        sentry["burst_shots_left"] = 0
        sentry["waiting_for_hit"] = False
        sentry["waiting_until"] = now_value + config["post_attack_wait"]
        sentry["attack_cycle_id"] += 1
        sentry["current_cycle_id"] = sentry["attack_cycle_id"]
        base_angle = math.atan2(player_y - sentry["y"], player_x - sentry["x"])
        for _ in range(config["entry_burst_count"]):
            spawn_projectile(sentry, attack_kind="fast", base_angle=base_angle, speed_override=config["entry_burst_speed"])

    for sentry in sentries:
        if sentry["health"] <= 0:
            sentry["burst_shots_left"] = 0
            sentry["queued_roll"] = None
            sentry["player_in_radius_last"] = False
            continue

        target_angle = math.atan2(player_y - sentry["y"], player_x - sentry["x"])
        sentry["facing_angle"] = wrap_angle(
            sentry["facing_angle"] + wrap_angle(target_angle - sentry["facing_angle"]) * min(1.0, delta_time * 8.0)
        )

        if blocked:
            sentry["burst_shots_left"] = 0
            sentry["queued_roll"] = None
            sentry["player_in_radius_last"] = False
            continue

        in_radius = player_in_radius(sentry)
        if in_radius and not sentry.get("player_in_radius_last", False):
            launch_entry_burst(sentry)
        sentry["player_in_radius_last"] = in_radius
        sees_player = player_in_sight(sentry)
        if not sees_player:
            sentry["burst_shots_left"] = 0
            if sentry["queued_roll"] is not None:
                sentry["queued_roll"] = None
                sentry["roll_visible_until"] = 0.0
            continue

        if sentry["waiting_for_hit"]:
            if now_value < sentry["waiting_until"]:
                continue
            sentry["waiting_for_hit"] = False

        if sentry["queued_roll"] is None and sentry["burst_shots_left"] <= 0:
            queue_next_roll(sentry)
            continue

        if sentry["queued_roll"] is not None and sentry["burst_shots_left"] <= 0:
            if now_value >= sentry["cooldown_until"]:
                start_burst(sentry)
            continue

        if sentry["burst_shots_left"] > 0 and now_value >= sentry["next_shot_at"]:
            spawn_projectile(sentry)
            sentry["burst_shots_fired"] += 1
            sentry["burst_shots_left"] -= 1
            if sentry["burst_shots_left"] > 0:
                sentry["next_shot_at"] = now_value + config["burst_delay"]
            else:
                sentry["waiting_until"] = now_value + config["post_attack_wait"]
                sentry["waiting_for_hit"] = True

    if not sentry_projectiles:
        return

    kept_projectiles = []
    for projectile in sentry_projectiles:
        projectile["age"] = projectile.get("age", 0.0) + delta_time
        velocity_x = projectile["vx"]
        velocity_y = projectile["vy"]
        speed = math.hypot(velocity_x, velocity_y)
        if speed > 0.0001:
            if projectile.get("kind") == "homing":
                target_angle = math.atan2(player_y - projectile["y"], player_x - projectile["x"])
                current_angle = math.atan2(velocity_y, velocity_x)
                angle_diff = wrap_angle(target_angle - current_angle)
                current_angle += max(-config["homing_turn_rate"] * delta_time, min(config["homing_turn_rate"] * delta_time, angle_diff))
                velocity_x = math.cos(current_angle) * speed
                velocity_y = math.sin(current_angle) * speed
            elif projectile.get("kind") == "snake":
                target_angle = math.atan2(player_y - projectile["y"], player_x - projectile["x"])
                current_angle = math.atan2(velocity_y, velocity_x)
                angle_diff = wrap_angle(target_angle - current_angle)
                current_angle += max(-config["snake_turn_rate"] * delta_time, min(config["snake_turn_rate"] * delta_time, angle_diff))
                wave_offset = math.sin(projectile["age"] * config["snake_wave_speed"] + projectile.get("wave_phase", 0.0))
                current_angle += projectile.get("wave_direction", 1) * wave_offset * config["snake_wave_amplitude"] * delta_time
                velocity_x = math.cos(current_angle) * speed
                velocity_y = math.sin(current_angle) * speed
            projectile["vx"] = velocity_x
            projectile["vy"] = velocity_y

        next_x = projectile["x"] + velocity_x * delta_time
        next_y = projectile["y"] + velocity_y * delta_time
        if is_wall(next_x, next_y):
            continue
        if math.hypot(next_x - player_x, next_y - player_y) <= config["player_hit_radius"]:
            for sentry in sentries:
                if (sentry["cell_x"], sentry["cell_y"]) != projectile.get("owner_cell"):
                    continue
                if sentry.get("current_cycle_id") != projectile.get("cycle_id"):
                    continue
                sentry["waiting_for_hit"] = False
                sentry["waiting_until"] = now_value
                break
            damage_player(config["projectile_damage"], now_value)
            continue
        projectile["x"] = next_x
        projectile["y"] = next_y
        kept_projectiles.append(projectile)
    sentry_projectiles[:] = kept_projectiles
