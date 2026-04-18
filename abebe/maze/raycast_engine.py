"""
Raycasting wall rendering and billboard sprites (Pygame).
"""
import math
import time

import pygame
from PIL import Image, ImageEnhance
from abebe.core.user_settings import get_fov_radians

FOV = math.pi / 3
# Р—РЅР°С‡РµРЅРёРµ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ; Р°РєС‚СѓР°Р»СЊРЅРѕРµ С‡РёСЃР»Рѕ Р»СѓС‡РµР№ Р±РµСЂРµС‚СЃСЏ РёР· С€РёСЂРёРЅС‹ Р±СѓС„РµСЂР°.
NUM_RAYS = 320
MAX_DEPTH = 10
MAX_RENDER_DIST = 25
RAY_EPSILON = 1e-6
DEFAULT_EYE_HEIGHT = 0.70


def pil_to_surface(pil_img: Image.Image) -> pygame.Surface:
    """PIL Image -> pygame.Surface (RGBA preserved)."""
    mode = pil_img.mode
    size = pil_img.size
    data = pil_img.tobytes()
    surf = pygame.image.frombytes(data, size, mode)
    if mode == "RGBA":
        return surf.convert_alpha()
    return surf.convert()


def draw_floor_ceiling(surface, W, H, num_steps=60, ceiling_base=120, floor_base=120):
    horizon = H // 2
    for i in range(num_steps):
        y1 = int(i * max(1, horizon) / num_steps)
        y2 = int((i + 1) * max(1, horizon) / num_steps)
        dist_ratio = i / num_steps
        fog = 1 - dist_ratio
        shade = int(ceiling_base * fog)
        shade = max(15, min(shade, 220))
        color = (shade, shade, shade)
        pygame.draw.rect(surface, color, (0, y1, W, y2 - y1))

    floor_height = H - horizon
    for i in range(num_steps):
        y1 = horizon + int(i * max(1, floor_height) / num_steps)
        y2 = horizon + int((i + 1) * max(1, floor_height) / num_steps)
        dist_ratio = i / num_steps
        fog = dist_ratio
        shade = int(floor_base * fog)
        shade = max(15, min(shade, 220))
        color = (shade, shade, shade)
        pygame.draw.rect(surface, color, (0, y1, W, y2 - y1))


def _safe_call(getter, *args, default=None):
    if getter is None:
        return default
    value = getter(*args)
    if value is None:
        return default
    return value


