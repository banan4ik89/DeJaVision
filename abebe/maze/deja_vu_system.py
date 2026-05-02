import math


DEJA_VU_REWARD_VIEW_SECONDS = 1.0
DEJA_VU_MAX_REWARDED_ENEMIES = 3
DEJA_VU_ENEMY_VIEW_HALF_FOV = math.radians(40.0)
DEJA_VU_BREAK_MAX_LEVEL = 8
DEJA_VU_BLACKOUT_DURATION = 2.0
DEJA_VU_CRITICAL_FREEZE_DURATION = 2.0
FLASHBACK_DURATION = 12.0
FLASHBACK_POST_DURATION = 30.0
FLASHBACK_KILL_BONUS = 3.0
FLASHBACK_SPEED_BOOST = 1.45
FLASHBACK_DAMAGE_SHIELD = 0.5
FLASHBACK_DEATH_DURATION = 1.85
FLASHBACK_FADE_DURATION = 1.4


def build_deja_vu_state(max_charge):
    return {
        "deja_vu_active": False,
        "deja_vu_started_at": 0.0,
        "deja_vu_charge": max_charge,
        "deja_vu_recharge_available_at": 0.0,
        "deja_vu_snapshot": None,
        "deja_vu_ghost_trail": [],
        "deja_vu_ghost_acc": 0.0,
        "deja_vu_return_started_at": None,
        "deja_vu_active_budget": 0.0,
        "deja_vu_enemy_view_time": {},
        "deja_vu_rewarded_enemies": set(),
        "deja_vu_break_level": 0,
        "deja_vu_blackout_started_at": None,
        "deja_vu_blackout_until": 0.0,
        "deja_vu_death_return_pending": False,
        "deja_vu_critical_freeze_until": 0.0,
        "deja_vu_critical_break_times": [],
        "deja_vu_critical_break_index": 0,
        "flashback_pending": False,
        "flashback_active": False,
        "flashback_started_at": 0.0,
        "flashback_ends_at": 0.0,
        "flashback_post_active": False,
        "flashback_post_remaining": 0.0,
        "flashback_post_last_second": None,
        "flashback_fade_started_at": 0.0,
        "flashback_fade_until": 0.0,
        "flashback_death_active": False,
        "flashback_death_started_at": 0.0,
    }


def is_available(state, *, blocked, min_activation):
    return (
        not state["deja_vu_active"]
        and not blocked
        and state["deja_vu_charge"] >= min_activation
    )


def activate(state, *, now_value, snapshot, player_x, player_y):
    state["deja_vu_snapshot"] = snapshot
    state["deja_vu_active"] = True
    state["deja_vu_started_at"] = now_value
    state["deja_vu_active_budget"] = state["deja_vu_charge"]
    state["deja_vu_ghost_trail"] = [{"x": player_x, "y": player_y, "spawned_at": now_value}]
    state["deja_vu_ghost_acc"] = 0.0
    state["deja_vu_return_started_at"] = None
    state["deja_vu_enemy_view_time"] = {}
    state["deja_vu_rewarded_enemies"] = set()


def finish(state, *, now_value, max_charge, recharge_delay):
    if state["deja_vu_snapshot"] is None:
        state["deja_vu_active"] = False
        return {"snapshot": None, "heal": 0}
    elapsed = max(0.0, now_value - state["deja_vu_started_at"])
    state["deja_vu_charge"] = max(0.0, min(max_charge, state["deja_vu_active_budget"] - elapsed))
    state["deja_vu_recharge_available_at"] = now_value + recharge_delay
    result = {
        "snapshot": state["deja_vu_snapshot"],
        "heal": min(DEJA_VU_MAX_REWARDED_ENEMIES, len(state["deja_vu_rewarded_enemies"])),
    }
    state["deja_vu_active"] = False
    state["deja_vu_snapshot"] = None
    state["deja_vu_ghost_acc"] = 0.0
    state["deja_vu_active_budget"] = 0.0
    state["deja_vu_return_started_at"] = now_value
    state["deja_vu_enemy_view_time"] = {}
    state["deja_vu_rewarded_enemies"] = set()
    return result


def can_see_enemy_point(player_x, player_y, player_angle, enemy_x, enemy_y, wrap_angle_fn, has_line_of_sight_fn, half_fov=DEJA_VU_ENEMY_VIEW_HALF_FOV):
    dx = enemy_x - player_x
    dy = enemy_y - player_y
    if math.hypot(dx, dy) <= 0.001:
        return True
    angle_diff = wrap_angle_fn(math.atan2(dy, dx) - player_angle)
    return abs(angle_diff) <= half_fov and has_line_of_sight_fn(player_x, player_y, enemy_x, enemy_y)


