import copy
import json
import math
from pathlib import Path

from abebe.core.utils import get_exe_dir


CUSTOM_MAPS_DIR = Path(get_exe_dir()) / "data" / "levels" / "custom_maps"
LEGACY_CUSTOM_MAPS_DIR = Path(get_exe_dir()) / "data" / "custom" / "custommaps"
MAX_MAP_SIZE = 64
DEFAULT_MAP_W = 24
DEFAULT_MAP_H = 24
STORY_HEIGHT = 1.0
DEFAULT_ROOM_CEILING_HEIGHT = 2.4

_TILE_TO_SYMBOL = {
    "empty": ".",
    "wall": "#",
    "stair": "I",
    "spawn": "P",
    "mannequin": "M",
    "hexagaze": "C",
    "gun": "G",
    "bomb": "B",
}


class CustomMapError(Exception):
    pass


def ensure_custom_maps_dir():
    CUSTOM_MAPS_DIR.mkdir(parents=True, exist_ok=True)
    return CUSTOM_MAPS_DIR


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rotation_vector(rotation_degrees):
    angle = math.radians(float(rotation_degrees) % 360.0)
    return math.cos(angle), math.sin(angle)


def _stair_corners(x, y, base_z, height, rotation_degrees):
    dir_x, dir_y = _rotation_vector(rotation_degrees)
    corners = []
    raw = (
        (x, y, 0.0 * dir_x + 0.0 * dir_y),
        (x + 1.0, y, 1.0 * dir_x + 0.0 * dir_y),
        (x, y + 1.0, 0.0 * dir_x + 1.0 * dir_y),
        (x + 1.0, y + 1.0, 1.0 * dir_x + 1.0 * dir_y),
    )
    dot_min = min(item[2] for item in raw)
    dot_max = max(item[2] for item in raw)
    dot_range = max(1e-6, dot_max - dot_min)
    for world_x, world_y, dot in raw:
        progress = (dot - dot_min) / dot_range
        corners.append({"x": world_x, "y": world_y, "z": base_z + progress * height})
    return corners


def _clamp(value, low, high):
    return max(low, min(high, value))


def _stair_endpoints(stair):
    corners = _stair_corners(stair["x"], stair["y"], stair["base_z"], stair["height"], stair["rotation"])
    min_z = min(corner["z"] for corner in corners)
    max_z = max(corner["z"] for corner in corners)
    low = [corner for corner in corners if abs(corner["z"] - min_z) < 1e-6]
    high = [corner for corner in corners if abs(corner["z"] - max_z) < 1e-6]
    low_center = {
        "x": sum(corner["x"] for corner in low) / len(low),
        "y": sum(corner["y"] for corner in low) / len(low),
        "z": min_z,
    }
    high_center = {
        "x": sum(corner["x"] for corner in high) / len(high),
        "y": sum(corner["y"] for corner in high) / len(high),
        "z": max_z,
    }
    return low_center, high_center


def _build_stair_links(stairs):
    links = []
    stairs_by_layer = {}
    for index, stair in enumerate(stairs):
        stair["index"] = index
        stair["low_point"], stair["high_point"] = _stair_endpoints(stair)
        stairs_by_layer.setdefault(stair["layer"], []).append(stair)

    for lower in stairs:
        upper_candidates = []
        for upper in stairs_by_layer.get(lower["layer"] + 1, []):
            if abs(upper["base_z"] - (lower["base_z"] + lower["height"])) > 1e-6:
                continue
            cell_dx = upper["x"] - lower["x"]
            cell_dy = upper["y"] - lower["y"]
            if max(abs(cell_dx), abs(cell_dy)) > 1:
                continue
            dx = upper["low_point"]["x"] - lower["high_point"]["x"]
            dy = upper["low_point"]["y"] - lower["high_point"]["y"]
            dist = math.hypot(dx, dy)
            if dist > 2.2:
                continue
            upper_candidates.append((dist, upper))
        if not upper_candidates:
            continue
        upper_candidates.sort(key=lambda item: item[0])
        _, upper = upper_candidates[0]
        links.append(
            {
                "from_index": lower["index"],
                "to_index": upper["index"],
                "from_layer": lower["layer"],
                "to_layer": upper["layer"],
                "start_x": lower["high_point"]["x"],
                "start_y": lower["high_point"]["y"],
                "start_z": lower["high_point"]["z"],
                "end_x": upper["low_point"]["x"],
                "end_y": upper["low_point"]["y"],
                "end_z": upper["low_point"]["z"],
                "width": 0.34,
            }
        )
    for stair in stairs:
        stair.pop("low_point", None)
        stair.pop("high_point", None)
        stair.pop("index", None)
    return links


