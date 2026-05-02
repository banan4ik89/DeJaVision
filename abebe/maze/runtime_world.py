import math
import time

from abebe.entities import hexagaze as hexagaze_logic
from abebe.entities import mannequin as mannequin_logic
from abebe.maze.opengl_maze_core import (
    draw_billboard,
    draw_floor_and_ceiling,
    draw_floor_cell_fill,
    draw_floor_cell_outline,
    fog_shade,
)


def draw_billboard_sprite(sprite_batch, player_x, player_y, x, y, bottom_z, pil_image, height_world, alpha=1.0, tint=(1.0, 1.0, 1.0)):
    if pil_image is None:
        return
    sprite_batch.append(
        {
            "dist": math.hypot(x - player_x, y - player_y),
            "x": x,
            "y": y,
            "bottom_z": bottom_z,
            "image": pil_image,
            "height_world": height_world,
            "alpha": alpha,
            "tint": tint,
        }
    )


def has_line_of_sight(x1, y1, x2, y2, is_wall_fn, step=0.1):
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist <= 0.01:
        return True
    steps = max(1, int(dist / step))
    for i in range(1, steps):
        px = x1 + dx * (i / steps)
        py = y1 + dy * (i / steps)
        if is_wall_fn(px, py):
            return False
    return True


def get_player_spawn(runtime_geometry, map_rows):
    if runtime_geometry is not None:
        spawn_x, spawn_y = runtime_geometry["spawn_cell"]
        return spawn_x + 0.5, spawn_y + 0.5
    for y, row in enumerate(map_rows):
        for x, cell in enumerate(row):
            if cell == "P":
                return x + 0.5, y + 0.5
    return 10.5, 2.5


def draw_runtime_floor_and_ceiling(runtime_geometry, map_rows, get_floor_height, get_ceiling_height, viewer_x, viewer_y, viewer_angle, rear_cull):
    if runtime_geometry is None:
        draw_floor_and_ceiling(
            map_rows,
            get_floor_height,
            ceiling_height_fn=get_ceiling_height,
            viewer_x=viewer_x,
            viewer_y=viewer_y,
            viewer_angle=viewer_angle,
            rear_cull=rear_cull,
        )
        return

    for surface in runtime_geometry["floor_surfaces"]:
        cell_x = surface["x"]
        cell_y = surface["y"]
        floor_z = surface["z"]
        if rear_cull:
            dx = (cell_x + 0.5) - viewer_x
            dy = (cell_y + 0.5) - viewer_y
            dist = math.hypot(dx, dy)
            if dist > 1.4:
                facing = (dx * math.cos(viewer_angle) + dy * math.sin(viewer_angle)) / max(0.0001, dist)
                if facing < -0.28:
                    continue
        dist = math.hypot((cell_x + 0.5) - viewer_x, (cell_y + 0.5) - viewer_y)
        shade = fog_shade(dist, min_light=0.28)
        draw_floor_cell_fill(cell_x, cell_y, floor_z, color=((0.16 + floor_z * 0.10) * shade, (0.16 + floor_z * 0.03) * shade, 0.18 * shade), alpha=1.0)

    for surface in runtime_geometry["ceiling_surfaces"]:
        cell_x = surface["x"]
        cell_y = surface["y"]
        ceiling_z = surface["z"]
        if rear_cull:
            dx = (cell_x + 0.5) - viewer_x
            dy = (cell_y + 0.5) - viewer_y
            dist = math.hypot(dx, dy)
            if dist > 1.4:
                facing = (dx * math.cos(viewer_angle) + dy * math.sin(viewer_angle)) / max(0.0001, dist)
                if facing < -0.28:
                    continue
        dist = math.hypot((cell_x + 0.5) - viewer_x, (cell_y + 0.5) - viewer_y)
        ceiling_shade = max(0.18, fog_shade(dist, min_light=0.28) * 0.85)
        draw_floor_cell_fill(cell_x, cell_y, ceiling_z, color=(0.08 * ceiling_shade, 0.08 * ceiling_shade, 0.10 * ceiling_shade), alpha=0.95, lift=-0.006)


