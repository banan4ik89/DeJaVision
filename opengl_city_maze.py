from city_maze import (
    MAP,
    SKYSCRAPER_HEIGHT_SCALE,
    get_map_cell,
    get_player_spawn,
    is_collision_wall,
    is_render_wall,
)
from opengl_maze_core import run_opengl_maze


def _floor_height(x, y):
    cell = get_map_cell(x, y)
    if cell == "N":
        return 0.45
    if cell == "G":
        return 0.2
    if cell == "P":
        return 0.25
    return 0.0


def _wall_height(x, y):
    cell = get_map_cell(x, y)
    if cell == "S":
        return SKYSCRAPER_HEIGHT_SCALE
    return 1.0


def _cell(x, y):
    return get_map_cell(x + 0.5, y + 0.5)


def start_city_maze_opengl(root=None):
    del root
    return run_opengl_maze(
        title="CITY OPENGL",
        map_rows=MAP,
        is_wall_fn=is_collision_wall,
        floor_height_fn=_floor_height,
        spawn_getter=get_player_spawn,
        render_wall_fn=is_render_wall,
        wall_height_fn=_wall_height,
        cell_getter=_cell,
        ceiling_z=18.5,
    )


start_game = start_city_maze_opengl
