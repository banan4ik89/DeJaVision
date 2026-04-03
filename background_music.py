import os

import pygame

from config import DATA_DIR
from user_settings import get_effective_music_volume, get_effective_sfx_volume
from utils import get_exe_dir


_current_music = None
_mixer_ready = False
_sound_cache = {}
_overlay_channel = None
_overlay_sound = None
_background_duck = 1.0
_background_duck_target = 1.0
_background_duck_speed = 0.0


def _ensure_mixer():
    global _mixer_ready
    if _mixer_ready and pygame.mixer.get_init():
        return True
    try:
        if not pygame.get_init():
            pygame.init()
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        _mixer_ready = True
        return True
    except pygame.error:
        _mixer_ready = False
        return False


def _get_music_path(filename):
    return os.path.join(get_exe_dir(), DATA_DIR, filename)


def _apply_music_volume():
    if _ensure_mixer():
        volume = get_effective_music_volume() * _background_duck
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))


def _apply_overlay_volume():
    if _overlay_channel is not None:
        _overlay_channel.set_volume(max(0.0, min(1.0, get_effective_music_volume())))


def apply_music_settings():
    _apply_music_volume()
    _apply_overlay_volume()


def play_music(filename):
    global _current_music, _background_duck, _background_duck_target, _background_duck_speed
    _current_music = filename
    _background_duck = 1.0
    _background_duck_target = 1.0
    _background_duck_speed = 0.0

    path = _get_music_path(filename)
    if not os.path.exists(path):
        return
    if not _ensure_mixer():
        return

    try:
        pygame.mixer.music.load(path)
        _apply_music_volume()
        pygame.mixer.music.play(-1)
    except pygame.error:
        pass


def stop_music():
    if _ensure_mixer():
        pygame.mixer.music.stop()
    stop_overlay_music(fade_ms=0, restore_background=False)


def resume_music(fade_ms=0):
    global _background_duck, _background_duck_target, _background_duck_speed
    if _current_music:
        _background_duck = 1.0
        _background_duck_target = 1.0
        _background_duck_speed = 0.0
        path = _get_music_path(_current_music)
        if not os.path.exists(path):
            return
        if not _ensure_mixer():
            return
        try:
            pygame.mixer.music.load(path)
            _apply_music_volume()
            pygame.mixer.music.play(-1, fade_ms=int(max(0, fade_ms)))
        except pygame.error:
            pass


def update_music(delta_time):
    global _background_duck, _overlay_channel, _overlay_sound

    if _background_duck != _background_duck_target and _background_duck_speed > 0.0:
        step = _background_duck_speed * max(0.0, float(delta_time))
        if _background_duck < _background_duck_target:
            _background_duck = min(_background_duck_target, _background_duck + step)
        else:
            _background_duck = max(_background_duck_target, _background_duck - step)
        _apply_music_volume()

    if _overlay_channel is not None and not _overlay_channel.get_busy():
        _overlay_channel = None
        _overlay_sound = None


def play_overlay_music(path, fade_ms=900):
    global _overlay_channel, _overlay_sound, _background_duck_target, _background_duck_speed

    if not os.path.exists(path):
        return
    if not _ensure_mixer():
        return

    sound = _sound_cache.get(path)
    if sound is None:
        try:
            sound = pygame.mixer.Sound(path)
        except pygame.error:
            return
        _sound_cache[path] = sound

    if _overlay_channel is not None and _overlay_channel.get_busy() and _overlay_sound == sound:
        return

    channel = _overlay_channel
    if channel is None:
        channel = pygame.mixer.find_channel()
    if channel is None:
        return

    if _overlay_channel is not None and _overlay_channel.get_busy():
        _overlay_channel.fadeout(int(max(0, fade_ms)))

    _overlay_channel = channel
    _overlay_sound = sound
    _apply_overlay_volume()
    _overlay_channel.play(sound, loops=-1, fade_ms=int(max(0, fade_ms)))

    fade_seconds = max(0.001, int(max(0, fade_ms)) / 1000.0)
    _background_duck_target = 0.0
    _background_duck_speed = 1.0 / fade_seconds


def stop_overlay_music(fade_ms=900, restore_background=True):
    global _overlay_channel, _overlay_sound, _background_duck_target, _background_duck_speed

    if _overlay_channel is not None:
        _overlay_channel.fadeout(int(max(0, fade_ms)))
        if fade_ms <= 0:
            _overlay_channel = None
            _overlay_sound = None

    if restore_background:
        fade_seconds = max(0.001, int(max(0, fade_ms)) / 1000.0)
        _background_duck_target = 1.0
        _background_duck_speed = 1.0 / fade_seconds
    else:
        _background_duck_target = _background_duck
        _background_duck_speed = 0.0


def play_sound_effect(path, volume_scale=1.0):
    if not os.path.exists(path):
        return
    if not _ensure_mixer():
        return

    sound = _sound_cache.get(path)
    if sound is None:
        try:
            sound = pygame.mixer.Sound(path)
        except pygame.error:
            return
        _sound_cache[path] = sound

    sound.set_volume(max(0.0, min(1.0, get_effective_sfx_volume() * float(volume_scale))))
    sound.play()