def iter_runtime_walls(runtime_geometry, map_rows, has_upper_wall_fn):
    if runtime_geometry is None:
        for y, row in enumerate(map_rows):
            for x, cell in enumerate(row):
                if cell != "#":
                    continue
                yield {"x": x, "y": y, "base_z": 0.0, "height": 1.0, "cell": cell}
                if has_upper_wall_fn(x, y):
                    yield {"x": x, "y": y, "base_z": 1.0, "height": 1.0, "cell": cell}
        return

    for wall in runtime_geometry["wall_columns"]:
        yield {
            "x": wall["x"],
            "y": wall["y"],
            "base_z": wall["base_z"],
            "height": wall["height"],
            "cell": "#",
            "scale_x": wall.get("scale_x", 1.0),
            "scale_y": wall.get("scale_y", 1.0),
            "scale_z": wall.get("scale_z", 1.0),
            "offset_x": wall.get("offset_x", 0.0),
            "offset_y": wall.get("offset_y", 0.0),
            "offset_z": wall.get("offset_z", 0.0),
            "rotation": wall.get("rotation", 0.0),
            "rotation_x": wall.get("rotation_x", 0.0),
            "rotation_y": wall.get("rotation_y", 0.0),
        }


def iter_runtime_stairs(runtime_geometry):
    if runtime_geometry is None:
        return
    for stair in runtime_geometry.get("stairs", []):
        yield stair


def iter_runtime_stair_links(runtime_geometry):
    if runtime_geometry is None:
        return
    for link in runtime_geometry.get("stair_links", []):
        yield link


