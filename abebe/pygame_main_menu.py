from __future__ import annotations

import subprocess
import sys
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pygame
from PIL import Image, ImageSequence

from abebe.core.background_music import apply_music_settings, play_music, stop_music
from abebe.core.config import BACKGROUND_MUSIC
from abebe.core.user_settings import DEFAULT_SETTINGS, PIXEL_PRESETS, load_settings, save_settings
from abebe.core.utils import get_exe_dir
from abebe.custom_maps import CUSTOM_MAPS_DIR, CustomMapError, ensure_custom_maps_dir, list_custom_map_names, load_custom_map_document
from abebe.maze.city_maze import MAP as CITY_MAP
from abebe.maze.custom_maze import start_custom_maze
from abebe.maze.opengl_city_maze import start_city_maze_opengl
from abebe.maze.opengl_maze_core import prewarm_opengl_display
from abebe.maze.opengl_secret_maze import start_secret_maze_opengl
from abebe.maze.opengl_testing_maze import start_testing_maze_opengl
from abebe.maze.opengl_tutor_maze import start_tutor_maze_opengl
from abebe.maze.secret_maze import MAP as SECRET_MAP
from abebe.maze.testing_maze import MAP as TESTING_MAP
from abebe.maze.tutor_maze import MAP as TUTOR_MAP


DESKTOP_BG = (195, 195, 195)
DESKTOP_DARK = (184, 184, 184)
TITLE_BLUE = (0, 0, 128)
PANEL_BG = (195, 195, 195)
PANEL_ACTIVE = (220, 220, 220)
PANEL_BORDER = (128, 128, 128)
TEXT_COLOR = (0, 0, 0)
TEXT_MUTED = (74, 74, 74)
WHITE = (245, 245, 245)
BLACK = (18, 18, 18)
TERMINAL_BG = (0, 0, 0)
TERMINAL_FG = (240, 240, 240)
HIGHLIGHT = (70, 120, 255)
WARN = (170, 70, 50)
SECTION_LABELS = {
    "graphics": "Graphics",
    "audio": "Audio",
    "game": "General",
}
INTRO_SUBTITLES = [
    "Hello, my friend.",
    "My name is Abebe, and I am your digital assistant in our organization.",
    "Here we store the most secret files.",
    "I hope you are not an intruder.",
    "I mean to protect our company from bad people.",
]
EDITOR_TILE_OPTIONS = [
    ("wall", "#6A6A6A", "#"),
    ("spawn", "#FFB347", "P"),
    ("mannequin", "#D4D4D4", "M"),
    ("hexagaze", "#FF5D5D", "C"),
    ("gun", "#58AEFF", "G"),
    ("bomb", "#FFD24A", "B"),
    ("stair", "#8B6CFF", "I"),
]
EDITOR_TILE_SET = {name for name, _color, _char in EDITOR_TILE_OPTIONS}
EDITOR_TILE_CHARS = {name: char for name, _color, char in EDITOR_TILE_OPTIONS}
EDITOR_TILE_COLORS = {name: color for name, color, _char in EDITOR_TILE_OPTIONS}
EDITOR_MAX_MAP_SIZE = 64
EDITOR_MAX_LAYERS = 16


@dataclass
class DesktopIcon:
    key: str
    label: str
    image_key: str
    enabled: bool = True
    rect: pygame.Rect | None = None


@dataclass
class StartMenuItem:
    label: str
    action: str
    enabled: bool = True