def update_enemy_rewards(state, *, delta_time, visible_enemy_ids):
    if not state["deja_vu_active"]:
        return 0
    if len(state["deja_vu_rewarded_enemies"]) >= DEJA_VU_MAX_REWARDED_ENEMIES:
        return 0
    newly_rewarded = 0
    new_view_times = {}
    for enemy_id in visible_enemy_ids:
        tracked_time = state["deja_vu_enemy_view_time"].get(enemy_id, 0.0) + delta_time
        if enemy_id not in state["deja_vu_rewarded_enemies"] and tracked_time >= DEJA_VU_REWARD_VIEW_SECONDS:
            state["deja_vu_rewarded_enemies"].add(enemy_id)
            newly_rewarded += 1
        new_view_times[enemy_id] = tracked_time
    state["deja_vu_enemy_view_time"] = new_view_times
    return newly_rewarded


def update_runtime(state, *, now_value, delta_time, max_charge, fast_charge_cap, fast_charge_time, slow_charge_time, ghost_lifetime, ghost_interval, player_x, player_y):
    state["deja_vu_ghost_trail"] = [
        point for point in state["deja_vu_ghost_trail"]
        if now_value - point["spawned_at"] < ghost_lifetime
    ]
    if not state["deja_vu_active"] and now_value >= state["deja_vu_recharge_available_at"] and state["deja_vu_charge"] < max_charge:
        fast_rate = fast_charge_cap / fast_charge_time
        slow_charge_amount = max(0.0, max_charge - fast_charge_cap)
        slow_rate = slow_charge_amount / slow_charge_time if slow_charge_amount > 0 else fast_rate
        recharge_left = max(0.0, delta_time)
        if state["deja_vu_charge"] < fast_charge_cap and recharge_left > 0.0:
            fast_missing = fast_charge_cap - state["deja_vu_charge"]
            fast_gain = min(fast_missing, recharge_left * fast_rate)
            state["deja_vu_charge"] += fast_gain
            recharge_left -= fast_gain / fast_rate
        if state["deja_vu_charge"] >= fast_charge_cap and recharge_left > 0.0:
            state["deja_vu_charge"] = min(max_charge, state["deja_vu_charge"] + recharge_left * slow_rate)
    if state["deja_vu_return_started_at"] is not None:
        if now_value >= state["deja_vu_return_started_at"]:
            pass
    if state["deja_vu_active"]:
        state["deja_vu_ghost_acc"] += delta_time
        if state["deja_vu_ghost_acc"] >= ghost_interval:
            state["deja_vu_ghost_acc"] = 0.0
            if not state["deja_vu_ghost_trail"] or math.hypot(player_x - state["deja_vu_ghost_trail"][-1]["x"], player_y - state["deja_vu_ghost_trail"][-1]["y"]) > 0.08:
                state["deja_vu_ghost_trail"].append({"x": player_x, "y": player_y, "spawned_at": now_value})
    return state["deja_vu_active"] and now_value - state["deja_vu_started_at"] >= state["deja_vu_active_budget"]


def update_return_fade(state, *, now_value, return_fade):
    if state["deja_vu_return_started_at"] is None:
        return False
    if (now_value - state["deja_vu_return_started_at"]) / max(0.001, return_fade) >= 1.0:
        state["deja_vu_return_started_at"] = None
        return True
    return False


def trigger_death_break(state, *, now_value, blackout_duration=DEJA_VU_BLACKOUT_DURATION):
    state["deja_vu_break_level"] = min(DEJA_VU_BREAK_MAX_LEVEL, state["deja_vu_break_level"] + 1)
    state["deja_vu_blackout_started_at"] = now_value
    state["deja_vu_blackout_until"] = now_value + blackout_duration
    state["deja_vu_death_return_pending"] = True
    return state["deja_vu_break_level"]


def blackout_active(state, *, now_value):
    return state["deja_vu_death_return_pending"] and now_value < state["deja_vu_blackout_until"]


def should_complete_death_break(state, *, now_value):
    return state["deja_vu_death_return_pending"] and now_value >= state["deja_vu_blackout_until"]


