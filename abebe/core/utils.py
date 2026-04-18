import os
import sys
from pathlib import Path

_ASSET_PATH_ALIASES = (
    ("data/PaneOS/", "data/app/pane_os/"),
    ("data/custom_maps/", "data/levels/custom_maps/"),
    ("data/custom/custommaps/", "data/levels/custom_maps/"),
    ("data/music/", "data/audio/music/"),
    ("data/orbs/", "data/levels/assets/orbs/"),
    ("data/gifs/bomb/", "data/levels/assets/bomb/"),
    ("data/gifs/cicada/", "data/levels/assets/cicada/"),
    ("data/gifs/hands/", "data/levels/assets/hands/"),
    ("data/gifs/hexagaze/", "data/levels/assets/hexagaze/"),
    ("data/gifs/mannequin/", "data/levels/assets/mannequin/"),
    ("data/gifs/eye_", "data/app/abebe/eye_"),
    ("data/abebehello.gif", "data/app/abebe/abebehello.gif"),
    ("data/abebehello.wav", "data/app/abebe/abebehello.wav"),
    ("data/abebe_angry.gif", "data/app/abebe/abebe_angry.gif"),
    ("data/abebe_happy.gif", "data/app/abebe/abebe_happy.gif"),
    ("data/abebe_neutral.gif", "data/app/abebe/abebe_neutral.gif"),
    ("data/abebecorpbankrupt.png", "data/app/abebe/abebecorpbankrupt.png"),
    ("data/goodendabebe.gif", "data/app/abebe/goodendabebe.gif"),
    ("data/goodendabebe.wav", "data/app/abebe/goodendabebe.wav"),
    ("data/laugh.gif", "data/app/abebe/laugh.gif"),
    ("data/laugh.wav", "data/app/abebe/laugh.wav"),
    ("data/12340.txt", "data/app/story/12340.txt"),
    ("data/1401.zip", "data/app/story/1401.zip"),
    ("data/death.png", "data/app/story/death.png"),
    ("data/easteregg.png", "data/app/story/easteregg.png"),
    ("data/iobey98.wav", "data/app/story/iobey98.wav"),
    ("data/abebesoundtrack.wav", "data/audio/music/abebesoundtrack.wav"),
    ("data/LocalCodepastElevator.wav", "data/audio/music/LocalCodepastElevator.wav"),
    ("data/Lelevatordoor.png", "data/levels/assets/doors/Lelevatordoor.png"),
    ("data/Relevatordoor.png", "data/levels/assets/doors/Relevatordoor.png"),
    ("data/eyewall.png", "data/levels/assets/textures/eyewall.png"),
    ("data/fridge.png", "data/levels/assets/textures/fridge.png"),
    ("data/gunitem.png", "data/levels/assets/textures/gunitem.png"),
    ("data/hud.png", "data/levels/assets/textures/hud.png"),
    ("data/prison.png", "data/levels/assets/textures/prison.png"),
    ("data/prisonwindow.png", "data/levels/assets/textures/prisonwindow.png"),
    ("data/unknown.png", "data/levels/assets/textures/unknown.png"),
    ("data/wall.png", "data/levels/assets/textures/wall.png"),
    ("data/window.png", "data/levels/assets/textures/window.png"),
    ("data/key.gif", "data/levels/assets/actors/key.gif"),
    ("data/metopear.gif", "data/levels/assets/actors/metopear.gif"),
    ("data/patrol.gif", "data/levels/assets/actors/patrol.gif"),
    ("data/whatthe.gif", "data/levels/assets/actors/whatthe.gif"),
    ("data/step.wav", "data/levels/assets/audio/step.wav"),
)


def _project_root():
    return Path(__file__).resolve().parents[2]


def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return str(_project_root())

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return str(_project_root())

def resolve_asset_path(*parts):
    normalized = "/".join(str(part).replace("\\", "/").strip("/") for part in parts if str(part))
    for old_prefix, new_prefix in _ASSET_PATH_ALIASES:
        if normalized == old_prefix.rstrip("/"):
            normalized = new_prefix.rstrip("/")
            break
        if normalized.startswith(old_prefix):
            normalized = new_prefix + normalized[len(old_prefix):]
            break
    return normalized

def get_resource_path(*parts):
    resolved = resolve_asset_path(*parts)
    if not resolved:
        return get_exe_dir()
    return os.path.join(get_exe_dir(), *resolved.split("/"))

def block_esc(widget):
    widget.bind("<Escape>", lambda e: "break")

def safe_destroy(win):
    try:
        if win and win.winfo_exists():
            win.destroy()
    except:
        pass