def _normalize_document(data):
    map_w = max(1, min(MAX_MAP_SIZE, _safe_int(data.get("width"), DEFAULT_MAP_W)))
    map_h = max(1, min(MAX_MAP_SIZE, _safe_int(data.get("height"), DEFAULT_MAP_H)))
    layers = copy.deepcopy(data.get("layers") or [])
    if not isinstance(layers, list) or not layers:
        layers = [[[{"tile": "empty", "height": 1, "rotation": 0.0, "rotation_x": 0.0, "rotation_y": 0.0, "has_floor": True, "has_ceiling": True, "scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.0, "offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0, "texture": "", "color": "", "collidable": True} for _x in range(map_w)] for _y in range(map_h)]]

    normalized_layers = []
    for layer_index, layer in enumerate(layers):
        normalized_layer = []
        for y in range(map_h):
            row = layer[y] if isinstance(layer, list) and y < len(layer) and isinstance(layer[y], list) else []
            normalized_row = []
            for x in range(map_w):
                raw_cell = row[x] if x < len(row) and isinstance(row[x], dict) else {}
                tile = raw_cell.get("tile", "empty")
                if tile not in _TILE_TO_SYMBOL:
                    tile = "empty"
                height = max(1, min(5, _safe_int(raw_cell.get("height"), 1)))
                rotation = _safe_float(raw_cell.get("rotation"), 0.0) % 360.0
                has_floor = _safe_bool(raw_cell.get("has_floor"), True)
                has_ceiling = _safe_bool(raw_cell.get("has_ceiling"), tile != "stair")
                if layer_index == 0:
                    has_floor = True
                normalized_row.append(
                    {
                        "tile": tile,
                        "height": height,
                        "rotation": rotation,
                        "rotation_x": _safe_float(raw_cell.get("rotation_x"), 0.0) % 360.0,
                        "rotation_y": _safe_float(raw_cell.get("rotation_y"), 0.0) % 360.0,
                        "has_floor": has_floor,
                        "has_ceiling": has_ceiling,
                        "scale_x": _clamp(_safe_float(raw_cell.get("scale_x"), 1.0), 0.35, 2.5),
                        "scale_y": _clamp(_safe_float(raw_cell.get("scale_y"), 1.0), 0.35, 2.5),
                        "scale_z": _clamp(_safe_float(raw_cell.get("scale_z"), 1.0), 0.35, 2.5),
                        "offset_x": _clamp(_safe_float(raw_cell.get("offset_x"), 0.0), -0.49, 0.49),
                        "offset_y": _clamp(_safe_float(raw_cell.get("offset_y"), 0.0), -0.49, 0.49),
                        "offset_z": _clamp(_safe_float(raw_cell.get("offset_z"), 0.0), -0.95, 0.95),
                        "texture": str(raw_cell.get("texture", "") or "")[:96],
                        "color": str(raw_cell.get("color", "") or "")[:16],
                        "collidable": _safe_bool(raw_cell.get("collidable"), tile in {"wall", "stair"}),
                    }
                )
            normalized_layer.append(normalized_row)
        normalized_layers.append(normalized_layer)

    return {
        "name": str(data.get("name") or "Untitled"),
        "width": map_w,
        "height": map_h,
        "layers": normalized_layers,
    }


