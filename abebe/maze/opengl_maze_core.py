import math
import time

from PIL import Image


try:
    import pygame
    from OpenGL.GL import (
        GL_BLEND,
        GL_COLOR_BUFFER_BIT,
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST,
        GL_NEAREST,
        GL_MODELVIEW,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_PROJECTION_MATRIX,
        GL_PROJECTION,
        GL_QUADS,
        GL_RGBA,
        GL_SRC_ALPHA,
        GL_TEXTURE_2D,
        GL_TRIANGLES,
        GL_TEXTURE_MAG_FILTER,
        GL_TEXTURE_MIN_FILTER,
        GL_UNSIGNED_BYTE,
        GL_VIEWPORT,
        glBegin,
        glBindTexture,
        glBlendFunc,
        glCopyTexImage2D,
        glClear,
        glClearColor,
        glColor3f,
        glColor4f,
        glDeleteTextures,
        glDisable,
        glEnable,
        glEnd,
        glGenTextures,
        glGetDoublev,
        glGetIntegerv,
        glLoadIdentity,
        glMatrixMode,
        glOrtho,
        glPopMatrix,
        glPushMatrix,
        glRotatef,
        glTexCoord2f,
        glTexImage2D,
        glTexParameteri,
        glTranslatef,
        glVertex3f,
        glVertex2f,
        glViewport,
    )
    from OpenGL.GLU import gluPerspective
except Exception:  # pragma: no cover - runtime dependency check
    pygame = None


SPEED = 2.4
MOUSE_SENSITIVITY = 0.13
PLAYER_EYE_HEIGHT = 0.70
TARGET_FPS = 120
DEFAULT_CEILING_Z = 1.3
DEFAULT_FOG_START = 3.0
DEFAULT_FOG_END = 14.0


def fog_shade(distance, start=DEFAULT_FOG_START, end=DEFAULT_FOG_END, min_light=0.22):
    if distance <= start:
        return 1.0
    if distance >= end:
        return min_light
    t = (distance - start) / max(0.001, end - start)
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - min_light) * (t * t)


def require_opengl_dependencies():
    if pygame is None:
        raise RuntimeError(
            "OpenGL mode requires pygame and PyOpenGL. "
            "Install dependencies from requirements.txt first."
        )


def wrap_angle(angle):
    while angle > math.pi:
        angle -= math.tau
    while angle < -math.pi:
        angle += math.tau
    return angle


def default_spawn_getter(map_rows):
    for y, row in enumerate(map_rows):
        for x, cell in enumerate(row):
            if cell == "P":
                return x + 0.5, y + 0.5
    return 2.5, 2.5


def default_render_wall(x, y):
    return True


def default_wall_height(x, y):
    return 1.0


def default_wall_bottom(x, y):
    return 0.0


def default_cell_color(cell):
    palette = {
        "#": (0.38, 0.40, 0.44),
        "S": (0.44, 0.44, 0.48),
        "I": (0.10, 0.10, 0.12),
        "W": (0.36, 0.16, 0.18),
        "N": (0.18, 0.36, 0.46),
        "T": (0.38, 0.30, 0.14),
    }
    return palette.get(cell, (0.34, 0.34, 0.38))


def create_texture_from_pil(image):
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    image = image.transpose(Image.FLIP_TOP_BOTTOM)
    width, height = image.size
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(
        GL_TEXTURE_2D,
        0,
        GL_RGBA,
        width,
        height,
        0,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        image.tobytes(),
    )
    return texture_id, width, height


def create_empty_texture(width, height):
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(
        GL_TEXTURE_2D,
        0,
        GL_RGBA,
        width,
        height,
        0,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        None,
    )
    return texture_id, width, height


def create_texture_from_surface(surface):
    image = pygame.image.tostring(surface, "RGBA", False)
    width, height = surface.get_size()
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(
        GL_TEXTURE_2D,
        0,
        GL_RGBA,
        width,
        height,
        0,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        image,
    )
    return texture_id, width, height


