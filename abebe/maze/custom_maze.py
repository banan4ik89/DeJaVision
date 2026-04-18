from abebe.custom_maps import CustomMapError, build_runtime_maps, load_custom_map_document
from abebe.maze import opengl_tutor_maze as opengl_tutor_maze_module
from abebe.maze import tutor_maze as tutor_maze_module


_CURRENT_CUSTOM_MAP_NAME = None


def start_custom_maze(root=None, map_name=None):
    global _CURRENT_CUSTOM_MAP_NAME

    if map_name is not None:
        _CURRENT_CUSTOM_MAP_NAME = map_name

    if not _CURRENT_CUSTOM_MAP_NAME:
        raise CustomMapError("Custom map name was not provided.")

    document = load_custom_map_document(_CURRENT_CUSTOM_MAP_NAME)
    runtime_map = build_runtime_maps(document)
    original_map = tutor_maze_module.MAP
    original_ceiling_map = tutor_maze_module.CEILING_MAP
    original_upper_wall_map = tutor_maze_module.UPPER_WALL_MAP
    original_runtime_geometry = getattr(tutor_maze_module, "CUSTOM_RUNTIME_GEOMETRY", None)
    original_opengl_map = opengl_tutor_maze_module.MAP
    original_opengl_geometry = getattr(opengl_tutor_maze_module, "CUSTOM_RUNTIME_GEOMETRY", None)

    tutor_maze_module.MAP = runtime_map["map_rows"]
    tutor_maze_module.CEILING_MAP = runtime_map["ceiling_rows"]
    tutor_maze_module.UPPER_WALL_MAP = runtime_map["upper_wall_rows"]
    tutor_maze_module.CUSTOM_RUNTIME_GEOMETRY = runtime_map["geometry"]
    opengl_tutor_maze_module.MAP = runtime_map["map_rows"]
    opengl_tutor_maze_module.CUSTOM_RUNTIME_GEOMETRY = runtime_map["geometry"]

    try:
        return opengl_tutor_maze_module.start_tutor_maze_opengl(root)
    finally:
        opengl_tutor_maze_module.MAP = original_opengl_map
        opengl_tutor_maze_module.CUSTOM_RUNTIME_GEOMETRY = original_opengl_geometry
        tutor_maze_module.MAP = original_map
        tutor_maze_module.CEILING_MAP = original_ceiling_map
        tutor_maze_module.UPPER_WALL_MAP = original_upper_wall_map
        tutor_maze_module.CUSTOM_RUNTIME_GEOMETRY = original_runtime_geometry


start_game = start_custom_maze
