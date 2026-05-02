import math
import random
import time


ROB_MARKER = "R"
ROB_TALK_ANIM = "data/levels/assets/models/human/talk/robtalk.glb"
ROB_BAD_ANIM = "data/levels/assets/models/human/bad/robbad.glb"
ROB_GOOD_ANIM = "data/levels/assets/models/human/good/robgood.glb"
ROB_HACK_ANIM = "data/levels/assets/models/human/hack/robhack.glb"
ROB_IDLE_ANIM = "data/levels/assets/models/human/idle/robidle.glb"
ROB_WALK_ANIM = "data/levels/assets/models/human/walk/robwalk.glb"
ROB_VISION_RADIUS = 8.0
ROB_INTERACTION_DISTANCE = 1.05
ROB_IDLE_MIN = 3.0
ROB_IDLE_MAX = 4.0
ROB_WANDER_MIN = 5.0
ROB_WANDER_MAX = 7.0
ROB_IGNORE_BAD = 8.0
ROB_IGNORE_GOOD = 12.0
ROB_IGNORE_GOOD_SPECIAL = 13.0
ROB_IGNORE_SHORT = 5.0
ROB_FLEE_TIME = 2.8
ROB_REACTION_HOLD_TIME = 1.0
ROB_WANDER_SPEED = 1.08
ROB_CHASE_SPEED = 1.62


INTRO_DIALOG = {
    "id": "intro",
    "prompt": "Hi, my name is ROB, what is yours?",
    "choices": (
        {
            "id": "bad",
            "text": "Go away",
            "anger": 1,
            "ignore_for": ROB_IGNORE_BAD,
        },
        {
            "id": "good",
            "text": "Hello, my name is [REDACTED]",
            "kindness": 1,
            "ignore_for": ROB_IGNORE_GOOD,
        },
    ),
}

FOLLOWUP_DIALOGS = (
    {
        "id": "unchanged",
        "prompt": "I asked about this before. You have not changed at all.",
        "choices": (
            {
                "id": "bad",
                "text": "I do not understand what you mean.",
                "anger": 1,
                "ignore_for": ROB_IGNORE_BAD,
            },
            {
                "id": "good",
                "text": "You are mistaken.",
                "kindness": 1,
                "ignore_for": ROB_IGNORE_GOOD_SPECIAL,
                "invisible_for": 2.0,
            },
        ),
    },
    {
        "id": "jellyfish",
        "prompt": "Some jellyfish do not die. They only restart...",
        "choices": (
            {
                "id": "bad",
                "text": "That is not true.",
                "anger": 1,
                "ignore_for": ROB_IGNORE_BAD,
            },
            {
                "id": "hack",
                "text": "How are you?",
                "hack": 1,
                "ignore_range": (3.0, 15.0),
            },
        ),
    },
    {
        "id": "system",
        "prompt": "You are not yourself when the system is broken.",
        "choices": (
            {
                "id": "good",
                "text": "I am fine.",
                "kindness": 1,
                "heal_player": 1,
                "ignore_for": ROB_IGNORE_GOOD,
            },
            {
                "id": "hack",
                "text": "What system?",
                "hack": 1,
                "ignore_range": (3.0, 15.0),
                "phase_shift": True,
                "invisible_for": 1.0,
            },
        ),
    },
    {
        "id": "crows",
        "prompt": "Crows remember faces well. Even when the faces do not exist anymore.",
        "choices": (
            {
                "id": "good",
                "text": "Did you remember my face?",
                "kindness": 1,
                "heal_player": 1,
                "ignore_for": ROB_IGNORE_GOOD,
            },
            {
                "id": "bad",
                "text": "So what?",
                "anger": 1,
                "ignore_for": ROB_IGNORE_SHORT,
            },
        ),
    },
)