def copy_framebuffer_to_texture(texture_id, width, height):
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glCopyTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 0, 0, width, height, 0)


def delete_texture(texture_id):
    if texture_id:
        glDeleteTextures(int(texture_id))


def _rotate_point(point, center, rotation_x=0.0, rotation_y=0.0, rotation_z=0.0):
    px, py, pz = point
    cx, cy, cz = center
    dx = px - cx
    dy = py - cy
    dz = pz - cz
    rx = math.radians(rotation_x % 360.0)
    ry = math.radians(rotation_y % 360.0)
    rz = math.radians(rotation_z % 360.0)
    cos_rx, sin_rx = math.cos(rx), math.sin(rx)
    cos_ry, sin_ry = math.cos(ry), math.sin(ry)
    cos_rz, sin_rz = math.cos(rz), math.sin(rz)
    dy, dz = dy * cos_rx - dz * sin_rx, dy * sin_rx + dz * cos_rx
    dx, dz = dx * cos_ry + dz * sin_ry, -dx * sin_ry + dz * cos_ry
    dx, dy = dx * cos_rz - dy * sin_rz, dx * sin_rz + dy * cos_rz
    return (cx + dx, cy + dy, cz + dz)


def draw_box(
    x,
    floor_z,
    y,
    size,
    height,
    color,
    texture_id=None,
    alpha=1.0,
    shade=1.0,
    *,
    scale_x=1.0,
    scale_y=1.0,
    scale_z=1.0,
    offset_x=0.0,
    offset_y=0.0,
    offset_z=0.0,
    rotation_x=0.0,
    rotation_y=0.0,
    rotation_z=0.0,
):
    center_x = x + size * 0.5 + offset_x
    center_y = y + size * 0.5 + offset_y
    base_z = floor_z + offset_z
    half_x = size * scale_x * 0.5
    half_y = size * scale_y * 0.5
    top_z = base_z + height * scale_z
    center_z = base_z + (height * scale_z * 0.5)
    corners = [
        (center_x - half_x, center_y - half_y, base_z),
        (center_x + half_x, center_y - half_y, base_z),
        (center_x + half_x, center_y + half_y, base_z),
        (center_x - half_x, center_y + half_y, base_z),
        (center_x - half_x, center_y - half_y, top_z),
        (center_x + half_x, center_y - half_y, top_z),
        (center_x + half_x, center_y + half_y, top_z),
        (center_x - half_x, center_y + half_y, top_z),
    ]
    center = (center_x, center_y, center_z)
    corners = [_rotate_point(point, center, rotation_x=rotation_x, rotation_y=rotation_y, rotation_z=rotation_z) for point in corners]
    r, g, b = color
    r *= shade
    g *= shade
    b *= shade
    wobble = 0.028 * math.sin((x * 0.73 + y * 0.41) * 3.0 + time.time() * 2.1) if texture_id is not None else 0.0
    u0 = 0.0 + wobble
    u1 = 1.0 + wobble
    v0 = 0.0
    v1 = 1.0

    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor4f(r, g, b, alpha)
    else:
        glDisable(GL_TEXTURE_2D)

    glBegin(GL_QUADS)

    if texture_id is None:
        glColor3f(r * 1.00, g * 1.00, b * 1.00)
    glTexCoord2f(u0, v1)
    glVertex3f(corners[0][0], corners[0][2], corners[0][1])
    glTexCoord2f(u1, v1)
    glVertex3f(corners[1][0], corners[1][2], corners[1][1])
    glTexCoord2f(u1, v0)
    glVertex3f(corners[5][0], corners[5][2], corners[5][1])
    glTexCoord2f(u0, v0)
    glVertex3f(corners[4][0], corners[4][2], corners[4][1])

    if texture_id is None:
        glColor3f(r * 0.86, g * 0.86, b * 0.86)
    glTexCoord2f(u0, v1)
    glVertex3f(corners[1][0], corners[1][2], corners[1][1])
    glTexCoord2f(u1, v1)
    glVertex3f(corners[2][0], corners[2][2], corners[2][1])
    glTexCoord2f(u1, v0)
    glVertex3f(corners[6][0], corners[6][2], corners[6][1])
    glTexCoord2f(u0, v0)
    glVertex3f(corners[5][0], corners[5][2], corners[5][1])

    if texture_id is None:
        glColor3f(r * 0.72, g * 0.72, b * 0.72)
    glTexCoord2f(u0, v1)
    glVertex3f(corners[2][0], corners[2][2], corners[2][1])
    glTexCoord2f(u1, v1)
    glVertex3f(corners[3][0], corners[3][2], corners[3][1])
    glTexCoord2f(u1, v0)
    glVertex3f(corners[7][0], corners[7][2], corners[7][1])
    glTexCoord2f(u0, v0)
    glVertex3f(corners[6][0], corners[6][2], corners[6][1])

    if texture_id is None:
        glColor3f(r * 0.92, g * 0.92, b * 0.92)
    glTexCoord2f(u0, v1)
    glVertex3f(corners[3][0], corners[3][2], corners[3][1])
    glTexCoord2f(u1, v1)
    glVertex3f(corners[0][0], corners[0][2], corners[0][1])
    glTexCoord2f(u1, v0)
    glVertex3f(corners[4][0], corners[4][2], corners[4][1])
    glTexCoord2f(u0, v0)
    glVertex3f(corners[7][0], corners[7][2], corners[7][1])

    if texture_id is None:
        glColor3f(r * 0.58, g * 0.58, b * 0.58)
    glTexCoord2f(u0, v1)
    glVertex3f(corners[4][0], corners[4][2], corners[4][1])
    glTexCoord2f(u1, v1)
    glVertex3f(corners[5][0], corners[5][2], corners[5][1])
    glTexCoord2f(u1, v0)
    glVertex3f(corners[6][0], corners[6][2], corners[6][1])
    glTexCoord2f(u0, v0)
    glVertex3f(corners[7][0], corners[7][2], corners[7][1])

    glEnd()
    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)


