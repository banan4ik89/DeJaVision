import math
import time
import tkinter as tk


FOV = math.pi / 3
NUM_RAYS = 320
MAX_DEPTH = 24
MOVE_SPEED = 3.6
ROT_SPEED = 1.9
LOOK_SPEED = 360
FLY_SPEED = 3.4
GRAVITY = 16.0
JUMP_SPEED = 5.2
STEP_HEIGHT = 0.75
PLAYER_HEIGHT = 1.7
EYE_HEIGHT = 1.55
WORLD_CEILING = 3.0
RAY_EPSILON = 1e-6


class RaycastEngine:
    def __init__(self, win, canvas, MAP):
        self.win = win
        self.canvas = canvas
        self.MAP = MAP

        self.W = max(1, win.winfo_screenwidth())
        self.H = max(1, win.winfo_screenheight())

        self.player_x = 2.5
        self.player_y = 2.5
        self.player_z = 0.0
        self.player_vz = 0.0
        self.player_angle = 0.0
        self.look_offset = 0.0
        self.flying = False
        self.grounded = True

        self.keys = {
            "w": False,
            "s": False,
            "a": False,
            "d": False,
            "left": False,
            "right": False,
            "up": False,
            "down": False,
            "q": False,
            "e": False,
            "space": False,
        }

        self.last_frame_time = time.time()

        self.lights = []
        self.light_states = {}
        self.light_timers = {}

        self.scan_lights()
        self.reset_vertical_position()

        win.bind("<KeyPress>", self.key_down)
        win.bind("<KeyRelease>", self.key_up)

    # -------------------------

    def scan_lights(self):
        self.lights.clear()
        self.light_states.clear()
        self.light_timers.clear()

        for y, row in enumerate(self.MAP):
            for x, c in enumerate(row):
                if c == "L":
                    pos = (x + 0.5, y + 0.5)
                    self.lights.append(pos)
                    self.light_states[pos] = True
                    self.light_timers[pos] = time.time()

    # -------------------------

    def reset_vertical_position(self):
        floor = self.get_floor_height(self.player_x, self.player_y)
        self.player_z = floor
        self.player_vz = 0.0
        self.grounded = True

    def get_cell(self, x, y):
        ix = int(x)
        iy = int(y)

        if ix < 0 or iy < 0:
            return "#"
        if iy >= len(self.MAP):
            return "#"
        if ix >= len(self.MAP[0]):
            return "#"

        return self.MAP[iy][ix]

    def cell_floor_height(self, cell):
        if cell == "#":
            return 0.0
        if cell in "123456789":
            return min(2.4, int(cell) * 0.28)
        if cell in "^U":
            return 1.0
        if cell == "=":
            return 0.45
        if cell == "~":
            return -0.35
        return 0.0

    def cell_ceiling_height(self, cell):
        if cell == "#":
            return 0.0
        return WORLD_CEILING

    def get_floor_height(self, x, y):
        return self.cell_floor_height(self.get_cell(x, y))

    def get_ceiling_height(self, x, y):
        return self.cell_ceiling_height(self.get_cell(x, y))

    def is_wall(self, x, y):
        return self.get_cell(x, y) == "#"

    def is_walkable(self, x, y, z):
        cell = self.get_cell(x, y)
        if cell == "#":
            return False

        floor = self.cell_floor_height(cell)
        ceiling = self.cell_ceiling_height(cell)

        if floor - z > STEP_HEIGHT:
            return False

        return floor + PLAYER_HEIGHT < ceiling

    # -------------------------

    def key_down(self, e):
        key = e.keysym.lower()

        if key == "f":
            self.flying = not self.flying
            if self.flying:
                self.player_vz = 0.0
            return

        if key in self.keys:
            if key == "space" and not self.keys["space"] and self.grounded and not self.flying:
                self.player_vz = JUMP_SPEED
                self.grounded = False
            self.keys[key] = True

    def key_up(self, e):
        key = e.keysym.lower()
        if key in self.keys:
            self.keys[key] = False

    # -------------------------

    def try_move_axis(self, dx, dy):
        next_x = self.player_x + dx
        next_y = self.player_y + dy

        if self.is_walkable(next_x, self.player_y, self.player_z):
            self.player_x = next_x

        if self.is_walkable(self.player_x, next_y, self.player_z):
            self.player_y = next_y

    def move_player(self, dt):
        move_step = MOVE_SPEED * dt
        rot_step = ROT_SPEED * dt
        look_step = LOOK_SPEED * dt

        forward = 0.0
        if self.keys["w"]:
            forward += 1.0
        if self.keys["s"]:
            forward -= 1.0

        strafe = 0.0
        if not self.flying:
            if self.keys["q"]:
                strafe -= 1.0
            if self.keys["e"]:
                strafe += 1.0

        if forward or strafe:
            cos_a = math.cos(self.player_angle)
            sin_a = math.sin(self.player_angle)

            move_x = (cos_a * forward - sin_a * strafe) * move_step
            move_y = (sin_a * forward + cos_a * strafe) * move_step
            self.try_move_axis(move_x, move_y)

        if self.keys["a"] or self.keys["left"]:
            self.player_angle -= rot_step
        if self.keys["d"] or self.keys["right"]:
            self.player_angle += rot_step

        if self.keys["up"]:
            self.look_offset -= look_step
        if self.keys["down"]:
            self.look_offset += look_step

        self.look_offset = max(-self.H * 0.4, min(self.H * 0.4, self.look_offset))

        if self.flying:
            vertical = 0.0
            if self.keys["q"]:
                vertical -= 1.0
            if self.keys["e"] or self.keys["space"]:
                vertical += 1.0
            self.player_z += vertical * FLY_SPEED * dt

            floor = self.get_floor_height(self.player_x, self.player_y)
            ceiling = self.get_ceiling_height(self.player_x, self.player_y)
            min_z = floor - 1.2
            max_z = ceiling - PLAYER_HEIGHT - 0.1
            self.player_z = max(min_z, min(max_z, self.player_z))
            self.player_vz = 0.0
            self.grounded = False
            return

        self.player_vz -= GRAVITY * dt
        self.player_z += self.player_vz * dt

        floor = self.get_floor_height(self.player_x, self.player_y)
        ceiling = self.get_ceiling_height(self.player_x, self.player_y)

        if self.player_z <= floor:
            self.player_z = floor
            self.player_vz = 0.0
            self.grounded = True
        else:
            self.grounded = False

        top_limit = ceiling - PLAYER_HEIGHT
        if self.player_z > top_limit:
            self.player_z = top_limit
            self.player_vz = min(0.0, self.player_vz)

    # -------------------------

    def project_height(self, world_z, depth):
        eye_z = self.player_z + EYE_HEIGHT
        proj = self.H * 0.82
        return self.H / 2 + self.look_offset - (world_z - eye_z) * proj / max(depth, 0.05)

    def render_floor_ceiling(self):
        horizon = int(self.H / 2 + self.look_offset)
        horizon = max(0, min(self.H, horizon))

        bands = 60

        for i in range(bands):
            y1 = int(i * max(1, horizon) / bands)
            y2 = int((i + 1) * max(1, horizon) / bands)
            fade = i / max(1, bands - 1)
            shade = int(20 + (1.0 - fade) * 42)
            color = f"#{shade:02x}{shade + 2:02x}{min(255, shade + 8):02x}"
            self.canvas.create_rectangle(0, y1, self.W, y2 + 1, fill=color, outline="")

        floor_height = self.H - horizon
        for i in range(bands):
            y1 = horizon + int(i * max(1, floor_height) / bands)
            y2 = horizon + int((i + 1) * max(1, floor_height) / bands)
            fade = i / max(1, bands - 1)
            shade = int(34 + fade * 58)
            color = f"#{shade:02x}{max(0, shade - 8):02x}{max(0, shade - 18):02x}"
            self.canvas.create_rectangle(0, y1, self.W, y2 + 1, fill=color, outline="")

    def cast_ray(self, ray_angle):
        map_x = int(self.player_x)
        map_y = int(self.player_y)

        ray_dir_x = math.cos(ray_angle)
        ray_dir_y = math.sin(ray_angle)

        delta_dist_x = abs(1 / ray_dir_x) if abs(ray_dir_x) > RAY_EPSILON else 1e30
        delta_dist_y = abs(1 / ray_dir_y) if abs(ray_dir_y) > RAY_EPSILON else 1e30

        if ray_dir_x < 0:
            step_x = -1
            side_dist_x = (self.player_x - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - self.player_x) * delta_dist_x

        if ray_dir_y < 0:
            step_y = -1
            side_dist_y = (self.player_y - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - self.player_y) * delta_dist_y

        traveled = 0.0

        while traveled < MAX_DEPTH:
            prev_x = map_x
            prev_y = map_y

            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            if side == 0:
                denom = ray_dir_x if abs(ray_dir_x) > RAY_EPSILON else (RAY_EPSILON if ray_dir_x >= 0 else -RAY_EPSILON)
                raw_depth = (map_x - self.player_x + (1 - step_x) / 2) / denom
            else:
                denom = ray_dir_y if abs(ray_dir_y) > RAY_EPSILON else (RAY_EPSILON if ray_dir_y >= 0 else -RAY_EPSILON)
                raw_depth = (map_y - self.player_y + (1 - step_y) / 2) / denom

            traveled = abs(raw_depth)
            corrected_depth = traveled * math.cos(ray_angle - self.player_angle)
            if corrected_depth <= 0:
                continue

            prev_cell = self.get_cell(prev_x, prev_y)
            cur_cell = self.get_cell(map_x, map_y)

            prev_floor = self.cell_floor_height(prev_cell)
            cur_floor = self.cell_floor_height(cur_cell)

            if cur_cell == "#":
                return corrected_depth, 0.0, WORLD_CEILING, side, cur_floor - prev_floor

            if abs(cur_floor - prev_floor) > 0.01:
                return corrected_depth, min(prev_floor, cur_floor), max(prev_floor, cur_floor), side, cur_floor - prev_floor

        return None

    def render_walls(self):
        depth_buffer = []
        line_width = max(2, int(math.ceil(self.W / NUM_RAYS)))

        for r in range(NUM_RAYS):
            ray_angle = self.player_angle - FOV / 2 + FOV * r / NUM_RAYS
            hit = self.cast_ray(ray_angle)

            if hit is None:
                depth_buffer.append(MAX_DEPTH)
                continue

            depth, bottom_z, top_z, side, height_delta = hit
            depth_buffer.append(depth)

            top_y = self.project_height(top_z, depth)
            bottom_y = self.project_height(bottom_z, depth)

            if bottom_y < top_y:
                top_y, bottom_y = bottom_y, top_y

            top_y = max(-self.H, min(self.H * 2, top_y))
            bottom_y = max(-self.H, min(self.H * 2, bottom_y))

            base = 165 if abs(height_delta) > 0.01 else 135
            shade = int(base / (1 + depth * depth * 0.065))
            if side == 1:
                shade = int(shade * 0.78)

            light_boost = 0
            hit_x = self.player_x + math.cos(ray_angle) * depth
            hit_y = self.player_y + math.sin(ray_angle) * depth
            for light_x, light_y in self.lights:
                if not self.light_states.get((light_x, light_y), False):
                    continue
                dist_light = math.hypot(hit_x - light_x, hit_y - light_y)
                if dist_light < 5:
                    light_boost += int((1.0 - dist_light / 5.0) * 45)

            shade = max(18, min(235, shade + light_boost))

            if abs(height_delta) > 0.01:
                color = f"#{shade:02x}{min(255, shade + 10):02x}{max(0, shade - 16):02x}"
            else:
                color = f"#{shade:02x}{shade:02x}{shade:02x}"

            x = r * self.W / NUM_RAYS
            self.canvas.create_line(
                x,
                top_y,
                x,
                bottom_y,
                fill=color,
                width=line_width,
            )

        return depth_buffer

    def render_hud(self):
        mode = "FLY" if self.flying else "WALK"
        floor = self.get_floor_height(self.player_x, self.player_y)
        info = (
            f"{mode}  "
            f"Z:{self.player_z:.2f}  FLOOR:{floor:.2f}  "
            f"F: fly  SPACE: jump/up  Q/E: strafe or down/up in fly  "
            f"ARROWS: look/turn"
        )
        self.canvas.create_text(
            12,
            12,
            anchor="nw",
            text=info,
            fill="#d8d8d8",
            font=("Terminal", 12),
        )

    # -------------------------

    def render(self):
        now = time.time()
        dt = min(0.05, max(0.001, now - self.last_frame_time))
        self.last_frame_time = now

        self.W = max(1, self.win.winfo_width())
        self.H = max(1, self.win.winfo_height())

        self.canvas.delete("all")
        self.move_player(dt)
        self.render_floor_ceiling()
        self.render_walls()
        self.render_hud()

        self.win.after(16, self.render)
