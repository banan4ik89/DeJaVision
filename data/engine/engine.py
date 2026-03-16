import tkinter as tk
import math
import time

# =====================
# === CONFIG ==========
# =====================
W, H = 1024, 768
FOV = math.pi / 3
NUM_RAYS = 300
MAX_DEPTH = 20
TILE_SIZE = 1
FPS = 60

# =====================
# === GLOBAL STATE ====
# =====================
player_x = 2.5
player_y = 2.5
player_a = 0

player_speed = 0.13
player_rot_speed = 0.08

MAP = []

is_moving_forward = False
is_moving_backward = False
is_strafing_left = False
is_strafing_right = False

# Bobbing
bob_phase = 0
bob_offset = 0

# gun
gunshoot_animating = False
gunreload_animating = False

# intro
intro_active = True
intro_text = "SECRET CASE 1.1.5 --- THE_CICADA"
intro_index = 0
intro_start = time.time()
intro_duration = 4

# depth buffer
depth_buffer = []

# tkinter
win = None
canvas = None

# =====================
# === INPUT ===========
# =====================

def key_press(event):
    global is_moving_forward, is_moving_backward
    global is_strafing_left, is_strafing_right

    key = event.keysym.lower()

    if key == "w":
        is_moving_forward = True
    if key == "s":
        is_moving_backward = True
    if key == "a":
        is_strafing_left = True
    if key == "d":
        is_strafing_right = True

    if key == "r":
        reload_gun()


def key_release(event):
    global is_moving_forward, is_moving_backward
    global is_strafing_left, is_strafing_right

    key = event.keysym.lower()

    if key == "w":
        is_moving_forward = False
    if key == "s":
        is_moving_backward = False
    if key == "a":
        is_strafing_left = False
    if key == "d":
        is_strafing_right = False


# =====================
# === GUN ============
# =====================

def shoot_gun():
    global gunshoot_animating
    gunshoot_animating = True


def reload_gun():
    global gunreload_animating
    gunreload_animating = True


# =====================
# === MAP ============
# =====================

def is_wall(x, y):

    if x < 0 or y < 0:
        return True

    if int(y) >= len(MAP):
        return True

    if int(x) >= len(MAP[0]):
        return True

    return MAP[int(y)][int(x)] == "#"


# =====================
# === CAMERA BOB ======
# =====================

def update_bob():
    global bob_phase, bob_offset

    moving = (
        is_moving_forward
        or is_moving_backward
        or is_strafing_left
        or is_strafing_right
    )

    if moving:
        bob_phase += 0.3
        bob_offset = math.sin(bob_phase) * 16
    else:
        bob_offset = 0


# =====================
# === PLAYER MOVE =====
# =====================

def update_player():
    global player_x, player_y, player_a

    move_x = 0
    move_y = 0

    if is_moving_forward:
        move_x += math.cos(player_a) * player_speed
        move_y += math.sin(player_a) * player_speed

    if is_moving_backward:
        move_x -= math.cos(player_a) * player_speed
        move_y -= math.sin(player_a) * player_speed

    nx = player_x + move_x
    ny = player_y + move_y

    if not is_wall(nx, ny):
        player_x = nx
        player_y = ny

    if is_strafing_left:
        player_a -= player_rot_speed

    if is_strafing_right:
        player_a += player_rot_speed


# =====================
# === RAYCAST =========
# =====================

def render_raycast():

    depth_buffer.clear()

    for r in range(NUM_RAYS):

        angle = player_a - FOV/2 + FOV*r/NUM_RAYS

        d = 0

        while d < MAX_DEPTH:

            d += 0.05

            tx = player_x + math.cos(angle)*d
            ty = player_y + math.sin(angle)*d

            if is_wall(tx, ty):
                break

        depth_buffer.append(d)

        h = min(H, H/(d+0.1))

        shade = int(255/(1+d*d*0.1))

        x = r * W / NUM_RAYS

        canvas.create_line(
            x,
            H/2 - h/2 + bob_offset,
            x,
            H/2 + h/2 + bob_offset,
            fill=f"#00{shade:02x}00",
            width=W/NUM_RAYS+1
        )


# =====================
# === CROSSHAIR =======
# =====================

def draw_crosshair():

    canvas.create_line(
        W//2-8,
        H//2,
        W//2+8,
        H//2,
        fill="white",
        width=2
    )

    canvas.create_line(
        W//2,
        H//2-8,
        W//2,
        H//2+8,
        fill="white",
        width=2
    )


# =====================
# === INTRO ===========
# =====================

def draw_intro():

    global intro_index
    global intro_active

    if intro_index < len(intro_text):
        intro_index += 1

    canvas.create_text(
        W//2,
        H//2,
        text=intro_text[:intro_index],
        fill="white",
        font=("Courier", 26)
    )

    if time.time() - intro_start > intro_duration:
        intro_active = False


# =====================
# === RENDER ==========
# =====================

def render():

    canvas.delete("all")

    update_player()
    update_bob()

    if intro_active:

        draw_intro()

        win.after(int(1000/FPS), render)
        return

    # sky
    canvas.create_rectangle(
        0,0,W,H//2,
        fill="#87CEEB",
        outline=""
    )

    # floor
    canvas.create_rectangle(
        0,H//2,W,H,
        fill="#555555",
        outline=""
    )

    render_raycast()

    draw_crosshair()

    win.after(int(1000/FPS), render)


# =====================
# === ENGINE START ====
# =====================

def start_engine(level_map):

    global MAP
    global win
    global canvas

    MAP = level_map

    win = tk.Tk()
    win.title("3D Engine")

    canvas = tk.Canvas(win, width=W, height=H, bg="black")
    canvas.pack()

    win.bind("<KeyPress>", key_press)
    win.bind("<KeyRelease>", key_release)
    win.bind("<Button-1>", lambda e: shoot_gun())

    render()

    win.mainloop()