def draw_ramp(
    x,
    floor_z,
    y,
    size,
    height,
    rotation_degrees,
    color,
    texture_id=None,
    alpha=1.0,
    shade=1.0,
    *,
    scale_x=1.0,
    scale_y=1.0,
    scale_z=1.0,
    offset_x=0.0,
    offset_y=0.0,
    offset_z=0.0,
    rotation_x=0.0,
    rotation_y=0.0,
):
    center_x = x + size * 0.5 + offset_x
    center_y = y + size * 0.5 + offset_y
    floor_z = floor_z + offset_z
    x1 = center_x - size * scale_x * 0.5
    x2 = center_x + size * scale_x * 0.5
    y1 = center_y - size * scale_y * 0.5
    y2 = center_y + size * scale_y * 0.5
    top_z = floor_z + height * scale_z
    angle = math.radians(rotation_degrees % 360.0)
    dir_x = math.cos(angle)
    dir_y = math.sin(angle)

    corners = [
        {"x": x1, "y": y1, "dot": 0.0 * dir_x + 0.0 * dir_y},
        {"x": x2, "y": y1, "dot": scale_x * dir_x + 0.0 * dir_y},
        {"x": x1, "y": y2, "dot": 0.0 * dir_x + scale_y * dir_y},
        {"x": x2, "y": y2, "dot": scale_x * dir_x + scale_y * dir_y},
    ]
    dot_min = min(corner["dot"] for corner in corners)
    dot_max = max(corner["dot"] for corner in corners)
    dot_range = max(1e-6, dot_max - dot_min)

    for corner in corners:
        corner["z"] = floor_z + ((corner["dot"] - dot_min) / dot_range) * (height * scale_z)
    center = (center_x, center_y, floor_z + (height * scale_z * 0.5))
    for corner in corners:
        rx, ry, rz = _rotate_point((corner["x"], corner["y"], corner["z"]), center, rotation_x=rotation_x, rotation_y=rotation_y, rotation_z=0.0)
        corner["x"] = rx
        corner["y"] = ry
        corner["z"] = rz

    low_corners = [corner for corner in corners if abs(corner["z"] - floor_z) < 1e-6]
    high_corners = [corner for corner in corners if abs(corner["z"] - top_z) < 1e-6]
    low_corners.sort(key=lambda item: (item["y"], item["x"]))
    high_corners.sort(key=lambda item: (item["y"], item["x"]))

    r, g, b = color
    r *= shade
    g *= shade
    b *= shade

    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
    else:
        glDisable(GL_TEXTURE_2D)

    glColor4f(r * 0.96, g * 0.96, b * 0.96, alpha)
    glBegin(GL_QUADS)
    top_uvs = ((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0))
    for corner, uv in zip(corners, top_uvs):
        if texture_id is not None:
            glTexCoord2f(uv[0], uv[1])
        glVertex3f(corner["x"], corner["z"], corner["y"])
    glEnd()

    if len(low_corners) == 2:
        glColor4f(r * 0.68, g * 0.68, b * 0.68, alpha)
        glBegin(GL_QUADS)
        if texture_id is not None:
            glTexCoord2f(0.0, 1.0)
        glVertex3f(low_corners[0]["x"], floor_z, low_corners[0]["y"])
        if texture_id is not None:
            glTexCoord2f(1.0, 1.0)
        glVertex3f(low_corners[1]["x"], floor_z, low_corners[1]["y"])
        if texture_id is not None:
            glTexCoord2f(1.0, 0.0)
        glVertex3f(low_corners[1]["x"], low_corners[1]["z"], low_corners[1]["y"])
        if texture_id is not None:
            glTexCoord2f(0.0, 0.0)
        glVertex3f(low_corners[0]["x"], low_corners[0]["z"], low_corners[0]["y"])
        glEnd()

    if len(high_corners) == 2:
        glColor4f(r * 0.82, g * 0.82, b * 0.82, alpha)
        glBegin(GL_QUADS)
        if texture_id is not None:
            glTexCoord2f(0.0, 1.0)
        glVertex3f(high_corners[0]["x"], floor_z, high_corners[0]["y"])
        if texture_id is not None:
            glTexCoord2f(1.0, 1.0)
        glVertex3f(high_corners[1]["x"], floor_z, high_corners[1]["y"])
        if texture_id is not None:
            glTexCoord2f(1.0, 0.0)
        glVertex3f(high_corners[1]["x"], high_corners[1]["z"], high_corners[1]["y"])
        if texture_id is not None:
            glTexCoord2f(0.0, 0.0)
        glVertex3f(high_corners[0]["x"], high_corners[0]["z"], high_corners[0]["y"])
        glEnd()

    glColor4f(r * 0.58, g * 0.58, b * 0.58, alpha)
    glBegin(GL_QUADS)
    if texture_id is not None:
        glTexCoord2f(0.0, 1.0)
    glVertex3f(x, floor_z, y)
    if texture_id is not None:
        glTexCoord2f(1.0, 1.0)
    glVertex3f(x2, floor_z, y)
    if texture_id is not None:
        glTexCoord2f(1.0, 0.0)
    glVertex3f(x2, floor_z, y2)
    if texture_id is not None:
        glTexCoord2f(0.0, 0.0)
    glVertex3f(x, floor_z, y2)
    glEnd()

    for quad in (
        (corners[0], corners[1]),
        (corners[1], corners[3]),
        (corners[3], corners[2]),
        (corners[2], corners[0]),
    ):
        a, b_corner = quad
        if abs(a["z"] - b_corner["z"]) < 1e-6:
            continue
        glColor4f(r * 0.74, g * 0.74, b * 0.74, alpha)
        glBegin(GL_QUADS)
        if texture_id is not None:
            glTexCoord2f(0.0, 1.0)
        glVertex3f(a["x"], floor_z, a["y"])
        if texture_id is not None:
            glTexCoord2f(1.0, 1.0)
        glVertex3f(b_corner["x"], floor_z, b_corner["y"])
        if texture_id is not None:
            glTexCoord2f(1.0, 0.0)
        glVertex3f(b_corner["x"], b_corner["z"], b_corner["y"])
        if texture_id is not None:
            glTexCoord2f(0.0, 0.0)
        glVertex3f(a["x"], a["z"], a["y"])
        glEnd()

    if len(low_corners) == 2:
        remaining = [corner for corner in corners if corner not in low_corners]
        if len(remaining) == 2:
            glColor4f(r * 0.88, g * 0.88, b * 0.88, alpha)
            glBegin(GL_TRIANGLES)
            if texture_id is not None:
                glTexCoord2f(0.0, 1.0)
            glVertex3f(low_corners[0]["x"], floor_z, low_corners[0]["y"])
            if texture_id is not None:
                glTexCoord2f(1.0, 0.0)
            glVertex3f(remaining[0]["x"], remaining[0]["z"], remaining[0]["y"])
            if texture_id is not None:
                glTexCoord2f(0.0, 0.0)
            glVertex3f(remaining[1]["x"], remaining[1]["z"], remaining[1]["y"])
            if texture_id is not None:
                glTexCoord2f(1.0, 1.0)
            glVertex3f(low_corners[1]["x"], floor_z, low_corners[1]["y"])
            if texture_id is not None:
                glTexCoord2f(1.0, 0.0)
            glVertex3f(remaining[0]["x"], remaining[0]["z"], remaining[0]["y"])
            if texture_id is not None:
                glTexCoord2f(0.0, 0.0)
            glVertex3f(remaining[1]["x"], remaining[1]["z"], remaining[1]["y"])
            glEnd()
    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)


