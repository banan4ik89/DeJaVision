import math
import random
import time

from OpenGL.GL import (
    GL_BLEND,
    GL_DEPTH_TEST,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_QUADS,
    GL_SRC_ALPHA,
    glBegin,
    glBlendFunc,
    glColor4f,
    glDisable,
    glEnable,
    glEnd,
    glVertex3f,
)

from abebe.entities import hexagaze as hexagaze_logic
from abebe.entities import mannequin as mannequin_logic
from abebe.maze.opengl_maze_core import draw_box


def sample_image_color(image, u=0.5, v=0.5):
    if image is None:
        return (0.8, 0.8, 0.8)
    width, height = image.size
    px = max(0, min(width - 1, int(u * width)))
    py = max(0, min(height - 1, int(v * height)))
    r, g, b, *rest = image.getpixel((px, py))
    return (r / 255.0, g / 255.0, b / 255.0)


def spawn_impact_particles(state, enabled, x, y, z, color, count=8, speed=0.9):
    if not enabled:
        return
    for _ in range(count):
        angle = random.uniform(0.0, math.tau)
        lateral_speed = random.uniform(0.06, 0.34) * speed
        upward_bias = random.uniform(-0.08, 0.34) * speed
        state["impact_particles"].append(
            {
                "x": x + random.uniform(-0.035, 0.035),
                "y": y + random.uniform(-0.035, 0.035),
                "z": z + random.uniform(-0.025, 0.05),
                "vx": math.cos(angle) * lateral_speed + random.uniform(-0.08, 0.08),
                "vy": math.sin(angle) * lateral_speed + random.uniform(-0.08, 0.08),
                "vz": upward_bias,
                "size": random.uniform(0.014, 0.042),
                "color": color,
                "life": random.uniform(0.28, 0.82),
                "gravity": random.uniform(1.4, 2.7),
                "drag": random.uniform(0.84, 0.94),
                "bounce": random.uniform(0.08, 0.26),
            }
        )


def spawn_bullet_mark(state, enabled, hit_type, x, y, z):
    if not enabled:
        return
    state["bullet_marks"].append(
        {
            "type": hit_type,
            "x": x,
            "y": y,
            "z": z,
            "life": 20.0,
            "size": random.uniform(0.028, 0.05),
            "alpha": random.uniform(0.18, 0.32),
            "expire_fast": False,
        }
    )
    overflow = len(state["bullet_marks"]) - 50
    if overflow > 0:
        for mark in state["bullet_marks"][:overflow]:
            mark["expire_fast"] = True


def update_impact_particles(state, delta_time, get_floor_height):
    kept = []
    for particle in state["impact_particles"]:
        particle["life"] -= delta_time
        if particle["life"] <= 0.0:
            continue
        particle["vz"] -= particle["gravity"] * delta_time
        particle["x"] += particle["vx"] * delta_time
        particle["y"] += particle["vy"] * delta_time
        particle["z"] += particle["vz"] * delta_time
        drag = particle["drag"] ** max(1.0, delta_time * 60.0)
        particle["vx"] *= drag
        particle["vy"] *= drag
        floor_here = get_floor_height(particle["x"], particle["y"])
        if particle["z"] <= floor_here:
            particle["z"] = floor_here
            particle["vx"] *= 0.55
            particle["vy"] *= 0.55
            particle["vz"] *= -particle["bounce"]
        kept.append(particle)
    state["impact_particles"] = kept


def update_bullet_marks(state, delta_time):
    kept = []
    for mark in state["bullet_marks"]:
        life_decay = 4.5 if mark.get("expire_fast") else 1.0
        mark["life"] -= delta_time * life_decay
        if mark["life"] > 0.0:
            kept.append(mark)
    state["bullet_marks"] = kept


def get_floor_particle_color(floor_z):
    return (
        min(1.0, 0.16 + floor_z * 0.10),
        min(1.0, 0.16 + floor_z * 0.03),
        0.18,
    )


def get_ceiling_particle_color(ceiling_z):
    ceiling_tint = max(0.0, min(1.0, (ceiling_z - 1.3) / 2.2))
    return (0.08 + ceiling_tint * 0.03, 0.08 + ceiling_tint * 0.03, 0.10 + ceiling_tint * 0.04)


