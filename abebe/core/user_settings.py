import json
from pathlib import Path
from abebe.core.utils import get_app_dir


SETTINGS_DIR = Path(get_app_dir()) / "userdata"
SETTINGS_FILE = SETTINGS_DIR / "user_settings.json"
LEGACY_SETTINGS_FILE = Path(get_app_dir()) / "user_settings.json"

PIXEL_PRESETS = {
    "ULTRA_HD(trustme)": (640, 360),
    "Almost_HD, bro": (854, 480),
    "Deluxe Ultra Mega PLus Edition": (960, 540),
    "Fake_HD_mode": (1280, 720),
}

DEFAULT_SETTINGS = {
    "music_enabled": True,
    "music_volume": 0.7,
    "master_volume": 1.0,
    "sfx_volume": 0.8,
    "fullscreen": True,
    "pixel_preset": "Almost_HD, bro",
    "brightness": 1.0,
    "view_bob": 1.0,
    "fov_degrees": 60.0,
    "flash_enabled": True,
    "mouse_wheel_weapon_switch": True,
    "impact_particles_enabled": True,
    "bullet_marks_enabled": True,
    "screen_effects_enabled": True,
    "rear_world_culling_enabled": True,
    "show_fps": False,
    "show_debug_stats": False,
    "selected_save_slot": None,
    "new_game_slot_prompt_seen": False,
    "main_menu_intro_seen": False,
}

_cached_settings = None


def _clamp_float(value, default):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _normalize_settings(data):
    settings = DEFAULT_SETTINGS.copy()
    settings.update(data)
    if settings["pixel_preset"] not in PIXEL_PRESETS:
        settings["pixel_preset"] = DEFAULT_SETTINGS["pixel_preset"]
    settings["music_enabled"] = bool(settings["music_enabled"])
    settings["fullscreen"] = bool(settings["fullscreen"])
    settings["flash_enabled"] = bool(settings["flash_enabled"])
    settings["mouse_wheel_weapon_switch"] = bool(settings["mouse_wheel_weapon_switch"])
    settings["impact_particles_enabled"] = bool(settings["impact_particles_enabled"])
    settings["bullet_marks_enabled"] = bool(settings["bullet_marks_enabled"])
    settings["screen_effects_enabled"] = bool(settings["screen_effects_enabled"])
    settings["rear_world_culling_enabled"] = bool(settings["rear_world_culling_enabled"])
    settings["show_fps"] = bool(settings["show_fps"])
    settings["show_debug_stats"] = bool(settings["show_debug_stats"])
    selected_save_slot = settings.get("selected_save_slot")
    settings["selected_save_slot"] = selected_save_slot if selected_save_slot in (1, 2, 3) else None
    settings["new_game_slot_prompt_seen"] = bool(settings.get("new_game_slot_prompt_seen"))
    settings["main_menu_intro_seen"] = bool(settings.get("main_menu_intro_seen"))
    settings["music_volume"] = _clamp_float(settings["music_volume"], DEFAULT_SETTINGS["music_volume"])
    settings["master_volume"] = _clamp_float(settings["master_volume"], DEFAULT_SETTINGS["master_volume"])
    settings["sfx_volume"] = _clamp_float(settings["sfx_volume"], DEFAULT_SETTINGS["sfx_volume"])
    settings["brightness"] = _clamp_float(settings["brightness"], DEFAULT_SETTINGS["brightness"])
    settings["view_bob"] = _clamp_float(settings["view_bob"], DEFAULT_SETTINGS["view_bob"])
    try:
        settings["fov_degrees"] = max(45.0, min(110.0, float(settings["fov_degrees"])))
    except (TypeError, ValueError):
        settings["fov_degrees"] = DEFAULT_SETTINGS["fov_degrees"]
    return settings


def load_settings():
    global _cached_settings
    if _cached_settings is not None:
        return _cached_settings.copy()
    settings_path = SETTINGS_FILE if SETTINGS_FILE.exists() else LEGACY_SETTINGS_FILE
    if not settings_path.exists():
        _cached_settings = DEFAULT_SETTINGS.copy()
        return _cached_settings.copy()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _cached_settings = DEFAULT_SETTINGS.copy()
        return _cached_settings.copy()
    _cached_settings = _normalize_settings(data)
    return _cached_settings.copy()


def save_settings(settings):
    global _cached_settings
    payload = load_settings()
    payload.update(settings)
    payload = _normalize_settings(payload)
    _cached_settings = payload
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def get_game_view_size():
    settings = load_settings()
    return PIXEL_PRESETS[settings["pixel_preset"]]


def get_num_rays():
    width, _ = get_game_view_size()
    return width


def get_master_volume():
    return float(load_settings()["master_volume"])


def get_sfx_volume():
    return float(load_settings()["sfx_volume"])


def get_music_volume():
    settings = load_settings()
    if not settings["music_enabled"]:
        return 0.0
    return float(settings["music_volume"])


def get_effective_music_volume():
    return get_master_volume() * get_music_volume()


def get_effective_sfx_volume():
    return get_master_volume() * get_sfx_volume()


def get_brightness():
    return float(load_settings()["brightness"])


def get_flash_enabled():
    return bool(load_settings()["flash_enabled"])


def get_view_bob():
    return float(load_settings()["view_bob"])


def get_fov_degrees():
    return float(load_settings()["fov_degrees"])


def get_fov_radians():
    import math

    return math.radians(get_fov_degrees())


def get_mouse_wheel_weapon_switch():
    return bool(load_settings()["mouse_wheel_weapon_switch"])


def get_impact_particles_enabled():
    return bool(load_settings()["impact_particles_enabled"])


def get_bullet_marks_enabled():
    return bool(load_settings()["bullet_marks_enabled"])


def get_screen_effects_enabled():
    return bool(load_settings()["screen_effects_enabled"])


def get_rear_world_culling_enabled():
    return bool(load_settings()["rear_world_culling_enabled"])


def get_show_fps():
    return bool(load_settings()["show_fps"])


def get_show_debug_stats():
    return bool(load_settings()["show_debug_stats"])