class PygameDesktopApp:
    def __init__(self):
        self.running = True
        self.password_history = []
        self.start_menu_open = False
        self.active_window = None
        self.minimized_window = None
        self.windows = []
        self.minimized_windows = []
        self.notification = ""
        self.notification_until = 0
        self.dragging_window = False
        self.drag_offset = (0, 0)
        self.drag_outline_rect = None
        self.drag_window = None
        self.windowed_size = (1280, 720)
        self.assets = {}
        self.wallpaper = None
        self.screen = None
        self.clock = None
        self.fonts = {}
        self.focus_target = None
        self.gallery_thumbs = {}
        self.intro_frames = []
        self.window_icons = {
            "new_game": "exe",
            "settings": "settings",
            "intro": "mycomputer",
            "terminal": "folder",
            "text_viewer": "data",
            "image_viewer": "data",
            "gallery": "folder",
            "editor": "settings",
        }
        self._init_pygame()
        self._build_desktop_model()

    def _init_pygame(self):
        pygame.init()
        pygame.display.init()
        pygame.display.set_caption("ABEBE WATCHER")
        self.clock = pygame.time.Clock()
        self._load_fonts()
        self.screen = self._make_display(self.windowed_size)
        self._load_assets()
        self._resume_menu_audio()
        self.wallpaper = self._fit_cover(self.assets.get("wallpaper"), self.screen.get_size())

    def _load_fonts(self):
        def make(size, bold=False):
            for name in ("Terminal", "Consolas", "Courier New", "Courier"):
                try:
                    return pygame.font.SysFont(name, size, bold=bold)
                except Exception:
                    continue
            return pygame.font.Font(None, size)

        self.fonts = {
            "title": make(38, True),
            "desktop": make(14, True),
            "body": make(20),
            "button": make(18, True),
            "small": make(14),
            "tiny": make(12),
            "window_title": make(16, True),
            "terminal": make(18),
        }

    def _load_assets(self):
        base = Path(get_exe_dir())
        pane_dir = base / "data" / "app" / "pane_os"
        brerder_dir = pane_dir / "brerder"
        story_dir = base / "data" / "app" / "story"
        abebe_dir = base / "data" / "app" / "abebe"
        assets = {}

        def load_image(path, fallback_size=(64, 64), fallback_color=(180, 180, 180)):
            try:
                return pygame.image.load(str(path)).convert_alpha()
            except Exception:
                surf = pygame.Surface(fallback_size, pygame.SRCALPHA)
                surf.fill(fallback_color)
                pygame.draw.rect(surf, BLACK, surf.get_rect(), 2)
                return surf

        assets["wallpaper"] = load_image(pane_dir / "SMILE.png", (320, 240), (110, 110, 110))
        for key, filename in {
            "mycomputer": "mycomputer.png",
            "exe": "exefile.png",
            "settings": "settingfile.png",
            "folder": "folder.png",
            "data": "datafile.png",
            "start": "start.png",
            "window_bg": "wondiw.png",
            "close_idle": "close1.png",
            "close_hover": "close2.png",
            "close_pressed": "close3.png",
            "min_idle": "minimaze1.png",
            "min_hover": "minimaze2.png",
            "min_pressed": "minimaze3.png",
            "max_idle": "maximize1.png",
            "max_hover": "maximize2.png",
            "max_pressed": "maximize3.png",
        }.items():
            assets[key] = load_image(pane_dir / filename)
        for tool_name in ("save", "paint", "erase", "cursor", "move", "rotate", "scale"):
            for state in ("1", "2", "3"):
                assets[f"brerder_{tool_name}_{state}"] = load_image(
                    brerder_dir / f"{tool_name}{state}.png",
                    (64, 22),
                    (195, 195, 195),
                )

        assets["death"] = load_image(story_dir / "death.png", (320, 240), (100, 0, 0))
        assets["easteregg"] = load_image(story_dir / "easteregg.png", (320, 240), (0, 80, 80))
        assets["abebe"] = load_image(abebe_dir / "abebecorpbankrupt.png", (256, 256), (80, 80, 140))
        self.assets = assets
        self.gallery_thumbs = {
            "death": pygame.transform.smoothscale(assets["death"], (96, 64)),
            "easteregg": pygame.transform.smoothscale(assets["easteregg"], (96, 64)),
        }
        self.intro_frames = self._load_intro_frames(abebe_dir / "abebehello.gif")

    def _load_intro_frames(self, path):
        frames = []
        try:
            image = Image.open(path)
            for frame in ImageSequence.Iterator(image):
                rgba = frame.convert("RGBA")
                mode = rgba.mode
                size = rgba.size
                data = rgba.tobytes()
                surface = pygame.image.fromstring(data, size, mode).convert_alpha()
                frames.append(surface)
        except Exception:
            return []
        return frames

    def _build_desktop_model(self):
        self.desktop_icons = [
            DesktopIcon("new_game", "ABEBE_PROTOCOL.exe", "exe"),
            DesktopIcon("save_data", "save_data.bin", "data", enabled=False),
            DesktopIcon("terminal", "secret_files/", "folder"),
            DesktopIcon("settings", "system_settings.ini", "settings"),
            DesktopIcon("intro", "my_computer.lnk", "mycomputer"),
            DesktopIcon("shutdown", "shutdown.exe", "exe"),
        ]
        self.start_items = [
            StartMenuItem("ABEBE_PROTOCOL.exe", "new_game"),
            StartMenuItem("save_data.bin", "save_data", False),
            StartMenuItem("secret_files/", "terminal"),
            StartMenuItem("system_settings.ini", "settings"),
            StartMenuItem("my_computer.lnk", "intro"),
            StartMenuItem("Brerder.exe", "editor"),
            StartMenuItem("Classic Desktop", "legacy"),
            StartMenuItem("shutdown.exe", "shutdown"),
        ]

    def _make_display(self, windowed_size):
        settings = load_settings()
        flags = 0
        if settings.get("fullscreen", True):
            info = pygame.display.Info()
            return pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
        return pygame.display.set_mode(windowed_size, pygame.RESIZABLE)

    def _refresh_display_mode(self):
        self.screen = self._make_display(self.windowed_size)
        self.wallpaper = self._fit_cover(self.assets.get("wallpaper"), self.screen.get_size())

    def _resume_menu_audio(self):
        if load_settings().get("music_enabled", True):
            play_music(BACKGROUND_MUSIC)
            apply_music_settings()

    def _fit_cover(self, image, size):
        if image is None:
            return None
        width, height = size
        scale = max(width / image.get_width(), height / image.get_height())
        scaled_size = (
            max(1, int(image.get_width() * scale)),
            max(1, int(image.get_height() * scale)),
        )
        scaled = pygame.transform.scale(image, scaled_size)
        surface = pygame.Surface(size)
        x = (width - scaled_size[0]) // 2
        y = (height - scaled_size[1]) // 2
        surface.blit(scaled, (x, y))
        return surface

    def _scaled_icon(self, key, size=(64, 64)):
        image = self.assets.get(key)
        if image is None:
            surface = pygame.Surface(size)
            surface.fill(DESKTOP_DARK)
            return surface
        return pygame.transform.scale(image, size)

    def _launch_legacy_desktop(self):
        subprocess.run([sys.executable, "-m", "abebe.legacy_tk_menu_backup"], check=False)

    def _show_notice(self, text, duration_ms=2600):
        self.notification = text
        self.notification_until = pygame.time.get_ticks() + duration_ms

    def _sync_active_window(self):
        self.active_window = self.windows[-1] if self.windows else None
        self.minimized_window = self.minimized_windows[-1] if self.minimized_windows else None

    def _focus_window(self, window):
        if window in self.windows:
            self.windows.remove(window)
            self.windows.append(window)
        self._sync_active_window()
        self.focus_target = window["kind"] if window else None

    def _find_window(self, kind):
        for window in reversed(self.windows):
            if window.get("kind") == kind:
                return window, False
        for window in reversed(self.minimized_windows):
            if window.get("kind") == kind:
                return window, True
        return None, False

    def _window_at_pos(self, pos):
        for window in reversed(self.windows):
            if window["rect"].collidepoint(pos):
                return window
        return None

    def _clear_window(self, window=None):
        target = window or self.active_window
        if target in self.windows:
            self.windows.remove(target)
        if target in self.minimized_windows:
            self.minimized_windows.remove(target)
        if self.drag_window is target:
            self.drag_window = None
            self.drag_outline_rect = None
            self.dragging_window = False
        self._sync_active_window()
        self.focus_target = None

    def _make_window(self, kind, title, size=(760, 500), **payload):
        existing, was_minimized = self._find_window(kind)
        if existing is not None:
            existing["title"] = title
            existing.update(payload)
            if was_minimized:
                self.minimized_windows.remove(existing)
                self.windows.append(existing)
            self._focus_window(existing)
            return existing
        sw, sh = self.screen.get_size()
        rect = pygame.Rect(0, 0, size[0], size[1])
        rect.center = (sw // 2, sh // 2)
        window = {
            "kind": kind,
            "title": title,
            "rect": rect,
            "normal_rect": rect.copy(),
            "maximized": False,
            "drag_rect": pygame.Rect(rect.x + 8, rect.y + 8, rect.w - 16, 24),
        }
        window.update(payload)
        self.windows.append(window)
        self._focus_window(window)
        return window

    def open_new_game(self):
        selected_slot = load_settings().get("selected_save_slot")
        stage = "cases" if selected_slot else "slots"
        self._make_window("new_game", "NEW_GAME.EXE", size=(760, 500), stage=stage)

    def open_settings(self):
        self._make_window("settings", "SYSTEM_SETTINGS.EXE", size=(820, 560), section="graphics")

    def open_intro(self):
        self._make_window(
            "intro",
            "FILE_054_Intro_Abebe.MP4",
            size=(920, 620),
            lines=INTRO_SUBTITLES,
            intro_frame=0,
            intro_tick=pygame.time.get_ticks(),
            intro_line=0,
        )

    def open_terminal(self):
        for window in self.windows:
            if window.get("kind") == "terminal":
                self._focus_window(window)
                return
        output = [
            "PaneOS SYSTEM TERMINAL v2.0",
            "(c) 2060 Abel B. E. & Bane C. E. Bros",
            "",
            'Type "!help" to display available commands.',
            "",
        ]
        self._make_window(
            "terminal",
            "COMMAND PROMPT",
            size=(860, 560),
            output=output,
            input="",
            cursor_timer=0.0,
            custom_maps=list_custom_map_names(),
        )

    def open_text_viewer(self, title, text):
        lines = text.splitlines() if isinstance(text, str) else list(text)
        self._make_window("text_viewer", title, size=(780, 520), lines=lines, scroll=0)

    def open_image_viewer(self, title, image_key):
        self._make_window("image_viewer", title, size=(780, 560), image_key=image_key)

    def open_gallery(self):
        self._make_window(
            "gallery",
            "GALLERY.EXE",
            size=(720, 420),
            items=[
                ("death.png", "death"),
                ("easteregg.png", "easteregg"),
                ("INFO.TXT", "info"),
                ("12340.TXT", "incident"),
            ],
        )

    def _make_blank_cell(self):
        return {
            "tile": "empty",
            "height": 1,
            "rotation": 0.0,
            "rotation_x": 0.0,
            "rotation_y": 0.0,
            "has_floor": True,
            "has_ceiling": True,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "scale_z": 1.0,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "offset_z": 0.0,
            "texture": "",
            "color": "",
            "collidable": True,
        }

    def _make_blank_layers(self, map_w, map_h, count=1):
        return [
            [[self._make_blank_cell() for _x in range(map_w)] for _y in range(map_h)]
            for _ in range(max(1, count))
        ]

    def _editor_export_document(self, editor):
        return {
            "name": editor["map_name"],
            "width": editor["width"],
            "height": editor["height"],
            "layers": editor["layers"],
        }

    def _editor_reset_camera(self, editor):
        center_x = max(1.0, editor["width"] * 0.5)
        center_y = max(1.0, editor["height"] * 0.5)
        size_hint = max(editor["width"], editor["height"])
        editor["camera_x"] = center_x - max(4.0, size_hint * 0.45)
        editor["camera_y"] = center_y - max(6.0, size_hint * 0.75)
        editor["camera_z"] = max(4.0, len(editor["layers"]) * 2.2 + 3.0)
        editor["camera_yaw"] = math.radians(40.0)
        editor["camera_pitch"] = math.radians(-18.0)
        editor["pressed_keys"] = set()

    def _new_editor_state(self, document=None):
        ensure_custom_maps_dir()
        if document is None:
            layers = self._make_blank_layers(24, 24, 1)
            editor = {
                "map_name": "Untitled",
                "width": 24,
                "height": 24,
                "layers": layers,
                "active_layer": 0,
                "selected_tile": "wall",
                "brush_height": 1,
                "selected_height": 1,
                "saved_path": None,
                "dirty": False,
                "palette_rects": [],
                "cell_rects": {},
                "load_rects": [],
                "builtin_rects": [],
                "name_editing": False,
                "undo_stack": [],
                "redo_stack": [],
                "page": "home",
                "view_mode": "2d",
                "active_tool": "paint",
                "selected_cell": None,
                "page_rects": [],
                "toolbar_rects": [],
                "menu_rects": [],
                "menu_item_rects": [],
                "layer_rects": [],
                "layer_flag_rects": [],
                "object_rects": [],
                "inspector_rects": [],
                "inspector_value_rects": [],
                "palette_box_rect": None,
                "layers_box_rect": None,
                "inspector_box_rect": None,
                "object_list_rect": None,
                "object_scroll": 0,
                "palette_scroll": 0,
                "layer_scroll": 0,
                "inspector_scroll": 0,
                "menu_open": None,
                "canvas_rect": None,
                "status": "Choose Open or New to begin editing.",
                "width_input": "24",
                "height_input": "24",
                "layers_input": "1",
                "new_focus": "width",
                "new_replace_on_type": True,
                "new_input_rects": [],
                "sidebar_rects": [],
                "load_page_rects": [],
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
                "panning_2d": False,
                "painting": False,
                "orbiting_3d": False,
                "pick_candidates": [],
                "gizmo_hits": [],
                "gizmo_drag": None,
                "inspector_focus": None,
                "last_object_click": {"id": None, "tick": 0},
                "orbit_focus": None,
            }
        else:
            editor = {
                "map_name": document.get("name") or document.get("resolved_name", "Untitled"),
                "width": int(document["width"]),
                "height": int(document["height"]),
                "layers": document["layers"],
                "active_layer": 0,
                "selected_tile": "wall",
                "brush_height": 1,
                "selected_height": 1,
                "saved_path": document.get("path"),
                "dirty": False,
                "palette_rects": [],
                "cell_rects": {},
                "load_rects": [],
                "builtin_rects": [],
                "name_editing": False,
                "undo_stack": [],
                "redo_stack": [],
                "page": "editor",
                "view_mode": "2d",
                "active_tool": "paint",
                "selected_cell": None,
                "page_rects": [],
                "toolbar_rects": [],
                "menu_rects": [],
                "menu_item_rects": [],
                "layer_rects": [],
                "layer_flag_rects": [],
                "object_rects": [],
                "inspector_rects": [],
                "inspector_value_rects": [],
                "palette_box_rect": None,
                "layers_box_rect": None,
                "inspector_box_rect": None,
                "object_list_rect": None,
                "object_scroll": 0,
                "palette_scroll": 0,
                "layer_scroll": 0,
                "inspector_scroll": 0,
                "menu_open": None,
                "canvas_rect": None,
                "status": f'Loaded "{document.get("name") or document.get("resolved_name", "Untitled")}"',
                "width_input": str(int(document["width"])),
                "height_input": str(int(document["height"])),
                "layers_input": str(max(1, len(document["layers"]))),
                "new_focus": "width",
                "new_replace_on_type": True,
                "new_input_rects": [],
                "sidebar_rects": [],
                "load_page_rects": [],
                "zoom": 1.0,
                "pan_x": 0.0,
                "pan_y": 0.0,
                "panning_2d": False,
                "painting": False,
                "orbiting_3d": False,
                "pick_candidates": [],
                "gizmo_hits": [],
                "gizmo_drag": None,
                "inspector_focus": None,
                "last_object_click": {"id": None, "tick": 0},
                "orbit_focus": None,
            }
        self._editor_reset_camera(editor)
        return editor

    def open_editor(self, document=None):
        editor = self._new_editor_state(document)
        self._make_window("editor", "Brerder.exe", size=(1320, 860), editor=editor)

    def _editor_snapshot(self, editor):
        return {
            "map_name": editor["map_name"],
            "width": editor["width"],
            "height": editor["height"],
            "layers": json.loads(json.dumps(editor["layers"])),
            "active_layer": editor["active_layer"],
            "selected_tile": editor["selected_tile"],
            "brush_height": editor["brush_height"],
            "selected_height": editor.get("selected_height", editor["brush_height"]),
            "selected_cell": editor.get("selected_cell"),
            "view_mode": editor.get("view_mode", "2d"),
            "page": editor.get("page", "editor"),
        }

    def _editor_restore_snapshot(self, editor, snapshot):
        editor["map_name"] = snapshot["map_name"]
        editor["width"] = snapshot["width"]
        editor["height"] = snapshot["height"]
        editor["layers"] = snapshot["layers"]
        editor["active_layer"] = min(snapshot["active_layer"], len(editor["layers"]) - 1)
        editor["selected_tile"] = snapshot["selected_tile"]
        editor["brush_height"] = snapshot["brush_height"]
        editor["selected_height"] = snapshot.get("selected_height", editor["brush_height"])
        editor["selected_cell"] = snapshot.get("selected_cell")
        editor["view_mode"] = snapshot.get("view_mode", "2d")
        editor["page"] = snapshot.get("page", "editor")
        editor["width_input"] = str(editor["width"])
        editor["height_input"] = str(editor["height"])
        editor["layers_input"] = str(len(editor["layers"]))
        editor["new_focus"] = "width"
        editor["new_replace_on_type"] = True
        self._editor_reset_camera(editor)
        editor["dirty"] = True

    def _editor_active_cell(self, editor):
        selected = editor.get("selected_cell")
        if selected is None:
            return None, None
        gx, gy = selected
        if 0 <= gx < editor["width"] and 0 <= gy < editor["height"]:
            return selected, editor["layers"][editor["active_layer"]][gy][gx]
        return None, None

    def _editor_object_entries(self, editor):
        entries = []
        for layer_idx, layer in enumerate(editor["layers"]):
            for y, row in enumerate(layer):
                for x, cell in enumerate(row):
                    tile = cell.get("tile", "empty")
                    if tile == "empty":
                        continue
                    focus_z = layer_idx + float(cell.get("offset_z", 0.0)) + (float(cell.get("height", 1)) * float(cell.get("scale_z", 1.0)) * 0.5)
                    entries.append(
                        {
                            "id": f"{layer_idx}:{x}:{y}",
                            "layer": layer_idx,
                            "x": x,
                            "y": y,
                            "tile": tile,
                            "height": int(cell.get("height", 1)),
                            "focus": (
                                x + 0.5 + float(cell.get("offset_x", 0.0)),
                                y + 0.5 + float(cell.get("offset_y", 0.0)),
                                focus_z,
                            ),
                        }
                    )
        return entries

    def _editor_select_object(self, editor, layer_idx, x_pos, y_pos):
        if not (0 <= layer_idx < len(editor["layers"])):
            return False
        if not (0 <= x_pos < editor["width"] and 0 <= y_pos < editor["height"]):
            return False
        cell = editor["layers"][layer_idx][y_pos][x_pos]
        if cell["tile"] == "empty":
            return False
        editor["active_layer"] = layer_idx
        editor["selected_cell"] = (x_pos, y_pos)
        editor["orbit_focus"] = (
            x_pos + 0.5 + float(cell.get("offset_x", 0.0)),
            y_pos + 0.5 + float(cell.get("offset_y", 0.0)),
            layer_idx + float(cell.get("offset_z", 0.0)) + (float(cell.get("height", 1)) * float(cell.get("scale_z", 1.0)) * 0.5),
        )
        editor["status"] = f"Selected {cell['tile']} at {x_pos}, {y_pos}, L{layer_idx + 1}"
        return True

    def _editor_focus_camera_on_selected(self, editor):
        selected, cell = self._editor_active_cell(editor)
        if selected is None or cell is None:
            return False
        focus = editor.get("orbit_focus")
        if focus is None:
            return False
        fx, fy, fz = focus
        dist = max(3.8, max(editor["width"], editor["height"]) * 0.18)
        yaw = editor.get("camera_yaw", math.radians(40.0))
        pitch = editor.get("camera_pitch", math.radians(-18.0))
        dir_x = -math.sin(yaw) * math.cos(pitch)
        dir_y = math.cos(yaw) * math.cos(pitch)
        dir_z = math.sin(pitch)
        editor["camera_x"] = fx - dir_x * dist
        editor["camera_y"] = fy - dir_y * dist
        editor["camera_z"] = fz - dir_z * dist
        editor["status"] = f"Focused camera on {cell['tile']}"
        return True

    def _editor_inspector_values(self, editor):
        selected, cell = self._editor_active_cell(editor)
        if selected is None or cell is None:
            return {}
        return {
            "name": cell["tile"],
            "pos_x": f"{selected[0] + float(cell.get('offset_x', 0.0)) + 0.5:.2f}",
            "pos_y": f"{selected[1] + float(cell.get('offset_y', 0.0)) + 0.5:.2f}",
            "pos_z": f"{editor['active_layer'] + float(cell.get('offset_z', 0.0)):.2f}",
            "rot_x": f"{float(cell.get('rotation_x', 0.0)) % 360.0:.1f}",
            "rot_y": f"{float(cell.get('rotation_y', 0.0)) % 360.0:.1f}",
            "rot_z": f"{float(cell.get('rotation', 0.0)) % 360.0:.1f}",
            "scale_x": f"{float(cell.get('scale_x', 1.0)):.2f}",
            "scale_y": f"{float(cell.get('scale_y', 1.0)):.2f}",
            "scale_z": f"{float(cell.get('scale_z', 1.0)):.2f}",
            "height": f"{float(cell.get('height', 1.0)):.2f}",
        }

    def _editor_apply_inspector_value(self, editor, key, raw_value):
        selected, cell = self._editor_active_cell(editor)
        if selected is None or cell is None:
            return False
        gx, gy = selected
        try:
            if key == "height":
                cell["height"] = max(0.5, min(5.0, float(raw_value)))
            elif key in {"scale_x", "scale_y", "scale_z"}:
                cell[key] = max(0.35, min(2.5, float(raw_value)))
            elif key in {"rot_x", "rot_y", "rot_z"}:
                target = {"rot_x": "rotation_x", "rot_y": "rotation_y", "rot_z": "rotation"}[key]
                cell[target] = float(raw_value) % 360.0
            elif key in {"pos_x", "pos_y", "pos_z"}:
                px = float(raw_value) if key == "pos_x" else gx + 0.5 + float(cell.get("offset_x", 0.0))
                py = float(raw_value) if key == "pos_y" else gy + 0.5 + float(cell.get("offset_y", 0.0))
                pz = float(raw_value) if key == "pos_z" else editor["active_layer"] + float(cell.get("offset_z", 0.0))
                if key != "pos_x":
                    px = gx + 0.5 + float(cell.get("offset_x", 0.0))
                if key != "pos_y":
                    py = gy + 0.5 + float(cell.get("offset_y", 0.0))
                if key != "pos_z":
                    pz = editor["active_layer"] + float(cell.get("offset_z", 0.0))
                dst_x = int(math.floor(px))
                dst_y = int(math.floor(py))
                dst_layer = int(max(0, min(len(editor["layers"]) - 1, math.floor(pz))))
                if not self._editor_move_selected_to(editor, dst_layer, dst_x, dst_y):
                    return False
                _selected2, moved = self._editor_active_cell(editor)
                if moved is None:
                    return False
                moved["offset_x"] = max(-0.49, min(0.49, px - (dst_x + 0.5)))
                moved["offset_y"] = max(-0.49, min(0.49, py - (dst_y + 0.5)))
                moved["offset_z"] = max(-0.95, min(0.95, pz - dst_layer))
            else:
                return False
        except ValueError:
            return False
        editor["dirty"] = True
        editor["status"] = f"Updated {key}"
        return True

    def _editor_move_selected_to(self, editor, dst_layer, dst_x, dst_y):
        selected = editor.get("selected_cell")
        if selected is None:
            return False
        src_x, src_y = selected
        src_layer = editor["active_layer"]
        if not (0 <= dst_layer < len(editor["layers"])):
            return False
        if not (0 <= dst_x < editor["width"] and 0 <= dst_y < editor["height"]):
            return False
        if src_layer == dst_layer and src_x == dst_x and src_y == dst_y:
            return True
        source_cell = editor["layers"][src_layer][src_y][src_x]
        if source_cell["tile"] == "empty":
            return False
        target_cell = editor["layers"][dst_layer][dst_y][dst_x]
        if target_cell["tile"] != "empty":
            return False
        editor["layers"][dst_layer][dst_y][dst_x] = json.loads(json.dumps(source_cell))
        editor["layers"][src_layer][src_y][src_x] = self._make_blank_cell()
        editor["active_layer"] = dst_layer
        editor["selected_cell"] = (dst_x, dst_y)
        editor["dirty"] = True
        editor["status"] = f"Moved object to {dst_x}, {dst_y}, L{dst_layer + 1}"
        return True

    def _editor_move_selected_along(self, editor, axis, direction):
        selected = editor.get("selected_cell")
        if selected is None:
            return False
        gx, gy = selected
        layer_idx = editor["active_layer"]
        if axis == "x":
            return self._editor_move_selected_to(editor, layer_idx, gx + direction, gy)
        if axis == "y":
            return self._editor_move_selected_to(editor, layer_idx, gx, gy + direction)
        return self._editor_move_selected_to(editor, layer_idx + direction, gx, gy)

    def _editor_nudge_selected_offset(self, editor, axis, delta):
        selected, cell = self._editor_active_cell(editor)
        if selected is None or cell is None or cell["tile"] == "empty":
            return False
        gx, gy = selected
        layer_idx = editor["active_layer"]
        if axis == "x":
            updated = float(cell.get("offset_x", 0.0)) + delta
            while updated > 0.5:
                if not self._editor_move_selected_to(editor, layer_idx, gx + 1, gy):
                    updated = 0.49
                    break
                selected, cell = self._editor_active_cell(editor)
                gx, gy = selected
                updated -= 1.0
            while updated < -0.5:
                if not self._editor_move_selected_to(editor, layer_idx, gx - 1, gy):
                    updated = -0.49
                    break
                selected, cell = self._editor_active_cell(editor)
                gx, gy = selected
                updated += 1.0
            cell["offset_x"] = max(-0.49, min(0.49, updated))
        elif axis == "y":
            updated = float(cell.get("offset_y", 0.0)) + delta
            while updated > 0.5:
                if not self._editor_move_selected_to(editor, layer_idx, gx, gy + 1):
                    updated = 0.49
                    break
                selected, cell = self._editor_active_cell(editor)
                gx, gy = selected
                updated -= 1.0
            while updated < -0.5:
                if not self._editor_move_selected_to(editor, layer_idx, gx, gy - 1):
                    updated = -0.49
                    break
                selected, cell = self._editor_active_cell(editor)
                gx, gy = selected
                updated += 1.0
            cell["offset_y"] = max(-0.49, min(0.49, updated))
        else:
            updated = float(cell.get("offset_z", 0.0)) + delta
            while updated > 1.0:
                if not self._editor_move_selected_to(editor, layer_idx + 1, gx, gy):
                    updated = 0.95
                    break
                layer_idx = editor["active_layer"]
                selected, cell = self._editor_active_cell(editor)
                updated -= 1.0
            while updated < 0.0:
                if not self._editor_move_selected_to(editor, layer_idx - 1, gx, gy):
                    updated = 0.0
                    break
                layer_idx = editor["active_layer"]
                selected, cell = self._editor_active_cell(editor)
                updated += 1.0
            cell["offset_z"] = max(0.0, min(0.95, updated))
        editor["dirty"] = True
        self._editor_select_object(editor, editor["active_layer"], editor["selected_cell"][0], editor["selected_cell"][1])
        return True

    def _editor_rotate_selected(self, editor, axis, delta):
        selected, cell = self._editor_active_cell(editor)
        if selected is None or cell is None or cell["tile"] == "empty":
            return False
        key = "rotation"
        if axis == "x":
            key = "rotation_x"
        elif axis == "y":
            key = "rotation_y"
        current = float(cell.get(key, 0.0))
        cell[key] = (current + delta) % 360.0
        editor["dirty"] = True
        editor["status"] = f"Rotated {axis.upper()} to {int(cell[key])}"
        return True

    def _editor_scale_selected(self, editor, axis, delta):
        selected, cell = self._editor_active_cell(editor)
        if selected is None or cell is None or cell["tile"] == "empty":
            return False
        key = {"x": "scale_x", "y": "scale_y", "z": "scale_z"}[axis]
        current = float(cell.get(key, 1.0))
        updated = max(0.35, min(2.5, round(current + delta, 3)))
        if abs(updated - current) < 0.001:
            return False
        cell[key] = updated
        editor["dirty"] = True
        editor["status"] = f"Scaled {axis.upper()} to {updated:.2f}"
        return True

    def _editor_adjust_selected_height(self, editor, delta):
        selected, cell = self._editor_active_cell(editor)
        if selected is None or cell is None or cell["tile"] == "empty":
            return False
        current = float(cell.get("height", 1))
        updated = max(0.5, min(5.0, round(current + delta, 3)))
        if abs(updated - current) < 0.001:
            return False
        cell["height"] = updated
        editor["dirty"] = True
        editor["status"] = f"Height set to {updated:.2f}"
        return True

    def _editor_toggle_selected_flag(self, editor, key):
        selected, cell = self._editor_active_cell(editor)
        if selected is None or cell is None or cell["tile"] == "empty":
            return False
        cell[key] = not bool(cell.get(key, True))
        editor["dirty"] = True
        editor["status"] = f"{key} = {cell[key]}"
        return True

    def _editor_layer_flag_value(self, editor, layer_idx, key):
        layer = editor["layers"][layer_idx]
        if not layer or not layer[0]:
            return True
        return bool(layer[0][0].get(key, True))

    def _editor_set_layer_flag(self, editor, layer_idx, key, value):
        if not (0 <= layer_idx < len(editor["layers"])):
            return False
        value = bool(value)
        layer = editor["layers"][layer_idx]
        changed = any(bool(cell.get(key, True)) != value for row in layer for cell in row)
        if not changed:
            editor["status"] = f'Layer {layer_idx + 1} {key.replace("has_", "")} already {"on" if value else "off"}.'
            return False
        self._editor_push_undo(editor)
        for row in layer:
            for cell in row:
                cell[key] = value
        editor["dirty"] = True
        editor["status"] = f'Layer {layer_idx + 1} {key.replace("has_", "")} {"enabled" if value else "disabled"}.'
        return True

    def _editor_toggle_layer_flag(self, editor, layer_idx, key):
        current = self._editor_layer_flag_value(editor, layer_idx, key)
        return self._editor_set_layer_flag(editor, layer_idx, key, not current)

    def _editor_set_page(self, editor, page):
        editor["page"] = page
        if page == "home":
            editor["status"] = "Legacy editor home page."
        elif page == "open":
            editor["status"] = "Load a built-in case or saved custom map."
        elif page == "new":
            editor["status"] = "Create a new document."
            editor["new_focus"] = "width"
            editor["new_replace_on_type"] = True

    def _editor_apply_dimensions(self, editor):
        def clamp_text(value, default, maximum):
            try:
                parsed = int(str(value).strip() or default)
            except ValueError:
                parsed = default
            return max(1, min(maximum, parsed))

        map_w = clamp_text(editor.get("width_input", "24"), 24, EDITOR_MAX_MAP_SIZE)
        map_h = clamp_text(editor.get("height_input", "24"), 24, EDITOR_MAX_MAP_SIZE)
        layer_count = clamp_text(editor.get("layers_input", "1"), 1, EDITOR_MAX_LAYERS)
        editor["width_input"] = str(map_w)
        editor["height_input"] = str(map_h)
        editor["layers_input"] = str(layer_count)
        editor["map_name"] = "Untitled"
        editor["width"] = map_w
        editor["height"] = map_h
        editor["layers"] = self._make_blank_layers(map_w, map_h, layer_count)
        editor["active_layer"] = 0
        editor["selected_cell"] = None
        editor["saved_path"] = None
        editor["dirty"] = False
        editor["undo_stack"].clear()
        editor["redo_stack"].clear()
        self._editor_reset_camera(editor)
        editor["page"] = "editor"
        editor["status"] = f"Created new {map_w} x {map_h} map with {layer_count} layer(s)."

    def _editor_cycle_view(self, editor):
        editor["view_mode"] = "3d" if editor.get("view_mode") == "2d" else "2d"
        if editor["view_mode"] == "3d":
            self._editor_reset_camera(editor)
            editor["status"] = "3D preview enabled. Use WASD, arrows and middle mouse."
        else:
            editor["status"] = "2D grid mode enabled."

    def _editor_world_to_camera(self, editor, x_pos, y_pos, z_pos):
        rel_x = x_pos - editor["camera_x"]
        rel_y = y_pos - editor["camera_y"]
        rel_z = z_pos - editor["camera_z"]
        yaw = -editor["camera_yaw"]
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        cam_x = rel_x * cos_yaw - rel_y * sin_yaw
        cam_y = rel_x * sin_yaw + rel_y * cos_yaw
        pitch = -editor["camera_pitch"]
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        cam_y2 = cam_y * cos_pitch - rel_z * sin_pitch
        cam_z = cam_y * sin_pitch + rel_z * cos_pitch
        return cam_x, cam_y2, cam_z

    def _editor_project_point(self, editor, canvas_rect, x_pos, y_pos, z_pos):
        cam_x, cam_y, cam_z = self._editor_world_to_camera(editor, x_pos, y_pos, z_pos)
        if cam_y <= 0.08:
            return None
        focal = min(canvas_rect.w, canvas_rect.h) * 0.72
        sx = canvas_rect.centerx + (cam_x / cam_y) * focal
        sy = canvas_rect.centery - (cam_z / cam_y) * focal
        return sx, sy, cam_y

    def _editor_support_height(self, editor, world_x, world_y, camera_z):
        eye_height = 1.55
        foot_z = camera_z - eye_height
        best_top = None
        for layer_idx, layer in enumerate(editor["layers"]):
            base_z = float(layer_idx) * 2.0
            for row_y, row in enumerate(layer):
                for cell_x, cell in enumerate(row):
                    if cell.get("tile") == "empty" or not cell.get("collidable", True):
                        continue
                    scale_x = max(0.35, float(cell.get("scale_x", 1.0)))
                    scale_y = max(0.35, float(cell.get("scale_y", 1.0)))
                    scale_z = max(0.35, float(cell.get("scale_z", 1.0)))
                    center_x = cell_x + 0.5 + float(cell.get("offset_x", 0.0))
                    center_y = row_y + 0.5 + float(cell.get("offset_y", 0.0))
                    half_x = 0.5 * scale_x
                    half_y = 0.5 * scale_y
                    if not (center_x - half_x <= world_x <= center_x + half_x and center_y - half_y <= world_y <= center_y + half_y):
                        continue
                    top_z = base_z + float(cell.get("offset_z", 0.0)) + max(1.0, float(cell.get("height", 1.0)) * scale_z)
                    if top_z > foot_z + 1.15:
                        continue
                    if top_z < foot_z - 2.4:
                        continue
                    if best_top is None or top_z > best_top:
                        best_top = top_z
        return None if best_top is None else best_top + eye_height

    def _editor_tick(self):
        if not self.active_window or self.active_window.get("kind") != "editor":
            return
        editor = self.active_window["editor"]
        if editor.get("page") != "editor":
            return
        pressed = editor.get("pressed_keys", set())
        if not pressed:
            return
        delta = min(0.05, max(0.0, self.clock.get_time() / 1000.0))
        if delta <= 0.0:
            return
        if editor.get("view_mode") == "2d":
            pan_speed = max(220.0, max(editor["width"], editor["height"]) * 10.0) * delta
            if "w" in pressed:
                editor["pan_y"] += pan_speed
            if "s" in pressed:
                editor["pan_y"] -= pan_speed
            if "a" in pressed:
                editor["pan_x"] += pan_speed
            if "d" in pressed:
                editor["pan_x"] -= pan_speed
            return
        if editor.get("view_mode") != "3d":
            return
        move_speed = max(2.4, max(editor["width"], editor["height"]) * 0.18) * delta
        yaw = editor["camera_yaw"]
        pitch = editor["camera_pitch"]
        forward_x = -math.sin(yaw)
        forward_y = math.cos(yaw)
        right_x = math.cos(yaw)
        right_y = math.sin(yaw)
        move_x = 0.0
        move_y = 0.0
        if "w" in pressed:
            move_x += forward_x
            move_y += forward_y
        if "s" in pressed:
            move_x -= forward_x
            move_y -= forward_y
        if "d" in pressed:
            move_x += right_x
            move_y += right_y
        if "a" in pressed:
            move_x -= right_x
            move_y -= right_y
        move_len = math.sqrt(move_x * move_x + move_y * move_y)
        if move_len > 1e-6:
            editor["orbit_focus"] = None
            editor["camera_x"] += (move_x / move_len) * move_speed
            editor["camera_y"] += (move_y / move_len) * move_speed
            support_z = self._editor_support_height(editor, editor["camera_x"], editor["camera_y"], editor["camera_z"])
            if support_z is not None:
                editor["camera_z"] = support_z
        look_speed = 1.4 * delta
        if "up" in pressed:
            editor["camera_pitch"] = max(math.radians(-80.0), min(math.radians(80.0), editor["camera_pitch"] + look_speed))
        if "down" in pressed:
            editor["camera_pitch"] = max(math.radians(-80.0), min(math.radians(80.0), editor["camera_pitch"] - look_speed))
        if "left" in pressed:
            editor["camera_yaw"] -= look_speed
        if "right" in pressed:
            editor["camera_yaw"] += look_speed

    def _editor_push_undo(self, editor):
        editor["undo_stack"].append(self._editor_snapshot(editor))
        if len(editor["undo_stack"]) > 80:
            editor["undo_stack"] = editor["undo_stack"][-80:]
        editor["redo_stack"].clear()

    def _editor_save_current(self):
        if not self.active_window or self.active_window.get("kind") != "editor":
            return
        editor = self.active_window["editor"]
        ensure_custom_maps_dir()
        map_name = (editor["map_name"] or "Untitled").strip()
        safe_name = "".join(ch for ch in map_name if ch.isalnum() or ch in {"_", "-", " "}).strip() or "Untitled"
        path = editor["saved_path"] or (CUSTOM_MAPS_DIR / f"{safe_name}.json")
        path.write_text(json.dumps(self._editor_export_document(editor), indent=2, ensure_ascii=True), encoding="utf-8")
        editor["saved_path"] = path
        editor["map_name"] = path.stem
        editor["dirty"] = False
        self._show_notice(f'Saved map "{path.stem}"')

    def _editor_menu_action(self, action):
        if not self.active_window or self.active_window.get("kind") != "editor":
            return
        editor = self.active_window["editor"]
        if action == "save":
            self._editor_save_current()
        elif action == "save_as":
            editor["saved_path"] = None
            editor["name_editing"] = True
            editor["status"] = "Type a new name and press Enter."
        elif action == "rename":
            editor["name_editing"] = True
            editor["status"] = "Rename current map."
        elif action == "open":
            self._editor_set_page(editor, "open")
        elif action == "exit":
            self._clear_window()
        elif action == "undo":
            self._editor_undo()
        elif action == "redo":
            self._editor_redo()

    def _editor_undo(self):
        if not self.active_window or self.active_window.get("kind") != "editor":
            return
        editor = self.active_window["editor"]
        if not editor["undo_stack"]:
            return
        editor["redo_stack"].append(self._editor_snapshot(editor))
        snapshot = editor["undo_stack"].pop()
        self._editor_restore_snapshot(editor, snapshot)

    def _editor_redo(self):
        if not self.active_window or self.active_window.get("kind") != "editor":
            return
        editor = self.active_window["editor"]
        if not editor["redo_stack"]:
            return
        editor["undo_stack"].append(self._editor_snapshot(editor))
        snapshot = editor["redo_stack"].pop()
        self._editor_restore_snapshot(editor, snapshot)

    def _editor_cycle_tile(self, step):
        editor = self.active_window["editor"]
        names = [name for name, _color, _char in EDITOR_TILE_OPTIONS]
        idx = names.index(editor["selected_tile"]) if editor["selected_tile"] in names else 0
        editor["selected_tile"] = names[(idx + step) % len(names)]

    def _editor_apply_paint(self, cell_x, cell_y, button):
        editor = self.active_window["editor"]
        self._editor_push_undo(editor)
        layer = editor["layers"][editor["active_layer"]]
        editor["selected_cell"] = (cell_x, cell_y)
        erase_mode = button == 3 or editor.get("active_tool") == "erase"
        if erase_mode:
            layer[cell_y][cell_x] = self._make_blank_cell()
        else:
            tile = editor["selected_tile"]
            new_cell = self._make_blank_cell()
            new_cell["tile"] = tile
            new_cell["height"] = editor.get("selected_height", editor["brush_height"])
            new_cell["has_ceiling"] = tile != "stair"
            new_cell["collidable"] = tile in {"wall", "stair"}
            if tile == "spawn":
                new_cell["collidable"] = False
            layer[cell_y][cell_x] = new_cell
        editor["dirty"] = True
        editor["status"] = f'Edited cell {cell_x}, {cell_y} on layer {editor["active_layer"] + 1}.'

    def _editor_open_selected_load(self, index):
        names = list_custom_map_names()
        if not names:
            self._show_notice("No custom maps found")
            return
        if 0 <= index < len(names):
            document = load_custom_map_document(names[index])
            self.open_editor(document)

    def _editor_run_current(self):
        editor = self.active_window["editor"]
        map_name = (editor["map_name"] or "Untitled").strip()
        safe_name = "".join(ch for ch in map_name if ch.isalnum() or ch in {"_", "-", " "}).strip() or "Untitled"
        path = CUSTOM_MAPS_DIR / f"{safe_name}.json"
        path.write_text(json.dumps(self._editor_export_document(editor), indent=2, ensure_ascii=True), encoding="utf-8")
        stop_music()
        self._prepare_level_transition()
        try:
            start_custom_maze(None, safe_name)
        finally:
            self._init_pygame()
            document = load_custom_map_document(safe_name)
            self.open_editor(document)

    def _editor_load_builtin(self, name, map_rows):
        map_h = len(map_rows)
        map_w = len(map_rows[0]) if map_rows else 24
        layers = self._make_blank_layers(map_w, map_h, 1)
        char_to_tile = {
            "#": "wall",
            "P": "spawn",
            "M": "mannequin",
            "C": "hexagaze",
            "G": "gun",
            "B": "bomb",
            "I": "stair",
        }
        for y, row in enumerate(map_rows):
            for x, ch in enumerate(row):
                tile = char_to_tile.get(ch, "empty")
                cell = layers[0][y][x]
                cell["tile"] = tile
                cell["has_ceiling"] = tile != "stair"
                cell["collidable"] = tile in {"wall", "stair"}
        self.open_editor({"name": name, "width": map_w, "height": map_h, "layers": layers})

    def _toggle_active_window_maximize(self):
        if not self.active_window:
            return
        window = self.active_window
        sw, sh = self.screen.get_size()
        if not window.get("maximized"):
            window["normal_rect"] = window["rect"].copy()
            window["rect"] = pygame.Rect(0, 28, sw, sh - 62)
            window["maximized"] = True
        else:
            window["rect"] = window["normal_rect"].copy()
            window["maximized"] = False

    def _minimize_active_window(self):
        if self.active_window is None:
            return
        self.minimized_windows.append(self.active_window)
        if self.active_window in self.windows:
            self.windows.remove(self.active_window)
        self._sync_active_window()

    def _prepare_level_transition(self):
        if not pygame.get_init() or self.screen is None:
            return
        try:
            self.screen, _width, _height = prewarm_opengl_display()
        except Exception:
            try:
                info = pygame.display.Info()
                fullscreen_size = (info.current_w, info.current_h)
                self.screen = pygame.display.set_mode(fullscreen_size, pygame.FULLSCREEN)
                self.screen.fill(BLACK)
                pygame.display.flip()
                pygame.event.pump()
            except pygame.error:
                pass
        except pygame.error:
            pass

    def _run_level(self, callback, *args):
        stop_music()
        self._prepare_level_transition()
        try:
            callback(None, *args)
        finally:
            self._init_pygame()
            self._clear_window()

    def handle_action(self, action):
        if action == "new_game":
            self.open_new_game()
        elif action == "save_data":
            self._show_notice("save_data.bin is still locked")
        elif action == "terminal":
            self.open_terminal()
        elif action == "settings":
            self.open_settings()
        elif action == "intro":
            self.open_intro()
        elif action == "shutdown":
            self.running = False
        elif action == "legacy":
            stop_music()
            self._launch_legacy_desktop()
            self._resume_menu_audio()
        elif action == "editor":
            self.open_editor()

    def _terminal_append(self, *lines):
        if not self.active_window or self.active_window.get("kind") != "terminal":
            return
        self.active_window["output"].extend(lines)

    def _execute_terminal_command(self, command):
        command = command.strip()
        if not command:
            return

        self.password_history.append(command)
        self._terminal_append(f"> {command}")
        terminal = self.active_window
        terminal["input"] = ""

        if command == "!help":
            self._terminal_append(
                "Available commands:",
                "!help",
                "!history",
                "!gallery",
                "!info",
                "!dev",
                "!reset",
                "!sound on/off",
                "!easteregg",
                "!12340",
                "load tutor",
                "load secret",
                "load city",
                "load test",
                "load custom <map>",
                "run edit",
                "",
            )
            return

        if command == "!history":
            if self.password_history:
                self._terminal_append("Entered commands:")
                self._terminal_append(*self.password_history[-12:])
            else:
                self._terminal_append("No history yet.")
            return

        if command == "!gallery":
            self.open_gallery()
            return

        if command == "!info":
            text = (Path(get_exe_dir()) / "data" / "app" / "story" / "info.txt").read_text(encoding="utf-8")
            self.open_text_viewer("INFO.TXT", text)
            return

        if command == "!dev":
            self.open_text_viewer(
                "DEV.INFO",
                "\n".join(
                    [
                        "Developer state:",
                        f"History items: {len(self.password_history)}",
                        f"Selected save slot: {load_settings().get('selected_save_slot')}",
                        "Watcher systems: disabled",
                    ]
                ),
            )
            return

        if command == "!reset":
            self.password_history.clear()
            save_settings({"selected_save_slot": None, "new_game_slot_prompt_seen": False})
            self._terminal_append("State reset complete.")
            return

        if command == "!easteregg":
            self.open_image_viewer("EASTER EGG", "easteregg")
            return

        if command == "!12340":
            text = (Path(get_exe_dir()) / "data" / "app" / "story" / "12340.txt").read_text(encoding="utf-8")
            self.open_text_viewer("12340.TXT", text)
            return

        if command.startswith("!sound"):
            if command.endswith("off"):
                save_settings({"music_enabled": False})
                stop_music()
                self._terminal_append("Background music disabled.")
            elif command.endswith("on"):
                save_settings({"music_enabled": True})
                self._resume_menu_audio()
                self._terminal_append("Background music enabled.")
            else:
                self._terminal_append("Use !sound on or !sound off")
            return

        if command == "run edit":
            self.open_editor()
            return

        if command.startswith("load "):
            target = command[5:].strip()
            if target == "tutor":
                self._run_level(start_tutor_maze_opengl)
                return
            if target == "secret":
                self._run_level(start_secret_maze_opengl)
                return
            if target == "city":
                self._run_level(start_city_maze_opengl)
                return
            if target == "test":
                self._run_level(start_testing_maze_opengl)
                return
            if target.startswith("custom "):
                map_name = target[7:].strip()
                try:
                    document = load_custom_map_document(map_name)
                except CustomMapError as exc:
                    self._terminal_append(str(exc))
                    return
                self._terminal_append(f'Loading custom map "{document["resolved_name"]}"')
                self._run_level(start_custom_maze, document["resolved_name"])
                return
            self._terminal_append(f"Unknown level: {target}")
            return

        self._terminal_append(f"Unknown command: {command}")

    def _settings_sections(self):
        current = load_settings()
        return {
            "graphics": [
                ("Fullscreen", current["fullscreen"], "toggle_fullscreen"),
                ("Pixel preset", current["pixel_preset"], "cycle_pixel"),
                ("Brightness", f'{int(current["brightness"] * 100)}%', "brightness"),
                ("View bob", f'{int(current["view_bob"] * 100)}%', "view_bob"),
                ("FOV", f'{int(current["fov_degrees"])} deg', "fov"),
            ],
            "audio": [
                ("Music enabled", current["music_enabled"], "toggle_music"),
                ("Master volume", f'{int(current["master_volume"] * 100)}%', "master_volume"),
                ("Music volume", f'{int(current["music_volume"] * 100)}%', "music_volume"),
                ("SFX volume", f'{int(current["sfx_volume"] * 100)}%', "sfx_volume"),
            ],
            "game": [
                ("Flash effects", current["flash_enabled"], "toggle_flash"),
                ("Impact particles", current["impact_particles_enabled"], "toggle_particles"),
                ("Bullet marks", current["bullet_marks_enabled"], "toggle_bullets"),
                ("Screen effects", current["screen_effects_enabled"], "toggle_screen_fx"),
                ("Rear world culling", current["rear_world_culling_enabled"], "toggle_culling"),
                ("Show FPS", current["show_fps"], "toggle_fps"),
                ("Show debug stats", current["show_debug_stats"], "toggle_debug"),
                ("Mouse wheel switch", current["mouse_wheel_weapon_switch"], "toggle_wheel"),
                ("Selected save slot", current["selected_save_slot"] or "NONE", "save_slot"),
                ("Reset save slot", "click", "reset_slot"),
                ("Reset defaults", "click", "reset_defaults"),
            ],
        }

    def _settings_change(self, command, direction=1):
        settings = load_settings()
        if command == "toggle_fullscreen":
            save_settings({"fullscreen": not settings["fullscreen"]})
            self._refresh_display_mode()
        elif command == "toggle_music":
            new_value = not settings["music_enabled"]
            save_settings({"music_enabled": new_value})
            if new_value:
                self._resume_menu_audio()
            else:
                stop_music()
        elif command == "toggle_flash":
            save_settings({"flash_enabled": not settings["flash_enabled"]})
        elif command == "toggle_particles":
            save_settings({"impact_particles_enabled": not settings["impact_particles_enabled"]})
        elif command == "toggle_bullets":
            save_settings({"bullet_marks_enabled": not settings["bullet_marks_enabled"]})
        elif command == "toggle_screen_fx":
            save_settings({"screen_effects_enabled": not settings["screen_effects_enabled"]})
        elif command == "toggle_culling":
            save_settings({"rear_world_culling_enabled": not settings["rear_world_culling_enabled"]})
        elif command == "toggle_fps":
            save_settings({"show_fps": not settings["show_fps"]})
        elif command == "toggle_debug":
            save_settings({"show_debug_stats": not settings["show_debug_stats"]})
        elif command == "toggle_wheel":
            save_settings({"mouse_wheel_weapon_switch": not settings["mouse_wheel_weapon_switch"]})
        elif command == "cycle_pixel":
            presets = list(PIXEL_PRESETS.keys())
            idx = presets.index(settings["pixel_preset"])
            save_settings({"pixel_preset": presets[(idx + direction) % len(presets)]})
        elif command == "brightness":
            value = max(0.0, min(1.0, settings["brightness"] + (0.05 * direction)))
            save_settings({"brightness": value})
        elif command == "view_bob":
            save_settings({"view_bob": max(0.0, min(1.0, settings["view_bob"] + (0.05 * direction)))})
        elif command == "fov":
            save_settings({"fov_degrees": max(45.0, min(110.0, settings["fov_degrees"] + (5.0 * direction)))})
        elif command == "master_volume":
            save_settings({"master_volume": max(0.0, min(1.0, settings["master_volume"] + (0.05 * direction)))})
            apply_music_settings()
        elif command == "music_volume":
            save_settings({"music_volume": max(0.0, min(1.0, settings["music_volume"] + (0.05 * direction))), "music_enabled": True})
            self._resume_menu_audio()
        elif command == "sfx_volume":
            save_settings({"sfx_volume": max(0.0, min(1.0, settings["sfx_volume"] + (0.05 * direction)))})
        elif command == "reset_slot":
            save_settings({"selected_save_slot": None, "new_game_slot_prompt_seen": False})
        elif command == "reset_defaults":
            save_settings(DEFAULT_SETTINGS.copy())
            self._refresh_display_mode()
            self._resume_menu_audio()

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return

        if event.type == pygame.VIDEORESIZE:
            self.windowed_size = event.size
            if not load_settings().get("fullscreen", True):
                self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
                self.wallpaper = self._fit_cover(self.assets.get("wallpaper"), self.screen.get_size())
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                settings = load_settings()
                save_settings({"fullscreen": not settings.get("fullscreen", True)})
                self._refresh_display_mode()
                return
            if event.key == pygame.K_ESCAPE:
                if self.start_menu_open:
                    self.start_menu_open = False
                elif self.active_window:
                    self._clear_window()
                else:
                    self.running = False
                return
            if self.active_window and self.active_window.get("kind") == "terminal":
                self._handle_terminal_key(event)
                return
            if self.active_window and self.active_window.get("kind") == "editor":
                self._handle_editor_key(event)
                return
            if self.active_window and self.active_window.get("kind") == "text_viewer":
                if event.key == pygame.K_UP:
                    self.active_window["scroll"] = max(0, self.active_window["scroll"] - 1)
                elif event.key == pygame.K_DOWN:
                    self.active_window["scroll"] += 1
                return

        if event.type == pygame.KEYUP and self.active_window and self.active_window.get("kind") == "editor":
            self._handle_editor_keyup(event)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 2, 3):
            self._handle_click(event.pos, event.button)
        elif event.type == pygame.MOUSEBUTTONUP and event.button in (1, 2, 3):
            if self.dragging_window and self.drag_window is not None and self.drag_outline_rect is not None:
                self.drag_window["rect"] = self.drag_outline_rect.copy()
                self.drag_window["normal_rect"] = self.drag_outline_rect.copy()
            if self.active_window and self.active_window.get("kind") == "editor":
                self._handle_editor_release(event.pos, event.button)
            self.dragging_window = False
            self.drag_window = None
            self.drag_outline_rect = None
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging_window and self.drag_window is not None:
                rect = self.drag_window["rect"]
                self.drag_outline_rect = pygame.Rect(
                    event.pos[0] - self.drag_offset[0],
                    event.pos[1] - self.drag_offset[1],
                    rect.w,
                    rect.h,
                )
            elif self.active_window and self.active_window.get("kind") == "editor":
                self._handle_editor_motion(event.pos, event.rel, event.buttons)
        elif event.type == pygame.MOUSEWHEEL and self.active_window and self.active_window.get("kind") == "editor":
            self._handle_editor_wheel(event.y)

    def _handle_terminal_key(self, event):
        terminal = self.active_window
        if event.key == pygame.K_RETURN:
            self._execute_terminal_command(terminal["input"])
        elif event.key == pygame.K_BACKSPACE:
            terminal["input"] = terminal["input"][:-1]
        elif event.key == pygame.K_TAB:
            if terminal.get("custom_maps"):
                terminal["input"] = f'load custom {terminal["custom_maps"][0]}'
        elif event.unicode and event.unicode.isprintable():
            if len(terminal["input"]) < 48:
                terminal["input"] += event.unicode

    def _handle_editor_key(self, event):
        editor = self.active_window["editor"]
        if editor.get("name_editing"):
            if event.key == pygame.K_RETURN:
                self._editor_save_current()
                editor["name_editing"] = False
            elif event.key == pygame.K_BACKSPACE:
                editor["map_name"] = editor["map_name"][:-1]
            elif event.unicode and event.unicode.isprintable() and len(editor["map_name"]) < 32:
                editor["map_name"] += event.unicode
            return
        if editor.get("page") == "new":
            field = editor.get("new_focus", "width")
            if event.key == pygame.K_TAB:
                order = ["width", "height", "layers"]
                editor["new_focus"] = order[(order.index(field) + 1) % len(order)]
                editor["new_replace_on_type"] = True
                return
            if event.key == pygame.K_RETURN:
                self._editor_apply_dimensions(editor)
                return
            target_key = f"{editor.get('new_focus', 'width')}_input"
            if event.key == pygame.K_BACKSPACE:
                editor[target_key] = editor.get(target_key, "")[:-1]
                editor["new_replace_on_type"] = False
            elif event.unicode and event.unicode.isdigit():
                current_value = editor.get(target_key, "")
                if editor.get("new_replace_on_type", False) or len(current_value) >= 2:
                    editor[target_key] = event.unicode
                else:
                    editor[target_key] = current_value + event.unicode
                editor["new_replace_on_type"] = False
            return
        if editor.get("page") != "editor":
            if event.key == pygame.K_F2:
                self._editor_set_page(editor, "open")
            elif event.key == pygame.K_F3:
                self._editor_set_page(editor, "new")
            return
        if event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._editor_save_current()
            return
        if event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._editor_undo()
            return
        if event.key == pygame.K_y and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self._editor_redo()
            return
        if event.key == pygame.K_n and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            self.active_window["editor"] = self._new_editor_state()
            return
        if event.key == pygame.K_TAB:
            editor["active_layer"] = (editor["active_layer"] + 1) % len(editor["layers"])
            return
        if event.key == pygame.K_LEFTBRACKET:
            editor["brush_height"] = max(1, editor["brush_height"] - 1)
            editor["selected_height"] = editor["brush_height"]
            return
        if event.key == pygame.K_RIGHTBRACKET:
            editor["brush_height"] = min(5, editor["brush_height"] + 1)
            editor["selected_height"] = editor["brush_height"]
            return
        if event.key == pygame.K_q:
            self._editor_cycle_tile(-1)
            return
        if event.key == pygame.K_e:
            self._editor_cycle_tile(1)
            return
        if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6):
            editor["active_tool"] = {
                pygame.K_1: "paint",
                pygame.K_2: "erase",
                pygame.K_3: "select",
                pygame.K_4: "move",
                pygame.K_5: "rotate",
                pygame.K_6: "resize",
            }[event.key]
            editor["status"] = f'Tool: {editor["active_tool"]}'
            return
        if event.key == pygame.K_F1:
            self._editor_set_page(editor, "home")
            return
        if event.key == pygame.K_F2:
            self._editor_set_page(editor, "open")
            return
        if event.key == pygame.K_F3:
            self._editor_set_page(editor, "new")
            return
        if event.key == pygame.K_F4:
            self._editor_cycle_view(editor)
            return
        if editor.get("inspector_focus"):
            if event.key == pygame.K_RETURN:
                key = editor["inspector_focus"]
                value = editor.get("inspector_buffer", "")
                self._editor_push_undo(editor)
                self._editor_apply_inspector_value(editor, key, value)
                editor["inspector_focus"] = None
                editor["inspector_buffer"] = ""
                return
            if event.key == pygame.K_ESCAPE:
                editor["inspector_focus"] = None
                editor["inspector_buffer"] = ""
                return
            if event.key == pygame.K_BACKSPACE:
                editor["inspector_buffer"] = editor.get("inspector_buffer", "")[:-1]
                return
            if event.unicode and event.unicode in "0123456789.-":
                editor["inspector_buffer"] = editor.get("inspector_buffer", "") + event.unicode
                return
        key_name = pygame.key.name(event.key)
        if key_name in {"w", "a", "s", "d", "up", "down", "left", "right"}:
            if editor.get("view_mode") == "3d":
                editor.setdefault("pressed_keys", set()).add(key_name)
            elif editor.get("view_mode") == "2d" and key_name in {"w", "a", "s", "d"}:
                if editor.get("active_tool") in {"move", "rotate", "resize"} and editor.get("selected_cell") is not None:
                    pass
                else:
                    editor.setdefault("pressed_keys", set()).add(key_name)
                    return
            elif editor.get("active_tool") == "move" and editor.get("selected_cell") is not None:
                self._editor_push_undo(editor)
                if key_name == "a":
                    self._editor_move_selected_along(editor, "x", -1)
                elif key_name == "d":
                    self._editor_move_selected_along(editor, "x", 1)
                elif key_name == "w":
                    self._editor_move_selected_along(editor, "y", -1)
                elif key_name == "s":
                    self._editor_move_selected_along(editor, "y", 1)
            elif editor.get("active_tool") == "rotate" and editor.get("selected_cell") is not None:
                self._editor_push_undo(editor)
                if key_name in {"a", "left"}:
                    self._editor_rotate_selected(editor, "z", -15)
                elif key_name in {"d", "right"}:
                    self._editor_rotate_selected(editor, "z", 15)
                elif key_name == "w":
                    self._editor_rotate_selected(editor, "x", 15)
                elif key_name == "s":
                    self._editor_rotate_selected(editor, "x", -15)
            elif editor.get("active_tool") == "resize" and editor.get("selected_cell") is not None:
                self._editor_push_undo(editor)
                if key_name == "w":
                    self._editor_adjust_selected_height(editor, 0.1)
                elif key_name == "s":
                    self._editor_adjust_selected_height(editor, -0.1)
                elif key_name == "a":
                    self._editor_scale_selected(editor, "x", -0.05)
                elif key_name == "d":
                    self._editor_scale_selected(editor, "x", 0.05)

    def _handle_editor_keyup(self, event):
        editor = self.active_window["editor"]
        key_name = pygame.key.name(event.key)
        editor.setdefault("pressed_keys", set()).discard(key_name)

    def _handle_editor_motion(self, pos, rel, buttons):
        editor = self.active_window["editor"]
        if editor.get("page") != "editor":
            return
        if editor.get("view_mode") == "2d":
            if editor.get("panning_2d"):
                editor["pan_x"] += rel[0]
                editor["pan_y"] += rel[1]
            elif editor.get("painting") and (buttons[0] or buttons[2]):
                for (cx, cy), cell_rect in editor.get("cell_rects", {}).items():
                    if cell_rect.collidepoint(pos):
                        self._editor_apply_paint(cx, cy, 1 if buttons[0] else 3)
                        break
        elif editor.get("gizmo_drag"):
            mode = editor["gizmo_drag"]["mode"]
            axis = editor["gizmo_drag"]["axis"]
            changed = False
            if mode == "move":
                if axis == "x":
                    changed = self._editor_nudge_selected_offset(editor, "x", rel[0] * 0.01)
                elif axis == "y":
                    changed = self._editor_nudge_selected_offset(editor, "y", rel[0] * 0.01)
                else:
                    changed = self._editor_nudge_selected_offset(editor, "z", -rel[1] * 0.01)
            elif mode == "rotate":
                changed = self._editor_rotate_selected(editor, axis, rel[0] * 1.4)
            elif mode == "resize":
                if axis == "z":
                    changed = self._editor_adjust_selected_height(editor, -rel[1] * 0.25)
                else:
                    changed = self._editor_scale_selected(editor, axis, rel[0] * 0.02)
            if changed:
                editor["dirty"] = True
        elif editor.get("orbiting_3d"):
            editor["camera_yaw"] += rel[0] * 0.012
            editor["camera_pitch"] = max(math.radians(-80.0), min(math.radians(80.0), editor["camera_pitch"] - rel[1] * 0.008))
            focus = editor.get("orbit_focus")
            if focus is not None:
                fx, fy, fz = focus
                dist_x = editor["camera_x"] - fx
                dist_y = editor["camera_y"] - fy
                dist_z = editor["camera_z"] - fz
                orbit_dist = max(1.8, math.sqrt(dist_x * dist_x + dist_y * dist_y + dist_z * dist_z))
                dir_x = -math.sin(editor["camera_yaw"]) * math.cos(editor["camera_pitch"])
                dir_y = math.cos(editor["camera_yaw"]) * math.cos(editor["camera_pitch"])
                dir_z = math.sin(editor["camera_pitch"])
                editor["camera_x"] = fx - dir_x * orbit_dist
                editor["camera_y"] = fy - dir_y * orbit_dist
                editor["camera_z"] = fz - dir_z * orbit_dist

    def _handle_editor_release(self, _pos, button):
        editor = self.active_window["editor"]
        if button in (1, 3):
            editor["painting"] = False
            editor["panning_2d"] = False
            editor["gizmo_drag"] = None
        if button == 2:
            editor["orbiting_3d"] = False

    def _handle_editor_wheel(self, delta):
        editor = self.active_window["editor"]
        if editor.get("page") != "editor":
            return
        mouse_pos = pygame.mouse.get_pos()
        object_list_rect = editor.get("object_list_rect")
        if object_list_rect and object_list_rect.collidepoint(mouse_pos):
            total = len(self._editor_object_entries(editor))
            visible = 8
            max_scroll = max(0, total - visible)
            editor["object_scroll"] = max(0, min(max_scroll, editor.get("object_scroll", 0) - delta))
            return
        palette_rect = editor.get("palette_box_rect")
        if palette_rect and palette_rect.collidepoint(mouse_pos):
            total = len(EDITOR_TILE_OPTIONS)
            visible = max(1, (palette_rect.h - 44) // 36)
            max_scroll = max(0, total - visible)
            editor["palette_scroll"] = max(0, min(max_scroll, editor.get("palette_scroll", 0) - delta))
            return
        layers_rect = editor.get("layers_box_rect")
        if layers_rect and layers_rect.collidepoint(mouse_pos):
            total = len(editor["layers"])
            visible = max(1, (layers_rect.h - 8) // 30)
            max_scroll = max(0, total - visible)
            editor["layer_scroll"] = max(0, min(max_scroll, editor.get("layer_scroll", 0) - delta))
            return
        inspector_rect = editor.get("inspector_box_rect")
        if inspector_rect and inspector_rect.collidepoint(mouse_pos):
            max_scroll = max(0, int(editor.get("inspector_scroll_max", 0)))
            editor["inspector_scroll"] = max(0, min(max_scroll, editor.get("inspector_scroll", 0) - (delta * 24)))
            return
        if editor.get("view_mode") == "2d":
            old_zoom = editor.get("zoom", 1.0)
            new_zoom = max(0.4, min(4.5, old_zoom * (1.12 if delta > 0 else 1 / 1.12)))
            editor["zoom"] = new_zoom
        else:
            step = max(0.5, max(editor["width"], editor["height"]) * 0.08)
            dir_x = -math.sin(editor["camera_yaw"]) * math.cos(editor["camera_pitch"])
            dir_y = math.cos(editor["camera_yaw"]) * math.cos(editor["camera_pitch"])
            dir_z = math.sin(editor["camera_pitch"])
            editor["camera_x"] += dir_x * step * delta
            editor["camera_y"] += dir_y * step * delta
            editor["camera_z"] += dir_z * step * delta

    def _handle_click(self, pos, button=1):
        clicked_window = self._window_at_pos(pos)
        if clicked_window is not None:
            self._focus_window(clicked_window)
            rect = clicked_window["rect"]
            drag_rect = pygame.Rect(rect.x + 8, rect.y + 8, rect.w - 56, 24)
            close_rect = pygame.Rect(rect.right - 40, rect.y + 8, 28, 24)
            max_rect = pygame.Rect(rect.right - 72, rect.y + 8, 28, 24)
            min_rect = pygame.Rect(rect.right - 104, rect.y + 8, 28, 24)
            if close_rect.collidepoint(pos):
                self._clear_window()
                return
            if button == 1 and max_rect.collidepoint(pos):
                self._toggle_active_window_maximize()
                return
            if button == 1 and min_rect.collidepoint(pos):
                self._minimize_active_window()
                return
            if button == 1 and drag_rect.collidepoint(pos):
                self.dragging_window = True
                self.drag_window = clicked_window
                self.drag_offset = (pos[0] - rect.x, pos[1] - rect.y)
                self.drag_outline_rect = rect.copy()
                return
            if self._handle_window_click(pos, button):
                return
            return

        start_rect = self._start_button_rect()
        if button == 1 and start_rect.collidepoint(pos):
            self.start_menu_open = not self.start_menu_open
            return

        task_rect = pygame.Rect(128, self.screen.get_size()[1] - 30, 168, 24)
        if button == 1 and task_rect.collidepoint(pos) and self.minimized_windows:
            restored = self.minimized_windows.pop()
            self.windows.append(restored)
            self._focus_window(restored)
            return

        if self.start_menu_open:
            if button == 1 and self._handle_start_menu_click(pos):
                return
            self.start_menu_open = False

        for icon in self.desktop_icons:
            if button == 1 and icon.rect and icon.rect.collidepoint(pos):
                if icon.enabled:
                    self.handle_action(icon.key)
                else:
                    self._show_notice(f"{icon.label} is locked")
                return

    def _handle_start_menu_click(self, pos):
        menu_rect = self._start_menu_rect()
        if not menu_rect.collidepoint(pos):
            return False
        x = menu_rect.x + 72
        y = menu_rect.y + 52
        h = 36
        for item in self.start_items:
            row = pygame.Rect(x, y, menu_rect.w - 84, h)
            if row.collidepoint(pos):
                self.start_menu_open = False
                if item.enabled:
                    self.handle_action(item.action)
                else:
                    self._show_notice(f"{item.label} is locked")
                return True
            y += h + 4
        return True

    def _handle_window_click(self, pos, button=1):
        kind = self.active_window["kind"]
        if kind == "new_game":
            return self._handle_new_game_click(pos)
        if kind == "settings":
            return self._handle_settings_click(pos)
        if kind == "gallery":
            return self._handle_gallery_click(pos)
        if kind == "editor":
            return self._handle_editor_click(pos, button)
        return False

    def _handle_new_game_click(self, pos):
        rect = self.active_window["rect"]
        if self.active_window["stage"] == "slots":
            card_y = rect.y + 180
            card_w = 170
            gap = 24
            start_x = rect.x + 84
            for slot in (1, 2, 3):
                card_rect = pygame.Rect(start_x + (slot - 1) * (card_w + gap), card_y, card_w, 180)
                if card_rect.collidepoint(pos):
                    save_settings({"selected_save_slot": slot, "new_game_slot_prompt_seen": True})
                    self.active_window["stage"] = "cases"
                    return True
        else:
            buttons = [
                ("Tutorial Case", lambda: self._run_level(start_testing_maze_opengl)),
                ("Secret Case", lambda: self._run_level(start_secret_maze_opengl)),
                ("City Case", lambda: self._run_level(start_city_maze_opengl)),
            ]
            y = rect.y + 170
            for label, callback in buttons:
                button_rect = pygame.Rect(rect.x + 70, y, rect.w - 140, 52)
                if button_rect.collidepoint(pos):
                    callback()
                    return True
                y += 68
        return False

    def _handle_settings_click(self, pos):
        rect = self.active_window["rect"]
        sections = ("graphics", "audio", "game")
        x = rect.x + 24
        y = rect.y + 88
        for section in sections:
            tab_rect = pygame.Rect(x, y, 170, 42)
            if tab_rect.collidepoint(pos):
                self.active_window["section"] = section
                return True
            y += 52

        rows = self._settings_sections()[self.active_window["section"]]
        row_y = rect.y + 96
        for _label, _value, command in rows:
            minus_rect = pygame.Rect(rect.x + rect.w - 170, row_y, 44, 34)
            plus_rect = pygame.Rect(rect.x + rect.w - 116, row_y, 44, 34)
            whole_rect = pygame.Rect(rect.x + 240, row_y - 4, rect.w - 280, 42)
            if command in {"toggle_fullscreen", "toggle_music", "toggle_fps", "toggle_wheel", "reset_slot"} and whole_rect.collidepoint(pos):
                self._settings_change(command)
                return True
            if command in {
                "toggle_flash",
                "toggle_particles",
                "toggle_bullets",
                "toggle_screen_fx",
                "toggle_culling",
                "toggle_debug",
                "reset_defaults",
            } and whole_rect.collidepoint(pos):
                self._settings_change(command)
                return True
            if minus_rect.collidepoint(pos):
                self._settings_change(command, -1)
                return True
            if plus_rect.collidepoint(pos):
                self._settings_change(command, 1)
                return True
            row_y += 56
        return False

    def _handle_gallery_click(self, pos):
        rect = self.active_window["rect"]
        x = rect.x + 56
        y = rect.y + 120
        for label, key in self.active_window["items"]:
            item_rect = pygame.Rect(x, y, rect.w - 112, 48)
            if item_rect.collidepoint(pos):
                if key == "death":
                    self.open_image_viewer(label, "death")
                elif key == "easteregg":
                    self.open_image_viewer(label, "easteregg")
                elif key == "info":
                    text = (Path(get_exe_dir()) / "data" / "app" / "story" / "info.txt").read_text(encoding="utf-8")
                    self.open_text_viewer("INFO.TXT", text)
                elif key == "incident":
                    text = (Path(get_exe_dir()) / "data" / "app" / "story" / "12340.txt").read_text(encoding="utf-8")
                    self.open_text_viewer("12340.TXT", text)
                return True
            y += 58
        return False

    def _handle_editor_click(self, pos, button=1):
        editor = self.active_window["editor"]
        for page, item_rect in editor.get("page_rects", []):
            if item_rect.collidepoint(pos):
                self._editor_set_page(editor, page)
                return True
        for action, item_rect in editor.get("menu_item_rects", []):
            if item_rect.collidepoint(pos):
                self._editor_menu_action(action)
                return True
        for menu_name, item_rect in editor.get("menu_rects", []):
            if item_rect.collidepoint(pos):
                editor["menu_open"] = menu_name
                return True

        if editor.get("page") == "home":
            for action, item_rect in editor.get("sidebar_rects", []):
                if item_rect.collidepoint(pos):
                    if action == "open":
                        self._editor_set_page(editor, "open")
                    elif action == "new":
                        self._editor_set_page(editor, "new")
                    return True
            return False

        if editor.get("page") == "open":
            for builtin_name, item_rect in editor.get("builtin_rects", []):
                if item_rect.collidepoint(pos):
                    builtin_maps = {
                        "Tutorial": TUTOR_MAP,
                        "Testing": TESTING_MAP,
                        "Secret": SECRET_MAP,
                        "City": CITY_MAP,
                    }
                    self._editor_load_builtin(builtin_name, builtin_maps[builtin_name])
                    return True
            for index, item_rect in editor.get("load_rects", []):
                if item_rect.collidepoint(pos):
                    self._editor_open_selected_load(index)
                    return True
            return False

        if editor.get("page") == "new":
            for field, rect in editor.get("new_input_rects", []):
                if rect.collidepoint(pos):
                    if field == "create":
                        self._editor_apply_dimensions(editor)
                    else:
                        editor["new_focus"] = field.replace("_input", "")
                        editor["new_replace_on_type"] = True
                    return True
            return False

        for action, item_rect in editor.get("toolbar_rects", []):
            if item_rect.collidepoint(pos):
                if action == "save":
                    self._editor_save_current()
                elif action == "run":
                    self._editor_run_current()
                elif action == "name":
                    editor["name_editing"] = True
                elif action == "view":
                    self._editor_cycle_view(editor)
                elif action in {"paint", "erase", "select", "move", "rotate", "resize"}:
                    editor["active_tool"] = action
                    editor["status"] = f"Tool: {action}"
                elif action == "layer_add":
                    if len(editor["layers"]) < EDITOR_MAX_LAYERS:
                        self._editor_push_undo(editor)
                        editor["layers"].append(self._make_blank_layers(editor["width"], editor["height"], 1)[0])
                        editor["active_layer"] = len(editor["layers"]) - 1
                        editor["dirty"] = True
                elif action == "layer_remove":
                    if len(editor["layers"]) > 1 and editor["active_layer"] > 0:
                        self._editor_push_undo(editor)
                        editor["layers"].pop(editor["active_layer"])
                        editor["active_layer"] = max(0, min(editor["active_layer"], len(editor["layers"]) - 1))
                        editor["dirty"] = True
                return True

        for layer_idx, key, flag_rect in editor.get("layer_flag_rects", []):
            if flag_rect.collidepoint(pos):
                return self._editor_toggle_layer_flag(editor, layer_idx, key)

        for layer_idx, layer_rect in editor.get("layer_rects", []):
            if layer_rect.collidepoint(pos):
                editor["active_layer"] = layer_idx
                return True

        for tile_name, palette_rect in editor.get("palette_rects", []):
            if palette_rect.collidepoint(pos):
                editor["selected_tile"] = tile_name
                editor["status"] = f"Selected {tile_name}."
                return True

        if editor.get("view_mode") == "2d":
            if editor.get("active_tool") == "select":
                for (cx, cy), cell_rect in editor.get("cell_rects", {}).items():
                    if cell_rect.collidepoint(pos):
                        return self._editor_select_object(editor, editor["active_layer"], cx, cy)
            if editor.get("active_tool") == "move":
                for (cx, cy), cell_rect in editor.get("cell_rects", {}).items():
                    if cell_rect.collidepoint(pos):
                        self._editor_push_undo(editor)
                        moved = self._editor_move_selected_to(editor, editor["active_layer"], cx, cy)
                        if not moved and editor["layers"][editor["active_layer"]][cy][cx]["tile"] != "empty":
                            return self._editor_select_object(editor, editor["active_layer"], cx, cy)
                        return moved
            if editor.get("active_tool") == "rotate":
                for (cx, cy), cell_rect in editor.get("cell_rects", {}).items():
                    if cell_rect.collidepoint(pos):
                        if self._editor_select_object(editor, editor["active_layer"], cx, cy):
                            self._editor_push_undo(editor)
                            return self._editor_rotate_selected(editor, "z", -90 if button == 3 else 90)
            if editor.get("active_tool") == "resize":
                for (cx, cy), cell_rect in editor.get("cell_rects", {}).items():
                    if cell_rect.collidepoint(pos):
                        if self._editor_select_object(editor, editor["active_layer"], cx, cy):
                            self._editor_push_undo(editor)
                            return self._editor_adjust_selected_height(editor, -0.1 if button == 3 else 0.1)
            for (cx, cy), cell_rect in editor.get("cell_rects", {}).items():
                if cell_rect.collidepoint(pos):
                    self._editor_apply_paint(cx, cy, button)
                    editor["painting"] = button in (1, 3)
                    return True
            canvas_rect = editor.get("canvas_rect")
            if button == 2 and canvas_rect and canvas_rect.collidepoint(pos):
                editor["panning_2d"] = True
                return True
        else:
            for hit in editor.get("gizmo_hits", []):
                if hit["rect"].collidepoint(pos):
                    editor["gizmo_drag"] = {"mode": hit["mode"], "axis": hit["axis"]}
                    return True
            for candidate in editor.get("pick_candidates", []):
                if candidate["rect"].collidepoint(pos):
                    return self._editor_select_object(editor, candidate["layer"], candidate["cell"][0], candidate["cell"][1])
            canvas_rect = editor.get("canvas_rect")
            if button == 2 and canvas_rect and canvas_rect.collidepoint(pos):
                editor["orbiting_3d"] = True
                return True
        for layer_idx, cell_x, cell_y, row_rect in editor.get("object_rects", []):
            if row_rect.collidepoint(pos):
                object_id = f"{layer_idx}:{cell_x}:{cell_y}"
                now = pygame.time.get_ticks()
                chosen = self._editor_select_object(editor, layer_idx, cell_x, cell_y)
                if chosen and editor.get("last_object_click", {}).get("id") == object_id and now - editor.get("last_object_click", {}).get("tick", 0) < 350:
                    self._editor_focus_camera_on_selected(editor)
                editor["last_object_click"] = {"id": object_id, "tick": now}
                return chosen
        for key, value_rect in editor.get("inspector_value_rects", []):
            if value_rect.collidepoint(pos):
                editor["inspector_focus"] = key
                editor["inspector_buffer"] = self._editor_inspector_values(editor).get(key, "")
                return True
        for action, action_rect in editor.get("inspector_rects", []):
            if action_rect.collidepoint(pos):
                self._editor_push_undo(editor)
                if action == "move_x-":
                    return self._editor_move_selected_along(editor, "x", -1)
                if action == "move_x+":
                    return self._editor_move_selected_along(editor, "x", 1)
                if action == "move_y-":
                    return self._editor_move_selected_along(editor, "y", -1)
                if action == "move_y+":
                    return self._editor_move_selected_along(editor, "y", 1)
                if action == "move_z-":
                    return self._editor_move_selected_along(editor, "z", -1)
                if action == "move_z+":
                    return self._editor_move_selected_along(editor, "z", 1)
                if action == "scale_x-":
                    return self._editor_scale_selected(editor, "x", -0.05)
                if action == "scale_x+":
                    return self._editor_scale_selected(editor, "x", 0.05)
                if action == "scale_y-":
                    return self._editor_scale_selected(editor, "y", -0.05)
                if action == "scale_y+":
                    return self._editor_scale_selected(editor, "y", 0.05)
                if action == "scale_z-":
                    return self._editor_scale_selected(editor, "z", -0.05)
                if action == "scale_z+":
                    return self._editor_scale_selected(editor, "z", 0.05)
                if action == "rot_x-":
                    return self._editor_rotate_selected(editor, "x", -15)
                if action == "rot_x+":
                    return self._editor_rotate_selected(editor, "x", 15)
                if action == "rot_y-":
                    return self._editor_rotate_selected(editor, "y", -15)
                if action == "rot_y+":
                    return self._editor_rotate_selected(editor, "y", 15)
                if action == "rot_z-":
                    return self._editor_rotate_selected(editor, "z", -15)
                if action == "rot_z+":
                    return self._editor_rotate_selected(editor, "z", 15)
                if action == "height-":
                    return self._editor_adjust_selected_height(editor, -0.1)
                if action == "height+":
                    return self._editor_adjust_selected_height(editor, 0.1)
                if action == "toggle_collision":
                    return self._editor_toggle_selected_flag(editor, "collidable")
                if action == "toggle_floor":
                    return self._editor_toggle_selected_flag(editor, "has_floor")
                if action == "toggle_ceiling":
                    return self._editor_toggle_selected_flag(editor, "has_ceiling")
        return False

    def _start_button_rect(self):
        sw, sh = self.screen.get_size()
        return pygame.Rect(8, sh - 30, 112, 24)

    def _start_menu_rect(self):
        sw, sh = self.screen.get_size()
        return pygame.Rect(8, sh - 450, 320, 416)

    def draw(self):
        sw, sh = self.screen.get_size()
        self.screen.fill(DESKTOP_BG)
        if self.wallpaper is not None:
            self.screen.blit(self.wallpaper, (0, 0))

        self._draw_top_bar(sw)
        self._draw_desktop_text(sw, sh)
        self._draw_desktop_icons(sw, sh)
        self._draw_taskbar(sw, sh)

        if self.start_menu_open:
            self._draw_start_menu()
        for window in self.windows:
            if window["kind"] == "intro" and self.intro_frames:
                now = pygame.time.get_ticks()
                if now - window.get("intro_tick", now) >= 85:
                    window["intro_tick"] = now
                    window["intro_frame"] = (window.get("intro_frame", 0) + 1) % len(self.intro_frames)
            self._draw_window(window)
        if self.drag_outline_rect is not None:
            pygame.draw.rect(self.screen, WHITE, self.drag_outline_rect, 1)
            pygame.draw.rect(self.screen, PANEL_BORDER, self.drag_outline_rect.inflate(2, 2), 1)
        if self.notification and pygame.time.get_ticks() < self.notification_until:
            self._draw_notification(sw, sh)
        if load_settings().get("show_fps"):
            self._draw_text(self.fonts["small"], f"FPS {int(self.clock.get_fps())}", WHITE, (sw - 90, 8))

        pygame.display.flip()

    def _draw_top_bar(self, sw):
        pygame.draw.rect(self.screen, TITLE_BLUE, (0, 0, sw, 28))
        self.screen.blit(self._scaled_icon("exe", (16, 16)), (8, 6))
        self._draw_text(self.fonts["small"], "SECURE_SYSTEM.EXE", WHITE, (30, 6))

    def _draw_taskbar(self, sw, sh):
        pygame.draw.rect(self.screen, DESKTOP_DARK, (0, sh - 34, sw, 34))
        pygame.draw.rect(self.screen, PANEL_BORDER, (0, sh - 34, sw, 34), 1)
        start_rect = self._start_button_rect()
        start_image = self.assets.get("start")
        if start_image is not None:
            scaled = pygame.transform.scale(start_image, (start_rect.w, start_rect.h))
            self.screen.blit(scaled, start_rect)
        else:
            pygame.draw.rect(self.screen, PANEL_BG, start_rect)
            pygame.draw.rect(self.screen, PANEL_BORDER, start_rect, 2)
            self._draw_text(self.fonts["button"], "START", TEXT_COLOR, (start_rect.x + 18, start_rect.y + 2))

        task_rect = pygame.Rect(128, sh - 30, 168, 24)
        active_task = self.active_window if self.active_window is not None else (self.minimized_windows[-1] if self.minimized_windows else None)
        self._draw_embossed_box(task_rect, PANEL_BG, sunken=active_task is not None)
        task_text = " " if active_task is None else active_task["title"][:18]
        self._draw_text(self.fonts["tiny"], task_text, TEXT_COLOR, (task_rect.x + 8, task_rect.y + 6))

        version_text = "Version 0.2.5-alpha"
        self._draw_text(self.fonts["small"], version_text, TEXT_MUTED, (sw - 280, sh - 27))

        now = datetime.now()
        clock_text = now.strftime("%Y %m %d   %H:%M")
        clock_rect = pygame.Rect(sw - 154, sh - 30, 144, 24)
        pygame.draw.rect(self.screen, PANEL_BG, clock_rect)
        pygame.draw.rect(self.screen, PANEL_BORDER, clock_rect, 2)
        self._draw_text(self.fonts["tiny"], clock_text, TEXT_COLOR, (clock_rect.x + 10, clock_rect.y + 6))

    def _draw_desktop_text(self, sw, sh):
        self._draw_centered(self.fonts["title"], "Abebe Protocol", TEXT_COLOR, (sw // 2, max(110, sh // 2 - 170)))
        self._draw_centered(self.fonts["small"], "Made by Mr. Banandee", TEXT_MUTED, (sw // 2, max(146, sh // 2 - 120)))
        self._draw_centered(self.fonts["body"], "AUTHORIZED ACCESS ONLY", TEXT_MUTED, (sw // 2, max(172, sh // 2 - 84)))

    def _draw_desktop_icons(self, sw, sh):
        center_x = sw // 2
        y = max(250, sh // 2 - 10)
        spacing = 138
        start_x = center_x - ((len(self.desktop_icons) - 1) * spacing) // 2
        for index, icon in enumerate(self.desktop_icons):
            x = start_x + index * spacing
            image = self._scaled_icon(icon.image_key)
            icon_rect = pygame.Rect(x - 32, y - 32, 64, 64)
            self.screen.blit(image, icon_rect)
            label_color = WHITE if icon.enabled else (181, 181, 181)
            text_surface = self.fonts["desktop"].render(icon.label, True, label_color)
            text_rect = text_surface.get_rect(center=(x, y + 58))
            shadow = self.fonts["desktop"].render(icon.label, True, BLACK)
            self.screen.blit(shadow, shadow.get_rect(center=(x + 1, y + 59)))
            self.screen.blit(text_surface, text_rect)
            icon.rect = pygame.Rect(x - 54, y - 36, 108, 104)

    def _draw_start_menu(self):
        rect = self._start_menu_rect()
        self._draw_window_panel(rect)
        sidebar = pygame.Rect(rect.x, rect.y, 62, rect.h)
        pygame.draw.rect(self.screen, TITLE_BLUE, sidebar)
        self._draw_text(self.fonts["button"], "PUSK", WHITE, (sidebar.x + 10, sidebar.bottom - 34))
        self._draw_text(self.fonts["button"], "Programs", TEXT_COLOR, (rect.x + 78, rect.y + 18))

        x = rect.x + 72
        y = rect.y + 52
        for item in self.start_items:
            row = pygame.Rect(x, y, rect.w - 84, 36)
            self._draw_embossed_box(row, PANEL_BG if item.enabled else DESKTOP_DARK, sunken=not item.enabled)
            icon_key = self._icon_for_action(item.action)
            icon = self._scaled_icon(icon_key, (18, 18))
            self.screen.blit(icon, (row.x + 8, row.y + 9))
            self._draw_text(
                self.fonts["small"],
                item.label,
                TEXT_COLOR if item.enabled else TEXT_MUTED,
                (row.x + 34, row.y + 9),
            )
            y += 40

    def _draw_window(self, window):
        rect = window["rect"]
        self._draw_window_panel(rect)
        title_bar = pygame.Rect(rect.x + 8, rect.y + 8, rect.w - 16, 24)
        pygame.draw.rect(self.screen, TITLE_BLUE, title_bar)
        icon_key = self.window_icons.get(window["kind"])
        if icon_key is not None:
            self.screen.blit(self._scaled_icon(icon_key, (16, 16)), (title_bar.x + 6, title_bar.y + 4))
            title_x = title_bar.x + 28
        else:
            title_x = title_bar.x + 8
        self._draw_text(self.fonts["window_title"], window["title"], WHITE, (title_x, title_bar.y + 3))
        max_rect = pygame.Rect(rect.right - 72, rect.y + 8, 28, 24)
        min_rect = pygame.Rect(rect.right - 104, rect.y + 8, 28, 24)
        max_image = self.assets.get("max_idle")
        min_image = self.assets.get("min_idle")
        close_rect = pygame.Rect(rect.right - 40, rect.y + 8, 28, 24)
        if min_image is not None:
            self.screen.blit(pygame.transform.scale(min_image, (min_rect.w, min_rect.h)), min_rect)
        else:
            self._draw_embossed_box(min_rect, PANEL_BG)
        if max_image is not None:
            self.screen.blit(pygame.transform.scale(max_image, (max_rect.w, max_rect.h)), max_rect)
        else:
            self._draw_embossed_box(max_rect, PANEL_BG)
        close_image = self.assets.get("close_idle")
        if close_image is not None:
            self.screen.blit(pygame.transform.scale(close_image, (close_rect.w, close_rect.h)), close_rect)
        else:
            pygame.draw.rect(self.screen, PANEL_BG, close_rect)
            pygame.draw.rect(self.screen, PANEL_BORDER, close_rect, 2)
            self._draw_text(self.fonts["button"], "X", TEXT_COLOR, (close_rect.x + 8, close_rect.y + 1))

        if window["kind"] == "new_game":
            self._draw_new_game(window)
        elif window["kind"] == "settings":
            self._draw_settings(window)
        elif window["kind"] == "intro":
            self._draw_intro(window)
        elif window["kind"] == "terminal":
            self._draw_terminal(window)
        elif window["kind"] == "text_viewer":
            self._draw_text_viewer(window)
        elif window["kind"] == "image_viewer":
            self._draw_image_viewer(window)
        elif window["kind"] == "gallery":
            self._draw_gallery(window)
        elif window["kind"] == "editor":
            self._draw_editor(window)

    def _draw_window_panel(self, rect):
        bg_image = self.assets.get("window_bg")
        if bg_image is not None:
            scaled = pygame.transform.scale(bg_image, (rect.w, rect.h))
            self.screen.blit(scaled, rect)
        else:
            pygame.draw.rect(self.screen, PANEL_BG, rect)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, 2)

    def _draw_embossed_box(self, rect, fill, sunken=False):
        pygame.draw.rect(self.screen, fill, rect)
        light = (244, 244, 244)
        dark = (128, 128, 128)
        tl = dark if sunken else light
        br = light if sunken else dark
        pygame.draw.line(self.screen, tl, (rect.x, rect.bottom - 1), (rect.x, rect.y))
        pygame.draw.line(self.screen, tl, (rect.x, rect.y), (rect.right - 1, rect.y))
        pygame.draw.line(self.screen, br, (rect.right - 1, rect.y), (rect.right - 1, rect.bottom - 1))
        pygame.draw.line(self.screen, br, (rect.right - 1, rect.bottom - 1), (rect.x, rect.bottom - 1))

    def _draw_button(self, rect, label, active=False):
        self._draw_embossed_box(rect, PANEL_ACTIVE if active else PANEL_BG, sunken=active)
        self._draw_centered(self.fonts["small"], label, TEXT_COLOR, rect.center)

    def _draw_toolbar_button(self, rect, action, label, active=False):
        sprite_name = {
            "save": "save",
            "paint": "paint",
            "erase": "erase",
            "select": "cursor",
            "move": "move",
            "rotate": "rotate",
            "resize": "scale",
        }.get(action)
        if not sprite_name:
            self._draw_button(rect, label, active=active)
            return
        mouse_pos = pygame.mouse.get_pos()
        mouse_down = bool(pygame.mouse.get_pressed()[0])
        hovered = rect.collidepoint(mouse_pos)
        if active or (hovered and mouse_down):
            state = "3"
        elif hovered:
            state = "2"
        else:
            state = "1"
        sprite = self.assets.get(f"brerder_{sprite_name}_{state}")
        if sprite is None:
            self._draw_button(rect, label, active=active)
            return
        scaled = pygame.transform.scale(sprite, (rect.w, rect.h))
        self.screen.blit(scaled, rect)

    def _icon_for_action(self, action):
        return {
            "new_game": "exe",
            "save_data": "data",
            "terminal": "folder",
            "settings": "settings",
            "intro": "mycomputer",
            "editor": "settings",
            "legacy": "exe",
            "shutdown": "exe",
        }.get(action, "data")

    def _draw_new_game(self, window):
        rect = window["rect"]
        slot = load_settings().get("selected_save_slot")
        shell = pygame.Rect(rect.x + 16, rect.y + 44, rect.w - 32, rect.h - 60)
        self._draw_embossed_box(shell, PANEL_BG)
        self._draw_text(self.fonts["body"], "CASE DIRECTORY", TEXT_COLOR, (rect.x + 40, rect.y + 56))
        if window["stage"] == "slots":
            self._draw_text(self.fonts["small"], "Select where your progress will be saved.", TEXT_MUTED, (rect.x + 40, rect.y + 96))
            card_y = rect.y + 180
            card_w = 170
            gap = 24
            start_x = rect.x + 84
            for index, num in enumerate((1, 2, 3)):
                card = pygame.Rect(start_x + index * (card_w + gap), card_y, card_w, 180)
                self._draw_embossed_box(card, DESKTOP_DARK)
                self._draw_centered(self.fonts["body"], f"SAVE {num}", TEXT_COLOR, (card.centerx, card.y + 54))
                self._draw_centered(self.fonts["small"], f"slot_{num:02}.sav", TEXT_MUTED, (card.centerx, card.y + 86))
                button = pygame.Rect(card.x + 42, card.bottom - 54, 86, 32)
                self._draw_button(button, "SELECT")
        else:
            self._draw_text(self.fonts["small"], f"Selected save slot: SAVE {slot}" if slot else "Selected save slot: NONE", TEXT_MUTED, (rect.x + 40, rect.y + 96))
            self._draw_text(self.fonts["small"], "Only a few investigations are unlocked right now.", TEXT_MUTED, (rect.x + 40, rect.y + 122))
            y = rect.y + 170
            cases = [
                ("case_0.0.0_tutorial.abebe", "case 0.0.0 // Tutorial"),
                ("case_0.0.1_archive.abebe", "case ???"),
                ("case_0.0.2_signal.abebe", "case ???"),
            ]
            for index, (filename, footer) in enumerate(cases):
                box = pygame.Rect(rect.x + 70, y, rect.w - 140, 52)
                self._draw_embossed_box(box, PANEL_ACTIVE if index == 0 else DESKTOP_DARK, sunken=index == 0)
                self._draw_text(self.fonts["small"], filename, TEXT_COLOR if index == 0 else TEXT_MUTED, (box.x + 12, box.y + 8))
                self._draw_text(self.fonts["tiny"], footer, TEXT_MUTED, (box.x + 12, box.y + 30))
                y += 68

    def _draw_settings(self, window):
        rect = window["rect"]
        shell = pygame.Rect(rect.x + 16, rect.y + 44, rect.w - 32, rect.h - 60)
        self._draw_embossed_box(shell, PANEL_BG)
        sections = ("graphics", "audio", "game")
        x = rect.x + 24
        y = rect.y + 88
        for section in sections:
            tab = pygame.Rect(x, y, 170, 42)
            active = section == window["section"]
            self._draw_embossed_box(tab, PANEL_ACTIVE if active else DESKTOP_DARK, sunken=active)
            self._draw_text(self.fonts["button"], SECTION_LABELS[section], TEXT_COLOR, (tab.x + 16, tab.y + 11))
            y += 52

        self._draw_text(self.fonts["body"], SECTION_LABELS[window["section"]], TEXT_COLOR, (rect.x + 240, rect.y + 56))
        row_y = rect.y + 96
        rows = self._settings_sections()[window["section"]]
        for label, value, _command in rows:
            line_rect = pygame.Rect(rect.x + 240, row_y - 4, rect.w - 280, 42)
            self._draw_embossed_box(line_rect, DESKTOP_DARK)
            self._draw_text(self.fonts["small"], label, TEXT_COLOR, (line_rect.x + 12, line_rect.y + 11))
            self._draw_text(self.fonts["small"], str(value), TEXT_MUTED, (line_rect.x + 270, line_rect.y + 11))
            minus_rect = pygame.Rect(rect.x + rect.w - 170, row_y, 44, 34)
            plus_rect = pygame.Rect(rect.x + rect.w - 116, row_y, 44, 34)
            self._draw_button(minus_rect, "-")
            self._draw_button(plus_rect, "+")
            row_y += 56

    def _draw_intro(self, window):
        rect = window["rect"]
        shell = pygame.Rect(rect.x + 16, rect.y + 44, rect.w - 32, rect.h - 60)
        self._draw_embossed_box(shell, PANEL_BG)
        frame = self.intro_frames[window.get("intro_frame", 0)] if self.intro_frames else self.assets["abebe"]
        preview_area = pygame.Rect(rect.x + 34, rect.y + 56, rect.w - 68, rect.h - 168)
        self._draw_embossed_box(preview_area, BLACK, sunken=True)
        scale = min(preview_area.w / frame.get_width(), preview_area.h / frame.get_height())
        scaled = pygame.transform.smoothscale(frame, (max(1, int(frame.get_width() * scale)), max(1, int(frame.get_height() * scale))))
        scaled_rect = scaled.get_rect(center=preview_area.center)
        self.screen.blit(scaled, scaled_rect)

        caption_rect = pygame.Rect(rect.x + 58, rect.bottom - 88, rect.w - 116, 46)
        self._draw_embossed_box(caption_rect, BLACK, sunken=True)
        subtitle_index = min(len(window["lines"]) - 1, (pygame.time.get_ticks() // 2600) % max(1, len(window["lines"])))
        self._draw_centered(self.fonts["small"], window["lines"][subtitle_index], WHITE, caption_rect.center)

    def _draw_terminal(self, window):
        rect = window["rect"]
        shell = pygame.Rect(rect.x + 16, rect.y + 44, rect.w - 32, rect.h - 60)
        self._draw_embossed_box(shell, PANEL_BG)
        terminal_rect = pygame.Rect(rect.x + 18, rect.y + 48, rect.w - 36, rect.h - 94)
        self._draw_embossed_box(terminal_rect, TERMINAL_BG, sunken=True)
        output = window["output"][-20:]
        y = terminal_rect.y + 12
        for line in output:
            self._draw_text(self.fonts["small"], line, TERMINAL_FG, (terminal_rect.x + 12, y))
            y += 22
        input_rect = pygame.Rect(terminal_rect.x + 8, terminal_rect.bottom - 42, terminal_rect.w - 16, 30)
        self._draw_embossed_box(input_rect, BLACK, sunken=True)
        cursor = "_" if (pygame.time.get_ticks() // 400) % 2 == 0 else ""
        self._draw_text(self.fonts["small"], f'> {window["input"]}{cursor}', WHITE, (input_rect.x + 8, input_rect.y + 6))

    def _draw_text_viewer(self, window):
        rect = window["rect"]
        shell = pygame.Rect(rect.x + 16, rect.y + 44, rect.w - 32, rect.h - 60)
        self._draw_embossed_box(shell, PANEL_BG)
        content_rect = pygame.Rect(rect.x + 18, rect.y + 48, rect.w - 36, rect.h - 68)
        self._draw_embossed_box(content_rect, BLACK, sunken=True)
        lines = window["lines"]
        scroll = window.get("scroll", 0)
        visible = lines[scroll:scroll + 18]
        y = content_rect.y + 12
        for line in visible:
            self._draw_text(self.fonts["small"], line, WHITE, (content_rect.x + 12, y))
            y += 24

    def _draw_image_viewer(self, window):
        rect = window["rect"]
        shell = pygame.Rect(rect.x + 16, rect.y + 44, rect.w - 32, rect.h - 60)
        self._draw_embossed_box(shell, PANEL_BG)
        image = self.assets.get(window["image_key"])
        if image is None:
            return
        available = pygame.Rect(rect.x + 24, rect.y + 56, rect.w - 48, rect.h - 84)
        scale = min(available.w / image.get_width(), available.h / image.get_height())
        scaled = pygame.transform.smoothscale(image, (int(image.get_width() * scale), int(image.get_height() * scale)))
        pos = scaled.get_rect(center=available.center)
        self._draw_embossed_box(available, BLACK, sunken=True)
        self.screen.blit(scaled, pos)

    def _draw_gallery(self, window):
        rect = window["rect"]
        shell = pygame.Rect(rect.x + 16, rect.y + 44, rect.w - 32, rect.h - 60)
        self._draw_embossed_box(shell, PANEL_BG)
        self._draw_text(self.fonts["body"], "FILE STORAGE", TEXT_COLOR, (rect.x + 36, rect.y + 72))
        y = rect.y + 120
        for label, key in window["items"]:
            row = pygame.Rect(rect.x + 56, y, rect.w - 112, 48)
            self._draw_embossed_box(row, DESKTOP_DARK)
            thumb = self.gallery_thumbs.get(key)
            if thumb is not None:
                self.screen.blit(thumb, (row.x + 8, row.y - 8))
                self._draw_text(self.fonts["small"], label, TEXT_COLOR, (row.x + 118, row.y + 14))
            else:
                self._draw_text(self.fonts["small"], label, TEXT_COLOR, (row.x + 14, row.y + 14))
            y += 70

    def _draw_editor_home(self, editor, sidebar_rect, content_rect):
        editor["sidebar_rects"] = []
        self._draw_text(self.fonts["body"], "DEJAVISION LEVEL EDITOR", TEXT_COLOR, (content_rect.x + 24, content_rect.y + 20))
        self._draw_text(self.fonts["small"], "Use Open to load built-in or saved maps.", TEXT_MUTED, (content_rect.x + 24, content_rect.y + 64))
        self._draw_text(self.fonts["small"], "Use New to create another editor document.", TEXT_MUTED, (content_rect.x + 24, content_rect.y + 88))
        card = pygame.Rect(content_rect.x + 22, content_rect.y + 140, min(560, content_rect.w - 44), 180)
        self._draw_embossed_box(card, DESKTOP_DARK)
        self._draw_text(self.fonts["body"], "Legacy Structure Port", TEXT_COLOR, (card.x + 20, card.y + 20))
        info = [
            "Pages: Home / Open / New / Editor",
            "2D grid editing and layered custom maps",
            "Integrated 3D preview inside the same window",
            "Ctrl+S save, Ctrl+Z undo, F4 toggle 2D/3D",
        ]
        text_y = card.y + 62
        for line in info:
            self._draw_text(self.fonts["small"], line, TEXT_MUTED, (card.x + 20, text_y))
            text_y += 26
        action_y = sidebar_rect.y + 58
        for action, label in (("open", "Open"), ("new", "New")):
            row = pygame.Rect(sidebar_rect.x + 10, action_y, sidebar_rect.w - 20, 38)
            self._draw_button(row, label)
            editor["sidebar_rects"].append((action, row))
            action_y += 46

    def _draw_editor_open_page(self, editor, sidebar_rect, content_rect):
        editor["builtin_rects"] = []
        editor["load_rects"] = []
        self._draw_text(self.fonts["body"], "Open Map", TEXT_COLOR, (content_rect.x + 24, content_rect.y + 20))
        self._draw_text(self.fonts["small"], "Built-in maze maps", TEXT_MUTED, (content_rect.x + 24, content_rect.y + 58))
        y = content_rect.y + 88
        for builtin_name in ("Tutorial", "Testing", "Secret", "City"):
            row = pygame.Rect(content_rect.x + 24, y, min(320, content_rect.w - 48), 30)
            self._draw_embossed_box(row, PANEL_BG)
            self._draw_text(self.fonts["small"], builtin_name, TEXT_COLOR, (row.x + 10, row.y + 7))
            load_btn = pygame.Rect(row.right - 82, row.y + 2, 72, 26)
            self._draw_button(load_btn, "LOAD")
            editor["builtin_rects"].append((builtin_name, load_btn))
            y += 38
        self._draw_text(self.fonts["small"], "Saved custom maps", TEXT_MUTED, (content_rect.x + 24, y + 12))
        y += 42
        for index, name in enumerate(list_custom_map_names()[:12]):
            row = pygame.Rect(content_rect.x + 24, y, min(420, content_rect.w - 48), 30)
            self._draw_embossed_box(row, DESKTOP_DARK)
            self._draw_text(self.fonts["small"], name, TEXT_COLOR, (row.x + 10, row.y + 7))
            load_btn = pygame.Rect(row.right - 82, row.y + 2, 72, 26)
            self._draw_button(load_btn, "LOAD")
            editor["load_rects"].append((index, load_btn))
            y += 36
        if not editor["load_rects"]:
            self._draw_text(self.fonts["small"], "No saved custom maps yet.", TEXT_MUTED, (content_rect.x + 24, y))
        self._draw_text(self.fonts["small"], "F1 Home  F3 New", TEXT_MUTED, (sidebar_rect.x + 12, sidebar_rect.bottom - 34))

    def _draw_editor_new_page(self, editor, sidebar_rect, content_rect):
        editor["new_input_rects"] = []
        self._draw_text(self.fonts["body"], "Create New Map", TEXT_COLOR, (content_rect.x + 24, content_rect.y + 20))
        self._draw_text(self.fonts["small"], "Maximum size is 64 x 64. Layers: 1-16.", TEXT_MUTED, (content_rect.x + 24, content_rect.y + 58))
        fields = [
            ("width_input", "Width", editor.get("width_input", "24")),
            ("height_input", "Height", editor.get("height_input", "24")),
            ("layers_input", "Layers", editor.get("layers_input", "1")),
        ]
        y = content_rect.y + 102
        for key, label, value in fields:
            row = pygame.Rect(content_rect.x + 24, y, 340, 38)
            self._draw_embossed_box(row, DESKTOP_DARK)
            self._draw_text(self.fonts["small"], label, TEXT_COLOR, (row.x + 12, row.y + 11))
            value_rect = pygame.Rect(row.x + 120, row.y + 4, row.w - 132, 28)
            self._draw_embossed_box(value_rect, PANEL_BG, sunken=editor.get("new_focus", "width") == key.replace("_input", ""))
            self._draw_centered(self.fonts["small"], value, TEXT_COLOR, value_rect.center)
            editor["new_input_rects"].append((key, value_rect))
            y += 52
        create_btn = pygame.Rect(content_rect.x + 24, y + 20, 112, 34)
        self._draw_button(create_btn, "CREATE")
        editor["new_input_rects"].append(("create", create_btn))
        self._draw_text(self.fonts["small"], "Tab switches field, Enter creates map.", TEXT_MUTED, (content_rect.x + 24, y + 66))
        self._draw_text(self.fonts["small"], "F1 Home  F2 Open", TEXT_MUTED, (sidebar_rect.x + 12, sidebar_rect.bottom - 34))

    def _draw_editor_3d_canvas(self, editor, canvas_rect):
        self._draw_embossed_box(canvas_rect, BLACK, sunken=True)
        clip_rect = canvas_rect.inflate(-2, -2)
        surface = pygame.Surface((max(1, canvas_rect.w - 4), max(1, canvas_rect.h - 4)))
        local_rect = surface.get_rect()
        sky_rect = pygame.Rect(0, 0, local_rect.w, int(local_rect.h * 0.58))
        floor_rect = pygame.Rect(0, sky_rect.bottom, local_rect.w, local_rect.h - sky_rect.bottom)
        pygame.draw.rect(surface, (17, 20, 23), sky_rect)
        pygame.draw.rect(surface, (26, 30, 36), floor_rect)
        faces = []
        picks = []
        outlines = []

        def project_world(point):
            projected_point = self._editor_project_point(editor, local_rect, *point)
            if projected_point is None:
                return None
            sx, sy, depth = projected_point
            return (canvas_rect.x + 2 + sx, canvas_rect.y + 2 + sy, depth)

        def add_face(points3d, fill, outline):
            projected = []
            depth_accum = 0.0
            for point in points3d:
                projected_point = self._editor_project_point(editor, local_rect, *point)
                if projected_point is None:
                    return
                sx, sy, depth = projected_point
                projected.append((sx, sy))
                depth_accum += depth
            faces.append((depth_accum / max(1, len(points3d)), projected, fill, outline))

        def add_horizontal_face(cell_x, cell_y, z_level, fill, outline):
            add_face(
                (
                    (cell_x, cell_y, z_level),
                    (cell_x + 1.0, cell_y, z_level),
                    (cell_x + 1.0, cell_y + 1.0, z_level),
                    (cell_x, cell_y + 1.0, z_level),
                ),
                fill,
                outline,
            )

        def shade(color_hex, factor):
            base = pygame.Color(color_hex)
            return (
                max(0, min(255, int(base.r * factor))),
                max(0, min(255, int(base.g * factor))),
                max(0, min(255, int(base.b * factor))),
            )

        def rotate_point(point, center, cell):
            px, py, pz = point
            cx, cy, cz = center
            dx = px - cx
            dy = py - cy
            dz = pz - cz
            rx = math.radians(float(cell.get("rotation_x", 0.0)) % 360.0)
            ry = math.radians(float(cell.get("rotation_y", 0.0)) % 360.0)
            rz = math.radians(float(cell.get("rotation", 0.0)) % 360.0)
            cos_rx, sin_rx = math.cos(rx), math.sin(rx)
            cos_ry, sin_ry = math.cos(ry), math.sin(ry)
            cos_rz, sin_rz = math.cos(rz), math.sin(rz)
            dy, dz = dy * cos_rx - dz * sin_rx, dy * sin_rx + dz * cos_rx
            dx, dz = dx * cos_ry + dz * sin_ry, -dx * sin_ry + dz * cos_ry
            dx, dy = dx * cos_rz - dy * sin_rz, dx * sin_rz + dy * cos_rz
            return (cx + dx, cy + dy, cz + dz)

        def draw_world_line(start_point, end_point, color, width=2):
            start = project_world(start_point)
            end = project_world(end_point)
            if start is None or end is None:
                return None
            pygame.draw.line(self.screen, color, start[:2], end[:2], width)
            hit = pygame.Rect(min(start[0], end[0]) - 8, min(start[1], end[1]) - 8, abs(end[0] - start[0]) + 16, abs(end[1] - start[1]) + 16)
            return start, end, hit

        def draw_world_ring(center, axis, radius, color):
            pts = []
            for step in range(25):
                angle = (math.pi * 2.0 * step) / 24.0
                if axis == "x":
                    point = (center[0], center[1] + math.cos(angle) * radius, center[2] + math.sin(angle) * radius)
                elif axis == "y":
                    point = (center[0] + math.cos(angle) * radius, center[1], center[2] + math.sin(angle) * radius)
                else:
                    point = (center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius, center[2])
                projected = project_world(point)
                if projected is not None:
                    pts.append(projected[:2])
            if len(pts) >= 6:
                pygame.draw.lines(self.screen, color, True, pts, 2)
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                return pygame.Rect(min(xs) - 6, min(ys) - 6, max(xs) - min(xs) + 12, max(ys) - min(ys) + 12)
            return None

        surface_layer_idx = editor.get("active_layer", 0)
        for layer_idx, layer in enumerate(editor["layers"]):
            base_z = float(layer_idx) * 2.0
            for y, row in enumerate(layer):
                for x, cell in enumerate(row):
                    if layer_idx == surface_layer_idx and cell.get("has_floor", True):
                        add_horizontal_face(x, y, base_z, (32, 37, 43), (43, 49, 56))
                    if layer_idx == surface_layer_idx and cell.get("has_ceiling", True):
                        add_horizontal_face(x, y, base_z + 1.0, (23, 28, 32), (36, 43, 49))
                    tile = cell["tile"]
                    if tile == "empty":
                        continue
                    scale_x = max(0.35, float(cell.get("scale_x", 1.0)))
                    scale_y = max(0.35, float(cell.get("scale_y", 1.0)))
                    scale_z = max(0.35, float(cell.get("scale_z", 1.0)))
                    height = max(1.0, float(cell.get("height", 1)) * scale_z)
                    center_x = x + 0.5 + float(cell.get("offset_x", 0.0))
                    center_y = y + 0.5 + float(cell.get("offset_y", 0.0))
                    half_x = 0.5 * scale_x
                    half_y = 0.5 * scale_y
                    min_x = center_x - half_x
                    max_x = center_x + half_x
                    min_y = center_y - half_y
                    max_y = center_y + half_y
                    min_z = base_z + float(cell.get("offset_z", 0.0))
                    max_z = min_z + height
                    color = EDITOR_TILE_COLORS.get(tile, "#6A6A6A")
                    corners = [
                        (min_x, min_y, min_z), (max_x, min_y, min_z), (max_x, max_y, min_z), (min_x, max_y, min_z),
                        (min_x, min_y, max_z), (max_x, min_y, max_z), (max_x, max_y, max_z), (min_x, max_y, max_z),
                    ]
                    center = (center_x, center_y, min_z + height * 0.5)
                    corners = [rotate_point(corner, center, cell) for corner in corners]
                    add_face((corners[0], corners[3], corners[2], corners[1]), shade(color, 0.48), "#111111")
                    add_face((corners[0], corners[1], corners[5], corners[4]), shade(color, 0.66), "#161616")
                    add_face((corners[1], corners[2], corners[6], corners[5]), shade(color, 0.58), "#161616")
                    add_face((corners[3], corners[2], corners[6], corners[7]), shade(color, 0.82), "#202020")
                    add_face((corners[0], corners[3], corners[7], corners[4]), shade(color, 0.72), "#202020")
                    add_face((corners[4], corners[5], corners[6], corners[7]), shade(color, 1.05), "#2A2A2A")
                    projected = [self._editor_project_point(editor, local_rect, *corner) for corner in corners]
                    projected = [point for point in projected if point is not None]
                    if projected:
                        xs = [point[0] for point in projected]
                        ys = [point[1] for point in projected]
                        pick_rect = pygame.Rect(canvas_rect.x + 2 + min(xs) - 8, canvas_rect.y + 2 + min(ys) - 8, max(xs) - min(xs) + 16, max(ys) - min(ys) + 16)
                        picks.append({"cell": (x, y), "layer": layer_idx, "rect": pygame.Rect(canvas_rect.x + 2 + min(xs) - 8, canvas_rect.y + 2 + min(ys) - 8, max(xs) - min(xs) + 16, max(ys) - min(ys) + 16)})
                        outlines.append({"cell": (x, y), "layer": layer_idx, "rect": pick_rect, "tile": tile, "center": (canvas_rect.x + 2 + sum(xs) / len(xs), canvas_rect.y + 2 + sum(ys) / len(ys)), "corners": corners})
        for _depth, points, fill, outline in sorted(faces, key=lambda item: item[0], reverse=True):
            pygame.draw.polygon(surface, fill, points)
            pygame.draw.polygon(surface, outline, points, 1)
        self.screen.blit(surface, (canvas_rect.x + 2, canvas_rect.y + 2))
        editor["pick_candidates"] = picks
        editor["gizmo_hits"] = []
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(clip_rect)
        selected = editor.get("selected_cell")
        if selected is not None:
            for item in reversed(outlines):
                if item["cell"] == selected and item["layer"] == editor["active_layer"]:
                    outline_color = (60, 255, 100) if editor.get("active_tool") == "select" else (255, 210, 80)
                    projected_corners = [project_world(corner) for corner in item["corners"]]
                    projected_corners = [p for p in projected_corners if p is not None]
                    if len(projected_corners) == 8:
                        edge_pairs = ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))
                        for a, b in edge_pairs:
                            pygame.draw.line(self.screen, outline_color, projected_corners[a][:2], projected_corners[b][:2], 2)
                    else:
                        pygame.draw.rect(self.screen, outline_color, item["rect"], 2)
                    if editor.get("active_tool") == "select":
                        info_rect = pygame.Rect(item["rect"].right + 8, max(canvas_rect.y + 8, item["rect"].y), 180, 72)
                        if info_rect.right > canvas_rect.right:
                            info_rect.x = item["rect"].x - info_rect.w - 8
                        self._draw_embossed_box(info_rect, (20, 40, 20), sunken=True)
                        _selected, cell = self._editor_active_cell(editor)
                        lines = [
                            cell["tile"],
                            f"Pos {selected[0]}, {selected[1]}, L{editor['active_layer'] + 1}",
                            f"Rot {int(cell.get('rotation_x', 0.0))}/{int(cell.get('rotation_y', 0.0))}/{int(cell.get('rotation', 0.0))}",
                            f"Size {cell.get('scale_x', 1.0):.1f}/{cell.get('scale_y', 1.0):.1f}/{cell.get('scale_z', 1.0):.1f}",
                        ]
                        iy = info_rect.y + 8
                        for line in lines:
                            self._draw_text(self.fonts["tiny"], line, (200, 255, 200), (info_rect.x + 8, iy))
                            iy += 15
                    _selected, cell = self._editor_active_cell(editor)
                    world_center = (
                        selected[0] + 0.5 + float(cell.get("offset_x", 0.0)),
                        selected[1] + 0.5 + float(cell.get("offset_y", 0.0)),
                        editor["active_layer"] + float(cell.get("offset_z", 0.0)) + max(0.5, float(cell.get("height", 1)) * float(cell.get("scale_z", 1.0)) * 0.5),
                    )
                    center = item["center"]
                    if editor.get("active_tool") == "move":
                        axis_specs = (
                            ("x", (255, 90, 90), (world_center[0] + 1.2, world_center[1], world_center[2])),
                            ("y", (90, 220, 90), (world_center[0], world_center[1] + 1.2, world_center[2])),
                            ("z", (90, 150, 255), (world_center[0], world_center[1], world_center[2] + 1.2)),
                        )
                        for axis, color, endpoint in axis_specs:
                            line = draw_world_line(world_center, endpoint, color, 3)
                            if line is not None:
                                _start, end, hit = line
                                pygame.draw.circle(self.screen, color, (int(end[0]), int(end[1])), 5)
                                editor["gizmo_hits"].append({"mode": "move", "axis": axis, "rect": hit})
                    elif editor.get("active_tool") == "rotate":
                        for axis, color, radius in (("x", (255, 90, 90), 0.9), ("y", (90, 220, 90), 1.05), ("z", (90, 150, 255), 1.2)):
                            hit = draw_world_ring(world_center, axis, radius, color)
                            if hit is not None:
                                editor["gizmo_hits"].append({"mode": "rotate", "axis": axis, "rect": hit})
                    elif editor.get("active_tool") == "resize":
                        axis_specs = (
                            ("x", (255, 90, 90), (world_center[0] + 1.2, world_center[1], world_center[2])),
                            ("y", (90, 220, 90), (world_center[0], world_center[1] + 1.2, world_center[2])),
                            ("z", (90, 150, 255), (world_center[0], world_center[1], world_center[2] + 1.2)),
                        )
                        for axis, color, endpoint in axis_specs:
                            line = draw_world_line(world_center, endpoint, color, 3)
                            if line is not None:
                                _start, end, hit = line
                                handle = pygame.Rect(end[0] - 6, end[1] - 6, 12, 12)
                                pygame.draw.rect(self.screen, color, handle)
                                editor["gizmo_hits"].append({"mode": "resize", "axis": axis, "rect": handle.inflate(8, 8).union(hit)})
                    break
        self._draw_text(self.fonts["tiny"], "WASD move  Arrows look  Wheel zoom  MMB orbit", WHITE, (canvas_rect.x + 12, canvas_rect.bottom - 22))
        self.screen.set_clip(previous_clip)

    def _draw_editor(self, window):
        rect = window["rect"]
        editor = window["editor"]

        def draw_menu_dropdowns():
            editor["menu_item_rects"] = []
            if editor.get("menu_open") == "file":
                drop = pygame.Rect(menu_bar.x + 8, menu_bar.bottom, 132, 126)
                self._draw_embossed_box(drop, PANEL_BG)
                y = drop.y + 4
                for action, label in (("save", "Save"), ("save_as", "Save As"), ("rename", "Rename"), ("open", "Open"), ("exit", "Exit")):
                    row = pygame.Rect(drop.x + 4, y, drop.w - 8, 20)
                    self._draw_embossed_box(row, DESKTOP_DARK if row.collidepoint(mouse_pos) else PANEL_BG, sunken=row.collidepoint(mouse_pos))
                    self._draw_text(self.fonts["tiny"], label, TEXT_COLOR, (row.x + 6, row.y + 4))
                    editor["menu_item_rects"].append((action, row))
                    y += 22
            elif editor.get("menu_open") == "edit":
                drop = pygame.Rect(menu_bar.x + 56, menu_bar.bottom, 112, 54)
                self._draw_embossed_box(drop, PANEL_BG)
                y = drop.y + 4
                for action, label in (("undo", "Undo"), ("redo", "Redo")):
                    row = pygame.Rect(drop.x + 4, y, drop.w - 8, 20)
                    self._draw_embossed_box(row, DESKTOP_DARK if row.collidepoint(mouse_pos) else PANEL_BG, sunken=row.collidepoint(mouse_pos))
                    self._draw_text(self.fonts["tiny"], label, TEXT_COLOR, (row.x + 6, row.y + 4))
                    editor["menu_item_rects"].append((action, row))
                    y += 22

        shell = pygame.Rect(rect.x + 16, rect.y + 44, rect.w - 32, rect.h - 60)
        self._draw_embossed_box(shell, PANEL_BG)
        self._draw_text(self.fonts["small"], f'Status: {editor.get("status", "")}', TEXT_COLOR, (rect.x + 24, rect.y + 36))

        page_bar = pygame.Rect(rect.x + 24, rect.y + 60, rect.w - 48, 34)
        self._draw_embossed_box(page_bar, DESKTOP_DARK)
        editor["page_rects"] = []
        page_x = page_bar.x + 8
        for page, label in (("home", "Home"), ("open", "Open"), ("new", "New"), ("editor", "Editor")):
            btn = pygame.Rect(page_x, page_bar.y + 4, 84, 26)
            active = editor.get("page") == page
            self._draw_button(btn, label, active=active)
            editor["page_rects"].append((page, btn))
            page_x += 90
        self._draw_text(self.fonts["tiny"], "F1/F2/F3 navigate", TEXT_MUTED, (page_bar.right - 132, page_bar.y + 9))

        menu_bar = pygame.Rect(rect.x + 24, rect.y + 98, rect.w - 48, 24)
        self._draw_embossed_box(menu_bar, PANEL_BG)
        editor["menu_rects"] = []
        editor["menu_item_rects"] = []
        mouse_pos = pygame.mouse.get_pos()
        mx = menu_bar.x + 8
        for menu_name, label in (("file", "FILE"), ("edit", "EDIT")):
            mrect = pygame.Rect(mx, menu_bar.y + 2, 42, 20)
            hovered = mrect.collidepoint(mouse_pos)
            if hovered:
                editor["menu_open"] = menu_name
            self._draw_button(mrect, label, active=editor.get("menu_open") == menu_name)
            editor["menu_rects"].append((menu_name, mrect))
            mx += 48

        body_rect = pygame.Rect(rect.x + 24, rect.y + 128, rect.w - 48, rect.h - 158)
        if editor.get("page") == "editor":
            sidebar_rect = None
            content_rect = body_rect.copy()
        else:
            sidebar_rect = pygame.Rect(body_rect.x, body_rect.y, 184, body_rect.h)
            content_rect = pygame.Rect(sidebar_rect.right + 12, body_rect.y, body_rect.w - sidebar_rect.w - 12, body_rect.h)
            self._draw_embossed_box(sidebar_rect, DESKTOP_DARK)
            self._draw_text(self.fonts["button"], "Editor", TEXT_COLOR, (sidebar_rect.x + 12, sidebar_rect.y + 16))
        self._draw_embossed_box(content_rect, PANEL_BG)

        if editor.get("page") == "home":
            self._draw_editor_home(editor, sidebar_rect, content_rect)
            return
        if editor.get("page") == "open":
            self._draw_editor_open_page(editor, sidebar_rect, content_rect)
            return
        if editor.get("page") == "new":
            self._draw_editor_new_page(editor, sidebar_rect, content_rect)
            return

        toolbar_rect = pygame.Rect(content_rect.x + 12, content_rect.y + 10, content_rect.w - 24, 40)
        self._draw_embossed_box(toolbar_rect, DESKTOP_DARK)
        editor["toolbar_rects"] = []
        tool_x = toolbar_rect.x + 8
        button_size = 28
        for action, label, width in (
            ("save", "SAVE", button_size),
            ("run", "RUN", 62),
            ("name", "RENAME", 76),
            ("view", "3D" if editor.get("view_mode") == "2d" else "2D", 46),
            ("paint", "PAINT", button_size),
            ("erase", "ERASE", button_size),
            ("select", "CURSOR", button_size),
            ("move", "MOVE", button_size),
            ("rotate", "ROTATE", button_size),
            ("resize", "RESIZE", button_size),
            ("layer_add", "+L", 42),
            ("layer_remove", "-L", 42),
        ):
            btn = pygame.Rect(tool_x, toolbar_rect.y + 6, width, button_size if width == button_size else 28)
            active = action == editor.get("active_tool") or (action == "view" and editor.get("view_mode") == "3d")
            self._draw_toolbar_button(btn, action, label, active=active)
            editor["toolbar_rects"].append((action, btn))
            tool_x += width + 6

        palette_width = 168
        side_width = 294
        panel_gap = 12
        palette_rect = pygame.Rect(content_rect.x + 12, content_rect.y + 54, palette_width, content_rect.h - 66)
        side_rect = pygame.Rect(content_rect.right - side_width, content_rect.y + 54, side_width, content_rect.h - 66)
        canvas_rect = pygame.Rect(palette_rect.right + panel_gap, content_rect.y + 54, max(320, side_rect.x - (palette_rect.right + panel_gap * 2)), content_rect.h - 66)
        self._draw_embossed_box(palette_rect, DESKTOP_DARK)
        self._draw_embossed_box(side_rect, DESKTOP_DARK)
        editor["palette_box_rect"] = palette_rect
        editor["canvas_rect"] = canvas_rect
        editor["palette_rects"] = []
        editor["layer_rects"] = []
        editor["layer_flag_rects"] = []
        editor["object_rects"] = []
        editor["inspector_rects"] = []
        editor["inspector_value_rects"] = []
        editor["inspector_scroll_max"] = 0

        self._draw_text(self.fonts["small"], "Palette", TEXT_COLOR, (palette_rect.x + 12, palette_rect.y + 10))
        palette_view = pygame.Rect(palette_rect.x + 6, palette_rect.y + 34, palette_rect.w - 12, palette_rect.h - 40)
        pal_y = palette_rect.y + 40
        visible_palette = max(1, palette_view.h // 36)
        palette_items = EDITOR_TILE_OPTIONS[editor.get("palette_scroll", 0):editor.get("palette_scroll", 0) + visible_palette]
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(palette_view)
        for tile_name, color, char in palette_items:
            row = pygame.Rect(palette_rect.x + 10, pal_y, palette_rect.w - 20, 32)
            self._draw_embossed_box(row, PANEL_ACTIVE if editor["selected_tile"] == tile_name else PANEL_BG, sunken=editor["selected_tile"] == tile_name)
            swatch = pygame.Rect(row.x + 6, row.y + 5, 22, 22)
            pygame.draw.rect(self.screen, pygame.Color(color), swatch)
            pygame.draw.rect(self.screen, BLACK, swatch, 1)
            self._draw_text(self.fonts["small"], f"{char} {tile_name}", TEXT_COLOR, (row.x + 38, row.y + 7))
            editor["palette_rects"].append((tile_name, row))
            pal_y += 36
        self.screen.set_clip(previous_clip)
        if len(EDITOR_TILE_OPTIONS) > visible_palette:
            palette_max_scroll = max(0, len(EDITOR_TILE_OPTIONS) - visible_palette)
            track = pygame.Rect(palette_rect.right - 10, palette_view.y + 2, 4, palette_view.h - 4)
            pygame.draw.rect(self.screen, PANEL_BORDER, track)
            thumb_h = max(18, int(track.h * (visible_palette / len(EDITOR_TILE_OPTIONS))))
            thumb_y = track.y + int((track.h - thumb_h) * (editor.get("palette_scroll", 0) / max(1, palette_max_scroll)))
            pygame.draw.rect(self.screen, TITLE_BLUE, pygame.Rect(track.x - 2, thumb_y, 8, thumb_h))

        self._draw_text(self.fonts["small"], "Layers", TEXT_COLOR, (side_rect.x + 12, side_rect.y + 10))
        editor["layers_box_rect"] = pygame.Rect(side_rect.x + 8, side_rect.y + 30, side_rect.w - 16, 148)
        layers_view = editor["layers_box_rect"].inflate(-4, -4)
        layer_y = side_rect.y + 38
        visible_layers = max(1, (editor["layers_box_rect"].h - 8) // 30)
        start_layer = editor.get("layer_scroll", 0)
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(layers_view)
        for layer_idx in range(start_layer, min(len(editor["layers"]), start_layer + visible_layers)):
            row = pygame.Rect(side_rect.x + 10, layer_y, side_rect.w - 20, 26)
            active = layer_idx == editor["active_layer"]
            self._draw_embossed_box(row, PANEL_ACTIVE if active else PANEL_BG, sunken=active)
            self._draw_text(self.fonts["tiny"], f"Layer {layer_idx + 1}", TEXT_COLOR, (row.x + 8, row.y + 6))
            floor_rect = pygame.Rect(row.right - 46, row.y + 4, 18, 18)
            ceil_rect = pygame.Rect(row.right - 24, row.y + 4, 18, 18)
            floor_on = self._editor_layer_flag_value(editor, layer_idx, "has_floor")
            ceil_on = self._editor_layer_flag_value(editor, layer_idx, "has_ceiling")
            self._draw_embossed_box(floor_rect, PANEL_ACTIVE if floor_on else DESKTOP_DARK, sunken=floor_on)
            self._draw_embossed_box(ceil_rect, PANEL_ACTIVE if ceil_on else DESKTOP_DARK, sunken=ceil_on)
            self._draw_centered(self.fonts["tiny"], "F", TEXT_COLOR if floor_on else TEXT_MUTED, floor_rect.center)
            self._draw_centered(self.fonts["tiny"], "C", TEXT_COLOR if ceil_on else TEXT_MUTED, ceil_rect.center)
            editor["layer_rects"].append((layer_idx, row))
            editor["layer_flag_rects"].append((layer_idx, "has_floor", floor_rect))
            editor["layer_flag_rects"].append((layer_idx, "has_ceiling", ceil_rect))
            layer_y += 30
        self.screen.set_clip(previous_clip)
        if len(editor["layers"]) > visible_layers:
            layer_max_scroll = max(0, len(editor["layers"]) - visible_layers)
            track = pygame.Rect(editor["layers_box_rect"].right - 10, layers_view.y + 2, 4, layers_view.h - 4)
            pygame.draw.rect(self.screen, PANEL_BORDER, track)
            thumb_h = max(18, int(track.h * (visible_layers / len(editor["layers"]))))
            thumb_y = track.y + int((track.h - thumb_h) * (editor.get("layer_scroll", 0) / max(1, layer_max_scroll)))
            pygame.draw.rect(self.screen, TITLE_BLUE, pygame.Rect(track.x - 2, thumb_y, 8, thumb_h))

        objects_box = pygame.Rect(side_rect.x + 8, layer_y + 6, side_rect.w - 16, 170)
        self._draw_embossed_box(objects_box, PANEL_BG, sunken=True)
        self._draw_text(self.fonts["small"], "Objects", TEXT_COLOR, (objects_box.x + 8, objects_box.y + 8))
        entries = self._editor_object_entries(editor)
        editor["object_list_rect"] = objects_box
        max_scroll = max(0, len(entries) - 8)
        editor["object_scroll"] = max(0, min(max_scroll, editor.get("object_scroll", 0)))
        obj_y = objects_box.y + 32
        visible_entries = entries[editor["object_scroll"]:editor["object_scroll"] + 8]
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(objects_box.x + 4, objects_box.y + 28, objects_box.w - 12, objects_box.h - 34))
        for entry in visible_entries:
            row = pygame.Rect(objects_box.x + 6, obj_y, objects_box.w - 12, 22)
            active = editor.get("selected_cell") == (entry["x"], entry["y"]) and editor["active_layer"] == entry["layer"]
            self._draw_embossed_box(row, PANEL_ACTIVE if active else DESKTOP_DARK, sunken=active)
            label = f'L{entry["layer"] + 1} {entry["tile"]} ({entry["x"]},{entry["y"]})'
            self._draw_text(self.fonts["tiny"], label[:24], TEXT_COLOR, (row.x + 6, row.y + 5))
            editor["object_rects"].append((entry["layer"], entry["x"], entry["y"], row))
            obj_y += 24
            if obj_y + 24 > objects_box.bottom:
                break
        self.screen.set_clip(previous_clip)
        if len(entries) > 8:
            scroll_track = pygame.Rect(objects_box.right - 8, objects_box.y + 30, 4, objects_box.h - 40)
            pygame.draw.rect(self.screen, PANEL_BORDER, scroll_track)
            thumb_h = max(18, int(scroll_track.h * (8 / len(entries))))
            thumb_y = scroll_track.y + int((scroll_track.h - thumb_h) * (editor["object_scroll"] / max(1, max_scroll)))
            pygame.draw.rect(self.screen, TITLE_BLUE, pygame.Rect(scroll_track.x - 2, thumb_y, 8, thumb_h))

        inspector_box = pygame.Rect(side_rect.x + 8, objects_box.bottom + 8, side_rect.w - 16, side_rect.bottom - objects_box.bottom - 16)
        self._draw_embossed_box(inspector_box, PANEL_BG, sunken=True)
        editor["inspector_box_rect"] = inspector_box
        self._draw_text(self.fonts["small"], "Inspector", TEXT_COLOR, (inspector_box.x + 8, inspector_box.y + 8))
        selected_pos, selected_cell = self._editor_active_cell(editor)
        inspector_view = pygame.Rect(inspector_box.x + 6, inspector_box.y + 30, inspector_box.w - 12, inspector_box.h - 36)
        info_y = inspector_box.y + 34 - editor.get("inspector_scroll", 0)
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(inspector_view)
        if selected_pos is None or selected_cell is None:
            for line in (
                f'Map: {editor["map_name"]}{" *" if editor["dirty"] else ""}',
                f'Size: {editor["width"]} x {editor["height"]}',
                f'Brush: {editor["selected_tile"]}',
                "No object selected",
            ):
                self._draw_text(self.fonts["tiny"], line, TEXT_MUTED, (inspector_box.x + 8, info_y))
                info_y += 18
            content_height = max(0, info_y - (inspector_box.y + 34))
        else:
            values = self._editor_inspector_values(editor)
            self._draw_text(self.fonts["tiny"], f'Name: {values["name"]}', TEXT_MUTED, (inspector_box.x + 8, info_y))
            info_y += 18
            field_specs = [
                ("pos_x", "PX"), ("pos_y", "PY"), ("pos_z", "PZ"),
                ("rot_x", "RX"), ("rot_y", "RY"), ("rot_z", "RZ"),
                ("scale_x", "SX"), ("scale_y", "SY"), ("scale_z", "SZ"),
                ("height", "H"),
            ]
            row_y = info_y + 4
            col = 0
            for key, label in field_specs:
                label_x = inspector_box.x + 8 + col * 80
                self._draw_text(self.fonts["tiny"], label, TEXT_MUTED, (label_x, row_y + 5))
                value_rect = pygame.Rect(label_x + 20, row_y, 52, 20)
                focused = editor.get("inspector_focus") == key
                self._draw_embossed_box(value_rect, PANEL_ACTIVE if focused else DESKTOP_DARK, sunken=focused)
                shown = editor.get("inspector_buffer", "") if focused else values[key]
                self._draw_centered(self.fonts["tiny"], shown[:7], TEXT_COLOR, value_rect.center)
                editor["inspector_value_rects"].append((key, value_rect))
                col += 1
                if col >= 3:
                    col = 0
                    row_y += 24
            info_y = row_y + 30

            action_specs = [
                ("move_x-", "X-"), ("move_x+", "X+"), ("move_y-", "Y-"), ("move_y+", "Y+"), ("move_z-", "Z-"), ("move_z+", "Z+"),
                ("scale_x-", "SX-"), ("scale_x+", "SX+"), ("scale_y-", "SY-"), ("scale_y+", "SY+"), ("scale_z-", "SZ-"), ("scale_z+", "SZ+"),
                ("rot_x-", "RX-"), ("rot_x+", "RX+"), ("rot_y-", "RY-"), ("rot_y+", "RY+"), ("rot_z-", "RZ-"), ("rot_z+", "RZ+"),
                ("height-", "H-"), ("height+", "H+"), ("toggle_collision", "COL"), ("toggle_floor", "FLR"), ("toggle_ceiling", "CEI"),
            ]
            btn_w = 46
            btn_h = 24
            start_y = info_y + 6
            row_y = start_y
            col = 0
            for action, label in action_specs:
                btn = pygame.Rect(inspector_box.x + 8 + col * (btn_w + 6), row_y, btn_w, btn_h)
                self._draw_button(btn, label)
                editor["inspector_rects"].append((action, btn))
                col += 1
                if col >= 4:
                    col = 0
                    row_y += btn_h + 6
            content_height = max(0, row_y + btn_h - (inspector_box.y + 34))
        self.screen.set_clip(previous_clip)
        editor["inspector_scroll_max"] = max(0, content_height - inspector_view.h)
        editor["inspector_scroll"] = max(0, min(editor["inspector_scroll"], editor["inspector_scroll_max"]))
        if editor["inspector_scroll_max"] > 0:
            track = pygame.Rect(inspector_box.right - 8, inspector_view.y + 2, 4, inspector_view.h - 4)
            pygame.draw.rect(self.screen, PANEL_BORDER, track)
            thumb_h = max(18, int(track.h * (inspector_view.h / max(inspector_view.h, content_height))))
            thumb_y = track.y + int((track.h - thumb_h) * (editor["inspector_scroll"] / max(1, editor["inspector_scroll_max"])))
            pygame.draw.rect(self.screen, TITLE_BLUE, pygame.Rect(track.x - 2, thumb_y, 8, thumb_h))

        if editor.get("view_mode") == "3d":
            self._draw_editor_3d_canvas(editor, canvas_rect)
            draw_menu_dropdowns()
            return

        self._draw_embossed_box(canvas_rect, BLACK, sunken=True)
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(canvas_rect.inflate(-2, -2))
        cell_size = max(10, int(min(canvas_rect.w / max(1, editor["width"]), canvas_rect.h / max(1, editor["height"])) * editor.get("zoom", 1.0)))
        cell_size = min(cell_size, 42)
        grid_w = cell_size * editor["width"]
        grid_h = cell_size * editor["height"]
        offset_x = canvas_rect.x + (canvas_rect.w - grid_w) // 2 + int(editor.get("pan_x", 0.0))
        offset_y = canvas_rect.y + (canvas_rect.h - grid_h) // 2 + int(editor.get("pan_y", 0.0))
        editor["cell_rects"] = {}
        active_layer = editor["layers"][editor["active_layer"]]
        for y in range(editor["height"]):
            for x in range(editor["width"]):
                cell = active_layer[y][x]
                tile = cell["tile"]
                color = EDITOR_TILE_COLORS.get(tile, "#1F1F1F") if tile != "empty" else "#20252B"
                cell_rect = pygame.Rect(offset_x + x * cell_size, offset_y + y * cell_size, cell_size, cell_size)
                if cell_rect.right < canvas_rect.x or cell_rect.bottom < canvas_rect.y or cell_rect.x > canvas_rect.right or cell_rect.y > canvas_rect.bottom:
                    continue
                pygame.draw.rect(self.screen, pygame.Color(color), cell_rect)
                pygame.draw.rect(self.screen, (70, 70, 70), cell_rect, 1)
                if tile != "empty":
                    char = EDITOR_TILE_CHARS.get(tile, "?")
                    self._draw_centered(self.fonts["tiny"], char, WHITE, cell_rect.center)
                    if cell.get("height", 1) > 1:
                        self._draw_text(self.fonts["tiny"], str(cell["height"]), (255, 230, 140), (cell_rect.x + 2, cell_rect.y + 2))
                if editor.get("selected_cell") == (x, y):
                    pygame.draw.rect(self.screen, HIGHLIGHT, cell_rect, 2)
                editor["cell_rects"][(x, y)] = cell_rect
        self.screen.set_clip(previous_clip)
        draw_menu_dropdowns()

    def _draw_notification(self, sw, sh):
        rect = pygame.Rect(sw // 2 - 220, sh - 92, 440, 42)
        pygame.draw.rect(self.screen, WARN, rect)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, 2)
        self._draw_centered(self.fonts["small"], self.notification, WHITE, rect.center)

    def _draw_text(self, font, text, color, pos):
        surf = font.render(str(text), True, color)
        self.screen.blit(surf, pos)

    def _draw_centered(self, font, text, color, center):
        surf = font.render(str(text), True, color)
        rect = surf.get_rect(center=center)
        self.screen.blit(surf, rect)

    def run(self):
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            self._editor_tick()
            self.draw()
            self.clock.tick(60)
        stop_music()
        pygame.quit()


def run():
    app = PygameDesktopApp()
    app.run()