def get_wall_sample_uv(hit_x, hit_y, hit_z):
    cell_x = math.floor(hit_x)
    cell_y = math.floor(hit_y)
    local_x = hit_x - cell_x
    local_y = hit_y - cell_y
    if min(local_x, 1.0 - local_x) < min(local_y, 1.0 - local_y):
        u = local_y
    else:
        u = local_x
    v = 1.0 - max(0.0, min(0.999, hit_z))
    return u % 1.0, v


def get_entity_hit_info(sample_x, sample_y, sample_z, state, textures, player_x, player_y, get_floor_height):
    mannequin_state = state["mannequin_state"]
    if mannequin_state["alive"] and mannequin_state["x"] is not None and mannequin_state["y"] is not None:
        base_z = get_floor_height(mannequin_state["x"], mannequin_state["y"])
        if math.hypot(sample_x - mannequin_state["x"], sample_y - mannequin_state["y"]) <= 0.26 and base_z + 0.06 <= sample_z <= base_z + 0.98:
            frame_index = mannequin_logic.get_frame_index(mannequin_state, player_x, player_y, len(textures["mannequin_frames"]))
            frame = textures["mannequin_frames"][frame_index]
            hit_v = 1.0 - max(0.0, min(0.999, (sample_z - base_z) / 0.98))
            return {"type": "mannequin", "x": sample_x, "y": sample_y, "z": sample_z, "color": sample_image_color(frame, 0.5, hit_v)}

    for orb in state["orbs"]:
        if orb["health"] <= 0:
            continue
        base_z = get_floor_height(orb["x"], orb["y"]) + 0.14
        radius = 0.18
        if math.hypot(sample_x - orb["x"], sample_y - orb["y"]) <= radius and base_z - 0.02 <= sample_z <= base_z + 0.34:
            hit_u = 0.5 + (sample_x - orb["x"]) / (radius * 2.0)
            hit_v = 1.0 - max(0.0, min(0.999, (sample_z - (base_z - 0.02)) / 0.36))
            return {
                "type": "orb",
                "entity": orb,
                "x": sample_x,
                "y": sample_y,
                "z": sample_z,
                "color": sample_image_color(textures["orbs"][orb["color"]], max(0.0, min(0.999, hit_u)), hit_v),
            }

    for sentry in state["sentries"]:
        if sentry["health"] <= 0:
            continue
        base_z = get_floor_height(sentry["x"], sentry["y"])
        if math.hypot(sample_x - sentry["x"], sample_y - sentry["y"]) <= 0.24 and base_z + 0.03 <= sample_z <= base_z + 0.74:
            roll_name = sentry.get("queued_roll")
            roll_frames = textures["hexagaze_rolls"].get(roll_name) if roll_name else None
            if roll_frames and sentry["burst_shots_left"] <= 0 and time.time() < sentry.get("roll_visible_until", 0.0):
                elapsed = max(0.0, time.time() - sentry.get("roll_started_at", 0.0))
                frame_index = int(elapsed / 0.06) % max(1, len(roll_frames))
                frame = roll_frames[frame_index]
            else:
                frame_index = hexagaze_logic.get_frame_index(sentry, player_x, player_y, len(textures["hexagaze_frames"]))
                frame = textures["hexagaze_frames"][frame_index]
            hit_v = 1.0 - max(0.0, min(0.999, (sample_z - base_z) / 0.74))
            return {"type": "sentry", "entity": sentry, "x": sample_x, "y": sample_y, "z": sample_z, "color": sample_image_color(frame, 0.5, hit_v)}
    return None