def complete_death_break(state, *, now_value, freeze_duration=DEJA_VU_CRITICAL_FREEZE_DURATION):
    state["deja_vu_death_return_pending"] = False
    state["deja_vu_blackout_started_at"] = None
    state["deja_vu_blackout_until"] = 0.0
    critical_break = state["deja_vu_break_level"] >= DEJA_VU_BREAK_MAX_LEVEL
    if critical_break:
        state["deja_vu_critical_freeze_until"] = now_value + freeze_duration
        state["deja_vu_critical_break_times"] = [
            now_value + 0.25,
            now_value + 0.95,
            now_value + 1.55,
        ]
        state["deja_vu_critical_break_index"] = 0
        state["flashback_pending"] = True
    return critical_break


def critical_freeze_active(state, *, now_value):
    return now_value < state["deja_vu_critical_freeze_until"]


def consume_critical_break_effects(state, *, now_value):
    triggered = 0
    while state["deja_vu_critical_break_index"] < len(state["deja_vu_critical_break_times"]):
        trigger_at = state["deja_vu_critical_break_times"][state["deja_vu_critical_break_index"]]
        if now_value < trigger_at:
            break
        state["deja_vu_critical_break_index"] += 1
        triggered += 1
    if not critical_freeze_active(state, now_value=now_value):
        state["deja_vu_critical_break_times"] = []
        state["deja_vu_critical_break_index"] = 0
        state["deja_vu_critical_freeze_until"] = 0.0
    return triggered


def break_overlay_strength(state):
    return min(1.0, state["deja_vu_break_level"] / float(DEJA_VU_BREAK_MAX_LEVEL))


def deja_vu_locked(state):
    return (
        state["flashback_pending"]
        or state["flashback_active"]
        or state["flashback_post_active"]
        or state["flashback_death_active"]
    )


def start_flashback(state, *, now_value, duration=FLASHBACK_DURATION):
    state["flashback_pending"] = False
    state["flashback_active"] = True
    state["flashback_started_at"] = now_value
    state["flashback_ends_at"] = now_value + duration
    state["deja_vu_break_level"] = 0
    state["deja_vu_critical_freeze_until"] = 0.0
    state["deja_vu_critical_break_times"] = []
    state["deja_vu_critical_break_index"] = 0


def flashback_should_end(state, *, now_value):
    return state["flashback_active"] and now_value >= state["flashback_ends_at"]


def finish_flashback(state, *, now_value, post_duration=FLASHBACK_POST_DURATION):
    state["flashback_active"] = False
    state["flashback_post_active"] = True
    state["flashback_post_remaining"] = post_duration
    state["flashback_post_last_second"] = int(math.ceil(post_duration))
    state["flashback_fade_started_at"] = now_value
    state["flashback_fade_until"] = now_value + FLASHBACK_FADE_DURATION
    state["deja_vu_recharge_available_at"] = max(state["deja_vu_recharge_available_at"], now_value + post_duration)


def update_flashback_post(state, *, delta_time):
    if not state["flashback_post_active"]:
        return False
    state["flashback_post_remaining"] = max(0.0, state["flashback_post_remaining"] - max(0.0, delta_time))
    if state["flashback_post_remaining"] <= 0.0:
        state["flashback_post_active"] = False
        state["flashback_post_last_second"] = None
        return True
    return False


def flashback_fade_strength(state, *, now_value):
    fade_until = state.get("flashback_fade_until", 0.0)
    fade_started = state.get("flashback_fade_started_at", 0.0)
    if fade_until <= now_value or fade_until <= fade_started:
        return 0.0
    return max(0.0, min(1.0, (fade_until - now_value) / max(0.001, fade_until - fade_started)))


def add_flashback_post_time(state, *, extra_seconds):
    if state["flashback_post_active"] and extra_seconds > 0.0:
        state["flashback_post_remaining"] += extra_seconds


def start_flashback_death(state, *, now_value):
    state["flashback_post_active"] = False
    state["flashback_post_remaining"] = 0.0
    state["flashback_post_last_second"] = None
    state["flashback_death_active"] = True
    state["flashback_death_started_at"] = now_value


def flashback_death_progress(state, *, now_value, duration=FLASHBACK_DEATH_DURATION):
    if not state["flashback_death_active"]:
        return 0.0
    return max(0.0, min(1.0, (now_value - state["flashback_death_started_at"]) / max(0.001, duration)))


def flashback_death_finished(state, *, now_value, duration=FLASHBACK_DEATH_DURATION):
    return state["flashback_death_active"] and flashback_death_progress(state, now_value=now_value, duration=duration) >= 1.0
