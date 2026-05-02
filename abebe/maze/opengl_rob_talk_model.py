import json
import math
import struct
from array import array
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path

from abebe.core.utils import get_resource_path


try:
    from OpenGL.GL import (
        GL_BLEND,
        GL_ARRAY_BUFFER,
        GL_COLOR_ARRAY,
        GL_DYNAMIC_DRAW,
        GL_FLOAT,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_SRC_ALPHA,
        GL_STATIC_DRAW,
        GL_TEXTURE_2D,
        GL_TRIANGLES,
        GL_VERTEX_ARRAY,
        glBindBuffer,
        glBegin,
        glBlendFunc,
        glBufferData,
        glColor4f,
        glColorPointer,
        glDisable,
        glDisableClientState,
        glDrawArrays,
        glEnable,
        glEnableClientState,
        glEnd,
        glGenBuffers,
        glNormal3f,
        glPopMatrix,
        glPushMatrix,
        glRotatef,
        glScalef,
        glTranslatef,
        glVertex3f,
        glVertexPointer,
    )
except Exception:  # pragma: no cover - runtime dependency check
    GL_BLEND = GL_ARRAY_BUFFER = GL_COLOR_ARRAY = GL_DYNAMIC_DRAW = GL_FLOAT = None
    GL_ONE_MINUS_SRC_ALPHA = GL_SRC_ALPHA = GL_STATIC_DRAW = GL_TEXTURE_2D = GL_TRIANGLES = None
    GL_VERTEX_ARRAY = None


MODEL_PATH = "data/levels/assets/models/human/talk/robtalk.glb"

_COMPONENT_FORMAT = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}

_TYPE_SIZE = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT4": 16,
}

_POSE_CACHE_FPS = 12.0
_HAS_VBO_SUPPORT = glGenBuffers is not None if "glGenBuffers" in globals() else False


def _identity_matrix():
    return [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def _matrix_multiply(a, b):
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return out


def _build_global_matrices(local_matrices, parent_indices):
    global_matrices = [None] * len(local_matrices)

    def resolve(node_index):
        cached = global_matrices[node_index]
        if cached is not None:
            return cached
        parent_index = parent_indices[node_index]
        local_matrix = local_matrices[node_index]
        if parent_index < 0:
            result = local_matrix
        else:
            result = _matrix_multiply(resolve(parent_index), local_matrix)
        global_matrices[node_index] = result
        return result

    for node_index in range(len(local_matrices)):
        resolve(node_index)
    return global_matrices


def _compute_skin_matrices(model, local_time):
    local_matrices = []
    for node_index, base in enumerate(model["base_transforms"]):
        track = model["tracks"].get(node_index, {})
        translation = _sample_track(track.get("translation"), local_time, base["translation"])
        rotation = _sample_track(track.get("rotation"), local_time, base["rotation"], is_rotation=True)
        scale = _sample_track(track.get("scale"), local_time, base["scale"])
        local_matrices.append(_matrix_from_trs(translation, rotation, scale))

    global_matrices = _build_global_matrices(local_matrices, model["parents"])
    skin_matrices = []
    for joint_list_index, node_index in enumerate(model["joint_nodes"]):
        skin_matrices.append(_matrix_multiply(global_matrices[node_index], model["inverse_bind_matrices"][joint_list_index]))
    return skin_matrices


def _compute_normalization_bounds(positions, joints, weights, skin_matrices):
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    for vertex_index, source_pos in enumerate(positions):
        blended_pos = [0.0, 0.0, 0.0]
        for joint_index, weight in zip(joints[vertex_index], weights[vertex_index]):
            if weight <= 0.00001:
                continue
            px, py, pz = _transform_point(skin_matrices[joint_index], source_pos)
            blended_pos[0] += px * weight
            blended_pos[1] += py * weight
            blended_pos[2] += pz * weight
        for axis in range(3):
            mins[axis] = min(mins[axis], blended_pos[axis])
            maxs[axis] = max(maxs[axis], blended_pos[axis])
    return mins, maxs


def _matrix_from_trs(translation, rotation, scale):
    x, y, z, w = rotation
    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z

    sx, sy, sz = scale
    return [
        (1.0 - 2.0 * (yy + zz)) * sx,
        (2.0 * (xy + wz)) * sx,
        (2.0 * (xz - wy)) * sx,
        0.0,
        (2.0 * (xy - wz)) * sy,
        (1.0 - 2.0 * (xx + zz)) * sy,
        (2.0 * (yz + wx)) * sy,
        0.0,
        (2.0 * (xz + wy)) * sz,
        (2.0 * (yz - wx)) * sz,
        (1.0 - 2.0 * (xx + yy)) * sz,
        0.0,
        translation[0],
        translation[1],
        translation[2],
        1.0,
    ]


def _transform_point(matrix, point):
    x, y, z = point
    return (
        matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
        matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
        matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
    )


def _transform_direction(matrix, vector):
    x, y, z = vector
    return (
        matrix[0] * x + matrix[4] * y + matrix[8] * z,
        matrix[1] * x + matrix[5] * y + matrix[9] * z,
        matrix[2] * x + matrix[6] * y + matrix[10] * z,
    )


def _normalize_vector(vector, fallback=(0.0, 1.0, 0.0)):
    x, y, z = vector
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1e-8:
        return fallback
    return x / length, y / length, z / length


def _normalize_quaternion(q):
    x, y, z, w = q
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-8:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / length, y / length, z / length, w / length)