class RaycastEngine:
    def __init__(self, screen, W, H, wall_tex, tex_size=32):
        self.screen = screen
        self.W = W
        self.H = H
        self.wall_tex = wall_tex
        self.TEX_SIZE = tex_size
        self.sprite_resize_cache = {}
        self.last_player_z = 0.0
        self.last_eye_height = DEFAULT_EYE_HEIGHT

    def _project_world_y(self, world_z, depth, player_z, bob_offset, eye_height):
        eye_z = player_z + eye_height
        return int(self.H / 2 + bob_offset - ((world_z - eye_z) / max(depth, 0.05)) * self.H)

    def _resolve_wall_segment(
        self,
        map_x,
        map_y,
        wall_height_getter,
        wall_vertical_anchor_getter,
        wall_bottom_getter,
    ):
        wall_scale = max(0.1, float(_safe_call(wall_height_getter, map_x, map_y, default=1.0)))
        wall_bottom = float(_safe_call(wall_bottom_getter, map_x, map_y, default=0.0))
        anchor = _safe_call(wall_vertical_anchor_getter, map_x, map_y, default="center")

        if anchor == "bottom":
            wall_top = wall_bottom + wall_scale
        else:
            center_z = wall_bottom + 0.5
            wall_bottom = center_z - wall_scale / 2
            wall_top = center_z + wall_scale / 2

        return wall_bottom, wall_top

    def _cast_wall_column(self, player_x, player_y, player_angle, ray_angle, is_wall):
        map_x = int(player_x)
        map_y = int(player_y)

        ray_dir_x = math.cos(ray_angle)
        ray_dir_y = math.sin(ray_angle)

        delta_dist_x = abs(1 / ray_dir_x) if abs(ray_dir_x) > RAY_EPSILON else 1e30
        delta_dist_y = abs(1 / ray_dir_y) if abs(ray_dir_y) > RAY_EPSILON else 1e30

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

        while True:
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            if is_wall(map_x, map_y):
                break

        if side == 0:
            denom = ray_dir_x if abs(ray_dir_x) > RAY_EPSILON else (RAY_EPSILON if ray_dir_x >= 0 else -RAY_EPSILON)
            depth = (map_x - player_x + (1 - step_x) / 2) / denom
        else:
            denom = ray_dir_y if abs(ray_dir_y) > RAY_EPSILON else (RAY_EPSILON if ray_dir_y >= 0 else -RAY_EPSILON)
            depth = (map_y - player_y + (1 - step_y) / 2) / denom

        corrected_depth = depth * math.cos(ray_angle - player_angle)
        return map_x, map_y, side, corrected_depth, ray_dir_x, ray_dir_y

    def _cast_height_transition(
        self,
        player_x,
        player_y,
        player_angle,
        ray_angle,
        is_wall,
        floor_height_getter,
        ceiling_height_getter,
    ):
        if floor_height_getter is None and ceiling_height_getter is None:
            return None

        map_x = int(player_x)
        map_y = int(player_y)

        ray_dir_x = math.cos(ray_angle)
        ray_dir_y = math.sin(ray_angle)

        delta_dist_x = abs(1 / ray_dir_x) if abs(ray_dir_x) > RAY_EPSILON else 1e30
        delta_dist_y = abs(1 / ray_dir_y) if abs(ray_dir_y) > RAY_EPSILON else 1e30

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

        prev_floor = float(_safe_call(floor_height_getter, map_x, map_y, default=0.0))
        prev_ceil = float(_safe_call(ceiling_height_getter, map_x, map_y, default=1.0))

        while True:
            prev_x = map_x
            prev_y = map_y

            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            if side == 0:
                denom = ray_dir_x if abs(ray_dir_x) > RAY_EPSILON else (RAY_EPSILON if ray_dir_x >= 0 else -RAY_EPSILON)
                depth = (map_x - player_x + (1 - step_x) / 2) / denom
            else:
                denom = ray_dir_y if abs(ray_dir_y) > RAY_EPSILON else (RAY_EPSILON if ray_dir_y >= 0 else -RAY_EPSILON)
                depth = (map_y - player_y + (1 - step_y) / 2) / denom

            corrected_depth = depth * math.cos(ray_angle - player_angle)
            if corrected_depth <= 0:
                continue
            if corrected_depth > MAX_RENDER_DIST:
                return None

            if is_wall(map_x, map_y):
                return None

            cur_floor = float(_safe_call(floor_height_getter, map_x, map_y, default=0.0))
            cur_ceil = float(_safe_call(ceiling_height_getter, map_x, map_y, default=1.0))

            if abs(cur_floor - prev_floor) > 1e-4:
                return {
                    "map_x": map_x,
                    "map_y": map_y,
                    "side": side,
                    "depth": corrected_depth,
                    "bottom_z": min(prev_floor, cur_floor),
                    "top_z": max(prev_floor, cur_floor),
                    "kind": "floor_step",
                    "prev_cell": (prev_x, prev_y),
                }

            if abs(cur_ceil - prev_ceil) > 1e-4:
                return {
                    "map_x": map_x,
                    "map_y": map_y,
                    "side": side,
                    "depth": corrected_depth,
                    "bottom_z": min(prev_ceil, cur_ceil),
                    "top_z": max(prev_ceil, cur_ceil),
                    "kind": "ceiling_step",
                    "prev_cell": (prev_x, prev_y),
                }

            prev_floor = cur_floor
            prev_ceil = cur_ceil

    def raycast_walls(
        self,
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
        flash_timer_ref,
        flash_duration,
        wall_texture_getter=None,
        wall_height_getter=None,
        wall_vertical_anchor_getter=None,
        wall_bottom_getter=None,
        floor_height_getter=None,
        ceiling_height_getter=None,
        eye_height=DEFAULT_EYE_HEIGHT,
    ):
        W = self.W
        H = self.H
        self.last_player_z = player_z
        self.last_eye_height = eye_height
        fov = get_fov_radians()
        num_rays = W
        wall_tex = self.wall_tex
        TEX_SIZE = self.TEX_SIZE
        depth_buffer = []
        ray_width = max(1, int(math.ceil(W / num_rays)))

        for r in range(num_rays):
            ray_angle = player_angle - fov / 2 + fov * r / num_rays

            map_x, map_y, side, depth, ray_dir_x, ray_dir_y = self._cast_wall_column(
                player_x,
                player_y,
                player_angle,
                ray_angle,
                is_wall,
            )
            transition_hit = self._cast_height_transition(
                player_x,
                player_y,
                player_angle,
                ray_angle,
                is_wall,
                floor_height_getter,
                ceiling_height_getter,
            )

            segment_kind = "wall"
            current_wall_tex = wall_tex

            wall_bottom_z, wall_top_z = self._resolve_wall_segment(
                map_x,
                map_y,
                wall_height_getter,
                wall_vertical_anchor_getter,
                wall_bottom_getter,
            )

            if transition_hit is not None and transition_hit["depth"] < depth:
                depth = transition_hit["depth"]
                side = transition_hit["side"]
                map_x = transition_hit["map_x"]
                map_y = transition_hit["map_y"]
                wall_bottom_z = transition_hit["bottom_z"]
                wall_top_z = transition_hit["top_z"]
                segment_kind = transition_hit["kind"]
                prev_x, prev_y = transition_hit["prev_cell"]
                if wall_texture_getter is not None:
                    tex = wall_texture_getter(prev_x, prev_y)
                    if tex is not None:
                        current_wall_tex = tex
            else:
                if wall_texture_getter is not None:
                    tex = wall_texture_getter(map_x, map_y)
                    if tex is not None:
                        current_wall_tex = tex

            if depth > MAX_RENDER_DIST or depth <= 0:
                depth_buffer.append(None)
                continue

            depth_buffer.append(depth)

            hit_x = player_x + ray_dir_x * depth
            hit_y = player_y + ray_dir_y * depth

            light_boost = 0
            for lx, ly in lights:
                if not light_states[(lx, ly)]:
                    continue
                dist_light = math.hypot(hit_x - lx, hit_y - ly)
                if dist_light < 4:
                    light_boost += (1 / (dist_light + 0.2)) * 120

            projected_top = self._project_world_y(
                wall_top_z,
                depth,
                player_z,
                bob_offset,
                eye_height,
            )
            projected_bottom = self._project_world_y(
                wall_bottom_z,
                depth,
                player_z,
                bob_offset,
                eye_height,
            )

            wall_height = max(1, abs(projected_bottom - projected_top))

            FOG_DIST = 7
            fog = min((depth / FOG_DIST) ** 1.5, 1)
            base = 150
            if segment_kind != "wall":
                base = 168
            shade = int(base * (1 - fog))
            shade += int(light_boost * (1 - fog))
            pulse = math.sin(t * 2 + r * 0.05) * 15
            shade += int(pulse)

            if flash_timer_ref[0] > 0:
                shade = min(255, shade + int(100 * (flash_timer_ref[0] / flash_duration)))

            shade = max(15, min(255, shade))

            line_x = int(r * W / num_rays)

            if side == 0:
                wall_u = hit_y
            else:
                wall_u = hit_x
            wall_u -= math.floor(wall_u)
            tex_x = int(wall_u * TEX_SIZE) % TEX_SIZE

            shade_bucket = shade // 8
            key = (id(current_wall_tex), tex_x, int(wall_height), shade_bucket, ray_width)

            if key not in texture_column_cache:
                col = current_wall_tex.crop((tex_x, 0, tex_x + 1, TEX_SIZE))
                enhancer = ImageEnhance.Brightness(col)
                col = enhancer.enhance(shade / 255)
                col = col.resize((ray_width, int(wall_height)), Image.NEAREST)
                texture_column_cache[key] = pil_to_surface(col)

            img = texture_column_cache[key]
            y_pos = min(projected_top, projected_bottom)
            self.screen.blit(img, (line_x, y_pos))

        if flash_timer_ref[0] > 0:
            flash_timer_ref[0] = max(0.0, flash_timer_ref[0] - delta)

        return depth_buffer

    def render_sprite(
        self,
        frames,
        frame_index,
        sx,
        sy,
        scale,
        depth_buffer,
        player_x,
        player_y,
        player_angle,
        bob_offset,
        sprite_cache,
        vertical_anchor="center",
        world_z=0.0,
        eye_height=None,
        player_z=None,
    ):
        W = self.W
        H = self.H
        if eye_height is None:
            eye_height = self.last_eye_height
        if player_z is None:
            player_z = self.last_player_z
        fov = get_fov_radians()
        num_rays = W
        dx = sx - player_x
        dy = sy - player_y

        dist = math.hypot(dx, dy)

        if dist < 0.5:
            dist = 0.5

        angle = math.atan2(dy, dx) - player_angle
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi

        if abs(angle) > fov / 2:
            return

        screen_x = (angle + fov / 2) / fov * W

        frame = frames[frame_index]

        sprite_height = int(H / (dist + 0.0001) * scale)

        sprite_width = int(sprite_height * frame.width / frame.height)
        qw = max(1, (sprite_width + 3) // 4 * 4)
        qh = max(1, (sprite_height + 3) // 4 * 4)

        # Cache by the concrete source frame, not just frame index/size.
        # Different sprite sets often use the same frame_index values.
        key = (id(frame), frame_index, qw, qh)

        if key not in self.sprite_resize_cache:
            img = frame.resize((qw, qh), Image.NEAREST)
            self.sprite_resize_cache[key] = pil_to_surface(img)

        img = self.sprite_resize_cache[key]

        x1 = screen_x - sprite_width // 2
        y1 = self._project_world_y(
            world_z + scale * 0.5,
            dist,
            player_z,
            bob_offset,
            eye_height,
        ) - sprite_height // 2
        if vertical_anchor == "floor":
            y1 = self._project_world_y(
                world_z,
                dist,
                player_z,
                bob_offset,
                eye_height,
            ) - sprite_height

        ray = int(screen_x / W * num_rays)
        if 0 <= ray < len(depth_buffer):
            if depth_buffer[ray] is not None and depth_buffer[ray] < dist:
                return

        self.screen.blit(img, (x1, y1))
        sprite_cache.append(img)

    def render_orb(self, orb, orb_textures, depth_buffer, player_x, player_y, player_angle, bob_offset, sprite_cache):
        texture = orb_textures[orb["color"]]

        float_y = orb["y"] + math.sin(time.time() * 2 + orb["x"]) * 0.1

        self.render_sprite(
            [texture],
            0,
            orb["x"],
            float_y,
            0.4,
            depth_buffer,
            player_x,
            player_y,
            player_angle,
            bob_offset,
            sprite_cache,
        )


def render_light(surface, W, H, x, y, player_x, player_y, player_angle):
    fov = get_fov_radians()
    dx = x - player_x
    dy = y - player_y

    dist = math.hypot(dx, dy)

    angle = math.atan2(dy, dx) - player_angle

    if abs(angle) > fov / 2:
        return

    screen_x = (angle + fov / 2) / fov * W

    size = int(H / (dist + 0.1) * 0.2)

    pygame.draw.ellipse(
        surface,
        (255, 170, 51),
        (screen_x - size, H // 2 - size, size * 2, size * 2),
    )


def draw_sky_floor_split(surface, W, H, sky_color, floor_color):
    if isinstance(sky_color, str):
        sky_color = pygame.Color(sky_color)
    if isinstance(floor_color, str):
        floor_color = pygame.Color(floor_color)
    surface.fill(sky_color, (0, 0, W, H // 2))
    surface.fill(floor_color, (0, H // 2, W, H // 2))


def raycast_step_sampling_walls(
    screen,
    W,
    H,
    num_rays,
    fov,
    max_depth,
    ray_step,
    player_x,
    player_y,
    player_angle,
    bob_offset,
    bob_side_offset,
    is_wall_fn,
    eye_event_active,
    eyewall_raw,
    sprite_cache,
):
    """РџРѕС€Р°РіРѕРІС‹Р№ Р»СѓС‡ (hack_maze3d): Р·РµР»С‘РЅС‹Р№ РіСЂР°РґРёРµРЅС‚ РёР»Рё СЃСЂРµР· eyewall."""
    depth_buffer = []
    line_w = max(1, int(W / num_rays) + 1)

    for r in range(num_rays):
        a = player_angle - fov / 2 + fov * r / num_rays
        d = 0.0
        while d < max_depth:
            d += ray_step
            tx = player_x + math.cos(a) * d
            ty = player_y + math.sin(a) * d
            if is_wall_fn(tx, ty):
                break
        depth_buffer.append(d)

        h = min(H, H / (d + 0.1))
        g = int(255 / (1 + d * d * 0.12))
        x = r * W / num_rays

        if eye_event_active:
            slice_width = int(W / num_rays) + 2
            slice_height = int(h)
            tex_w, tex_h = eyewall_raw.size
            tex_x = int((r / num_rays) * tex_w)
            column = eyewall_raw.crop((tex_x, 0, tex_x + 1, tex_h))
            column = column.resize((slice_width, slice_height), Image.NEAREST)
            tk_col = pil_to_surface(column)
            sprite_cache.append(tk_col)
            rect = tk_col.get_rect(center=(x + bob_side_offset, H / 2 + bob_offset))
            screen.blit(tk_col, rect)
        else:
            color = (0, min(255, g), 0)
            pygame.draw.line(
                screen,
                color,
                (x + bob_side_offset, H / 2 - h / 2 + bob_offset),
                (x + bob_side_offset, H / 2 + h / 2 + bob_offset),
                line_w,
            )
    return depth_buffer


def render_sprite_hack_square(
    screen,
    W,
    H,
    num_rays,
    fov,
    player_x,
    player_y,
    player_angle,
    bob_offset,
    frames,
    frame_index,
    world_x,
    world_y,
    scale,
    depth_buffer,
    sprite_cache,
    min_dist=0.3,
):
    dx = world_x - player_x
    dy = world_y - player_y
    dist = math.hypot(dx, dy)
    if dist < min_dist:
        return

    angle = math.atan2(dy, dx) - player_angle
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi

    if abs(angle) > fov / 2:
        return

    screen_x = (angle + fov / 2) / fov * W
    ray = int(screen_x * num_rays / W)
    if ray < 0:
        ray = 0
    if ray >= num_rays:
        ray = num_rays - 1

    if depth_buffer[ray] < dist:
        return

    size = int(H / dist * scale)
    if size > H:
        size = H
    frame = frames[frame_index]
    scaled = frame.resize((size, size), Image.NEAREST)
    tk_img = pil_to_surface(scaled)
    sprite_cache.append(tk_img)
    rect = tk_img.get_rect(center=(screen_x, H // 2 + bob_offset))
    screen.blit(tk_img, rect)

