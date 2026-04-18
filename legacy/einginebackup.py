import tkinter as tk
import math
import time
from PIL import Image, ImageTk


FOV = math.pi / 3
NUM_RAYS = 320
MAX_DEPTH = 10

SPEED = 0.42
ROT_SPEED = 0.11


class RaycastEngine:

    def __init__(self, win, canvas, MAP):

        self.win = win
        self.canvas = canvas
        self.MAP = MAP

        self.W = win.winfo_screenwidth()
        self.H = win.winfo_screenheight()

        self.player_x = 2.5
        self.player_y = 2.5
        self.player_angle = 0

        self.keys = {"w": False, "s": False, "a": False, "d": False}

        self.last_frame_time = time.time()

        self.sprite_cache = []
        self.sprite_resize_cache = {}

        self.lights = []
        self.light_states = {}
        self.light_timers = {}

        self.scan_lights()

        win.bind("<KeyPress>", self.key_down)
        win.bind("<KeyRelease>", self.key_up)

    # -------------------------

    def scan_lights(self):

        for y, row in enumerate(self.MAP):
            for x, c in enumerate(row):

                if c == "L":
                    self.lights.append((x + 0.5, y + 0.5))

        for l in self.lights:
            self.light_states[l] = True
            self.light_timers[l] = time.time()

    # -------------------------

    def is_wall(self, x, y):

        if x < 0 or y < 0:
            return True

        if int(y) >= len(self.MAP):
            return True

        if int(x) >= len(self.MAP[0]):
            return True

        return self.MAP[int(y)][int(x)] == "#"

    # -------------------------

    def key_down(self, e):

        k = e.keysym.lower()

        if k in self.keys:
            self.keys[k] = True

    def key_up(self, e):

        k = e.keysym.lower()

        if k in self.keys:
            self.keys[k] = False

    # -------------------------

    def move_player(self):

        move_x = 0
        move_y = 0

        if self.keys["w"]:
            move_x += math.cos(self.player_angle) * SPEED
            move_y += math.sin(self.player_angle) * SPEED

        if self.keys["s"]:
            move_x -= math.cos(self.player_angle) * SPEED
            move_y -= math.sin(self.player_angle) * SPEED

        nx = self.player_x + move_x
        ny = self.player_y + move_y

        if not self.is_wall(nx, ny):
            self.player_x = nx
            self.player_y = ny

        if self.keys["a"]:
            self.player_angle -= ROT_SPEED

        if self.keys["d"]:
            self.player_angle += ROT_SPEED

    # -------------------------

    def render_floor_ceiling(self):

        H = self.H
        W = self.W

        for y in range(H // 2):

            shade = 40

            self.canvas.create_line(
                0, y,
                W, y,
                fill=f"#{shade:02x}{shade:02x}{shade:02x}"
            )

        for y in range(H // 2, H):

            shade = 60

            self.canvas.create_line(
                0, y,
                W, y,
                fill=f"#{shade:02x}{shade:02x}{shade:02x}"
            )

    # -------------------------

    def render_walls(self):

        depth_buffer = []

        for r in range(NUM_RAYS):

            ray_angle = self.player_angle - FOV / 2 + FOV * r / NUM_RAYS

            depth = 0

            while depth < MAX_DEPTH:

                depth += 0.05

                tx = self.player_x + math.cos(ray_angle) * depth
                ty = self.player_y + math.sin(ray_angle) * depth

                if self.is_wall(tx, ty):
                    break

            depth_buffer.append(depth)

            wall_height = min(self.H, self.H / (depth + 0.1))

            shade = int(120 / (1 + depth * depth * 0.1))

            shade = max(20, min(200, shade))

            x = r * self.W / NUM_RAYS

            self.canvas.create_line(
                x,
                self.H / 2 - wall_height / 2,
                x,
                self.H / 2 + wall_height / 2,
                fill=f"#{shade:02x}{shade:02x}{shade:02x}",
                width=self.W / NUM_RAYS + 1
            )

        return depth_buffer

    # -------------------------

    def render(self):

        self.canvas.delete("all")

        self.move_player()

        self.render_floor_ceiling()

        depth_buffer = self.render_walls()

        self.win.after(16, self.render)