def create_rob_state(map_rows):
    for row_index, row in enumerate(map_rows):
        for col_index, cell in enumerate(row):
            if cell != ROB_MARKER:
                continue
            x = col_index + 0.5
            y = row_index + 0.5
            return {
                "active": True,
                "x": x,
                "y": y,
                "spawn_x": x,
                "spawn_y": y,
                "facing_angle": 0.0,
                "mode": "idle",
                "state_until": time.time() + random.uniform(ROB_IDLE_MIN, ROB_IDLE_MAX),
                "ignore_until": 0.0,
                "flee_until": 0.0,
                "dialog_active": False,
                "dialog_started_at": 0.0,
                "current_dialog": INTRO_DIALOG,
                "intro_seen": False,
                "last_choice": None,
                "anger_points": 0,
                "kindness_points": 0,
                "hack_points": 0,
                "player_name_masked": "[REDACTED]",
                "wander_dx": 0.0,
                "wander_dy": 0.0,
                "invisible_until": 0.0,
                "phase_shift_active": False,
                "reaction_animation": None,
                "reaction_animation_started_at": 0.0,
                "reaction_hold_until": 0.0,
                "pending_flee_after_reaction": False,
            }
    return {"active": False}


def _pick_cardinal_direction():
    return random.choice(((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)))


def _angle_to(target_x, target_y, x, y):
    return math.atan2(target_y - y, target_x - x)


def _select_dialog(state):
    if not state.get("intro_seen", False):
        return INTRO_DIALOG
    return random.choice(FOLLOWUP_DIALOGS)


def _move_towards(state, target_x, target_y, speed, delta_time, can_move_to):
    dx = target_x - state["x"]
    dy = target_y - state["y"]
    dist = math.hypot(dx, dy)
    if dist <= 1e-6:
        return False
    step = speed * delta_time
    move_dx = dx / dist
    move_dy = dy / dist
    state["facing_angle"] = math.atan2(move_dy, move_dx)

    next_x = state["x"] + move_dx * step
    next_y = state["y"] + move_dy * step
    moved = False
    if can_move_to(next_x, state["y"]):
        state["x"] = next_x
        moved = True
    if can_move_to(state["x"], next_y):
        state["y"] = next_y
        moved = True
    return moved


def _start_idle(state, now_value):
    state["mode"] = "idle"
    state["state_until"] = now_value + random.uniform(ROB_IDLE_MIN, ROB_IDLE_MAX)
    state["wander_dx"] = 0.0
    state["wander_dy"] = 0.0


def _start_wander(state, now_value):
    state["mode"] = "wander"
    state["state_until"] = now_value + random.uniform(ROB_WANDER_MIN, ROB_WANDER_MAX)
    state["wander_dx"], state["wander_dy"] = _pick_cardinal_direction()
    state["facing_angle"] = math.atan2(state["wander_dy"], state["wander_dx"])


def _start_flee(state, player_x, player_y, now_value):
    angle = math.atan2(state["y"] - player_y, state["x"] - player_x)
    state["wander_dx"] = math.cos(angle)
    state["wander_dy"] = math.sin(angle)
    state["facing_angle"] = angle
    state["mode"] = "flee"
    state["flee_until"] = now_value + ROB_FLEE_TIME
    state["state_until"] = state["flee_until"]


def _can_see_player(state, player_x, player_y, has_line_of_sight):
    if math.hypot(player_x - state["x"], player_y - state["y"]) > ROB_VISION_RADIUS:
        return False
    return has_line_of_sight(state["x"], state["y"], player_x, player_y)