def get_shot_hit_info(get_camera_origin, get_view_ray, state, textures, player_x, player_y, get_floor_height, get_ceiling_height, is_wall, max_distance=12.0, step=0.025):
    origin_x, origin_y, origin_z = get_camera_origin()
    ray_x, ray_y, ray_z = get_view_ray()
    distance = 0.05
    while distance <= max_distance:
        sample_x = origin_x + ray_x * distance
        sample_y = origin_y + ray_y * distance
        sample_z = origin_z + ray_z * distance

        entity_hit = get_entity_hit_info(sample_x, sample_y, sample_z, state, textures, player_x, player_y, get_floor_height)
        if entity_hit is not None:
            entity_hit["dist"] = distance
            return entity_hit

        if is_wall(sample_x, sample_y, sample_z):
            u, v = get_wall_sample_uv(sample_x, sample_y, sample_z)
            return {"type": "wall", "x": sample_x, "y": sample_y, "z": sample_z, "u": u, "v": v, "dist": distance}

        floor_z = get_floor_height(sample_x, sample_y, z_hint=sample_z)
        if sample_z <= floor_z + 0.01 and not is_wall(sample_x, sample_y, sample_z):
            return {"type": "floor", "x": sample_x, "y": sample_y, "z": floor_z, "dist": distance, "color": get_floor_particle_color(floor_z)}

        ceiling_here = get_ceiling_height(sample_x, sample_y, z_hint=sample_z)
        if sample_z >= ceiling_here - 0.01 and not is_wall(sample_x, sample_y, sample_z):
            return {"type": "ceiling", "x": sample_x, "y": sample_y, "z": ceiling_here, "dist": distance, "color": get_ceiling_particle_color(ceiling_here)}
        distance += step
    return None


def render_impact_particles(state, enabled, player_x, player_y, is_render_point_visible):
    if not enabled:
        return
    for particle in state["impact_particles"]:
        if math.hypot(particle["x"] - player_x, particle["y"] - player_y) > 12.0:
            continue
        if not is_render_point_visible(particle["x"], particle["y"], near_dist=0.9, back_margin=-0.08):
            continue
        size = particle["size"]
        life_alpha = max(0.18, min(1.0, particle["life"] / 0.7))
        draw_box(
            particle["x"] - size * 0.5,
            particle["z"],
            particle["y"] - size * 0.5,
            size,
            size,
            particle["color"],
            alpha=life_alpha,
        )


def render_bullet_marks(state, enabled, player_x, player_y, is_render_point_visible):
    if not enabled or not state["bullet_marks"]:
        return

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_DEPTH_TEST)
    try:
        for mark in state["bullet_marks"]:
            if math.hypot(mark["x"] - player_x, mark["y"] - player_y) > 6.0:
                continue
            if not is_render_point_visible(mark["x"], mark["y"], near_dist=0.9, back_margin=-0.08):
                continue
            size = mark["size"]
            half = size * 0.5
            fade = 1.0 if mark["life"] > 4.0 else max(0.0, mark["life"] / 4.0)
            alpha = mark["alpha"] * fade
            if alpha <= 0.0:
                continue
            glColor4f(0.08, 0.08, 0.08, alpha)
            glBegin(GL_QUADS)
            if mark["type"] == "floor":
                z = mark["z"] + 0.006
                glVertex3f(mark["x"] - half, z, mark["y"] - half)
                glVertex3f(mark["x"] + half, z, mark["y"] - half)
                glVertex3f(mark["x"] + half, z, mark["y"] + half)
                glVertex3f(mark["x"] - half, z, mark["y"] + half)
            elif mark["type"] == "ceiling":
                z = mark["z"] - 0.006
                glVertex3f(mark["x"] - half, z, mark["y"] + half)
                glVertex3f(mark["x"] + half, z, mark["y"] + half)
                glVertex3f(mark["x"] + half, z, mark["y"] - half)
                glVertex3f(mark["x"] - half, z, mark["y"] - half)
            else:
                cell_x = math.floor(mark["x"])
                cell_y = math.floor(mark["y"])
                local_x = mark["x"] - cell_x
                local_y = mark["y"] - cell_y
                inset = 0.006
                if min(local_x, 1.0 - local_x) < min(local_y, 1.0 - local_y):
                    wall_x = cell_x + (inset if local_x < 0.5 else 1.0 - inset)
                    glVertex3f(wall_x, mark["z"] - half, mark["y"] - half)
                    glVertex3f(wall_x, mark["z"] + half, mark["y"] - half)
                    glVertex3f(wall_x, mark["z"] + half, mark["y"] + half)
                    glVertex3f(wall_x, mark["z"] - half, mark["y"] + half)
                else:
                    wall_y = cell_y + (inset if local_y < 0.5 else 1.0 - inset)
                    glVertex3f(mark["x"] - half, mark["z"] - half, wall_y)
                    glVertex3f(mark["x"] + half, mark["z"] - half, wall_y)
                    glVertex3f(mark["x"] + half, mark["z"] + half, wall_y)
                    glVertex3f(mark["x"] - half, mark["z"] + half, wall_y)
            glEnd()
    finally:
        glEnable(GL_DEPTH_TEST)