def _resolve_custom_map_path(map_name):
    ensure_custom_maps_dir()
    requested = str(map_name or "").strip()
    if not requested:
        raise CustomMapError("Custom map name is empty.")

    requested_path = CUSTOM_MAPS_DIR / f"{requested}.json"
    if requested_path.exists():
        return requested_path

    legacy_requested_path = LEGACY_CUSTOM_MAPS_DIR / f"{requested}.json"
    if legacy_requested_path.exists():
        return legacy_requested_path

    requested_lower = requested.lower()
    for path in CUSTOM_MAPS_DIR.glob("*.json"):
        if path.stem.lower() == requested_lower:
            return path
    if LEGACY_CUSTOM_MAPS_DIR.exists():
        for path in LEGACY_CUSTOM_MAPS_DIR.glob("*.json"):
            if path.stem.lower() == requested_lower:
                return path

    raise CustomMapError(f'Custom map "{requested}" was not found.')


def list_custom_map_names():
    ensure_custom_maps_dir()
    names = {path.stem for path in CUSTOM_MAPS_DIR.glob("*.json")}
    if LEGACY_CUSTOM_MAPS_DIR.exists():
        names.update(path.stem for path in LEGACY_CUSTOM_MAPS_DIR.glob("*.json"))
    return sorted(names)