def _nlerp_quaternion(a, b, t):
    dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
    if dot < 0.0:
        b = (-b[0], -b[1], -b[2], -b[3])
    q = (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
        a[3] + (b[3] - a[3]) * t,
    )
    return _normalize_quaternion(q)


def _lerp_tuple(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def _read_accessor(gltf, binary_chunk, accessor_index):
    accessor = gltf["accessors"][accessor_index]
    view = gltf["bufferViews"][accessor["bufferView"]]
    component_format, component_size = _COMPONENT_FORMAT[accessor["componentType"]]
    component_count = _TYPE_SIZE[accessor["type"]]
    byte_offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    stride = view.get("byteStride", component_size * component_count)
    count = accessor["count"]
    item_size = component_size * component_count
    unpack_fmt = "<" + component_format * component_count
    values = []
    for index in range(count):
        start = byte_offset + index * stride
        chunk = binary_chunk[start:start + item_size]
        item = struct.unpack(unpack_fmt, chunk)
        if component_count == 1:
            values.append(item[0])
        else:
            values.append(tuple(item))
    return values


def _parse_glb(path):
    raw = path.read_bytes()
    magic, version, _length = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2:
        raise ValueError("Unsupported GLB file")
    offset = 12
    json_chunk = None
    binary_chunk = None
    while offset < len(raw):
        chunk_length, chunk_type = struct.unpack_from("<I4s", raw, offset)
        offset += 8
        payload = raw[offset:offset + chunk_length]
        offset += chunk_length
        if chunk_type == b"JSON":
            json_chunk = payload
        elif chunk_type == b"BIN\x00":
            binary_chunk = payload
    if json_chunk is None or binary_chunk is None:
        raise ValueError("GLB is missing required chunks")
    return json.loads(json_chunk.decode("utf-8")), binary_chunk


@lru_cache(maxsize=8)
def load_animated_human_model(model_path=MODEL_PATH):
    gltf, binary = _parse_glb(Path(get_resource_path(model_path)))
    mesh_node_index = next(index for index, node in enumerate(gltf["nodes"]) if node.get("mesh") == 0 and node.get("skin") == 0)
    mesh_node = gltf["nodes"][mesh_node_index]
    primitive = gltf["meshes"][mesh_node["mesh"]]["primitives"][0]

    positions = _read_accessor(gltf, binary, primitive["attributes"]["POSITION"])
    normals = _read_accessor(gltf, binary, primitive["attributes"]["NORMAL"])
    joints = _read_accessor(gltf, binary, primitive["attributes"]["JOINTS_0"])
    weights = _read_accessor(gltf, binary, primitive["attributes"]["WEIGHTS_0"])
    indices = _read_accessor(gltf, binary, primitive["indices"])

    joint_triplets = []
    for tri_index in range(0, len(indices), 3):
        joint_triplets.append((indices[tri_index], indices[tri_index + 1], indices[tri_index + 2]))

    skin = gltf["skins"][mesh_node["skin"]]
    inverse_bind_matrices = _read_accessor(gltf, binary, skin["inverseBindMatrices"])
    nodes = gltf["nodes"]

    parent_indices = [-1] * len(nodes)
    for parent_index, node in enumerate(nodes):
        for child_index in node.get("children", []):
            parent_indices[child_index] = parent_index

    animation = gltf["animations"][0]
    node_tracks = {}
    duration = 0.0
    for channel in animation["channels"]:
        sampler = animation["samplers"][channel["sampler"]]
        target = channel["target"]
        node_index = target["node"]
        path = target["path"]
        input_times = _read_accessor(gltf, binary, sampler["input"])
        output_values = _read_accessor(gltf, binary, sampler["output"])
        duration = max(duration, max(input_times) if input_times else 0.0)
        track = node_tracks.setdefault(node_index, {})
        track[path] = {
            "times": input_times,
            "values": output_values,
            "interpolation": sampler.get("interpolation", "LINEAR"),
        }

    base_transforms = []
    for node in nodes:
        translation = tuple(node.get("translation", (0.0, 0.0, 0.0)))
        rotation = tuple(node.get("rotation", (0.0, 0.0, 0.0, 1.0)))
        scale = tuple(node.get("scale", (1.0, 1.0, 1.0)))
        if "matrix" in node:
            matrix = list(node["matrix"])
            translation = (matrix[12], matrix[13], matrix[14])
            rotation = (0.0, 0.0, 0.0, 1.0)
            scale = (1.0, 1.0, 1.0)
        base_transforms.append(
            {
                "translation": translation,
                "rotation": _normalize_quaternion(rotation),
                "scale": scale,
            }
        )

    model = {
        "positions": positions,
        "normals": normals,
        "joints": joints,
        "weights": weights,
        "triangles": joint_triplets,
        "joint_nodes": skin["joints"],
        "inverse_bind_matrices": [list(matrix) for matrix in inverse_bind_matrices],
        "nodes": nodes,
        "parents": parent_indices,
        "tracks": node_tracks,
        "base_transforms": base_transforms,
        "duration": max(duration, 0.001),
    }
    bind_skin_matrices = _compute_skin_matrices(model, 0.0)
    mins, maxs = _compute_normalization_bounds(positions, joints, weights, bind_skin_matrices)
    model["norm_center_x"] = (mins[0] + maxs[0]) * 0.5
    model["norm_center_z"] = (mins[2] + maxs[2]) * 0.5
    model["norm_min_y"] = mins[1]
    model["norm_max_span"] = max(maxs[0] - mins[0], maxs[1] - mins[1], maxs[2] - mins[2], 1e-6)
    return model


def _sample_track(track, time_value, default_value, is_rotation=False):
    if track is None or not track["times"]:
        return default_value
    times = track["times"]
    values = track["values"]
    if len(times) == 1 or time_value <= times[0]:
        return values[0]
    if time_value >= times[-1]:
        return values[-1]
    right_index = bisect_right(times, time_value)
    left_index = max(0, right_index - 1)
    right_index = min(len(times) - 1, right_index)
    t0 = times[left_index]
    t1 = times[right_index]
    if abs(t1 - t0) <= 1e-8 or track.get("interpolation") == "STEP":
        return values[left_index]
    factor = (time_value - t0) / (t1 - t0)
    if is_rotation:
        return _nlerp_quaternion(values[left_index], values[right_index], factor)
    return _lerp_tuple(values[left_index], values[right_index], factor)


def get_animated_human_duration(model_path=MODEL_PATH):
    return load_animated_human_model(model_path)["duration"]


def _prepare_pose_triangles(model, transformed_positions, transformed_normals):
    prepared_triangles = []
    vertex_data = array("f")
    face_normals = []
    inv_span = 1.0 / max(model["norm_max_span"], 1e-6)
    center_x = model["norm_center_x"]
    center_z = model["norm_center_z"]
    min_y = model["norm_min_y"]
    for ia, ib, ic in model["triangles"]:
        transformed_points = (
            transformed_positions[ia],
            transformed_positions[ib],
            transformed_positions[ic],
        )
        tri_normals = (
            transformed_normals[ia],
            transformed_normals[ib],
            transformed_normals[ic],
        )
        face_normal = _normalize_vector((
            (tri_normals[0][0] + tri_normals[1][0] + tri_normals[2][0]) / 3.0,
            (tri_normals[0][1] + tri_normals[1][1] + tri_normals[2][1]) / 3.0,
            (tri_normals[0][2] + tri_normals[1][2] + tri_normals[2][2]) / 3.0,
        ))
        local_points = tuple(
            (
                (point[0] - center_x) * inv_span,
                (point[1] - min_y) * inv_span,
                (point[2] - center_z) * inv_span,
            )
            for point in transformed_points
        )
        for local_x, local_y, local_z in local_points:
            vertex_data.extend((local_x, local_y, local_z))
        face_normals.append(face_normal)
        prepared_triangles.append((local_points, face_normal))
    return {
        "triangles": prepared_triangles,
        "vertex_data": vertex_data,
        "face_normals": face_normals,
        "vertex_count": len(vertex_data) // 3,
        "vertex_vbo": None,
        "color_vbo": None,
    }


def _upload_pose_to_vbo(pose):
    if not _HAS_VBO_SUPPORT or pose["vertex_vbo"] is not None or pose["vertex_count"] <= 0:
        return
    vertex_vbo = glGenBuffers(1)
    color_vbo = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vertex_vbo)
    glBufferData(GL_ARRAY_BUFFER, pose["vertex_data"].tobytes(), GL_STATIC_DRAW)
    glBindBuffer(GL_ARRAY_BUFFER, color_vbo)
    glBufferData(GL_ARRAY_BUFFER, pose["vertex_count"] * 4 * 4, None, GL_DYNAMIC_DRAW)
    glBindBuffer(GL_ARRAY_BUFFER, 0)
    pose["vertex_vbo"] = vertex_vbo
    pose["color_vbo"] = color_vbo


