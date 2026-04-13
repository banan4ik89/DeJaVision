from opengl_maze_core import run_opengl_maze
from testing_maze import MAP, get_floor_height, is_wall


def _find_spawn():
    for y, row in enumerate(MAP):
        for x, cell in enumerate(row):
            if cell == "P":
                return x + 0.5, y + 0.5
    return 10.5, 2.5


def start_testing_maze_opengl(root=None):
    del root
    return run_opengl_maze(
        title="TESTING OPENGL",
        map_rows=MAP,
        is_wall_fn=is_wall,
        floor_height_fn=get_floor_height,
        spawn_getter=_find_spawn,
    )


start_game = start_testing_maze_opengl
