import math
from functools import lru_cache

from abebe.core.utils import get_resource_path


try:
    from OpenGL.GL import (
        GL_BLEND,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_SRC_ALPHA,
        GL_TEXTURE_2D,
        GL_TRIANGLES,
        glBegin,
        glBlendFunc,
        glColor4f,
        glDisable,
        glEnable,
        glEnd,
        glNormal3f,
        glVertex3f,
    )
except Exception:  # pragma: no cover - runtime dependency check
    GL_BLEND = GL_ONE_MINUS_SRC_ALPHA = GL_SRC_ALPHA = GL_TEXTURE_2D = GL_TRIANGLES = None


MODEL_PATH = "data/levels/assets/models/body/bodygg.obj"
_YAW_CACHE_BUCKETS = 360


def _parse_face_indices(tokens):
    indices = []
    for token in tokens:
        vertex_index = token.split("/")[0].strip()
        if not vertex_index:
            continue
        indices.append(int(vertex_index) - 1)
    if len(indices) < 3:
        return []
    triangles = []
    for offset in range(1, len(indices) - 1):
        triangles.append((indices[0], indices[offset], indices[offset + 1]))
    return triangles


def _compute_normal(a, b, c):
    abx = b[0] - a[0]
    aby = b[1] - a[1]
    abz = b[2] - a[2]
    acx = c[0] - a[0]
    acy = c[1] - a[1]
    acz = c[2] - a[2]
    nx = aby * acz - abz * acy
    ny = abz * acx - abx * acz
    nz = abx * acy - aby * acx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-8:
        return 0.0, 1.0, 0.0
    return nx / length, ny / length, nz / length


@lru_cache(maxsize=1)
def load_player_body_model():
    vertices = []
    triangles = []
    obj_path = get_resource_path(MODEL_PATH)
    with open(obj_path, "r", encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("v "):
                _prefix, sx, sy, sz = line.split(maxsplit=3)
                vertices.append((float(sx), float(sy), float(sz)))
            elif line.startswith("f "):
                triangles.extend(_parse_face_indices(line.split()[1:]))

    if not vertices or not triangles:
        return []

    min_x = min(point[0] for point in vertices)
    max_x = max(point[0] for point in vertices)
    min_y = min(point[1] for point in vertices)
    min_z = min(point[2] for point in vertices)
    max_z = max(point[2] for point in vertices)
    max_span = max(max_x - min_x, max(point[1] for point in vertices) - min_y, max_z - min_z, 1e-6)
    center_x = (min_x + max_x) * 0.5
    center_z = (min_z + max_z) * 0.5

    normalized_vertices = [
        (
            (vx - center_x) / max_span,
            (vy - min_y) / max_span,
            (vz - center_z) / max_span,
        )
        for vx, vy, vz in vertices
    ]

    prepared = []
    for ia, ib, ic in triangles:
        a = normalized_vertices[ia]
        b = normalized_vertices[ib]
        c = normalized_vertices[ic]
        prepared.append((a, b, c, _compute_normal(a, b, c)))
    return prepared


@lru_cache(maxsize=_YAW_CACHE_BUCKETS)
def _get_player_body_yaw_cache(yaw_bucket):
    triangles = load_player_body_model()
    if not triangles:
        return []
    angle = math.radians(yaw_bucket % 360)
    cos_yaw = math.cos(angle)
    sin_yaw = math.sin(angle)
    light_dir = (0.30, 0.86, 0.40)
    prepared = []
    for a, b, c, normal in triangles:
        nx, ny, nz = normal
        rot_nx = nx * cos_yaw - nz * sin_yaw
        rot_nz = nx * sin_yaw + nz * cos_yaw
        lighting = max(0.16, rot_nx * light_dir[0] + ny * light_dir[1] + rot_nz * light_dir[2])
        base_brightness = 0.35 + lighting * 0.45
        rotated = []
        for vx, vy, vz in (a, b, c):
            rot_x = vx * cos_yaw - vz * sin_yaw
            rot_z = vx * sin_yaw + vz * cos_yaw
            rotated.append((rot_x, vy, rot_z))
        prepared.append((tuple(rotated), (rot_nx, ny, rot_nz), base_brightness))
    return prepared


def draw_player_body(
    camera_x,
    camera_y,
    camera_z,
    player_angle,
    player_pitch,
    *,
    bob_side=0.0,
):
    if GL_TRIANGLES is None:
        return
    if player_pitch <= math.radians(1.5):
        return

    triangles = load_player_body_model()
    if not triangles:
        return

    look_ratio = max(0.0, min(1.0, (player_pitch - math.radians(1.5)) / math.radians(55.0)))
    forward_x = math.cos(player_angle)
    forward_y = math.sin(player_angle)
    right_x = math.cos(player_angle + math.pi / 2.0)
    right_y = math.sin(player_angle + math.pi / 2.0)
    horizontal = math.cos(player_pitch)
    up_x = math.sin(player_pitch) * forward_x
    up_y = math.sin(player_pitch) * forward_y
    up_z = horizontal

    down_x = -up_x
    down_y = -up_y
    down_z = -up_z

    world_x = camera_x + down_x * (0.34 + 0.08 * look_ratio) + forward_x * 0.28 + right_x * bob_side * 0.18
    world_y = camera_y + down_y * (0.34 + 0.08 * look_ratio) + forward_y * 0.28 + right_y * bob_side * 0.18
    world_z = camera_z - (0.60 + 0.08 * look_ratio) + down_z * (0.10 + 0.04 * look_ratio)
    scale = 0.48 + 0.03 * look_ratio
    yaw_degrees = math.degrees(player_angle) - 90.0
    alpha = 0.22 + 0.70 * look_ratio

    yaw_bucket = int(round(yaw_degrees)) % 360
    triangles = _get_player_body_yaw_cache(yaw_bucket)

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_TEXTURE_2D)
    glBegin(GL_TRIANGLES)
    for rotated_points, rotated_normal, brightness in triangles:
        glColor4f(0.18 * brightness, 0.24 * brightness, 0.22 * brightness, alpha)
        glNormal3f(rotated_normal[0], rotated_normal[1], rotated_normal[2])
        for vx, vy, vz in rotated_points:
            glVertex3f(world_x + vx * scale, world_z + vy * scale, world_y + vz * scale)
    glEnd()
    glDisable(GL_BLEND)