def _get_cached_pose(model, local_time, pose_fps):
    duration = max(model["duration"], 0.001)
    pose_fps = max(1.0, float(pose_fps))
    frame_time = 1.0 / pose_fps
    frame_index = int(local_time / frame_time)
    cache_key = (frame_index, pose_fps)
    pose_cache = model.setdefault("pose_cache", {})
    cached = pose_cache.get(cache_key)
    if cached is not None:
        return cached

    skin_matrices = _compute_skin_matrices(model, min(local_time, duration))
    transformed_positions = [None] * len(model["positions"])
    transformed_normals = [None] * len(model["normals"])
    for vertex_index, source_pos in enumerate(model["positions"]):
        source_normal = model["normals"][vertex_index]
        blended_pos = [0.0, 0.0, 0.0]
        blended_normal = [0.0, 0.0, 0.0]
        for joint_index, weight in zip(model["joints"][vertex_index], model["weights"][vertex_index]):
            if weight <= 0.00001:
                continue
            skin_matrix = skin_matrices[joint_index]
            px, py, pz = _transform_point(skin_matrix, source_pos)
            nx, ny, nz = _transform_direction(skin_matrix, source_normal)
            blended_pos[0] += px * weight
            blended_pos[1] += py * weight
            blended_pos[2] += pz * weight
            blended_normal[0] += nx * weight
            blended_normal[1] += ny * weight
            blended_normal[2] += nz * weight
        transformed_positions[vertex_index] = tuple(blended_pos)
        transformed_normals[vertex_index] = _normalize_vector(tuple(blended_normal))

    if len(pose_cache) > 48:
        pose_cache.clear()
    pose = _prepare_pose_triangles(model, transformed_positions, transformed_normals)
    _upload_pose_to_vbo(pose)
    pose_cache[cache_key] = pose
    return pose