def draw_bridge_plane(start_x, start_z, start_y, end_x, end_z, end_y, width, color, texture_id=None, alpha=1.0, shade=1.0):
    dx = end_x - start_x
    dy = end_y - start_y
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    nx = -dy / length
    ny = dx / length
    half_w = width * 0.5
    corners = (
        (start_x + nx * half_w, start_z, start_y + ny * half_w),
        (start_x - nx * half_w, start_z, start_y - ny * half_w),
        (end_x - nx * half_w, end_z, end_y - ny * half_w),
        (end_x + nx * half_w, end_z, end_y + ny * half_w),
    )
    r, g, b = color
    r *= shade
    g *= shade
    b *= shade
    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
    else:
        glDisable(GL_TEXTURE_2D)
    glColor4f(r * 0.94, g * 0.94, b * 0.94, alpha)
    glBegin(GL_QUADS)
    uvs = ((0.0, 1.0), (0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
    for corner, uv in zip(corners, uvs):
        if texture_id is not None:
            glTexCoord2f(uv[0], uv[1])
        glVertex3f(corner[0], corner[1], corner[2])
    glEnd()
    if texture_id is not None:
        glDisable(GL_TEXTURE_2D)


def draw_floor_and_ceiling(
    map_rows,
    floor_height_fn,
    ceiling_z=DEFAULT_CEILING_Z,
    ceiling_height_fn=None,
    viewer_x=None,
    viewer_y=None,
    viewer_angle=None,
    rear_cull=False,
    cull_margin=-0.28,
    cull_near_dist=1.4,
    fog_start=DEFAULT_FOG_START,
    fog_end=DEFAULT_FOG_END,
):
    glBegin(GL_QUADS)
    for y, row in enumerate(map_rows):
        for x, _cell in enumerate(row):
            if rear_cull and viewer_x is not None and viewer_y is not None and viewer_angle is not None:
                dx = (x + 0.5) - viewer_x
                dy = (y + 0.5) - viewer_y
                dist = math.hypot(dx, dy)
                if dist > cull_near_dist:
                    facing = (dx * math.cos(viewer_angle) + dy * math.sin(viewer_angle)) / max(0.0001, dist)
                    if facing < cull_margin:
                        continue
            floor_z = floor_height_fn(x + 0.5, y + 0.5)
            cell_ceiling_z = ceiling_z if ceiling_height_fn is None else ceiling_height_fn(x + 0.5, y + 0.5)
            shade = 1.0
            if viewer_x is not None and viewer_y is not None:
                dist = math.hypot((x + 0.5) - viewer_x, (y + 0.5) - viewer_y)
                shade = fog_shade(dist, start=fog_start, end=fog_end, min_light=0.28)

            glColor3f((0.16 + floor_z * 0.10) * shade, (0.16 + floor_z * 0.03) * shade, 0.18 * shade)
            glVertex3f(x, floor_z, y)
            glVertex3f(x + 1, floor_z, y)
            glVertex3f(x + 1, floor_z, y + 1)
            glVertex3f(x, floor_z, y + 1)

            ceiling_shade = max(0.18, shade * 0.85)
            glColor3f(0.08 * ceiling_shade, 0.08 * ceiling_shade, 0.10 * ceiling_shade)
            glVertex3f(x, cell_ceiling_z, y + 1)
            glVertex3f(x + 1, cell_ceiling_z, y + 1)
            glVertex3f(x + 1, cell_ceiling_z, y)
            glVertex3f(x, cell_ceiling_z, y)
    glEnd()


def draw_floor_cell_outline(cell_x, cell_y, floor_z, color=(1.0, 1.0, 0.2), inset=0.08, thickness=0.04, lift=0.01):
    x1 = cell_x + inset
    y1 = cell_y + inset
    x2 = cell_x + 1.0 - inset
    y2 = cell_y + 1.0 - inset
    z = floor_z + lift

    glDisable(GL_TEXTURE_2D)
    glColor3f(color[0], color[1], color[2])
    glBegin(GL_QUADS)
    glVertex3f(x1, z, y1)
    glVertex3f(x2, z, y1)
    glVertex3f(x2, z, y1 + thickness)
    glVertex3f(x1, z, y1 + thickness)

    glVertex3f(x1, z, y2 - thickness)
    glVertex3f(x2, z, y2 - thickness)
    glVertex3f(x2, z, y2)
    glVertex3f(x1, z, y2)

    glVertex3f(x1, z, y1)
    glVertex3f(x1 + thickness, z, y1)
    glVertex3f(x1 + thickness, z, y2)
    glVertex3f(x1, z, y2)

    glVertex3f(x2 - thickness, z, y1)
    glVertex3f(x2, z, y1)
    glVertex3f(x2, z, y2)
    glVertex3f(x2 - thickness, z, y2)
    glEnd()


def draw_floor_cell_fill(cell_x, cell_y, floor_z, color=(1.0, 0.0, 0.0), alpha=0.25, inset=0.06, lift=0.006):
    x1 = cell_x + inset
    y1 = cell_y + inset
    x2 = cell_x + 1.0 - inset
    y2 = cell_y + 1.0 - inset
    z = floor_z + lift

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_TEXTURE_2D)
    glColor4f(color[0], color[1], color[2], alpha)
    glBegin(GL_QUADS)
    glVertex3f(x1, z, y1)
    glVertex3f(x2, z, y1)
    glVertex3f(x2, z, y2)
    glVertex3f(x1, z, y2)
    glEnd()


def draw_billboard(
    x,
    y,
    bottom_z,
    width,
    height,
    texture_id,
    player_angle=None,
    viewer_x=None,
    viewer_y=None,
    tint=(1.0, 1.0, 1.0),
    alpha=1.0,
):
    half_w = width * 0.5
    if viewer_x is not None and viewer_y is not None:
        dx = viewer_x - x
        dy = viewer_y - y
        dist = math.hypot(dx, dy)
        if dist > 1e-6:
            right_x = -(dy / dist) * half_w
            right_y = (dx / dist) * half_w
        else:
            right_x = 0.0
            right_y = half_w
    else:
        player_angle = 0.0 if player_angle is None else player_angle
        right_x = math.sin(player_angle) * half_w
        right_y = -math.cos(player_angle) * half_w
    top_z = bottom_z + height

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(tint[0], tint[1], tint[2], alpha)
    glBegin(GL_QUADS)
    # `create_texture_from_pil()` flips images vertically before upload,
    # so an upright standing billboard needs bottom vertices on V=0
    # and top vertices on V=1.
    glTexCoord2f(0.0, 0.0)
    glVertex3f(x - right_x, bottom_z, y - right_y)
    glTexCoord2f(1.0, 0.0)
    glVertex3f(x + right_x, bottom_z, y + right_y)
    glTexCoord2f(1.0, 1.0)
    glVertex3f(x + right_x, top_z, y + right_y)
    glTexCoord2f(0.0, 1.0)
    glVertex3f(x - right_x, top_z, y - right_y)
    glEnd()
    glDisable(GL_TEXTURE_2D)


def begin_overlay(width, height):
    projection = glGetDoublev(GL_PROJECTION_MATRIX)
    viewport = glGetIntegerv(GL_VIEWPORT)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_TEXTURE_2D)
    return projection, viewport