def load_custom_map_document(map_name):
    path = _resolve_custom_map_path(map_name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CustomMapError(f'Custom map "{map_name}" was not found.') from exc
    except json.JSONDecodeError as exc:
        raise CustomMapError(f'Custom map "{path.stem}" has invalid JSON.') from exc
    document = _normalize_document(data)
    document["resolved_name"] = path.stem
    document["path"] = path
    return document


def _build_runtime_geometry(layers, map_w, map_h):
    wall_columns = []
    stairs = []
    floor_surfaces = []
    ceiling_surfaces = []
    gun_pickups = []
    bomb_pickups = []
    sentries = []
    mannequin_spawn = None
    collision_objects = []
    spawn_cell = None
    fallback_spawn_cell = None

    for layer_index, layer in enumerate(layers):
        base_z = layer_index * STORY_HEIGHT
        for y in range(map_h):
            for x in range(map_w):
                cell = layer[y][x]
                tile = cell["tile"]
                center_x = x + 0.5 + float(cell.get("offset_x", 0.0))
                center_y = y + 0.5 + float(cell.get("offset_y", 0.0))
                base_floor_z = base_z + float(cell.get("offset_z", 0.0))
                scale_x = float(cell.get("scale_x", 1.0))
                scale_y = float(cell.get("scale_y", 1.0))
                scale_z = float(cell.get("scale_z", 1.0))
                rotation = float(cell.get("rotation", 0.0)) % 360.0
                rotation_x = float(cell.get("rotation_x", 0.0)) % 360.0
                rotation_y = float(cell.get("rotation_y", 0.0)) % 360.0
                collidable = bool(cell.get("collidable", True))

                if tile == "wall":
                    wall_columns.append(
                        {
                            "x": x,
                            "y": y,
                            "center_x": center_x,
                            "center_y": center_y,
                            "base_z": base_z,
                            "offset_z": float(cell.get("offset_z", 0.0)),
                            "height": cell["height"] * STORY_HEIGHT * scale_z,
                            "rotation": rotation,
                            "rotation_x": rotation_x,
                            "rotation_y": rotation_y,
                            "scale_x": scale_x,
                            "scale_y": scale_y,
                            "scale_z": scale_z,
                            "offset_x": float(cell.get("offset_x", 0.0)),
                            "offset_y": float(cell.get("offset_y", 0.0)),
                            "collidable": collidable,
                            "layer": layer_index,
                        }
                    )
                    if collidable:
                        collision_objects.append(
                            {
                                "type": "wall",
                                "tile": tile,
                                "x": x,
                                "y": y,
                                "layer": layer_index,
                                "center_x": center_x,
                                "center_y": center_y,
                                "base_z": base_floor_z,
                                "height": cell["height"] * STORY_HEIGHT * scale_z,
                                "rotation": rotation,
                                "rotation_x": rotation_x,
                                "rotation_y": rotation_y,
                                "scale_x": scale_x,
                                "scale_y": scale_y,
                                "scale_z": scale_z,
                            }
                        )
                    continue

                if tile == "stair":
                    stairs.append(
                        {
                            "x": x,
                            "y": y,
                            "center_x": center_x,
                            "center_y": center_y,
                            "base_z": base_z,
                            "offset_z": float(cell.get("offset_z", 0.0)),
                            "height": cell["height"] * STORY_HEIGHT * scale_z,
                            "rotation": rotation,
                            "rotation_x": rotation_x,
                            "rotation_y": rotation_y,
                            "scale_x": scale_x,
                            "scale_y": scale_y,
                            "scale_z": scale_z,
                            "offset_x": float(cell.get("offset_x", 0.0)),
                            "offset_y": float(cell.get("offset_y", 0.0)),
                            "collidable": collidable,
                            "layer": layer_index,
                        }
                    )
                    if collidable:
                        collision_objects.append(
                            {
                                "type": "stair",
                                "tile": tile,
                                "x": x,
                                "y": y,
                                "layer": layer_index,
                                "center_x": center_x,
                                "center_y": center_y,
                                "base_z": base_floor_z,
                                "height": cell["height"] * STORY_HEIGHT * scale_z,
                                "rotation": rotation,
                                "rotation_x": rotation_x,
                                "rotation_y": rotation_y,
                                "scale_x": scale_x,
                                "scale_y": scale_y,
                                "scale_z": scale_z,
                            }
                        )
                elif tile != "empty" and collidable:
                    collision_objects.append(
                        {
                            "type": "box",
                            "tile": tile,
                            "x": x,
                            "y": y,
                            "layer": layer_index,
                            "center_x": center_x,
                            "center_y": center_y,
                            "base_z": base_floor_z,
                            "height": cell["height"] * STORY_HEIGHT * scale_z,
                            "rotation": rotation,
                            "rotation_x": rotation_x,
                            "rotation_y": rotation_y,
                            "scale_x": scale_x,
                            "scale_y": scale_y,
                            "scale_z": scale_z,
                        }
                    )

                if tile == "gun":
                    gun_pickups.append((center_x, center_y))
                elif tile == "bomb":
                    bomb_pickups.append((center_x, center_y))
                elif tile == "spawn":
                    spawn_cell = (x, y)
                elif tile == "hexagaze":
                    sentries.append(
                        {
                            "x": center_x,
                            "y": center_y,
                            "cell_x": x,
                            "cell_y": y,
                        }
                    )
                elif tile == "mannequin" and mannequin_spawn is None:
                    mannequin_spawn = {
                        "x": center_x,
                        "y": center_y,
                        "cell_x": x,
                        "cell_y": y,
                    }

                if fallback_spawn_cell is None:
                    fallback_spawn_cell = (x, y)
                if spawn_cell is None and layer_index == 0 and cell.get("has_floor", True):
                    spawn_cell = (x, y)

                if tile != "stair" and cell.get("has_floor", True):
                    floor_surfaces.append({"x": x, "y": y, "z": base_z, "layer": layer_index})
                if cell.get("has_ceiling", True):
                    ceiling_z = base_z + DEFAULT_ROOM_CEILING_HEIGHT
                    for upper_layer_index in range(layer_index + 1, len(layers)):
                        upper_cell = layers[upper_layer_index][y][x]
                        upper_floor_z = upper_layer_index * STORY_HEIGHT
                        if upper_cell["tile"] == "wall" or upper_cell.get("has_floor", True):
                            ceiling_z = upper_floor_z
                            break
                    ceiling_surfaces.append({"x": x, "y": y, "z": ceiling_z, "layer": layer_index})

    wall_columns.sort(key=lambda item: (item["layer"], item["y"], item["x"]))
    stairs.sort(key=lambda item: (item["layer"], item["y"], item["x"]))
    stair_links = _build_stair_links(stairs)
    floor_surfaces.sort(key=lambda item: (item["layer"], item["y"], item["x"]))
    ceiling_surfaces.sort(key=lambda item: (item["layer"], item["y"], item["x"]))
    collision_buckets = {}
    for obj in collision_objects:
        radius_x = max(0.75, 0.5 * obj.get("scale_x", 1.0) + 0.5)
        radius_y = max(0.75, 0.5 * obj.get("scale_y", 1.0) + 0.5)
        min_cell_x = max(0, int(math.floor(obj["center_x"] - radius_x)))
        max_cell_x = min(map_w - 1, int(math.floor(obj["center_x"] + radius_x)))
        min_cell_y = max(0, int(math.floor(obj["center_y"] - radius_y)))
        max_cell_y = min(map_h - 1, int(math.floor(obj["center_y"] + radius_y)))
        for bucket_y in range(min_cell_y, max_cell_y + 1):
            for bucket_x in range(min_cell_x, max_cell_x + 1):
                collision_buckets.setdefault((bucket_x, bucket_y), []).append(obj)

    if spawn_cell is None:
        spawn_cell = fallback_spawn_cell
    if spawn_cell is None:
        raise CustomMapError("Custom map must contain at least one walkable cell.")

    return {
        "story_height": STORY_HEIGHT,
        "wall_columns": wall_columns,
        "stairs": stairs,
        "stair_links": stair_links,
        "floor_surfaces": floor_surfaces,
        "ceiling_surfaces": ceiling_surfaces,
        "gun_pickups": gun_pickups,
        "bomb_pickups": bomb_pickups,
        "sentries": sentries,
        "mannequin_spawn": mannequin_spawn,
        "collision_objects": collision_objects,
        "collision_buckets": collision_buckets,
        "spawn_cell": spawn_cell,
    }


def build_runtime_geometry(document):
    normalized = _normalize_document(document)
    geometry = _build_runtime_geometry(normalized["layers"], normalized["width"], normalized["height"])
    geometry["width"] = normalized["width"]
    geometry["height"] = normalized["height"]
    geometry["layers"] = normalized["layers"]
    return geometry


def build_runtime_maps(document):
    normalized = _normalize_document(document)
    layers = normalized["layers"]
    map_w = normalized["width"]
    map_h = normalized["height"]
    geometry = _build_runtime_geometry(layers, map_w, map_h)
    geometry["width"] = map_w
    geometry["height"] = map_h
    geometry["layers"] = layers

    map_rows = []
    upper_rows = []

    for y in range(map_h):
        map_row = []
        upper_row = []
        for x in range(map_w):
            base_cell = layers[0][y][x]
            base_tile = base_cell["tile"]
            symbol = _TILE_TO_SYMBOL.get(base_tile, ".")

            has_upper_wall = base_tile == "wall" and base_cell["height"] > 1
            for extra_layer in layers[1:]:
                if extra_layer[y][x]["tile"] == "wall":
                    has_upper_wall = True
                    break

            map_row.append(symbol)
            upper_row.append("#" if has_upper_wall else ".")
        map_rows.append("".join(map_row))
        upper_rows.append("".join(upper_row))

    spawn_x, spawn_y = geometry["spawn_cell"]
    row_chars = list(map_rows[spawn_y])
    row_chars[spawn_x] = "P"
    map_rows[spawn_y] = "".join(row_chars)

    ceiling_rows = ["3" * map_w for _ in range(map_h)]
    return {
        "name": normalized["name"],
        "width": map_w,
        "height": map_h,
        "map_rows": map_rows,
        "ceiling_rows": ceiling_rows,
        "upper_wall_rows": upper_rows,
        "geometry": geometry,
        "spawn_point": (spawn_x + 0.5, spawn_y + 0.5, 0.0),
    }
