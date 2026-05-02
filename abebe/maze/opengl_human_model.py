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


MODEL_PATH = "data/levels/assets/models/human/lowpolyhuman.obj"
HUMAN_MARKER = "H"
_YAW_CACHE_BUCKETS = 360


def collect_human_markers(map_rows):
    markers = []
    for row_index, row in enumerate(map_rows):
        for col_index, cell in enumerate(row):
            if cell == HUMAN_MARKER:
                markers.append((col_index + 0.5, row_index + 0.5))
    return markers


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
def load_human_model():
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
    max_y = max(point[1] for point in vertices)
    min_z = min(point[2] for point in vertices)
    max_z = max(point[2] for point in vertices)

    center_x = (min_x + max_x) * 0.5
    center_z = (min_z + max_z) * 0.5
    size_x = max_x - min_x
    size_y = max_y - min_y
    size_z = max_z - min_z
    max_span = max(size_x, size_y, size_z, 1e-6)

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
def _get_human_model_yaw_cache(yaw_bucket):
    triangles = load_human_model()
    if not triangles:
        return []
    angle = math.radians(yaw_bucket % 360)
    cos_yaw = math.cos(angle)
    sin_yaw = math.sin(angle)
    light_dir = (0.35, 0.82, 0.44)
    prepared = []
    for a, b, c, normal in triangles:
        nx, ny, nz = normal
        rot_nx = nx * cos_yaw - nz * sin_yaw
        rot_nz = nx * sin_yaw + nz * cos_yaw
        lighting = max(0.18, rot_nx * light_dir[0] + ny * light_dir[1] + rot_nz * light_dir[2])
        base_brightness = max(0.08, min(1.0, 0.45 + lighting * 0.55))
        rotated = []
        for vx, vy, vz in (a, b, c):
            rot_x = vx * cos_yaw - vz * sin_yaw
            rot_z = vx * sin_yaw + vz * cos_yaw
            rotated.append((rot_x, vy, rot_z))
        prepared.append((tuple(rotated), (rot_nx, ny, rot_nz), base_brightness))
    return prepared


def draw_human_model(world_x, floor_z, world_y, *, scale=0.9, yaw_degrees=180.0, shade=1.0, alpha=1.0, tint=(0.76, 0.88, 0.81)):
    if GL_TRIANGLES is None:
        return
    yaw_bucket = int(round(yaw_degrees)) % 360
    triangles = _get_human_model_yaw_cache(yaw_bucket)
    if not triangles:
        return

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_TEXTURE_2D)
    glBegin(GL_TRIANGLES)
    for rotated_points, rotated_normal, base_brightness in triangles:
        brightness = max(0.08, min(1.0, base_brightness * shade))
        glColor4f(tint[0] * brightness, tint[1] * brightness, tint[2] * brightness, alpha)
        glNormal3f(rotated_normal[0], rotated_normal[1], rotated_normal[2])
        for vx, vy, vz in rotated_points:
            glVertex3f(world_x + vx * scale, floor_z + vy * scale, world_y + vz * scale)
    glEnd()
    glDisable(GL_BLEND)