def end_overlay(previous_projection, viewport):
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glViewport(int(viewport[0]), int(viewport[1]), int(viewport[2]), int(viewport[3]))
    glMatrixMode(GL_MODELVIEW)


def draw_overlay_texture(texture_id, x, y, width, height, tint=(1.0, 1.0, 1.0), alpha=1.0):
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(tint[0], tint[1], tint[2], alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 1.0)
    glVertex2f(x, y)
    glTexCoord2f(1.0, 1.0)
    glVertex2f(x + width, y)
    glTexCoord2f(1.0, 0.0)
    glVertex2f(x + width, y + height)
    glTexCoord2f(0.0, 0.0)
    glVertex2f(x, y + height)
    glEnd()


def draw_overlay_text_texture(texture_id, x, y, width, height, tint=(1.0, 1.0, 1.0), alpha=1.0):
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(tint[0], tint[1], tint[2], alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(1.0, 1.0)
    glVertex2f(x, y)
    glTexCoord2f(0.0, 1.0)
    glVertex2f(x + width, y)
    glTexCoord2f(0.0, 0.0)
    glVertex2f(x + width, y + height)
    glTexCoord2f(1.0, 0.0)
    glVertex2f(x, y + height)
    glEnd()


def draw_markers(map_rows, floor_height_fn):
    markers = {
        "E": (0.74, 0.12, 0.12),
        "M": (0.86, 0.86, 0.92),
        "G": (0.22, 0.78, 0.28),
        "B": (0.86, 0.54, 0.14),
        "C": (0.14, 0.76, 0.82),
        "L": (0.92, 0.78, 0.18),
        "N": (0.18, 0.54, 0.86),
        "T": (0.82, 0.58, 0.22),
        "W": (0.62, 0.18, 0.22),
    }
    for y, row in enumerate(map_rows):
        for x, cell in enumerate(row):
            if cell not in markers:
                continue
            floor_z = floor_height_fn(x + 0.5, y + 0.5)
            draw_box(x + 0.35, floor_z, y + 0.35, 0.30, 0.40, markers[cell])


def run_opengl_maze(
    *,
    title,
    map_rows,
    is_wall_fn,
    floor_height_fn,
    spawn_getter=None,
    render_wall_fn=None,
    wall_height_fn=None,
    wall_bottom_fn=None,
    cell_getter=None,
    start_offset=2.0,
    ceiling_z=DEFAULT_CEILING_Z,
):
    require_opengl_dependencies()

    if spawn_getter is None:
        spawn_getter = lambda: default_spawn_getter(map_rows)
    if render_wall_fn is None:
        render_wall_fn = default_render_wall
    if wall_height_fn is None:
        wall_height_fn = default_wall_height
    if wall_bottom_fn is None:
        wall_bottom_fn = default_wall_bottom
    if cell_getter is None:
        cell_getter = lambda x, y: map_rows[int(y)][int(x)]

    pygame.init()
    info = pygame.display.Info()
    width, height = info.current_w, info.current_h
    pygame.display.set_mode((width, height), pygame.DOUBLEBUF | pygame.OPENGL | pygame.FULLSCREEN)
    clock = pygame.time.Clock()

    glViewport(0, 0, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(75.0, width / max(1, height), 0.05, 160.0)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.03, 0.03, 0.045, 1.0)

    player_x, player_y = spawn_getter()
    player_x -= start_offset
    player_z = floor_height_fn(player_x, player_y)
    player_angle = 0.0

    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)
    pygame.mouse.get_rel()

    running = True
    fps_display = 0
    fps_timer = 0.0

    while running:
        delta = clock.tick(TARGET_FPS) / 1000.0
        delta = max(1.0 / 240.0, min(delta, 0.05))
        fps_timer += delta
        if fps_timer >= 0.2:
            fps_display = int(clock.get_fps())
            fps_timer = 0.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        mouse_dx, _mouse_dy = pygame.mouse.get_rel()
        player_angle = wrap_angle(player_angle + mouse_dx * MOUSE_SENSITIVITY * delta * 60.0)

        keys = pygame.key.get_pressed()
        move_x = 0.0
        move_y = 0.0

        forward_x = math.cos(player_angle)
        forward_y = math.sin(player_angle)
        right_x = math.cos(player_angle + math.pi / 2)
        right_y = math.sin(player_angle + math.pi / 2)

        if keys[pygame.K_w]:
            move_x += forward_x
            move_y += forward_y
        if keys[pygame.K_s]:
            move_x -= forward_x
            move_y -= forward_y
        if keys[pygame.K_a]:
            move_x -= right_x
            move_y -= right_y
        if keys[pygame.K_d]:
            move_x += right_x
            move_y += right_y

        move_len = math.hypot(move_x, move_y)
        if move_len > 0.0:
            move_x = move_x / move_len * SPEED * delta
            move_y = move_y / move_len * SPEED * delta

        next_x = player_x + move_x
        next_y = player_y + move_y
        if not is_wall_fn(next_x, player_y):
            player_x = next_x
        if not is_wall_fn(player_x, next_y):
            player_y = next_y

        player_z = floor_height_fn(player_x, player_y)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glRotatef(math.degrees(player_angle) + 90.0, 0.0, 1.0, 0.0)
        glTranslatef(-player_x, -(player_z + PLAYER_EYE_HEIGHT), -player_y)

        draw_floor_and_ceiling(map_rows, floor_height_fn, ceiling_z=ceiling_z)

        for y, row in enumerate(map_rows):
            for x, _cell in enumerate(row):
                if not render_wall_fn(x + 0.5, y + 0.5):
                    continue
                color = default_cell_color(cell_getter(x, y))
                bottom_z = wall_bottom_fn(x + 0.5, y + 0.5)
                height_z = wall_height_fn(x + 0.5, y + 0.5)
                draw_box(x, bottom_z, y, 1.0, height_z, color)

        draw_markers(map_rows, floor_height_fn)

        pygame.display.set_caption(
            f"{title} | FPS {fps_display} | "
            f"POS {player_x:.2f} {player_y:.2f} Z {player_z:.2f} | "
            "WASD move, mouse turn, ESC exit"
        )
        pygame.display.flip()

    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)
    pygame.quit()