def render_world_sprites(
    state,
    player_x,
    player_y,
    player_angle,
    textures,
    bomb_world_frame_index,
    is_render_point_visible,
    runtime_geometry,
    get_floor_height,
):
    sprite_batch = []

    if state["deja_vu_active"]:
        for sentry in state["sentries"]:
            if sentry["health"] <= 0:
                continue
            safe_cells = sentry["zone_cells"] - sentry["visible_cells"]
            for cell_x, cell_y in safe_cells:
                if not is_render_point_visible(cell_x + 0.5, cell_y + 0.5, near_dist=1.2, back_margin=-0.22):
                    continue
                floor_z = get_floor_height(cell_x + 0.5, cell_y + 0.5)
                draw_floor_cell_fill(cell_x, cell_y, floor_z, color=(0.18, 0.9, 0.36), alpha=0.18)
                draw_floor_cell_outline(cell_x, cell_y, floor_z, color=(0.28, 1.0, 0.42), inset=0.10, thickness=0.03)
            for cell_x, cell_y in sentry["visible_cells"]:
                if not is_render_point_visible(cell_x + 0.5, cell_y + 0.5, near_dist=1.2, back_margin=-0.22):
                    continue
                floor_z = get_floor_height(cell_x + 0.5, cell_y + 0.5)
                draw_floor_cell_fill(cell_x, cell_y, floor_z, color=(1.0, 0.12, 0.12), alpha=0.18)
                draw_floor_cell_outline(cell_x, cell_y, floor_z, color=(1.0, 0.28, 0.22), inset=0.10, thickness=0.03)

    for gx, gy in state["gun_pickups"]:
        if not is_render_point_visible(gx, gy):
            continue
        draw_billboard_sprite(sprite_batch, player_x, player_y, gx, gy, get_floor_height(gx, gy), textures["gun_pickup"], 0.42)

    for bx, by in state["bomb_pickups"]:
        if not is_render_point_visible(bx, by):
            continue
        draw_billboard_sprite(sprite_batch, player_x, player_y, bx, by, get_floor_height(bx, by), textures["bomb_pickup"], 0.40)

    if state["placed_bombs"]:
        bomb_frames = textures["bombon_frames"]
        bomb_frame = bomb_frames[bomb_world_frame_index % len(bomb_frames)]
        for bomb in state["placed_bombs"]:
            if not is_render_point_visible(bomb["x"], bomb["y"]):
                continue
            draw_billboard_sprite(sprite_batch, player_x, player_y, bomb["x"], bomb["y"], get_floor_height(bomb["x"], bomb["y"]), bomb_frame, 0.42)

    for explosion in state["active_explosions"]:
        if not is_render_point_visible(explosion["x"], explosion["y"], near_dist=1.0, back_margin=-0.12):
            continue
        frame_index = min(explosion["frame_index"], len(textures["boom_frames"]) - 1)
        draw_billboard_sprite(
            sprite_batch,
            player_x,
            player_y,
            explosion["x"],
            explosion["y"],
            get_floor_height(explosion["x"], explosion["y"]),
            textures["boom_frames"][frame_index],
            1.0,
        )

    for orb in state["orbs"]:
        if orb["health"] <= 0:
            continue
        if not is_render_point_visible(orb["x"], orb["y"]):
            continue
        bob = math.sin(time.time() * 2.0 + orb["x"]) * 0.08
        draw_billboard_sprite(
            sprite_batch,
            player_x,
            player_y,
            orb["x"],
            orb["y"],
            get_floor_height(orb["x"], orb["y"]) + 0.14 + bob,
            textures["orbs"][orb["color"]],
            0.34,
        )

    sentry_frames = textures["hexagaze_frames"]
    for sentry in state["sentries"]:
        if sentry["health"] <= 0:
            continue
        if not is_render_point_visible(sentry["x"], sentry["y"]):
            continue
        roll_name = sentry.get("queued_roll")
        roll_frames = textures["hexagaze_rolls"].get(roll_name) if roll_name else None
        if roll_frames and sentry["burst_shots_left"] <= 0 and time.time() < sentry.get("roll_visible_until", 0.0):
            elapsed = max(0.0, time.time() - sentry.get("roll_started_at", 0.0))
            frame_index = int(elapsed / 0.06) % max(1, len(roll_frames))
            sentry_frame = roll_frames[frame_index]
        else:
            frame_index = mannequin_logic.get_directional_frame_index(
                sentry["x"],
                sentry["y"],
                player_x,
                player_y,
                len(sentry_frames),
            )
            sentry_frame = sentry_frames[frame_index]
        draw_billboard_sprite(sprite_batch, player_x, player_y, sentry["x"], sentry["y"], get_floor_height(sentry["x"], sentry["y"]), sentry_frame, 0.72)

    for projectile in state["sentry_projectiles"]:
        if not is_render_point_visible(projectile["x"], projectile["y"], near_dist=1.0, back_margin=-0.10):
            continue
        draw_billboard_sprite(
            sprite_batch,
            player_x,
            player_y,
            projectile["x"],
            projectile["y"],
            get_floor_height(projectile["x"], projectile["y"]) + 0.15,
            textures["orbs"][projectile["color"]],
            0.18,
        )

    mannequin_state = state["mannequin_state"]
    if mannequin_state["alive"] and mannequin_state["x"] is not None and mannequin_state["y"] is not None:
        if is_render_point_visible(mannequin_state["x"], mannequin_state["y"]):
            frame_index = mannequin_logic.get_frame_index(mannequin_state, player_x, player_y, len(textures["mannequin_frames"]))
            draw_billboard_sprite(
                sprite_batch,
                player_x,
                player_y,
                mannequin_state["x"],
                mannequin_state["y"],
                get_floor_height(mannequin_state["x"], mannequin_state["y"]),
                textures["mannequin_frames"][frame_index],
                0.95,
            )

    ghost_frames = textures["ghost_frames"]
    for ghost in state["deja_vu_ghost_trail"]:
        life_ratio = 1.0 - ((time.time() - ghost["spawned_at"]) / max(0.001, 9.0))
        if life_ratio <= 0.0:
            continue
        if not is_render_point_visible(ghost["x"], ghost["y"], near_dist=0.9, back_margin=-0.08):
            continue
        frame_index = min(len(ghost_frames) - 1, int((1.0 - life_ratio) * len(ghost_frames)))
        draw_billboard_sprite(
            sprite_batch,
            player_x,
            player_y,
            ghost["x"],
            ghost["y"],
            get_floor_height(ghost["x"], ghost["y"]) + 0.04,
            ghost_frames[frame_index],
            0.22,
            alpha=max(0.15, life_ratio * 0.7),
            tint=(0.72, 1.0, 0.96),
        )

    sprite_batch.sort(key=lambda item: item["dist"], reverse=True)
    texture_getter = textures.get("get_cached_texture") or textures.get("texture_cache")
    if texture_getter is None:
        raise KeyError("textures is missing texture cache function")
    for sprite in sprite_batch:
        texture_id, tex_w, tex_h = texture_getter(sprite["image"])
        width_world = sprite["height_world"] * (tex_w / max(1, tex_h))
        draw_billboard(
            sprite["x"],
            sprite["y"],
            sprite["bottom_z"],
            width_world,
            sprite["height_world"],
            texture_id,
            viewer_x=player_x,
            viewer_y=player_y,
            alpha=sprite["alpha"],
            tint=sprite["tint"],
        )
