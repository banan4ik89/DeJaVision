from abebe.maze.opengl_maze_core import run_opengl_maze
from abebe.maze.secret_maze import MAP, get_floor_height, is_wall


def _spawn():
    return 10.5, 2.5


def start_secret_maze_opengl(root=None):
    del root
    return run_opengl_maze(
        title="SECRET OPENGL",
        map_rows=MAP,
        is_wall_fn=is_wall,
        floor_height_fn=get_floor_height,
        spawn_getter=_spawn,
    )


start_game = start_secret_maze_opengl