def draw_animated_human_model(world_x, floor_z, world_y, *, model_path=MODEL_PATH, elapsed_time, loop=True, scale=0.82, yaw_degrees=0.0, shade=1.0, alpha=1.0, tint=(0.84, 0.92, 0.72), pose_fps=_POSE_CACHE_FPS):
    if GL_TRIANGLES is None:
        return
    try:
        model = load_animated_human_model(model_path)
    except Exception:
        return
    if not model["triangles"]:
        return

    duration = max(model["duration"], 0.001)
    local_time = (elapsed_time % duration) if loop else min(max(0.0, elapsed_time), duration)
    pose = _get_cached_pose(model, local_time, pose_fps)

    angle = math.radians(yaw_degrees % 360.0)
    cos_yaw = math.cos(angle)
    sin_yaw = math.sin(angle)
    light_dir = (0.35, 0.82, 0.44)

    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_TEXTURE_2D)
    if pose["vertex_vbo"] is not None and pose["color_vbo"] is not None:
        color_data = array("f")
        for face_normal in pose["face_normals"]:
            rot_nx = face_normal[0] * cos_yaw - face_normal[2] * sin_yaw
            rot_nz = face_normal[0] * sin_yaw + face_normal[2] * cos_yaw
            lighting = max(0.18, rot_nx * light_dir[0] + face_normal[1] * light_dir[1] + rot_nz * light_dir[2])
            brightness = max(0.08, min(1.0, (0.45 + lighting * 0.55) * shade))
            r = tint[0] * brightness
            g = tint[1] * brightness
            b = tint[2] * brightness
            for _ in range(3):
                color_data.extend((r, g, b, alpha))

        glPushMatrix()
        glTranslatef(world_x, floor_z, world_y)
        glRotatef(-yaw_degrees, 0.0, 1.0, 0.0)
        glScalef(scale, scale, scale)
        glBindBuffer(GL_ARRAY_BUFFER, pose["vertex_vbo"])
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, None)
        glBindBuffer(GL_ARRAY_BUFFER, pose["color_vbo"])
        glBufferData(GL_ARRAY_BUFFER, color_data.tobytes(), GL_DYNAMIC_DRAW)
        glEnableClientState(GL_COLOR_ARRAY)
        glColorPointer(4, GL_FLOAT, 0, None)
        glDrawArrays(GL_TRIANGLES, 0, pose["vertex_count"])
        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glPopMatrix()
    else:
        glBegin(GL_TRIANGLES)
        for local_points, face_normal in pose["triangles"]:
            rot_nx = face_normal[0] * cos_yaw - face_normal[2] * sin_yaw
            rot_nz = face_normal[0] * sin_yaw + face_normal[2] * cos_yaw
            lighting = max(0.18, rot_nx * light_dir[0] + face_normal[1] * light_dir[1] + rot_nz * light_dir[2])
            brightness = max(0.08, min(1.0, (0.45 + lighting * 0.55) * shade))
            glColor4f(tint[0] * brightness, tint[1] * brightness, tint[2] * brightness, alpha)
            glNormal3f(rot_nx, face_normal[1], rot_nz)

            for point in local_points:
                local_x = point[0] * scale
                local_y = point[1] * scale
                local_z = point[2] * scale
                rot_x = local_x * cos_yaw - local_z * sin_yaw
                rot_z = local_x * sin_yaw + local_z * cos_yaw
                glVertex3f(world_x + rot_x, floor_z + local_y, world_y + rot_z)
        glEnd()
    glDisable(GL_BLEND)


def draw_rob_talk_model(world_x, floor_z, world_y, *, elapsed_time, scale=0.82, yaw_degrees=0.0, shade=1.0, alpha=1.0, tint=(0.84, 0.92, 0.72)):
    draw_animated_human_model(
        world_x,
        floor_z,
        world_y,
        model_path=MODEL_PATH,
        elapsed_time=elapsed_time,
        loop=True,
        scale=scale,
        yaw_degrees=yaw_degrees,
        shade=shade,
        alpha=alpha,
        tint=tint,
    )