def update_rob(state, delta_time, now_value, player_x, player_y, can_move_to, has_line_of_sight):
    if not state.get("active"):
        return

    if state["dialog_active"]:
        state["facing_angle"] = _angle_to(player_x, player_y, state["x"], state["y"])
        return

    if now_value < state.get("reaction_hold_until", 0.0):
        state["mode"] = "reaction"
        state["facing_angle"] = _angle_to(player_x, player_y, state["x"], state["y"])
        return

    if state.get("pending_flee_after_reaction", False):
        state["pending_flee_after_reaction"] = False
        state["reaction_hold_until"] = 0.0
        _start_flee(state, player_x, player_y, now_value)
        return

    sees_player = now_value >= state["ignore_until"] and _can_see_player(state, player_x, player_y, has_line_of_sight)
    distance_to_player = math.hypot(player_x - state["x"], player_y - state["y"])
    if sees_player and distance_to_player <= ROB_INTERACTION_DISTANCE:
        state["dialog_active"] = True
        state["dialog_started_at"] = now_value
        state["mode"] = "dialog"
        state["facing_angle"] = _angle_to(player_x, player_y, state["x"], state["y"])
        state["current_dialog"] = _select_dialog(state)
        state["phase_shift_active"] = False
        if not state["intro_seen"]:
            state["intro_seen"] = True
        return

    if sees_player:
        state["mode"] = "chase"

    if state["mode"] == "chase":
        state["facing_angle"] = _angle_to(player_x, player_y, state["x"], state["y"])
        if sees_player:
            _move_towards(state, player_x, player_y, ROB_CHASE_SPEED, delta_time, can_move_to)
            return
        _start_idle(state, now_value)

    if state["mode"] == "flee":
        step = ROB_CHASE_SPEED * delta_time
        next_x = state["x"] + state["wander_dx"] * step
        next_y = state["y"] + state["wander_dy"] * step
        if can_move_to(next_x, state["y"]):
            state["x"] = next_x
        else:
            state["wander_dx"] *= -1.0
        if can_move_to(state["x"], next_y):
            state["y"] = next_y
        else:
            state["wander_dy"] *= -1.0
        state["facing_angle"] = math.atan2(state["wander_dy"], state["wander_dx"])
        if now_value >= state["flee_until"]:
            _start_idle(state, now_value)
        return

    if state["mode"] == "idle":
        if now_value >= state["state_until"]:
            _start_wander(state, now_value)
        return

    if state["mode"] != "wander":
        _start_idle(state, now_value)
        return

    if now_value >= state["state_until"]:
        _start_idle(state, now_value)
        return

    step = ROB_WANDER_SPEED * delta_time
    next_x = state["x"] + state["wander_dx"] * step
    next_y = state["y"] + state["wander_dy"] * step
    moved_x = False
    moved_y = False
    if can_move_to(next_x, state["y"]):
        state["x"] = next_x
        moved_x = True
    if can_move_to(state["x"], next_y):
        state["y"] = next_y
        moved_y = True
    if not moved_x and not moved_y:
        state["wander_dx"], state["wander_dy"] = _pick_cardinal_direction()
    state["facing_angle"] = math.atan2(state["wander_dy"], state["wander_dx"])


def resolve_dialog_choice(state, player_x, player_y, now_value, choice_id):
    if not state.get("dialog_active"):
        return {"heal_player": 0, "hack_gain": 0, "reaction_animation": None}

    dialog = state.get("current_dialog") or INTRO_DIALOG
    selected = None
    for choice in dialog.get("choices", ()):
        if choice["id"] == choice_id:
            selected = choice
            break
    if selected is None:
        selected = dialog["choices"][0]

    state["dialog_active"] = False
    state["dialog_started_at"] = 0.0
    state["last_choice"] = selected["id"]
    state["anger_points"] += int(selected.get("anger", 0))
    state["kindness_points"] += int(selected.get("kindness", 0))
    state["hack_points"] += int(selected.get("hack", 0))
    if selected.get("anger", 0):
        state["reaction_animation"] = ROB_BAD_ANIM
        state["reaction_animation_started_at"] = now_value
    elif selected.get("kindness", 0):
        state["reaction_animation"] = ROB_GOOD_ANIM
        state["reaction_animation_started_at"] = now_value
    elif selected.get("hack", 0):
        state["reaction_animation"] = ROB_HACK_ANIM
        state["reaction_animation_started_at"] = now_value

    reaction_hold = ROB_REACTION_HOLD_TIME

    ignore_for = selected.get("ignore_for")
    if ignore_for is None:
        ignore_range = selected.get("ignore_range")
        if ignore_range is not None:
            ignore_for = random.uniform(float(ignore_range[0]), float(ignore_range[1]))
        else:
            ignore_for = ROB_IGNORE_BAD
    state["ignore_until"] = now_value + reaction_hold + float(ignore_for)

    invisible_for = float(selected.get("invisible_for", 0.0))
    if invisible_for > 0.0:
        state["invisible_until"] = now_value + reaction_hold + invisible_for
    if selected.get("phase_shift"):
        state["phase_shift_active"] = True

    state["reaction_hold_until"] = now_value + reaction_hold
    state["pending_flee_after_reaction"] = True
    state["mode"] = "reaction"
    return {
        "heal_player": int(selected.get("heal_player", 0)),
        "hack_gain": int(selected.get("hack", 0)),
        "reaction_animation": state["reaction_animation"],
    }
