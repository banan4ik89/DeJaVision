import copy
import json
import math
import tkinter as tk
import time
from pathlib import Path

from PIL import Image, ImageTk

from abebe.custom_maps import CUSTOM_MAPS_DIR, ensure_custom_maps_dir
from abebe.ui.settings_window import (
    PANE_ACTIVE,
    PANE_BG,
    PANE_BG_DARK,
    PANE_BORDER_DARK,
    PANE_TEXT,
    PANE_TEXT_MUTED,
    PANE_TITLE,
    _geometry_string,
    make_draggable,
)
from abebe.core.utils import get_exe_dir


PANE_OS_DIR = Path(get_exe_dir()) / "data" / "app" / "pane_os"
WINDOW_SIZE = (1380, 920)
WINDOW_IMAGE_SIZE = (WINDOW_SIZE[0], WINDOW_SIZE[1])
MAX_MAP_SIZE = 64
DEFAULT_MAP_W = 24
DEFAULT_MAP_H = 24
GRID_PIXEL_SIZE = 700
MAX_LAYERS = 16

PALETTE_ITEMS = [
    ("wall", "Wall", "#", "#6A6A6A"),
    ("spawn", "Spawn", "P", "#FFB347"),
    ("mannequin", "Mannequin", "M", "#D4D4D4"),
    ("hexagaze", "Hexagaze", "H", "#FF5D5D"),
    ("gun", "Gun", "G", "#58AEFF"),
    ("bomb", "Bomb", "B", "#FFD24A"),
]

TOOLS = [
    ("paint", "Brush"),
    ("erase", "Eraser"),
    ("rotate", "Rotate"),
    ("select", "Cursor"),
    ("move", "Move"),
    ("resize", "Resize"),
]

VIEW_MODES = [
    ("2d", "2D"),
    ("3d", "3D"),
]

BUILTIN_MAPS = {
    "Tutorial Maze": ("tutor_maze", "MAP"),
    "Testing Maze": ("testing_maze", "MAP"),
    "Secret Maze": ("secret_maze", "MAP"),
    "City Maze": ("city_maze", "MAP"),
}


def _section_button(parent, text, command, width=18):
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=("Terminal", 12),
        bg=PANE_BG,
        fg=PANE_TEXT,
        activebackground=PANE_ACTIVE,
        activeforeground=PANE_TEXT,
        relief="raised",
        borderwidth=2,
        anchor="w",
        padx=14,
        width=width,
    )


def _clear_children(parent):
    for child in parent.winfo_children():
        child.destroy()


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sanitize_name(name):
    cleaned = "".join(ch for ch in name.strip() if ch.isalnum() or ch in {"_", "-", " "}).strip()
    return cleaned[:48]


def _make_blank_cells(map_w, map_h):
    return [[{"tile": "empty", "height": 1, "rotation": 0.0, "rotation_x": 0.0, "rotation_y": 0.0, "has_floor": True, "has_ceiling": True, "scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.0, "offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0, "texture": "", "color": "", "collidable": True} for _x in range(map_w)] for _y in range(map_h)]


def _make_blank_layers(map_w, map_h, count=1):
    return [_make_blank_cells(map_w, map_h) for _ in range(max(1, count))]


def _normalize_layers(layers, map_w, map_h):
    normalized = []
    source_layers = layers if isinstance(layers, list) and layers else _make_blank_layers(map_w, map_h, 1)
    for layer_index in range(min(MAX_LAYERS, len(source_layers))):
        source_layer = source_layers[layer_index] if isinstance(source_layers[layer_index], list) else []
        layer = []
        for y in range(map_h):
            source_row = source_layer[y] if y < len(source_layer) and isinstance(source_layer[y], list) else []
            row = []
            for x in range(map_w):
                raw_cell = source_row[x] if x < len(source_row) and isinstance(source_row[x], dict) else {}
                tile = raw_cell.get("tile", "empty")
                if tile not in {"empty", "wall", "stair", "spawn", "mannequin", "hexagaze", "gun", "bomb"}:
                    tile = "empty"
                row.append(
                    {
                        "tile": tile,
                        "height": max(1, min(5, _safe_int(raw_cell.get("height"), 1))),
                        "rotation": float(raw_cell.get("rotation", 0.0)) % 360.0,
                        "rotation_x": float(raw_cell.get("rotation_x", 0.0)) % 360.0,
                        "rotation_y": float(raw_cell.get("rotation_y", 0.0)) % 360.0,
                        "has_floor": True if layer_index == 0 else bool(raw_cell.get("has_floor", True)),
                        "has_ceiling": bool(raw_cell.get("has_ceiling", tile != "stair")),
                        "scale_x": max(0.35, min(2.5, float(raw_cell.get("scale_x", 1.0)))),
                        "scale_y": max(0.35, min(2.5, float(raw_cell.get("scale_y", 1.0)))),
                        "scale_z": max(0.35, min(2.5, float(raw_cell.get("scale_z", 1.0)))),
                        "offset_x": max(-0.49, min(0.49, float(raw_cell.get("offset_x", 0.0)))),
                        "offset_y": max(-0.49, min(0.49, float(raw_cell.get("offset_y", 0.0)))),
                        "offset_z": max(-0.95, min(0.95, float(raw_cell.get("offset_z", 0.0)))),
                        "texture": str(raw_cell.get("texture", "") or "")[:96],
                        "color": str(raw_cell.get("color", "") or "")[:16],
                        "collidable": bool(raw_cell.get("collidable", tile in {"wall", "stair"})),
                    }
                )
            layer.append(row)
        normalized.append(layer)
    return normalized or _make_blank_layers(map_w, map_h, 1)


def _snapshot_state(editor_state):
    return {
        "map_name": editor_state["map_name"],
        "width": editor_state["width"],
        "height": editor_state["height"],
        "layers": copy.deepcopy(editor_state["layers"]),
        "active_layer": editor_state["active_layer"],
    }


def _restore_state(editor_state, snapshot):
    editor_state["map_name"] = snapshot["map_name"]
    editor_state["width"] = snapshot["width"]
    editor_state["height"] = snapshot["height"]
    editor_state["layers"] = copy.deepcopy(snapshot["layers"])
    editor_state["active_layer"] = max(0, min(snapshot["active_layer"], len(editor_state["layers"]) - 1))
    editor_state["selection"] = set()
    editor_state["selection_rect"] = None
    editor_state["rotate_target"] = None
    editor_state["rotate_dragging"] = False
    editor_state["rotate_undo_started"] = False


def _single_selected_cell(selection):
    return next(iter(selection)) if len(selection) == 1 else None


def _show_small_prompt(parent, title, message, buttons):
    result = {"value": None}
    win = tk.Toplevel(parent)
    win.overrideredirect(True)
    win.transient(parent)
    win.configure(bg=PANE_BG)
    win.attributes("-topmost", True)
    win.geometry(_geometry_string(420, 210, parent.winfo_rootx() + 120, parent.winfo_rooty() + 120))

    shell = tk.Frame(win, bg=PANE_BG, highlightbackground=PANE_BORDER_DARK, highlightthickness=2)
    shell.pack(fill="both", expand=True)
    title_bar = tk.Frame(shell, bg=PANE_TITLE, height=24)
    title_bar.pack(fill="x", padx=8, pady=(8, 0))
    tk.Label(title_bar, text=title, bg=PANE_TITLE, fg="white", font=("Terminal", 10)).pack(side="left", padx=6)
    make_draggable(win, title_bar)

    body = tk.Frame(shell, bg=PANE_BG)
    body.pack(fill="both", expand=True, padx=18, pady=18)
    tk.Label(body, text=message, bg=PANE_BG, fg=PANE_TEXT, font=("Terminal", 12), justify="left", wraplength=360).pack(anchor="w", pady=(0, 22))
    row = tk.Frame(body, bg=PANE_BG)
    row.pack(anchor="e")

    def choose(value):
        result["value"] = value
        try:
            if win.grab_current() == win:
                win.grab_release()
        except tk.TclError:
            pass
        win.destroy()

    for value, label in buttons:
        _section_button(row, label, lambda v=value: choose(v), width=10).pack(side="left", padx=(6, 0))

    def activate_dialog():
        try:
            win.deiconify()
            win.lift(parent)
            win.focus_force()
            win.grab_set()
        except tk.TclError:
            pass

    win.bind("<Escape>", lambda _e: choose(None))
    win.after_idle(activate_dialog)
    win.wait_window()
    return result["value"]


def _show_name_dialog(parent, title, initial_value):
    result = {"value": None}
    win = tk.Toplevel(parent)
    win.overrideredirect(True)
    win.transient(parent)
    win.configure(bg=PANE_BG)
    win.attributes("-topmost", True)
    win.geometry(_geometry_string(420, 190, parent.winfo_rootx() + 140, parent.winfo_rooty() + 130))

    shell = tk.Frame(win, bg=PANE_BG, highlightbackground=PANE_BORDER_DARK, highlightthickness=2)
    shell.pack(fill="both", expand=True)
    title_bar = tk.Frame(shell, bg=PANE_TITLE, height=24)
    title_bar.pack(fill="x", padx=8, pady=(8, 0))
    tk.Label(title_bar, text=title, bg=PANE_TITLE, fg="white", font=("Terminal", 10)).pack(side="left", padx=6)
    make_draggable(win, title_bar)

    body = tk.Frame(shell, bg=PANE_BG)
    body.pack(fill="both", expand=True, padx=18, pady=18)
    tk.Label(body, text="Map Name", bg=PANE_BG, fg=PANE_TEXT, font=("Terminal", 12)).pack(anchor="w")
    value_var = tk.StringVar(value=initial_value)
    entry = tk.Entry(body, textvariable=value_var, font=("Terminal", 12), width=30)
    entry.pack(anchor="w", pady=(8, 18))
    entry.select_range(0, tk.END)
    entry.focus_set()

    row = tk.Frame(body, bg=PANE_BG)
    row.pack(anchor="e")

    def cancel():
        try:
            if win.grab_current() == win:
                win.grab_release()
        except tk.TclError:
            pass
        win.destroy()

    def save():
        name = _sanitize_name(value_var.get())
        if not name:
            return
        result["value"] = name
        try:
            if win.grab_current() == win:
                win.grab_release()
        except tk.TclError:
            pass
        win.destroy()

    _section_button(row, "Cancel", cancel, width=10).pack(side="left", padx=(0, 6))
    _section_button(row, "Save", save, width=10).pack(side="left")
    entry.bind("<Return>", lambda _e: save())

    def activate_dialog():
        try:
            win.deiconify()
            win.lift(parent)
            entry.focus_force()
            win.grab_set()
        except tk.TclError:
            pass

    win.bind("<Escape>", lambda _e: cancel())
    win.after_idle(activate_dialog)
    win.wait_window()
    return result["value"]


def _show_confirm_delete_dialog(parent, object_label, ask_again_default=True):
    result = {"confirmed": False, "ask_again": ask_again_default}
    win = tk.Toplevel(parent)
    win.overrideredirect(True)
    win.transient(parent)
    win.configure(bg=PANE_BG)
    win.attributes("-topmost", True)
    win.geometry(_geometry_string(460, 230, parent.winfo_rootx() + 150, parent.winfo_rooty() + 140))

    shell = tk.Frame(win, bg=PANE_BG, highlightbackground=PANE_BORDER_DARK, highlightthickness=2)
    shell.pack(fill="both", expand=True)
    title_bar = tk.Frame(shell, bg=PANE_TITLE, height=24)
    title_bar.pack(fill="x", padx=8, pady=(8, 0))
    tk.Label(title_bar, text="DELETE OBJECT", bg=PANE_TITLE, fg="white", font=("Terminal", 10)).pack(side="left", padx=6)
    make_draggable(win, title_bar)

    body = tk.Frame(shell, bg=PANE_BG)
    body.pack(fill="both", expand=True, padx=18, pady=18)
    tk.Label(body, text=f"Delete {object_label}?", bg=PANE_BG, fg=PANE_TEXT, font=("Terminal", 12), justify="left", wraplength=390).pack(anchor="w", pady=(0, 14))
    ask_var = tk.BooleanVar(value=ask_again_default)
    tk.Checkbutton(
        body,
        text="Ask before deleting next time",
        variable=ask_var,
        fg=PANE_TEXT,
        bg=PANE_BG,
        selectcolor=PANE_BG,
        activebackground=PANE_BG,
        activeforeground=PANE_TEXT,
        font=("Terminal", 10),
        anchor="w",
    ).pack(anchor="w", pady=(0, 18))
    row = tk.Frame(body, bg=PANE_BG)
    row.pack(anchor="e")

    def close(confirmed):
        result["confirmed"] = confirmed
        result["ask_again"] = bool(ask_var.get())
        try:
            if win.grab_current() == win:
                win.grab_release()
        except tk.TclError:
            pass
        win.destroy()

    _section_button(row, "Cancel", lambda: close(False), width=10).pack(side="left", padx=(0, 6))
    _section_button(row, "Delete", lambda: close(True), width=10).pack(side="left")

    def activate_dialog():
        try:
            win.deiconify()
            win.lift(parent)
            win.focus_force()
            win.grab_set()
        except tk.TclError:
            pass

    win.bind("<Escape>", lambda _e: close(False))
    win.after_idle(activate_dialog)
    win.wait_window()
    return result["confirmed"], result["ask_again"]


def show_level_editor(root, force_new=False):
    existing = getattr(root, "_level_editor_window", None)
    if not force_new and existing is not None and existing.winfo_exists():
        existing.lift()
        return

    ensure_custom_maps_dir()

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg=PANE_BG)
    win.attributes("-topmost", True)
    win.geometry(_geometry_string(WINDOW_SIZE[0], WINDOW_SIZE[1], 180, 90))
    root._level_editor_window = win

    window_bg_source = Image.open(PANE_OS_DIR / "wondiw.png")
    close_idle = tk.PhotoImage(file=str(PANE_OS_DIR / "close1.png"))
    close_hover = tk.PhotoImage(file=str(PANE_OS_DIR / "close2.png"))
    close_pressed = tk.PhotoImage(file=str(PANE_OS_DIR / "close3.png"))

    def render_background(width, height):
        image = window_bg_source.resize((width, height), Image.NEAREST)
        win._window_bg = ImageTk.PhotoImage(image)
        background.config(image=win._window_bg)

    background = tk.Label(win, borderwidth=0, highlightthickness=0)
    background.place(x=0, y=0, relwidth=1, relheight=1)
    render_background(*WINDOW_IMAGE_SIZE)

    title_bar = tk.Frame(win, bg=PANE_TITLE, height=24)
    title_bar.place(x=8, y=8, width=WINDOW_SIZE[0] - 16, height=24)
    title_text_var = tk.StringVar(value="Brerder.exe")
    tk.Label(title_bar, textvariable=title_text_var, bg=PANE_TITLE, fg="white", font=("Terminal", 10)).pack(side="left", padx=6)

    close_btn = tk.Label(title_bar, bg=PANE_TITLE, cursor="hand2", borderwidth=0, highlightthickness=0)
    close_btn.pack(side="right", padx=4, pady=4)

    def set_sprite(widget, sprite):
        widget.config(image=sprite)
        widget.image = sprite

    def bind_sprite_button(widget, sprites, on_click):
        idle, hover, pressed = sprites
        set_sprite(widget, idle)
        widget.bind("<Enter>", lambda _e: set_sprite(widget, hover))
        widget.bind("<Leave>", lambda _e: set_sprite(widget, idle))
        widget.bind("<ButtonPress-1>", lambda _e: set_sprite(widget, pressed))

        def release(event):
            hovered = 0 <= event.x < widget.winfo_width() and 0 <= event.y < widget.winfo_height()
            set_sprite(widget, hover if hovered else idle)
            if hovered:
                on_click()

        widget.bind("<ButtonRelease-1>", release)

    shell = tk.Frame(win, bg=PANE_BG, highlightbackground=PANE_BORDER_DARK, highlightthickness=2)
    shell.place(x=16, y=44, width=WINDOW_SIZE[0] - 32, height=WINDOW_SIZE[1] - 60)

    menu_bar = tk.Frame(shell, bg=PANE_BG_DARK, height=28)
    menu_bar.pack(fill="x", padx=8, pady=(8, 0))

    workspace = tk.Frame(shell, bg=PANE_BG)
    workspace.pack(fill="both", expand=True, padx=8, pady=8)
    sidebar = tk.Frame(workspace, bg=PANE_BG, width=220)
    sidebar.pack(side="left", fill="y", padx=(0, 8))
    content = tk.Frame(workspace, bg=PANE_BG)
    content.pack(side="left", fill="both", expand=True)

    editor_state = {
        "map_name": "Untitled",
        "width": DEFAULT_MAP_W,
        "height": DEFAULT_MAP_H,
        "layers": _make_blank_layers(DEFAULT_MAP_W, DEFAULT_MAP_H, 1),
        "active_layer": 0,
        "selected_tile": "wall",
        "selected_height": 1,
        "selected_rotation": 0.0,
        "active_tool": "paint",
        "dragging": False,
        "panning": False,
        "zoom": 1.0,
        "pan_x": 0.0,
        "pan_y": 0.0,
        "view_mode": "2d",
        "selection": set(),
        "selection_rect": None,
        "rotate_target": None,
        "rotate_dragging": False,
        "rotate_undo_started": False,
        "last_pan_x": 0,
        "last_pan_y": 0,
        "dirty": False,
        "saved_path": None,
        "undo_stack": [],
        "redo_stack": [],
        "camera_x": DEFAULT_MAP_W * 0.5,
        "camera_y": -DEFAULT_MAP_H * 0.75,
        "camera_z": 7.5,
        "camera_yaw": math.radians(58.0),
        "camera_pitch": math.radians(-24.0),
        "orbiting_3d": False,
        "panning_3d": False,
        "pan3d_last_x": 0,
        "pan3d_last_y": 0,
        "orbit_last_x": 0,
        "orbit_last_y": 0,
        "pressed_keys": set(),
        "last_3d_tick": time.perf_counter(),
        "selected_object_id": None,
        "object_orbit_focus": None,
        "last_3d_frame_time": time.perf_counter(),
        "fps_3d": 0.0,
        "confirm_delete_object": True,
        "side_panel_dirty": True,
        "object_cache_dirty": True,
        "object_cache_entries": [],
        "move_gizmo_dragging": False,
        "move_gizmo_axis": None,
        "move_gizmo_remainder": 0.0,
        "resize_gizmo_dragging": False,
        "resize_gizmo_axis": None,
        "resize_gizmo_remainder": 0.0,
        "rotate_gizmo_dragging": False,
        "rotate_gizmo_axis": None,
        "rotate_gizmo_last_angle": 0.0,
    }

    ui = {}
    menus = {"active": None}
    status_var = tk.StringVar(value="Choose File > New Map or File > Open Map.")
    width_var = tk.StringVar(value=str(DEFAULT_MAP_W))
    height_var = tk.StringVar(value=str(DEFAULT_MAP_H))
    layer_count_var = tk.StringVar(value="1")
    tool_var = tk.StringVar(value=editor_state["active_tool"])
    palette_var = tk.StringVar(value=editor_state["selected_tile"])
    rotation_var = tk.StringVar(value="0")
    view_mode_var = tk.StringVar(value=editor_state["view_mode"])
    object_search_var = tk.StringVar(value="")

    def clamp(value, low, high):
        return max(low, min(high, value))

    def mark_side_panel_dirty():
        editor_state["side_panel_dirty"] = True
        editor_state["object_cache_dirty"] = True

    def shade_color(hex_color, factor):
        value = hex_color.lstrip("#")
        if len(value) != 6:
            return hex_color
        factor = max(0.0, factor)
        r = clamp(int(int(value[0:2], 16) * factor), 0, 255)
        g = clamp(int(int(value[2:4], 16) * factor), 0, 255)
        b = clamp(int(int(value[4:6], 16) * factor), 0, 255)
        return f"#{r:02X}{g:02X}{b:02X}"

    def normalize_hex_color(value):
        raw = str(value or "").strip().lstrip("#")
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        if len(raw) != 6:
            return ""
        try:
            int(raw, 16)
        except ValueError:
            return ""
        return f"#{raw.upper()}"

    def reset_3d_camera():
        editor_state["camera_x"] = editor_state["width"] * 0.5
        editor_state["camera_y"] = -max(4.5, editor_state["height"] * 0.7)
        editor_state["camera_z"] = max(6.0, len(editor_state["layers"]) * 1.8 + 3.5)
        editor_state["camera_yaw"] = math.radians(62.0)
        editor_state["camera_pitch"] = math.radians(-26.0)
        editor_state["last_3d_tick"] = time.perf_counter()

    def set_view_mode(mode_id):
        if mode_id not in {"2d", "3d"}:
            return
        editor_state["view_mode"] = mode_id
        view_mode_var.set(mode_id)
        if mode_id == "3d":
            editor_state["pressed_keys"].clear()
            editor_state["last_3d_tick"] = time.perf_counter()
            status_var.set("3D view: WASD fly, arrows look, wheel zoom, MMB orbit.")
        mark_side_panel_dirty()
        if "draw_grid" in ui:
            ui["draw_grid"]()

    def build_object_entries():
        if not editor_state.get("object_cache_dirty", True):
            return list(editor_state.get("object_cache_entries", []))
        entries = []
        counter = 0
        for layer_index, layer in enumerate(editor_state["layers"]):
            base_z = layer_index * 1.0
            for y in range(editor_state["height"]):
                for x in range(editor_state["width"]):
                    cell = layer[y][x]
                    tile = cell["tile"]
                    if tile == "empty":
                        continue
                    scale_z = float(cell.get("scale_z", 1.0))
                    center_x = x + 0.5 + float(cell.get("offset_x", 0.0))
                    center_y = y + 0.5 + float(cell.get("offset_y", 0.0))
                    if tile == "spawn":
                        center_z = base_z + float(cell.get("offset_z", 0.0)) + 0.18
                    else:
                        center_z = base_z + float(cell.get("offset_z", 0.0)) + (cell["height"] * scale_z * 0.5 if tile != "stair" else max(0.35, cell["height"] * scale_z * 0.5))
                    entries.append(
                        {
                            "id": f"{layer_index}:{x}:{y}:{counter}",
                            "layer": layer_index,
                            "x": x,
                            "y": y,
                            "tile": tile,
                            "height": cell["height"],
                            "rotation": cell.get("rotation", 0.0),
                            "rotation_x": cell.get("rotation_x", 0.0),
                            "rotation_y": cell.get("rotation_y", 0.0),
                            "label": f"L{layer_index + 1} {tile} ({x},{y}) h{cell['height']}",
                            "focus": (center_x, center_y, center_z),
                        }
                    )
                    counter += 1
        editor_state["object_cache_entries"] = list(entries)
        editor_state["object_cache_dirty"] = False
        return entries

    def focus_camera_on_object(entry):
        focus_x, focus_y, focus_z = entry["focus"]
        editor_state["object_orbit_focus"] = (focus_x, focus_y, focus_z)
        editor_state["camera_yaw"] = editor_state["camera_yaw"] % (math.pi * 2.0)
        editor_state["camera_pitch"] = clamp(editor_state["camera_pitch"], math.radians(-65.0), math.radians(65.0))
        view_distance = max(2.8, 3.4 + entry["height"] * 0.35)
        dir_x = -math.sin(editor_state["camera_yaw"]) * math.cos(editor_state["camera_pitch"])
        dir_y = math.cos(editor_state["camera_yaw"]) * math.cos(editor_state["camera_pitch"])
        dir_z = math.sin(editor_state["camera_pitch"])
        editor_state["camera_x"] = focus_x - dir_x * view_distance
        editor_state["camera_y"] = focus_y - dir_y * view_distance
        editor_state["camera_z"] = focus_z - dir_z * view_distance + 0.2

    def nudge_camera_to_object(entry):
        focus_x, focus_y, focus_z = entry["focus"]
        editor_state["object_orbit_focus"] = (focus_x, focus_y, focus_z)
        current_dx = editor_state["camera_x"] - focus_x
        current_dy = editor_state["camera_y"] - focus_y
        current_dz = editor_state["camera_z"] - focus_z
        current_dist = math.sqrt(current_dx * current_dx + current_dy * current_dy + current_dz * current_dz)
        target_dist = max(1.8, min(current_dist * 0.6, 3.0))
        dir_x = -math.sin(editor_state["camera_yaw"]) * math.cos(editor_state["camera_pitch"])
        dir_y = math.cos(editor_state["camera_yaw"]) * math.cos(editor_state["camera_pitch"])
        dir_z = math.sin(editor_state["camera_pitch"])
        editor_state["camera_x"] = focus_x - dir_x * target_dist
        editor_state["camera_y"] = focus_y - dir_y * target_dist
        editor_state["camera_z"] = focus_z - dir_z * target_dist + 0.15

    def clear_object_focus():
        editor_state["object_orbit_focus"] = None

    def handle_object_pick(_event=None):
        object_list = ui.get("object_list")
        object_entries = ui.get("filtered_object_entries", ui.get("object_entries", []))
        if object_list is None:
            return
        selected = object_list.curselection()
        if not selected:
            return
        entry = object_entries[selected[0]]
        editor_state["selected_object_id"] = entry["id"]
        editor_state["active_layer"] = entry["layer"]
        editor_state["selection"] = {(entry["x"], entry["y"])}
        editor_state["rotate_target"] = (entry["x"], entry["y"])
        sync_rotation = ui.get("sync_rotation_inputs")
        if sync_rotation is not None:
            sync_rotation(editor_state["layers"][entry["layer"]][entry["y"]][entry["x"]].get("rotation", 0.0))
        focus_camera_on_object(entry)
        mark_side_panel_dirty()
        if "refresh_inspector" in ui:
            ui["refresh_inspector"]()
        if "draw_grid" in ui:
            ui["draw_grid"]()

    def set_selected_object(entry, focus_camera=False, nudge_camera=False):
        if entry is None:
            return False
        editor_state["selected_object_id"] = entry["id"]
        editor_state["active_layer"] = entry["layer"]
        editor_state["selection"] = {(entry["x"], entry["y"])}
        editor_state["rotate_target"] = (entry["x"], entry["y"])
        sync_rotation = ui.get("sync_rotation_inputs")
        if sync_rotation is not None:
            sync_rotation(editor_state["layers"][entry["layer"]][entry["y"]][entry["x"]].get("rotation", 0.0))
        if focus_camera:
            focus_camera_on_object(entry)
        elif nudge_camera:
            nudge_camera_to_object(entry)
        else:
            editor_state["object_orbit_focus"] = entry["focus"]
        mark_side_panel_dirty()
        if "refresh_inspector" in ui:
            ui["refresh_inspector"]()
        return True

    def handle_object_double_click(_event=None):
        object_list = ui.get("object_list")
        object_entries = ui.get("filtered_object_entries", ui.get("object_entries", []))
        if object_list is None:
            return
        selected = object_list.curselection()
        if not selected:
            return
        entry = object_entries[selected[0]]
        editor_state["selected_object_id"] = entry["id"]
        nudge_camera_to_object(entry)
        mark_side_panel_dirty()
        if "draw_grid" in ui:
            ui["draw_grid"]()

    def refresh_object_list():
        object_list = ui.get("object_list")
        if object_list is None:
            return
        entries = build_object_entries()
        ui["object_entries"] = entries
        query = object_search_var.get().strip().lower()
        filtered = []
        object_list.delete(0, tk.END)
        selected_index = None
        for entry in entries:
            if query and query not in entry["label"].lower() and query not in entry["tile"].lower():
                continue
            filtered.append(entry)
        ui["filtered_object_entries"] = filtered
        for index, entry in enumerate(filtered):
            object_list.insert(tk.END, entry["label"])
            if entry["id"] == editor_state.get("selected_object_id"):
                selected_index = index
        if selected_index is not None:
            object_list.selection_set(selected_index)
            object_list.see(selected_index)

    def delete_selected_object(_event=None):
        object_list = ui.get("object_list")
        object_entries = ui.get("filtered_object_entries", ui.get("object_entries", []))
        if object_list is None and editor_state.get("selected_object_id") is None:
            return
        entry = None
        if object_list is not None:
            selected = object_list.curselection()
            if selected:
                entry = object_entries[selected[0]]
        if entry is None:
            selected_id = editor_state.get("selected_object_id")
            if selected_id is not None:
                for candidate in build_object_entries():
                    if candidate["id"] == selected_id:
                        entry = candidate
                        break
        if entry is None:
            delete_selection()
            return
        if editor_state.get("confirm_delete_object", True):
            confirmed, ask_again = _show_confirm_delete_dialog(win, entry["label"], ask_again_default=True)
            editor_state["confirm_delete_object"] = ask_again
            if not confirmed:
                return
        push_undo_snapshot()
        cell = editor_state["layers"][entry["layer"]][entry["y"]][entry["x"]]
        cell["tile"] = "empty"
        cell["height"] = 1
        cell["rotation"] = 0.0
        cell["rotation_x"] = 0.0
        cell["rotation_y"] = 0.0
        cell["has_ceiling"] = True
        cell["scale_x"] = 1.0
        cell["scale_y"] = 1.0
        cell["scale_z"] = 1.0
        cell["offset_x"] = 0.0
        cell["offset_y"] = 0.0
        cell["offset_z"] = 0.0
        cell["texture"] = ""
        cell["color"] = ""
        cell["collidable"] = True
        if entry["layer"] > 0:
            cell["has_floor"] = True
        editor_state["selection"] = set()
        editor_state["rotate_target"] = None
        editor_state["selected_object_id"] = None
        clear_object_focus()
        mark_dirty()
        if "refresh_inspector" in ui:
            ui["refresh_inspector"]()
        if "draw_grid" in ui:
            ui["draw_grid"]()

    def select_object_by_cell(layer_index, gx, gy):
        for entry in build_object_entries():
            if entry["layer"] == layer_index and entry["x"] == gx and entry["y"] == gy:
                editor_state["selected_object_id"] = entry["id"]
                editor_state["object_orbit_focus"] = entry["focus"]
                mark_side_panel_dirty()
                if "refresh_inspector" in ui:
                    ui["refresh_inspector"]()
                return

    def on_key_press(event):
        key = (event.keysym or "").lower()
        if key in {"w", "a", "s", "d", "up", "down"}:
            editor_state["pressed_keys"].add(key)

    def on_key_release(event):
        key = (event.keysym or "").lower()
        editor_state["pressed_keys"].discard(key)

    def world_to_camera(x_pos, y_pos, z_pos):
        rel_x = x_pos - editor_state["camera_x"]
        rel_y = y_pos - editor_state["camera_y"]
        rel_z = z_pos - editor_state["camera_z"]
        yaw = -editor_state["camera_yaw"]
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        cam_x = rel_x * cos_yaw - rel_y * sin_yaw
        cam_y = rel_x * sin_yaw + rel_y * cos_yaw
        pitch = -editor_state["camera_pitch"]
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        cam_y2 = cam_y * cos_pitch - rel_z * sin_pitch
        cam_z = cam_y * sin_pitch + rel_z * cos_pitch
        return cam_x, cam_y2, cam_z

    def project_point(x_pos, y_pos, z_pos):
        cam_x, cam_y, cam_z = world_to_camera(x_pos, y_pos, z_pos)
        if cam_y <= 0.08:
            return None
        focal = GRID_PIXEL_SIZE * 0.9
        sx = GRID_PIXEL_SIZE * 0.5 + (cam_x / cam_y) * focal
        sy = GRID_PIXEL_SIZE * 0.58 - (cam_z / cam_y) * focal
        return sx, sy, cam_y

    def tick_3d_navigation():
        now = time.perf_counter()
        delta = min(0.05, now - editor_state["last_3d_tick"])
        editor_state["last_3d_tick"] = now
        if editor_state["view_mode"] == "3d" and editor_state["pressed_keys"]:
            move_speed = max(2.4, max(editor_state["width"], editor_state["height"]) * 0.16) * delta
            yaw = editor_state["camera_yaw"]
            pitch = editor_state["camera_pitch"]
            forward_x = -math.sin(yaw) * math.cos(pitch)
            forward_y = math.cos(yaw) * math.cos(pitch)
            forward_z = math.sin(pitch)
            right_x = math.cos(yaw)
            right_y = math.sin(yaw)
            move_x = 0.0
            move_y = 0.0
            move_z = 0.0
            if "w" in editor_state["pressed_keys"]:
                move_x += forward_x
                move_y += forward_y
                move_z += forward_z
            if "s" in editor_state["pressed_keys"]:
                move_x -= forward_x
                move_y -= forward_y
                move_z -= forward_z
            if "d" in editor_state["pressed_keys"]:
                move_x += right_x
                move_y += right_y
            if "a" in editor_state["pressed_keys"]:
                move_x -= right_x
                move_y -= right_y
            move_len = math.sqrt(move_x * move_x + move_y * move_y + move_z * move_z)
            if move_len > 1e-6:
                clear_object_focus()
                editor_state["camera_x"] += (move_x / move_len) * move_speed
                editor_state["camera_y"] += (move_y / move_len) * move_speed
                editor_state["camera_z"] += (move_z / move_len) * move_speed
            look_speed = 1.45 * delta
            if "up" in editor_state["pressed_keys"]:
                editor_state["camera_pitch"] = clamp(editor_state["camera_pitch"] + look_speed, math.radians(-80.0), math.radians(80.0))
            if "down" in editor_state["pressed_keys"]:
                editor_state["camera_pitch"] = clamp(editor_state["camera_pitch"] - look_speed, math.radians(-80.0), math.radians(80.0))
            if move_len > 1e-6 or "up" in editor_state["pressed_keys"] or "down" in editor_state["pressed_keys"]:
                if "draw_grid" in ui:
                    ui["draw_grid"]()
        try:
            win.after(16, tick_3d_navigation)
        except tk.TclError:
            return

    def active_cells():
        return editor_state["layers"][editor_state["active_layer"]]

    def is_entity_tile(tile):
        return tile in {"mannequin", "hexagaze", "gun", "bomb"}

    def is_spawn_tile(tile):
        return tile == "spawn"

    def is_locked_transform_tile(tile):
        return is_entity_tile(tile) or is_spawn_tile(tile)

    def update_title():
        dirty_mark = "*" if editor_state["dirty"] else ""
        title_text_var.set(f"Brerder.exe - {editor_state['map_name']}{dirty_mark}")

    def mark_dirty():
        editor_state["dirty"] = True
        update_title()

    def mark_clean():
        editor_state["dirty"] = False
        update_title()

    def refresh_menus():
        update_title()

    def push_undo_snapshot():
        editor_state["undo_stack"].append(_snapshot_state(editor_state))
        if len(editor_state["undo_stack"]) > 80:
            editor_state["undo_stack"] = editor_state["undo_stack"][-80:]
        editor_state["redo_stack"].clear()
        mark_side_panel_dirty()
        refresh_menus()

    def set_new_document(map_name, map_w, map_h, layers, saved_path=None, dirty=False):
        editor_state["map_name"] = map_name
        editor_state["width"] = map_w
        editor_state["height"] = map_h
        editor_state["layers"] = _normalize_layers(copy.deepcopy(layers), map_w, map_h)
        editor_state["active_layer"] = 0
        editor_state["selection"] = set()
        editor_state["selection_rect"] = None
        editor_state["rotate_target"] = None
        editor_state["rotate_dragging"] = False
        editor_state["rotate_undo_started"] = False
        editor_state["zoom"] = 1.0
        editor_state["pan_x"] = 0.0
        editor_state["pan_y"] = 0.0
        reset_3d_camera()
        editor_state["saved_path"] = saved_path
        editor_state["undo_stack"].clear()
        editor_state["redo_stack"].clear()
        mark_side_panel_dirty()
        width_var.set(str(map_w))
        height_var.set(str(map_h))
        if dirty:
            mark_dirty()
        else:
            mark_clean()
        show_editor_page()

    def export_document():
        return {
            "name": editor_state["map_name"],
            "width": editor_state["width"],
            "height": editor_state["height"],
            "layers": editor_state["layers"],
        }

    def save_document(path=None):
        save_path = path or editor_state["saved_path"]
        if save_path is None:
            chosen_name = _show_name_dialog(win, "SAVE MAP", editor_state["map_name"])
            if not chosen_name:
                return False
            save_path = CUSTOM_MAPS_DIR / f"{chosen_name}.json"
            editor_state["map_name"] = chosen_name
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(export_document(), indent=2, ensure_ascii=True), encoding="utf-8")
        editor_state["saved_path"] = save_path
        mark_clean()
        show_editor_page()
        status_var.set(f"Saved {editor_state['map_name']}.")
        return True

    def prompt_save_if_needed():
        if not editor_state["dirty"]:
            return True
        choice = _show_small_prompt(
            win,
            "UNSAVED CHANGES",
            "This map has unsaved changes. Do you want to save before continuing?",
            [("save", "Save"), ("discard", "Dont Save"), ("cancel", "Cancel")],
        )
        if choice == "save":
            return save_document()
        if choice == "discard":
            return True
        return False

    def close_editor():
        if not prompt_save_if_needed():
            return
        win.destroy()

    def undo_action():
        if not editor_state["undo_stack"]:
            return
        editor_state["redo_stack"].append(_snapshot_state(editor_state))
        snapshot = editor_state["undo_stack"].pop()
        _restore_state(editor_state, snapshot)
        width_var.set(str(editor_state["width"]))
        height_var.set(str(editor_state["height"]))
        mark_dirty()
        show_editor_page()

    def redo_action():
        if not editor_state["redo_stack"]:
            return
        editor_state["undo_stack"].append(_snapshot_state(editor_state))
        snapshot = editor_state["redo_stack"].pop()
        _restore_state(editor_state, snapshot)
        width_var.set(str(editor_state["width"]))
        height_var.set(str(editor_state["height"]))
        mark_dirty()
        show_editor_page()

    def rename_map():
        if editor_state["saved_path"] is None:
            status_var.set("Save the map first before renaming.")
            return
        new_name = _show_name_dialog(win, "RENAME MAP", editor_state["map_name"])
        if not new_name:
            return
        new_path = editor_state["saved_path"].with_name(f"{new_name}.json")
        if new_path != editor_state["saved_path"]:
            editor_state["saved_path"].replace(new_path)
        editor_state["saved_path"] = new_path
        editor_state["map_name"] = new_name
        save_document(new_path)
        status_var.set(f"Renamed to {new_name}.")

    def hide_active_menu(_event=None):
        menu = menus.get("active")
        if menu is not None:
            try:
                menu.unpost()
            except tk.TclError:
                pass
            menus["active"] = None

    def build_menu_button(label, item_builder):
        holder = tk.Frame(menu_bar, bg=PANE_BG_DARK)
        holder.pack(side="left", padx=(0, 6))
        btn = tk.Label(holder, text=label, bg=PANE_BG_DARK, fg=PANE_TEXT, font=("Terminal", 11), padx=8, pady=4)
        btn.pack()
        menu = tk.Menu(win, tearoff=False, bg=PANE_BG, fg=PANE_TEXT, activebackground=PANE_ACTIVE, activeforeground=PANE_TEXT, font=("Terminal", 11))

        def show_menu(_event=None):
            hide_active_menu()
            menu.delete(0, tk.END)
            item_builder(menu)
            menu.post(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
            menus["active"] = menu

        btn.bind("<Enter>", show_menu)
        btn.bind("<Button-1>", show_menu)

    def file_menu_items(menu):
        menu.add_command(label="New Map", command=lambda: [hide_active_menu(), show_level_editor(root, force_new=True)])
        menu.add_command(label="Open Map", command=lambda: [hide_active_menu(), open_map_browser()])
        menu.add_command(label="Save Map", command=lambda: [hide_active_menu(), save_document()])
        menu.add_separator()
        menu.add_command(label="Exit", command=lambda: [hide_active_menu(), close_editor()])

    def edit_menu_items(menu):
        menu.add_command(label="Undo", command=lambda: [hide_active_menu(), undo_action()], state=("normal" if editor_state["undo_stack"] else "disabled"))
        menu.add_command(label="Redo", command=lambda: [hide_active_menu(), redo_action()], state=("normal" if editor_state["redo_stack"] else "disabled"))
        menu.add_separator()
        menu.add_command(label="Rename", command=lambda: [hide_active_menu(), rename_map()], state=("normal" if editor_state["saved_path"] is not None else "disabled"))

    def view_menu_items(menu):
        menu.add_command(label="Reset View", command=lambda: [hide_active_menu(), reset_view()])

    build_menu_button("File", file_menu_items)
    build_menu_button("Edit", edit_menu_items)
    build_menu_button("View", view_menu_items)
    shell.bind("<Button-1>", hide_active_menu, add="+")
    workspace.bind("<Button-1>", hide_active_menu, add="+")

    bind_sprite_button(close_btn, (close_idle, close_hover, close_pressed), close_editor)
    make_draggable(win, title_bar)

    def load_builtin_map(module_name, attr_name, display_name):
        module = __import__(module_name)
        map_rows = getattr(module, attr_name)
        map_h = min(MAX_MAP_SIZE, len(map_rows))
        map_w = min(MAX_MAP_SIZE, len(map_rows[0]) if map_rows else 1)
        layers = _make_blank_layers(map_w, map_h, 1)
        char_to_tile = {"#": "wall", "I": "stair", "P": "spawn", "M": "mannequin", "G": "gun", "B": "bomb", "C": "hexagaze", "N": "hexagaze"}
        for y in range(map_h):
            for x in range(map_w):
                layers[0][y][x]["tile"] = char_to_tile.get(map_rows[y][x], "empty")
                layers[0][y][x]["height"] = 1
                layers[0][y][x]["rotation"] = 0.0
                layers[0][y][x]["rotation_x"] = 0.0
                layers[0][y][x]["rotation_y"] = 0.0
                layers[0][y][x]["has_floor"] = True
                layers[0][y][x]["has_ceiling"] = layers[0][y][x]["tile"] != "stair"
                layers[0][y][x]["texture"] = ""
                layers[0][y][x]["color"] = ""
                layers[0][y][x]["collidable"] = layers[0][y][x]["tile"] in {"wall", "stair"}
        set_new_document(display_name, map_w, map_h, layers, saved_path=None, dirty=False)
        status_var.set(f"Loaded {display_name}.")

    def load_custom_map(path):
        data = json.loads(path.read_text(encoding="utf-8"))
        map_w = max(1, min(MAX_MAP_SIZE, _safe_int(data.get("width"), DEFAULT_MAP_W)))
        map_h = max(1, min(MAX_MAP_SIZE, _safe_int(data.get("height"), DEFAULT_MAP_H)))
        layers = _normalize_layers(copy.deepcopy(data.get("layers") or _make_blank_layers(map_w, map_h, 1)), map_w, map_h)
        set_new_document(data.get("name") or path.stem, map_w, map_h, layers, saved_path=path, dirty=False)
        status_var.set(f"Loaded {path.stem}.")

    def start_new_map():
        if not prompt_save_if_needed():
            return
        show_new_page()

    def open_map_browser():
        if not prompt_save_if_needed():
            return
        show_open_page()

    def show_home_page():
        _clear_children(sidebar)
        _clear_children(content)
        tk.Label(sidebar, text="Editor", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 16), anchor="w").pack(fill="x", pady=(6, 14))
        _section_button(sidebar, "Open", open_map_browser).pack(fill="x", pady=(0, 8))
        _section_button(sidebar, "New", start_new_map).pack(fill="x", pady=(0, 8))
        intro = tk.Frame(content, bg=PANE_BG)
        intro.pack(fill="both", expand=True)
        tk.Label(intro, text="DEJAVISION LEVEL EDITOR", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 20)).pack(anchor="w", pady=(18, 12))
        tk.Label(
            intro,
            text="Use File > New Map to create another editor window.\nUse File > Open Map to load built-in or saved custom maps.",
            fg=PANE_TEXT_MUTED,
            bg=PANE_BG,
            justify="left",
            font=("Terminal", 12),
        ).pack(anchor="w")

    def show_open_page():
        _clear_children(sidebar)
        _clear_children(content)
        tk.Label(sidebar, text="Open", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 16), anchor="w").pack(fill="x", pady=(6, 14))
        _section_button(sidebar, "Home", show_home_page).pack(fill="x", pady=(0, 8))
        _section_button(sidebar, "New", start_new_map).pack(fill="x", pady=(0, 8))
        tk.Label(content, text="Open Map", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 18)).pack(anchor="w", pady=(18, 8))
        tk.Label(content, text="Built-in maze maps", fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 11)).pack(anchor="w", pady=(0, 8))

        builtin_frame = tk.Frame(content, bg=PANE_BG)
        builtin_frame.pack(fill="x", pady=(0, 14))
        for label, (module_name, attr_name) in BUILTIN_MAPS.items():
            row = tk.Frame(builtin_frame, bg=PANE_BG)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 12), anchor="w").pack(side="left")
            _section_button(row, "Load", lambda m=module_name, a=attr_name, n=label: load_builtin_map(m, a, n), width=10).pack(side="right")

        tk.Label(content, text="Saved custom maps", fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 11)).pack(anchor="w", pady=(0, 8))
        custom_frame = tk.Frame(content, bg=PANE_BG)
        custom_frame.pack(fill="both", expand=True)
        custom_files = sorted(CUSTOM_MAPS_DIR.glob("*.json"))
        if not custom_files:
            tk.Label(custom_frame, text="No saved custom maps yet.", fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 11)).pack(anchor="w")
        else:
            for path in custom_files:
                row = tk.Frame(custom_frame, bg=PANE_BG)
                row.pack(fill="x", pady=4)
                tk.Label(row, text=path.stem, fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 12), anchor="w").pack(side="left")
                _section_button(row, "Load", lambda p=path: load_custom_map(p), width=10).pack(side="right")

    def create_new_map():
        map_w = max(1, min(MAX_MAP_SIZE, _safe_int(width_var.get(), DEFAULT_MAP_W)))
        map_h = max(1, min(MAX_MAP_SIZE, _safe_int(height_var.get(), DEFAULT_MAP_H)))
        layer_count = max(1, min(MAX_LAYERS, _safe_int(layer_count_var.get(), 1)))
        set_new_document("Untitled", map_w, map_h, _make_blank_layers(map_w, map_h, layer_count), saved_path=None, dirty=False)
        status_var.set(f"Created new {map_w} x {map_h} map with {layer_count} layer(s).")

    def show_new_page():
        _clear_children(sidebar)
        _clear_children(content)
        tk.Label(sidebar, text="New Map", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 16), anchor="w").pack(fill="x", pady=(6, 14))
        _section_button(sidebar, "Home", show_home_page).pack(fill="x", pady=(0, 8))
        _section_button(sidebar, "Open", show_open_page).pack(fill="x", pady=(0, 8))
        tk.Label(content, text="Create New Map", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 18)).pack(anchor="w", pady=(18, 12))
        tk.Label(content, text="Maximum size is 64 x 64.", fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 11)).pack(anchor="w", pady=(0, 16))
        size_row = tk.Frame(content, bg=PANE_BG)
        size_row.pack(anchor="w", pady=(0, 14))
        tk.Label(size_row, text="Width", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 12)).pack(side="left")
        tk.Entry(size_row, textvariable=width_var, width=6, font=("Terminal", 12), justify="center").pack(side="left", padx=(8, 18))
        tk.Label(size_row, text="Height", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 12)).pack(side="left")
        tk.Entry(size_row, textvariable=height_var, width=6, font=("Terminal", 12), justify="center").pack(side="left", padx=(8, 0))
        layers_row = tk.Frame(content, bg=PANE_BG)
        layers_row.pack(anchor="w", pady=(0, 14))
        tk.Label(layers_row, text="Layers", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 12)).pack(side="left")
        tk.Entry(layers_row, textvariable=layer_count_var, width=6, font=("Terminal", 12), justify="center").pack(side="left", padx=(8, 12))
        tk.Label(layers_row, text="1-16 floors, stacked upward", fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 10)).pack(side="left")
        tk.Label(content, text="After creation, the editor shows a Layers bar where you can add, remove and reorder floors.", fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 10)).pack(anchor="w", pady=(0, 12))
        _section_button(content, "Create", create_new_map, width=12).pack(anchor="w")

    def reset_view():
        if editor_state["view_mode"] == "3d":
            reset_3d_camera()
        else:
            editor_state["zoom"] = 1.0
            editor_state["pan_x"] = 0.0
            editor_state["pan_y"] = 0.0
        if "draw_grid" in ui:
            ui["draw_grid"]()

    def show_editor_page():
        _clear_children(sidebar)
        _clear_children(content)
        ui.clear()

        tk.Label(sidebar, text="Palette", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 16), anchor="w").pack(fill="x", pady=(6, 10))
        _section_button(sidebar, "Home", show_home_page).pack(fill="x", pady=(0, 8))
        _section_button(sidebar, "Open", open_map_browser).pack(fill="x", pady=(0, 8))
        _section_button(sidebar, "Save", save_document).pack(fill="x", pady=(0, 10))

        def select_tool(tool_id):
            editor_state["active_tool"] = tool_id
            tool_var.set(tool_id)
            mark_side_panel_dirty()
            if tool_id != "select":
                editor_state["selection"] = set()
                editor_state["selection_rect"] = None
            if tool_id not in {"rotate", "select"}:
                editor_state["rotate_target"] = None
                editor_state["rotate_dragging"] = False
                editor_state["rotate_undo_started"] = False
            elif editor_state["rotate_target"] is None:
                editor_state["rotate_target"] = _single_selected_cell(editor_state["selection"])
            if tool_id != "move":
                editor_state["move_gizmo_dragging"] = False
                editor_state["move_gizmo_axis"] = None
                editor_state["move_gizmo_remainder"] = 0.0
            if tool_id != "resize":
                editor_state["resize_gizmo_dragging"] = False
                editor_state["resize_gizmo_axis"] = None
                editor_state["resize_gizmo_remainder"] = 0.0
            if tool_id != "rotate":
                editor_state["rotate_gizmo_dragging"] = False
                editor_state["rotate_gizmo_axis"] = None
            if editor_state["rotate_target"] is not None:
                gx, gy = editor_state["rotate_target"]
                sync_rotation_inputs(active_cells()[gy][gx].get("rotation", 0.0))
            if "refresh_rotation_ui" in ui:
                ui["refresh_rotation_ui"]()
            ui["draw_grid"]()

        rotation_panel = tk.Frame(sidebar, bg=PANE_BG)
        rotation_label = tk.Label(rotation_panel, text="Degrees", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 12), anchor="w")
        rotation_entry = tk.Entry(rotation_panel, textvariable=rotation_var, width=8, font=("Terminal", 11), justify="center")
        rotation_scale_var = tk.DoubleVar(value=0.0)
        rotation_scale_state = {"syncing": False, "dragging": False, "undo_started": False}
        rotation_scale = tk.Scale(
            rotation_panel,
            from_=0,
            to=360,
            orient="horizontal",
            resolution=1,
            variable=rotation_scale_var,
            length=180,
            showvalue=False,
            troughcolor=PANE_BG_DARK,
            bg=PANE_BG,
            fg=PANE_TEXT,
            activebackground=PANE_ACTIVE,
            highlightthickness=0,
            borderwidth=0,
            sliderlength=18,
            font=("Terminal", 10),
        )

        def sync_rotation_inputs(angle):
            normalized = float(angle) % 360.0
            rotation_scale_state["syncing"] = True
            try:
                editor_state["selected_rotation"] = normalized
                rotation_var.set(str(int(round(normalized)) % 360))
                rotation_scale_var.set(normalized)
            finally:
                rotation_scale_state["syncing"] = False
        ui["sync_rotation_inputs"] = sync_rotation_inputs

        def apply_rotation_value(angle, *, use_undo=False, track_slider=False):
            normalized = float(angle) % 360.0
            sync_rotation_inputs(normalized)
            target = editor_state.get("rotate_target")
            if editor_state["active_tool"] not in {"rotate", "select"} or target is None:
                return False
            gx, gy = target
            cell = active_cells()[gy][gx]
            if abs(cell.get("rotation", 0.0) - normalized) < 0.001:
                return False
            if use_undo:
                if track_slider:
                    if not rotation_scale_state["undo_started"]:
                        push_undo_snapshot()
                        mark_dirty()
                        rotation_scale_state["undo_started"] = True
                else:
                    push_undo_snapshot()
                    mark_dirty()
            rotate_cell(gx, gy, normalized)
            ui["draw_grid"]()
            return True

        def commit_rotation(*_args):
            try:
                angle = float(rotation_var.get())
            except (TypeError, ValueError):
                return
            apply_rotation_value(angle, use_undo=True)

        def on_rotation_scale_change(value):
            if rotation_scale_state["syncing"]:
                return
            try:
                angle = float(value)
            except (TypeError, ValueError):
                return
            apply_rotation_value(angle, use_undo=True, track_slider=True)

        def start_rotation_scale_drag(_event):
            rotation_scale_state["dragging"] = True
            rotation_scale_state["undo_started"] = False

        def stop_rotation_scale_drag(_event):
            rotation_scale_state["dragging"] = False
            rotation_scale_state["undo_started"] = False

        rotation_scale.config(command=on_rotation_scale_change)

        def refresh_rotation_ui():
            if editor_state["active_tool"] in {"rotate", "select"}:
                if not rotation_panel.winfo_ismapped():
                    rotation_panel.pack(fill="x", pady=(12, 4))
                    rotation_label.pack(fill="x", pady=(0, 4))
                    rotation_entry.pack(anchor="w")
                    rotation_scale.pack(fill="x", pady=(8, 0))
            else:
                if rotation_panel.winfo_ismapped():
                    rotation_panel.pack_forget()

        rotation_entry.bind("<Return>", commit_rotation)
        rotation_entry.bind("<FocusOut>", commit_rotation)
        rotation_scale.bind("<ButtonPress-1>", start_rotation_scale_drag)
        rotation_scale.bind("<ButtonRelease-1>", stop_rotation_scale_drag)
        ui["refresh_rotation_ui"] = refresh_rotation_ui
        refresh_rotation_ui()

        palette_var.set(editor_state["selected_tile"])

        def select_tile(tile_id):
            editor_state["selected_tile"] = tile_id
            palette_var.set(tile_id)
            if editor_state["active_tool"] not in {"paint", "erase"}:
                editor_state["active_tool"] = "paint"
                tool_var.set("paint")
                if "refresh_rotation_ui" in ui:
                    ui["refresh_rotation_ui"]()

        palette_grid = tk.Frame(sidebar, bg=PANE_BG)
        palette_grid.pack(fill="x", pady=(0, 10))
        for index, (tile_id, label, _char, color) in enumerate(PALETTE_ITEMS):
            button = tk.Button(
                palette_grid,
                text=label,
                command=lambda t=tile_id: select_tile(t),
                font=("Terminal", 9),
                bg=color,
                fg="#101010",
                activebackground=PANE_ACTIVE,
                activeforeground=PANE_TEXT,
                relief="raised",
                borderwidth=2,
                width=9,
                height=2,
                wraplength=72,
            )
            button.grid(row=index // 3, column=index % 3, padx=2, pady=2, sticky="nsew")
        for column in range(3):
            palette_grid.grid_columnconfigure(column, weight=1)

        tk.Label(sidebar, text="Inspector", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 16), anchor="w").pack(fill="x", pady=(10, 6))
        inspector_frame = tk.Frame(sidebar, bg=PANE_BG_DARK, highlightbackground=PANE_BORDER_DARK, highlightthickness=2)
        inspector_frame.pack(fill="x", pady=(0, 10))

        tk.Label(sidebar, text="Height", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 12), anchor="w").pack(fill="x", pady=(14, 6))
        height_label = tk.Label(sidebar, text=str(editor_state["selected_height"]), fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 11), anchor="e")
        height_label.pack(fill="x")

        def change_height(raw):
            editor_state["selected_height"] = max(1, min(5, int(float(raw))))
            height_label.config(text=str(editor_state["selected_height"]))

        slider = tk.Scale(sidebar, from_=1, to=5, orient="horizontal", command=change_height, showvalue=False, resolution=1, length=170, troughcolor=PANE_BG_DARK, bg=PANE_BG, fg=PANE_TEXT, highlightthickness=0, activebackground=PANE_ACTIVE, font=("Terminal", 10))
        slider.pack(anchor="w")
        slider.set(editor_state["selected_height"])
        tk.Label(sidebar, textvariable=status_var, fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 10), justify="left", wraplength=190, anchor="w").pack(fill="x", pady=(16, 0))

        toolbar = tk.Frame(content, bg=PANE_BG_DARK, highlightbackground=PANE_BORDER_DARK, highlightthickness=2)
        toolbar.pack(fill="x", pady=(8, 8))
        tool_var.set(editor_state["active_tool"])
        for tool_id, label in TOOLS:
            tk.Radiobutton(
                toolbar,
                text=label,
                value=tool_id,
                variable=tool_var,
                command=lambda t=tool_id: select_tool(t),
                fg=PANE_TEXT,
                bg=PANE_BG_DARK,
                selectcolor=PANE_ACTIVE,
                activebackground=PANE_BG_DARK,
                activeforeground=PANE_TEXT,
                font=("Terminal", 11),
                indicatoron=False,
                relief="ridge",
                borderwidth=2,
                padx=12,
                pady=6,
                width=10,
            ).pack(side="left", padx=4, pady=4)
        tk.Label(toolbar, text="Tools", fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10)).pack(side="right", padx=10)

        header = tk.Frame(content, bg=PANE_BG)
        header.pack(fill="x", pady=(0, 8))
        tk.Label(header, text=f"{editor_state['map_name']}  [{editor_state['width']} x {editor_state['height']}]", fg=PANE_TEXT, bg=PANE_BG, font=("Terminal", 18)).pack(side="left")
        header_right = tk.Frame(header, bg=PANE_BG)
        header_right.pack(side="right")
        tk.Label(header_right, text=f"L{editor_state['active_layer'] + 1}/{len(editor_state['layers'])} | 2D: wheel zoom, middle pan | 3D: WASD fly, arrows look, wheel, MMB orbit", fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 10)).pack(side="right", padx=(10, 0))
        mode_switch = tk.Frame(header_right, bg=PANE_BG)
        mode_switch.pack(side="right")
        tk.Label(mode_switch, text="View", fg=PANE_TEXT_MUTED, bg=PANE_BG, font=("Terminal", 10)).pack(side="left", padx=(0, 8))
        for mode_id, label in VIEW_MODES:
            tk.Radiobutton(
                mode_switch,
                text=label,
                value=mode_id,
                variable=view_mode_var,
                command=lambda m=mode_id: set_view_mode(m),
                fg=PANE_TEXT,
                bg=PANE_BG,
                selectcolor=PANE_BG,
                activebackground=PANE_BG,
                activeforeground=PANE_TEXT,
                font=("Terminal", 10),
            ).pack(side="left", padx=(0, 4))

        editor_body = tk.Frame(content, bg=PANE_BG)
        editor_body.pack(fill="both", expand=True, pady=(4, 0))

        board_column = tk.Frame(editor_body, bg=PANE_BG)
        board_column.pack(side="left", anchor="n")
        board_wrap = tk.Frame(board_column, bg=PANE_BG_DARK, highlightbackground=PANE_BORDER_DARK, highlightthickness=2)
        board_wrap.pack(anchor="nw")
        canvas = tk.Canvas(board_wrap, width=GRID_PIXEL_SIZE, height=GRID_PIXEL_SIZE, bg="#202020", highlightthickness=0)
        canvas.pack()

        right_panel = tk.Frame(editor_body, bg=PANE_BG_DARK, highlightbackground=PANE_BORDER_DARK, highlightthickness=2, width=340)
        right_panel.pack(side="left", fill="y", padx=(12, 0))
        right_panel.pack_propagate(False)

        tk.Label(right_panel, text="Layers", fg=PANE_TEXT, bg=PANE_BG_DARK, font=("Terminal", 14), anchor="w").pack(fill="x", padx=10, pady=(10, 8))
        layer_buttons_frame = tk.Frame(right_panel, bg=PANE_BG_DARK)
        layer_buttons_frame.pack(fill="both", expand=True, padx=10)
        layer_tools_frame = tk.Frame(right_panel, bg=PANE_BG_DARK)
        layer_tools_frame.pack(fill="x", padx=10, pady=(8, 6))

        layer_options_row = tk.Frame(right_panel, bg=PANE_BG_DARK)
        layer_options_row.pack(fill="x", padx=10, pady=(4, 6))
        layer_floor_var = tk.BooleanVar(value=True)
        layer_ceiling_var = tk.BooleanVar(value=True)
        tk.Label(right_panel, text="Layers stack upward by 1 floor. Upper layers can hide floor or ceiling for open vertical view.", fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10), justify="left", wraplength=300, anchor="w").pack(fill="x", padx=10, pady=(2, 10))
        tk.Label(right_panel, text="Objects", fg=PANE_TEXT, bg=PANE_BG_DARK, font=("Terminal", 14), anchor="w").pack(fill="x", padx=10, pady=(4, 4))
        object_search_entry = tk.Entry(right_panel, textvariable=object_search_var, font=("Terminal", 10))
        object_search_entry.pack(fill="x", padx=10, pady=(0, 8))
        object_list = tk.Listbox(
            right_panel,
            bg=PANE_BG,
            fg=PANE_TEXT,
            selectbackground=PANE_ACTIVE,
            selectforeground=PANE_TEXT,
            highlightthickness=1,
            highlightbackground=PANE_BORDER_DARK,
            relief="flat",
            font=("Terminal", 9),
            height=10,
        )
        object_list.pack(fill="both", expand=False, padx=10, pady=(0, 10))
        object_list.bind("<<ListboxSelect>>", handle_object_pick)
        object_list.bind("<Double-Button-1>", handle_object_double_click)
        ui["object_list"] = object_list
        ui["object_entries"] = []
        ui["filtered_object_entries"] = []

        char_map = {"empty": "", "stair": "I", **{tile_id: char for tile_id, _label, char, _color in PALETTE_ITEMS}}
        color_map = {"empty": "#141414", "stair": "#89D0A1", **{tile_id: color for tile_id, _label, _char, color in PALETTE_ITEMS}}

        def preview_color_for_cell(cell):
            override = normalize_hex_color(cell.get("color", ""))
            if override:
                return override
            return color_map.get(cell.get("tile", "empty"), "#6A6A6A")

        def get_view_metrics():
            base_cell_size = min(GRID_PIXEL_SIZE / editor_state["width"], GRID_PIXEL_SIZE / editor_state["height"])
            cell_size = base_cell_size * editor_state["zoom"]
            offset_x = (GRID_PIXEL_SIZE - cell_size * editor_state["width"]) / 2 + editor_state["pan_x"]
            offset_y = (GRID_PIXEL_SIZE - cell_size * editor_state["height"]) / 2 + editor_state["pan_y"]
            return cell_size, offset_x, offset_y

        def cell_from_xy(x_pos, y_pos):
            cell_size, offset_x, offset_y = get_view_metrics()
            gx = int((x_pos - offset_x) // cell_size)
            gy = int((y_pos - offset_y) // cell_size)
            return (gx, gy) if 0 <= gx < editor_state["width"] and 0 <= gy < editor_state["height"] else None

        def cell_bounds(gx, gy):
            cell_size, offset_x, offset_y = get_view_metrics()
            x1 = offset_x + gx * cell_size
            y1 = offset_y + gy * cell_size
            return cell_size, x1, y1, x1 + cell_size, y1 + cell_size

        def get_selected_object_entry():
            selected_id = editor_state.get("selected_object_id")
            if selected_id is None:
                return None
            for entry in ui.get("object_entries", []):
                if entry["id"] == selected_id:
                    return entry
            return None

        def get_selected_cell():
            entry = get_selected_object_entry()
            if entry is None:
                return None, None
            return entry, editor_state["layers"][entry["layer"]][entry["y"]][entry["x"]]

        inspector_sync = {"active": False}
        inspector_controls = {}
        inspector_vars = {
            "world_x": tk.StringVar(value=""),
            "world_y": tk.StringVar(value=""),
            "world_z": tk.StringVar(value=""),
            "scale_x": tk.StringVar(value=""),
            "scale_y": tk.StringVar(value=""),
            "scale_z": tk.StringVar(value=""),
            "rot_x": tk.StringVar(value=""),
            "rot_y": tk.StringVar(value=""),
            "rot_z": tk.StringVar(value=""),
            "height": tk.StringVar(value=""),
            "layer": tk.StringVar(value=""),
            "texture": tk.StringVar(value=""),
            "color": tk.StringVar(value=""),
            "collidable": tk.BooleanVar(value=True),
            "has_floor": tk.BooleanVar(value=True),
            "has_ceiling": tk.BooleanVar(value=True),
        }

        def clear_spawn_objects(except_layer=None, except_x=None, except_y=None):
            for layer_index, layer in enumerate(editor_state["layers"]):
                for y in range(editor_state["height"]):
                    for x in range(editor_state["width"]):
                        if layer_index == except_layer and x == except_x and y == except_y:
                            continue
                        if layer[y][x]["tile"] == "spawn":
                            layer[y][x] = copy.deepcopy(_make_blank_cells(1, 1)[0][0])

        def sync_rotation_display_from_cell(cell):
            sync_rotation_inputs(float(cell.get("rotation", 0.0)))

        def move_selected_object_to(dst_layer, dst_x, dst_y):
            entry = get_selected_object_entry()
            if entry is None:
                return False
            src_layer = entry["layer"]
            src_x = entry["x"]
            src_y = entry["y"]
            if src_layer == dst_layer and src_x == dst_x and src_y == dst_y:
                return True
            if not (0 <= dst_layer < len(editor_state["layers"])):
                return False
            if not (0 <= dst_x < editor_state["width"] and 0 <= dst_y < editor_state["height"]):
                return False
            source_cell = editor_state["layers"][src_layer][src_y][src_x]
            target_cell = editor_state["layers"][dst_layer][dst_y][dst_x]
            if target_cell["tile"] != "empty":
                return False
            moved_state = copy.deepcopy(source_cell)
            editor_state["layers"][src_layer][src_y][src_x] = copy.deepcopy(_make_blank_cells(1, 1)[0][0])
            editor_state["layers"][dst_layer][dst_y][dst_x].update(moved_state)
            editor_state["active_layer"] = dst_layer
            editor_state["selection"] = {(dst_x, dst_y)}
            editor_state["rotate_target"] = (dst_x, dst_y)
            select_object_by_cell(dst_layer, dst_x, dst_y)
            moved_entry = get_selected_object_entry()
            if moved_entry is not None:
                editor_state["object_orbit_focus"] = moved_entry["focus"]
            mark_side_panel_dirty()
            return True

        def apply_inspector_position(world_x, world_y, world_z):
            entry, cell = get_selected_cell()
            if entry is None or cell is None:
                return False
            target_x = clamp(world_x, 0.5, editor_state["width"] - 0.5)
            target_y = clamp(world_y, 0.5, editor_state["height"] - 0.5)
            half_height = cell["height"] * float(cell.get("scale_z", 1.0)) * 0.5
            target_base = world_z - half_height
            dst_x = int(math.floor(target_x))
            dst_y = int(math.floor(target_y))
            dst_layer = int(clamp(round(target_base), 0, len(editor_state["layers"]) - 1))
            if not move_selected_object_to(dst_layer, dst_x, dst_y):
                return False
            moved_entry, moved_cell = get_selected_cell()
            if moved_entry is None or moved_cell is None:
                return False
            moved_cell["offset_x"] = round(clamp(target_x - (dst_x + 0.5), -0.49, 0.49), 3)
            moved_cell["offset_y"] = round(clamp(target_y - (dst_y + 0.5), -0.49, 0.49), 3)
            moved_cell["offset_z"] = round(clamp(target_base - dst_layer, -0.95, 0.95), 3)
            editor_state["object_orbit_focus"] = moved_entry["focus"]
            return True

        def refresh_inspector():
            entry, cell = get_selected_cell()
            inspector_sync["active"] = True
            try:
                if entry is None or cell is None:
                    for key, var in inspector_vars.items():
                        if isinstance(var, tk.BooleanVar):
                            var.set(True)
                        else:
                            var.set("")
                    for key, widget in inspector_controls.items():
                        widget.configure(state="normal" if key == "apply" else "disabled")
                    return
                inspector_vars["world_x"].set(f"{entry['focus'][0]:.3f}")
                inspector_vars["world_y"].set(f"{entry['focus'][1]:.3f}")
                inspector_vars["world_z"].set(f"{entry['focus'][2]:.3f}")
                inspector_vars["scale_x"].set(f"{float(cell.get('scale_x', 1.0)):.3f}")
                inspector_vars["scale_y"].set(f"{float(cell.get('scale_y', 1.0)):.3f}")
                inspector_vars["scale_z"].set(f"{float(cell.get('scale_z', 1.0)):.3f}")
                inspector_vars["rot_x"].set(f"{float(cell.get('rotation_x', 0.0)) % 360.0:.1f}")
                inspector_vars["rot_y"].set(f"{float(cell.get('rotation_y', 0.0)) % 360.0:.1f}")
                inspector_vars["rot_z"].set(f"{float(cell.get('rotation', 0.0)) % 360.0:.1f}")
                inspector_vars["height"].set(str(int(cell.get("height", 1))))
                inspector_vars["layer"].set(str(int(entry.get("layer", 0)) + 1))
                inspector_vars["texture"].set(str(cell.get("texture", "") or ""))
                inspector_vars["color"].set(str(cell.get("color", "") or ""))
                inspector_vars["collidable"].set(bool(cell.get("collidable", True)))
                inspector_vars["has_floor"].set(bool(cell.get("has_floor", True)))
                inspector_vars["has_ceiling"].set(bool(cell.get("has_ceiling", True)))
                locked_spawn = is_spawn_tile(cell["tile"])
                allowed_keys = {"world_x", "world_y", "world_z", "apply"}
                for key, widget in inspector_controls.items():
                    widget.configure(state="normal" if (not locked_spawn or key in allowed_keys) else "disabled")
            finally:
                inspector_sync["active"] = False

        def apply_inspector_changes(*_args):
            if inspector_sync["active"]:
                return
            entry, cell = get_selected_cell()
            if entry is None or cell is None:
                return
            try:
                world_x = float(inspector_vars["world_x"].get())
                world_y = float(inspector_vars["world_y"].get())
                world_z = float(inspector_vars["world_z"].get())
                scale_x = clamp(float(inspector_vars["scale_x"].get()), 0.35, 2.5)
                scale_y = clamp(float(inspector_vars["scale_y"].get()), 0.35, 2.5)
                scale_z = clamp(float(inspector_vars["scale_z"].get()), 0.35, 2.5)
                rot_x = float(inspector_vars["rot_x"].get()) % 360.0
                rot_y = float(inspector_vars["rot_y"].get()) % 360.0
                rot_z = float(inspector_vars["rot_z"].get()) % 360.0
                new_height = max(1, min(5, int(float(inspector_vars["height"].get()))))
                new_layer = max(1, min(len(editor_state["layers"]), int(float(inspector_vars["layer"].get()))))
            except (TypeError, ValueError):
                refresh_inspector()
                return
            push_undo_snapshot()
            mark_dirty()
            if new_layer - 1 != entry["layer"]:
                if move_selected_object_to(new_layer - 1, entry["x"], entry["y"]):
                    entry, cell = get_selected_cell()
            if apply_inspector_position(world_x, world_y, world_z):
                entry, cell = get_selected_cell()
            if entry is None or cell is None:
                refresh_inspector()
                return
            if is_spawn_tile(cell["tile"]):
                cell["height"] = 1
                cell["scale_x"] = 1.0
                cell["scale_y"] = 1.0
                cell["scale_z"] = 1.0
                cell["rotation_x"] = 0.0
                cell["rotation_y"] = 0.0
                cell["rotation"] = 0.0
                cell["texture"] = ""
                cell["color"] = ""
                cell["collidable"] = False
                cell["has_floor"] = True
                cell["has_ceiling"] = True
                sync_rotation_display_from_cell(cell)
                mark_side_panel_dirty()
                refresh_inspector()
                draw_grid()
                return
            cell["height"] = new_height
            cell["scale_x"] = round(scale_x, 3)
            cell["scale_y"] = round(scale_y, 3)
            cell["scale_z"] = round(scale_z, 3)
            cell["rotation_x"] = rot_x
            cell["rotation_y"] = rot_y
            cell["rotation"] = rot_z
            cell["texture"] = inspector_vars["texture"].get().strip()[:96]
            cell["color"] = normalize_hex_color(inspector_vars["color"].get())
            cell["collidable"] = bool(inspector_vars["collidable"].get())
            cell["has_floor"] = bool(inspector_vars["has_floor"].get()) if entry["layer"] > 0 else True
            cell["has_ceiling"] = bool(inspector_vars["has_ceiling"].get())
            sync_rotation_display_from_cell(cell)
            mark_side_panel_dirty()
            refresh_inspector()
            draw_grid()

        inspector_body = tk.Frame(inspector_frame, bg=PANE_BG_DARK)
        inspector_body.pack(fill="x", padx=8, pady=8)

        def make_triplet_row(row_index, title, keys):
            tk.Label(inspector_body, text=f"{title}:", fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10), anchor="w").grid(row=row_index, column=0, sticky="w", pady=2)
            col = 1
            for axis_label, key in keys:
                tk.Label(inspector_body, text=axis_label, fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10)).grid(row=row_index, column=col, sticky="e", padx=(6, 2))
                entry_widget = tk.Entry(inspector_body, textvariable=inspector_vars[key], font=("Terminal", 10), width=6, justify="center")
                entry_widget.grid(row=row_index, column=col + 1, sticky="ew", padx=(0, 2))
                entry_widget.bind("<Return>", apply_inspector_changes)
                entry_widget.bind("<FocusOut>", apply_inspector_changes)
                inspector_controls[key] = entry_widget
                col += 2

        def make_pair_row(row_index, title, left_label, left_key, right_label, right_key):
            tk.Label(inspector_body, text=f"{title}:", fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10), anchor="w").grid(row=row_index, column=0, sticky="w", pady=2)
            tk.Label(inspector_body, text=left_label, fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10)).grid(row=row_index, column=1, sticky="e", padx=(6, 2))
            left_entry = tk.Entry(inspector_body, textvariable=inspector_vars[left_key], font=("Terminal", 10), width=6, justify="center")
            left_entry.grid(row=row_index, column=2, sticky="ew", padx=(0, 6))
            left_entry.bind("<Return>", apply_inspector_changes)
            left_entry.bind("<FocusOut>", apply_inspector_changes)
            inspector_controls[left_key] = left_entry
            tk.Label(inspector_body, text=right_label, fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10)).grid(row=row_index, column=3, sticky="e", padx=(6, 2))
            right_entry = tk.Entry(inspector_body, textvariable=inspector_vars[right_key], font=("Terminal", 10), width=6, justify="center")
            right_entry.grid(row=row_index, column=4, sticky="ew", padx=(0, 2))
            right_entry.bind("<Return>", apply_inspector_changes)
            right_entry.bind("<FocusOut>", apply_inspector_changes)
            inspector_controls[right_key] = right_entry

        def make_text_row(row_index, title, key):
            tk.Label(inspector_body, text=f"{title}:", fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10), anchor="w").grid(row=row_index, column=0, sticky="w", pady=2)
            entry_widget = tk.Entry(inspector_body, textvariable=inspector_vars[key], font=("Terminal", 10))
            entry_widget.grid(row=row_index, column=1, columnspan=6, sticky="ew", padx=(6, 0))
            entry_widget.bind("<Return>", apply_inspector_changes)
            entry_widget.bind("<FocusOut>", apply_inspector_changes)
            inspector_controls[key] = entry_widget

        make_triplet_row(0, "Position", (("X", "world_x"), ("Y", "world_y"), ("Z", "world_z")))
        make_triplet_row(1, "Scale", (("X", "scale_x"), ("Y", "scale_y"), ("Z", "scale_z")))
        make_triplet_row(2, "Rotation", (("X", "rot_x"), ("Y", "rot_y"), ("Z", "rot_z")))
        make_pair_row(3, "Shape", "H", "height", "L", "layer")
        make_text_row(4, "Texture", "texture")
        make_text_row(5, "Color", "color")
        flags_row = tk.Frame(inspector_body, bg=PANE_BG_DARK)
        flags_row.grid(row=6, column=0, columnspan=7, sticky="ew", pady=(6, 0))
        for label, key in (("Collision", "collidable"), ("Floor", "has_floor"), ("Ceiling", "has_ceiling")):
            checkbox = tk.Checkbutton(
                flags_row,
                text=label,
                variable=inspector_vars[key],
                command=apply_inspector_changes,
                fg=PANE_TEXT,
                bg=PANE_BG_DARK,
                selectcolor=PANE_BG_DARK,
                activebackground=PANE_BG_DARK,
                activeforeground=PANE_TEXT,
                font=("Terminal", 10),
                anchor="w",
            )
            checkbox.pack(side="left", padx=(0, 8))
            inspector_controls[key] = checkbox
        apply_button = tk.Button(
            inspector_body,
            text="Apply Inspector",
            command=apply_inspector_changes,
            font=("Terminal", 10),
            bg=PANE_BG,
            fg=PANE_TEXT,
            activebackground=PANE_ACTIVE,
            activeforeground=PANE_TEXT,
            relief="raised",
            borderwidth=2,
        )
        apply_button.grid(row=7, column=0, columnspan=7, sticky="ew", pady=(8, 0))
        inspector_controls["apply"] = apply_button
        for col in range(7):
            inspector_body.grid_columnconfigure(col, weight=1 if col in {2, 4, 6} else 0)
        ui["refresh_inspector"] = refresh_inspector

        def wrap_rotation_delta(delta):
            while delta > 180.0:
                delta -= 360.0
            while delta < -180.0:
                delta += 360.0
            return delta

        def move_gizmo_value_delta(axis, pixel_delta):
            if axis == "x":
                return ("offset_x", pixel_delta * 0.014)
            if axis == "y":
                return ("offset_y", pixel_delta * 0.014)
            return ("offset_z", pixel_delta * 0.018)

        def apply_object_offset_cross_cell(entry, key, delta):
            cell = editor_state["layers"][entry["layer"]][entry["y"]][entry["x"]]
            updated = float(cell.get(key, 0.0)) + delta
            if key == "offset_z":
                cell[key] = clamp(updated, -0.95, 0.95)
                return True
            axis_name = "x" if key == "offset_x" else "y"
            while updated > 0.5:
                next_x = entry["x"] + (1 if axis_name == "x" else 0)
                next_y = entry["y"] + (1 if axis_name == "y" else 0)
                if next_x >= editor_state["width"] or next_y >= editor_state["height"]:
                    updated = 0.49
                    break
                if editor_state["layers"][entry["layer"]][next_y][next_x]["tile"] != "empty":
                    updated = 0.49
                    break
                if not move_selected_object_along(axis_name, 1):
                    updated = 0.49
                    break
                entry = get_selected_object_entry()
                if entry is None:
                    return False
                cell = editor_state["layers"][entry["layer"]][entry["y"]][entry["x"]]
                updated -= 1.0
            while updated < -0.5:
                next_x = entry["x"] - (1 if axis_name == "x" else 0)
                next_y = entry["y"] - (1 if axis_name == "y" else 0)
                if next_x < 0 or next_y < 0:
                    updated = -0.49
                    break
                if editor_state["layers"][entry["layer"]][next_y][next_x]["tile"] != "empty":
                    updated = -0.49
                    break
                if not move_selected_object_along(axis_name, -1):
                    updated = -0.49
                    break
                entry = get_selected_object_entry()
                if entry is None:
                    return False
                cell = editor_state["layers"][entry["layer"]][entry["y"]][entry["x"]]
                updated += 1.0
            clamped = clamp(updated, -0.49, 0.49)
            if abs(clamped - float(cell.get(key, 0.0))) < 0.0001:
                return False
            cell[key] = round(clamped, 3)
            return True

        def move_selected_object_smooth(axis, pixel_delta):
            entry = get_selected_object_entry()
            if entry is None:
                return False
            key, delta = move_gizmo_value_delta(axis, pixel_delta)
            moved = apply_object_offset_cross_cell(entry, key, delta)
            moved_entry = get_selected_object_entry()
            if moved and moved_entry is not None:
                editor_state["object_orbit_focus"] = moved_entry["focus"]
                mark_side_panel_dirty()
            return moved

        def get_rotation_axes_for_cell(cell):
            return {
                "x": float(cell.get("rotation_x", 0.0)) % 360.0,
                "y": float(cell.get("rotation_y", 0.0)) % 360.0,
                "z": float(cell.get("rotation", 0.0)) % 360.0,
            }

        def set_rotation_axis_value(cell, axis, value):
            normalized = float(value) % 360.0
            if axis == "x":
                cell["rotation_x"] = normalized
            elif axis == "y":
                cell["rotation_y"] = normalized
            else:
                cell["rotation"] = normalized

        def rotate_selected_object_3d(axis, delta_angle):
            entry, cell = get_selected_cell()
            if entry is None or cell is None or is_locked_transform_tile(cell["tile"]):
                return False
            current = get_rotation_axes_for_cell(cell)[axis]
            updated = (current + delta_angle) % 360.0
            if abs(wrap_rotation_delta(updated - current)) < 0.001:
                return False
            set_rotation_axis_value(cell, axis, updated)
            if axis == "z":
                sync_rotation_inputs(updated)
            mark_side_panel_dirty()
            moved_entry = get_selected_object_entry()
            if moved_entry is not None:
                editor_state["object_orbit_focus"] = moved_entry["focus"]
            return True

        def move_gizmo_hit_axis(x_pos, y_pos):
            for axis, x1, y1, x2, y2 in ui.get("move_gizmo_hits", []):
                min_x = min(x1, x2) - 15
                max_x = max(x1, x2) + 15
                min_y = min(y1, y2) - 15
                max_y = max(y1, y2) + 15
                if min_x <= x_pos <= max_x and min_y <= y_pos <= max_y:
                    return axis
            return None

        def resize_gizmo_hit_axis(x_pos, y_pos):
            for axis, x1, y1, x2, y2 in ui.get("resize_gizmo_hits", []):
                min_x = min(x1, x2) - 16
                max_x = max(x1, x2) + 16
                min_y = min(y1, y2) - 16
                max_y = max(y1, y2) + 16
                if min_x <= x_pos <= max_x and min_y <= y_pos <= max_y:
                    return axis
            return None

        def rotate_gizmo_hit_axis(x_pos, y_pos):
            for axis, cx, cy, radius in ui.get("rotate_gizmo_hits", []):
                distance = math.hypot(x_pos - cx, y_pos - cy)
                if abs(distance - radius) <= 14.0:
                    return axis
            return None

        def move_selected_object_along(axis, direction):
            entry = get_selected_object_entry()
            if entry is None:
                return False
            src_layer = entry["layer"]
            src_x = entry["x"]
            src_y = entry["y"]
            dst_layer = src_layer
            dst_x = src_x
            dst_y = src_y
            if axis == "x":
                dst_x += direction
            elif axis == "y":
                dst_y += direction
            elif axis == "z":
                dst_layer += direction
            if not (0 <= dst_layer < len(editor_state["layers"])):
                return False
            if not (0 <= dst_x < editor_state["width"] and 0 <= dst_y < editor_state["height"]):
                return False
            source_cell = editor_state["layers"][src_layer][src_y][src_x]
            target_cell = editor_state["layers"][dst_layer][dst_y][dst_x]
            if target_cell["tile"] != "empty":
                return False
            moved_tile = source_cell["tile"]
            moved_height = source_cell["height"]
            moved_rotation = source_cell.get("rotation", 0.0)
            moved_rotation_x = source_cell.get("rotation_x", 0.0)
            moved_rotation_y = source_cell.get("rotation_y", 0.0)
            moved_has_floor = source_cell.get("has_floor", True)
            moved_has_ceiling = source_cell.get("has_ceiling", True)
            moved_scale_x = source_cell.get("scale_x", 1.0)
            moved_scale_y = source_cell.get("scale_y", 1.0)
            moved_scale_z = source_cell.get("scale_z", 1.0)
            moved_offset_x = source_cell.get("offset_x", 0.0)
            moved_offset_y = source_cell.get("offset_y", 0.0)
            moved_offset_z = source_cell.get("offset_z", 0.0)
            moved_texture = source_cell.get("texture", "")
            moved_color = source_cell.get("color", "")
            moved_collidable = source_cell.get("collidable", True)
            source_cell["tile"] = "empty"
            source_cell["height"] = 1
            source_cell["rotation"] = 0.0
            source_cell["rotation_x"] = 0.0
            source_cell["rotation_y"] = 0.0
            source_cell["scale_x"] = 1.0
            source_cell["scale_y"] = 1.0
            source_cell["scale_z"] = 1.0
            source_cell["offset_x"] = 0.0
            source_cell["offset_y"] = 0.0
            source_cell["offset_z"] = 0.0
            source_cell["texture"] = ""
            source_cell["color"] = ""
            source_cell["collidable"] = True
            target_cell["tile"] = moved_tile
            target_cell["height"] = moved_height
            target_cell["rotation"] = moved_rotation
            target_cell["rotation_x"] = moved_rotation_x
            target_cell["rotation_y"] = moved_rotation_y
            target_cell["has_floor"] = moved_has_floor
            target_cell["has_ceiling"] = moved_has_ceiling
            target_cell["scale_x"] = moved_scale_x
            target_cell["scale_y"] = moved_scale_y
            target_cell["scale_z"] = moved_scale_z
            target_cell["offset_x"] = moved_offset_x
            target_cell["offset_y"] = moved_offset_y
            target_cell["offset_z"] = moved_offset_z
            target_cell["texture"] = moved_texture
            target_cell["color"] = moved_color
            target_cell["collidable"] = moved_collidable
            editor_state["active_layer"] = dst_layer
            editor_state["selection"] = {(dst_x, dst_y)}
            editor_state["rotate_target"] = (dst_x, dst_y)
            select_object_by_cell(dst_layer, dst_x, dst_y)
            moved_entry = get_selected_object_entry()
            if moved_entry is not None:
                editor_state["object_orbit_focus"] = moved_entry["focus"]
            mark_side_panel_dirty()
            return True

        def resize_selected_object_along(axis, direction):
            entry, cell = get_selected_cell()
            if entry is None or cell is None or is_locked_transform_tile(cell["tile"]):
                return False
            if axis == "x":
                key = "scale_x"
                delta = 0.1
            elif axis == "y":
                key = "scale_y"
                delta = 0.1
            else:
                key = "scale_z"
                delta = 0.1
            current = float(cell.get(key, 1.0))
            updated = clamp(round(current + direction * delta, 2), 0.35, 2.5)
            if abs(updated - current) < 0.001:
                return False
            cell[key] = updated
            mark_side_panel_dirty()
            return True

        def pick_object_in_3d(x_pos, y_pos):
            hit = None
            for candidate in ui.get("pick_candidates", []):
                if candidate["x1"] <= x_pos <= candidate["x2"] and candidate["y1"] <= y_pos <= candidate["y2"]:
                    if hit is None or candidate["depth"] < hit["depth"]:
                        hit = candidate
            if hit is None:
                return None
            for entry in ui.get("object_entries", []):
                if entry["id"] == hit["id"]:
                    return entry
            return None

        def rotation_handle_hit(x_pos, y_pos):
            target = editor_state.get("rotate_target")
            if target is None:
                return False
            gx, gy = target
            cell_size, x1, y1, x2, y2 = cell_bounds(gx, gy)
            cx = (x1 + x2) * 0.5
            cy = (y1 + y2) * 0.5
            angle_rad = math.radians(active_cells()[gy][gx].get("rotation", 0.0))
            handle_len = max(24.0, cell_size * 0.72)
            handle_x = cx + math.cos(angle_rad) * handle_len
            handle_y = cy + math.sin(angle_rad) * handle_len
            radius = max(14.0, cell_size * 0.22)
            if math.hypot(x_pos - handle_x, y_pos - handle_y) <= radius + 4.0:
                return True
            seg_start_x = cx
            seg_start_y = cy
            seg_dx = handle_x - seg_start_x
            seg_dy = handle_y - seg_start_y
            seg_len_sq = max(1.0, seg_dx * seg_dx + seg_dy * seg_dy)
            t = max(0.0, min(1.0, ((x_pos - seg_start_x) * seg_dx + (y_pos - seg_start_y) * seg_dy) / seg_len_sq))
            proj_x = seg_start_x + t * seg_dx
            proj_y = seg_start_y + t * seg_dy
            return math.hypot(x_pos - proj_x, y_pos - proj_y) <= max(10.0, cell_size * 0.16)

        def update_rotation_from_pointer(event_x, event_y):
            target = editor_state.get("rotate_target")
            if target is None:
                return False
            gx, gy = target
            _cell_size, x1, y1, x2, y2 = cell_bounds(gx, gy)
            cx = (x1 + x2) * 0.5
            cy = (y1 + y2) * 0.5
            angle = math.degrees(math.atan2(event_y - cy, event_x - cx)) % 360.0
            sync_rotation_inputs(angle)
            cell = active_cells()[gy][gx]
            if abs(cell.get("rotation", 0.0) - angle) < 0.001:
                return False
            if not editor_state.get("rotate_undo_started"):
                push_undo_snapshot()
                mark_dirty()
                editor_state["rotate_undo_started"] = True
            return rotate_cell(gx, gy, angle)

        def clear_cell(gx, gy):
            active_cells()[gy][gx]["tile"] = "empty"
            active_cells()[gy][gx]["height"] = 1
            active_cells()[gy][gx]["rotation"] = 0.0
            active_cells()[gy][gx]["rotation_x"] = 0.0
            active_cells()[gy][gx]["rotation_y"] = 0.0
            active_cells()[gy][gx]["has_ceiling"] = True
            active_cells()[gy][gx]["scale_x"] = 1.0
            active_cells()[gy][gx]["scale_y"] = 1.0
            active_cells()[gy][gx]["scale_z"] = 1.0
            active_cells()[gy][gx]["offset_x"] = 0.0
            active_cells()[gy][gx]["offset_y"] = 0.0
            active_cells()[gy][gx]["offset_z"] = 0.0
            active_cells()[gy][gx]["texture"] = ""
            active_cells()[gy][gx]["color"] = ""
            active_cells()[gy][gx]["collidable"] = True

        def paint_cell(gx, gy):
            cell = active_cells()[gy][gx]
            new_tile = "empty" if editor_state["active_tool"] == "erase" else editor_state["selected_tile"]
            new_height = 1 if new_tile == "empty" else editor_state["selected_height"]
            new_rotation = editor_state["selected_rotation"] if new_tile == "stair" else 0.0
            new_has_ceiling = cell.get("has_ceiling", True)
            if new_tile == "stair":
                new_has_ceiling = False
            elif new_tile == "empty":
                new_has_ceiling = True
            if cell["tile"] == new_tile and cell["height"] == new_height and abs(cell.get("rotation", 0.0) - new_rotation) < 0.001 and cell.get("has_ceiling", True) == new_has_ceiling:
                return False
            if new_tile == "spawn":
                clear_spawn_objects(except_layer=editor_state["active_layer"], except_x=gx, except_y=gy)
                new_height = 1
                new_rotation = 0.0
                new_has_ceiling = True
            cell["tile"] = new_tile
            cell["height"] = new_height
            cell["rotation"] = new_rotation
            if new_tile == "spawn":
                cell["rotation_x"] = 0.0
                cell["rotation_y"] = 0.0
            cell["has_ceiling"] = new_has_ceiling
            cell["collidable"] = new_tile in {"wall", "stair"}
            if new_tile == "spawn":
                cell["scale_x"] = 1.0
                cell["scale_y"] = 1.0
                cell["scale_z"] = 1.0
                cell["offset_x"] = 0.0
                cell["offset_y"] = 0.0
                cell["offset_z"] = 0.0
                cell["texture"] = ""
                cell["color"] = ""
                cell["collidable"] = False
                cell["has_floor"] = True
            if new_tile == "empty":
                cell["scale_x"] = 1.0
                cell["scale_y"] = 1.0
                cell["scale_z"] = 1.0
                cell["rotation_x"] = 0.0
                cell["rotation_y"] = 0.0
                cell["offset_x"] = 0.0
                cell["offset_y"] = 0.0
                cell["offset_z"] = 0.0
                cell["texture"] = ""
                cell["color"] = ""
                cell["collidable"] = True
            return True

        def create_selected_object_at_origin():
            tile_id = editor_state.get("selected_tile", "wall")
            if tile_id == "empty":
                status_var.set("Choose an object in Palette before adding it in 3D.")
                return False
            target_layer = 0
            target_x = 0
            target_y = 0
            cell = editor_state["layers"][target_layer][target_y][target_x]
            if cell["tile"] != "empty":
                status_var.set("Cell (0, 0, 0) is occupied. Clear it first or move that object.")
                return False
            push_undo_snapshot()
            mark_dirty()
            editor_state["active_layer"] = target_layer
            new_rotation = editor_state["selected_rotation"] if tile_id == "stair" else 0.0
            if tile_id == "spawn":
                clear_spawn_objects(except_layer=target_layer, except_x=target_x, except_y=target_y)
            cell["tile"] = tile_id
            cell["height"] = editor_state["selected_height"]
            cell["rotation"] = new_rotation
            cell["rotation_x"] = 0.0
            cell["rotation_y"] = 0.0
            cell["scale_x"] = 1.0
            cell["scale_y"] = 1.0
            cell["scale_z"] = 1.0
            cell["offset_x"] = 0.0
            cell["offset_y"] = 0.0
            cell["offset_z"] = 0.0
            cell["texture"] = ""
            cell["color"] = ""
            cell["collidable"] = tile_id in {"wall", "stair"}
            cell["has_floor"] = True
            cell["has_ceiling"] = tile_id != "stair"
            if tile_id == "spawn":
                cell["height"] = 1
                cell["rotation"] = 0.0
                cell["scale_x"] = 1.0
                cell["scale_y"] = 1.0
                cell["scale_z"] = 1.0
                cell["collidable"] = False
                cell["has_ceiling"] = True
            mark_side_panel_dirty()
            created_entry = None
            for candidate in build_object_entries():
                if candidate["layer"] == target_layer and candidate["x"] == target_x and candidate["y"] == target_y:
                    created_entry = candidate
                    break
            if created_entry is not None:
                set_selected_object(created_entry, focus_camera=True)
            status_var.set(f"Added {tile_id} at world origin.")
            return created_entry is not None

        def rotate_cell(gx, gy, new_rotation=None):
            cell = active_cells()[gy][gx]
            if cell["tile"] == "empty" or is_spawn_tile(cell["tile"]):
                return False
            new_rotation = editor_state["selected_rotation"] % 360.0 if new_rotation is None else float(new_rotation) % 360.0
            if abs(cell.get("rotation", 0.0) - new_rotation) < 0.001:
                return False
            cell["rotation"] = new_rotation
            return True

        def start_edit_action():
            push_undo_snapshot()
            mark_dirty()
            mark_side_panel_dirty()

        def start_drag(event):
            canvas.focus_set()
            if editor_state["view_mode"] == "3d":
                if editor_state["active_tool"] == "move":
                    hit_axis = move_gizmo_hit_axis(event.x, event.y)
                    if hit_axis is not None:
                        editor_state["move_gizmo_dragging"] = True
                        editor_state["move_gizmo_axis"] = hit_axis
                        editor_state["move_gizmo_remainder"] = 0.0
                        editor_state["pan3d_last_x"] = event.x
                        editor_state["pan3d_last_y"] = event.y
                        push_undo_snapshot()
                        mark_dirty()
                        mark_side_panel_dirty()
                        return
                elif editor_state["active_tool"] == "rotate":
                    hit_axis = rotate_gizmo_hit_axis(event.x, event.y)
                    if hit_axis is not None:
                        selected_entry = get_selected_object_entry()
                        if selected_entry is not None:
                            center = project_point(*selected_entry["focus"])
                            if center is not None:
                                cx, cy, _ = center
                                editor_state["rotate_gizmo_dragging"] = True
                                editor_state["rotate_gizmo_axis"] = hit_axis
                                editor_state["rotate_gizmo_last_angle"] = math.degrees(math.atan2(event.y - cy, event.x - cx))
                                push_undo_snapshot()
                                mark_dirty()
                                mark_side_panel_dirty()
                                return
                elif editor_state["active_tool"] == "resize":
                    hit_axis = resize_gizmo_hit_axis(event.x, event.y)
                    if hit_axis is not None:
                        editor_state["resize_gizmo_dragging"] = True
                        editor_state["resize_gizmo_axis"] = hit_axis
                        editor_state["resize_gizmo_remainder"] = 0.0
                        editor_state["pan3d_last_x"] = event.x
                        editor_state["pan3d_last_y"] = event.y
                        push_undo_snapshot()
                        mark_dirty()
                        mark_side_panel_dirty()
                        return
                picked_entry = pick_object_in_3d(event.x, event.y)
                if picked_entry is not None:
                    if set_selected_object(picked_entry):
                        draw_grid()
                elif editor_state["active_tool"] == "select":
                    if create_selected_object_at_origin():
                        draw_grid()
                return
            editor_state["dragging"] = True
            if editor_state["active_tool"] in {"paint", "erase"}:
                pos = cell_from_xy(event.x, event.y)
                if pos is not None:
                    start_edit_action()
                    paint_cell(pos[0], pos[1])
                    draw_grid()
            elif editor_state["active_tool"] in {"rotate", "select"}:
                pos = cell_from_xy(event.x, event.y)
                if rotation_handle_hit(event.x, event.y):
                    editor_state["rotate_dragging"] = True
                    editor_state["rotate_undo_started"] = False
                    if update_rotation_from_pointer(event.x, event.y):
                        draw_grid()
                    return
                if editor_state["active_tool"] == "rotate" and (pos is not None and editor_state.get("rotate_target") == pos):
                    editor_state["rotate_dragging"] = True
                    editor_state["rotate_undo_started"] = False
                    if update_rotation_from_pointer(event.x, event.y):
                        draw_grid()
                    return
                if pos is not None and active_cells()[pos[1]][pos[0]]["tile"] != "empty":
                    if editor_state["active_tool"] == "rotate":
                        editor_state["rotate_target"] = pos
                        select_object_by_cell(editor_state["active_layer"], pos[0], pos[1])
                        sync_rotation_inputs(active_cells()[pos[1]][pos[0]].get("rotation", 0.0))
                        editor_state["rotate_dragging"] = True
                        editor_state["rotate_undo_started"] = False
                        if update_rotation_from_pointer(event.x, event.y):
                            draw_grid()
                        else:
                            draw_grid()
                    else:
                        editor_state["selection"] = {pos}
                        editor_state["rotate_target"] = pos
                        select_object_by_cell(editor_state["active_layer"], pos[0], pos[1])
                        sync_rotation_inputs(active_cells()[pos[1]][pos[0]].get("rotation", 0.0))
                        draw_grid()
                elif editor_state["active_tool"] == "rotate":
                    editor_state["rotate_target"] = None
                    draw_grid()
            elif editor_state["active_tool"] == "select":
                pos = cell_from_xy(event.x, event.y)
                if pos is not None:
                    editor_state["selection_rect"] = (pos[0], pos[1], pos[0], pos[1])
                    draw_grid()
            elif editor_state["active_tool"] == "move":
                editor_state["panning"] = True
                editor_state["last_pan_x"] = event.x
                editor_state["last_pan_y"] = event.y

        def drag(event):
            if editor_state["view_mode"] == "3d":
                if editor_state["move_gizmo_dragging"]:
                    axis = editor_state.get("move_gizmo_axis")
                    delta = event.x - editor_state["pan3d_last_x"] if axis in {"x", "y"} else editor_state["pan3d_last_y"] - event.y
                    editor_state["pan3d_last_x"] = event.x
                    editor_state["pan3d_last_y"] = event.y
                    if move_selected_object_smooth(axis, delta):
                        draw_grid()
                elif editor_state["rotate_gizmo_dragging"]:
                    selected_entry = get_selected_object_entry()
                    if selected_entry is None:
                        return
                    center = project_point(*selected_entry["focus"])
                    if center is None:
                        return
                    cx, cy, _ = center
                    current_angle = math.degrees(math.atan2(event.y - cy, event.x - cx))
                    delta_angle = wrap_rotation_delta(current_angle - editor_state.get("rotate_gizmo_last_angle", current_angle))
                    editor_state["rotate_gizmo_last_angle"] = current_angle
                    axis = editor_state.get("rotate_gizmo_axis")
                    if axis is not None and rotate_selected_object_3d(axis, delta_angle):
                        draw_grid()
                elif editor_state["resize_gizmo_dragging"]:
                    axis = editor_state.get("resize_gizmo_axis")
                    delta = event.x - editor_state["pan3d_last_x"] if axis in {"x", "y"} else editor_state["pan3d_last_y"] - event.y
                    editor_state["pan3d_last_x"] = event.x
                    editor_state["pan3d_last_y"] = event.y
                    editor_state["resize_gizmo_remainder"] += delta
                    threshold = 18.0
                    changed = False
                    while editor_state["resize_gizmo_remainder"] >= threshold:
                        if resize_selected_object_along(axis, 1):
                            changed = True
                        editor_state["resize_gizmo_remainder"] -= threshold
                    while editor_state["resize_gizmo_remainder"] <= -threshold:
                        if resize_selected_object_along(axis, -1):
                            changed = True
                        editor_state["resize_gizmo_remainder"] += threshold
                    if changed:
                        draw_grid()
                return
            if editor_state["active_tool"] in {"paint", "erase"} and editor_state["dragging"]:
                pos = cell_from_xy(event.x, event.y)
                if pos is not None and paint_cell(pos[0], pos[1]):
                    draw_grid()
            elif editor_state["active_tool"] in {"rotate", "select"} and editor_state.get("rotate_dragging"):
                if update_rotation_from_pointer(event.x, event.y):
                    draw_grid()
            elif editor_state["active_tool"] == "select" and editor_state["selection_rect"] is not None:
                pos = cell_from_xy(event.x, event.y)
                if pos is not None:
                    x1, y1, _x2, _y2 = editor_state["selection_rect"]
                    editor_state["selection_rect"] = (x1, y1, pos[0], pos[1])
                    draw_grid()
            elif editor_state["active_tool"] == "move" and editor_state["panning"]:
                editor_state["pan_x"] += event.x - editor_state["last_pan_x"]
                editor_state["pan_y"] += event.y - editor_state["last_pan_y"]
                editor_state["last_pan_x"] = event.x
                editor_state["last_pan_y"] = event.y
                draw_grid()

        def stop_drag(_event):
            if editor_state["view_mode"] == "3d":
                editor_state["dragging"] = False
                editor_state["move_gizmo_dragging"] = False
                editor_state["move_gizmo_axis"] = None
                editor_state["move_gizmo_remainder"] = 0.0
                editor_state["rotate_gizmo_dragging"] = False
                editor_state["rotate_gizmo_axis"] = None
                editor_state["resize_gizmo_dragging"] = False
                editor_state["resize_gizmo_axis"] = None
                editor_state["resize_gizmo_remainder"] = 0.0
                return
            if editor_state["active_tool"] == "select" and editor_state["selection_rect"] is not None:
                x1, y1, x2, y2 = editor_state["selection_rect"]
                min_x, max_x = sorted((x1, x2))
                min_y, max_y = sorted((y1, y2))
                editor_state["selection"] = {(x, y) for y in range(min_y, max_y + 1) for x in range(min_x, max_x + 1) if active_cells()[y][x]["tile"] != "empty"}
                editor_state["rotate_target"] = _single_selected_cell(editor_state["selection"])
                if editor_state["rotate_target"] is not None:
                    gx, gy = editor_state["rotate_target"]
                    select_object_by_cell(editor_state["active_layer"], gx, gy)
                    sync_rotation_inputs(active_cells()[gy][gx].get("rotation", 0.0))
                editor_state["selection_rect"] = None
                draw_grid()
            editor_state["dragging"] = False
            editor_state["panning"] = False
            editor_state["rotate_dragging"] = False
            editor_state["rotate_undo_started"] = False

        def start_middle_pan(event):
            canvas.focus_set()
            if editor_state["view_mode"] == "3d":
                editor_state["orbiting_3d"] = True
                editor_state["orbit_last_x"] = event.x
                editor_state["orbit_last_y"] = event.y
                return
            editor_state["panning"] = True
            editor_state["last_pan_x"] = event.x
            editor_state["last_pan_y"] = event.y

        def middle_pan(event):
            if editor_state["view_mode"] == "3d":
                if not editor_state["orbiting_3d"]:
                    return
                dx = event.x - editor_state["orbit_last_x"]
                dy = event.y - editor_state["orbit_last_y"]
                editor_state["orbit_last_x"] = event.x
                editor_state["orbit_last_y"] = event.y
                editor_state["camera_yaw"] = (editor_state["camera_yaw"] + dx * 0.012) % (math.pi * 2.0)
                editor_state["camera_pitch"] = clamp(editor_state["camera_pitch"] - dy * 0.008, math.radians(-80.0), math.radians(80.0))
                focus = editor_state.get("object_orbit_focus")
                if focus is not None:
                    focus_x, focus_y, focus_z = focus
                    dist_x = editor_state["camera_x"] - focus_x
                    dist_y = editor_state["camera_y"] - focus_y
                    dist_z = editor_state["camera_z"] - focus_z
                    orbit_dist = max(1.8, math.sqrt(dist_x * dist_x + dist_y * dist_y + dist_z * dist_z))
                    dir_x = -math.sin(editor_state["camera_yaw"]) * math.cos(editor_state["camera_pitch"])
                    dir_y = math.cos(editor_state["camera_yaw"]) * math.cos(editor_state["camera_pitch"])
                    dir_z = math.sin(editor_state["camera_pitch"])
                    editor_state["camera_x"] = focus_x - dir_x * orbit_dist
                    editor_state["camera_y"] = focus_y - dir_y * orbit_dist
                    editor_state["camera_z"] = focus_z - dir_z * orbit_dist
                draw_grid()
                return
            if not editor_state["panning"]:
                return
            editor_state["pan_x"] += event.x - editor_state["last_pan_x"]
            editor_state["pan_y"] += event.y - editor_state["last_pan_y"]
            editor_state["last_pan_x"] = event.x
            editor_state["last_pan_y"] = event.y
            draw_grid()

        def stop_middle_pan(_event):
            editor_state["orbiting_3d"] = False
            editor_state["panning"] = False

        def handle_zoom(event):
            if editor_state["view_mode"] == "3d":
                delta_sign = 1 if getattr(event, "delta", 0) > 0 else -1
                zoom_step = max(0.5, max(editor_state["width"], editor_state["height"]) * 0.08)
                dir_x = -math.sin(editor_state["camera_yaw"]) * math.cos(editor_state["camera_pitch"])
                dir_y = math.cos(editor_state["camera_yaw"]) * math.cos(editor_state["camera_pitch"])
                dir_z = math.sin(editor_state["camera_pitch"])
                editor_state["camera_x"] += dir_x * zoom_step * delta_sign
                editor_state["camera_y"] += dir_y * zoom_step * delta_sign
                editor_state["camera_z"] += dir_z * zoom_step * delta_sign
                draw_grid()
                return
            zoom_mul = 1.12 if getattr(event, "delta", 0) > 0 else (1 / 1.12)
            old_zoom = editor_state["zoom"]
            new_zoom = max(0.4, min(4.5, old_zoom * zoom_mul))
            if abs(new_zoom - old_zoom) < 0.0001:
                return
            cell_size, offset_x, offset_y = get_view_metrics()
            world_x = (event.x - offset_x) / max(1e-6, cell_size)
            world_y = (event.y - offset_y) / max(1e-6, cell_size)
            editor_state["zoom"] = new_zoom
            new_cell_size, _, _ = get_view_metrics()
            editor_state["pan_x"] = event.x - ((GRID_PIXEL_SIZE - editor_state["width"] * new_cell_size) / 2 + world_x * new_cell_size)
            editor_state["pan_y"] = event.y - ((GRID_PIXEL_SIZE - editor_state["height"] * new_cell_size) / 2 + world_y * new_cell_size)
            draw_grid()

        def delete_selection(_event=None):
            if not editor_state["selection"]:
                return
            start_edit_action()
            for gx, gy in list(editor_state["selection"]):
                clear_cell(gx, gy)
            editor_state["selection"] = set()
            editor_state["rotate_target"] = None
            editor_state["selected_object_id"] = None
            clear_object_focus()
            draw_grid()

        def set_active_layer(index):
            editor_state["active_layer"] = index
            editor_state["selection"] = set()
            editor_state["rotate_target"] = None
            editor_state["selected_object_id"] = None
            mark_side_panel_dirty()
            show_editor_page()

        def active_layer_settings():
            return editor_state["layers"][editor_state["active_layer"]][0][0]

        def apply_layer_flags():
            layer_index = editor_state["active_layer"]
            allow_floor = layer_index > 0
            new_floor = True if not allow_floor else bool(layer_floor_var.get())
            new_ceiling = bool(layer_ceiling_var.get())
            changed = any(
                cell["has_floor"] != new_floor or cell["has_ceiling"] != new_ceiling
                for row in editor_state["layers"][layer_index]
                for cell in row
            )
            if not changed:
                return
            push_undo_snapshot()
            changed = False
            for row in editor_state["layers"][layer_index]:
                for cell in row:
                    if cell["has_floor"] != new_floor or cell["has_ceiling"] != new_ceiling:
                        cell["has_floor"] = new_floor
                        cell["has_ceiling"] = new_ceiling
                        changed = True
            if changed:
                mark_dirty()
                mark_side_panel_dirty()
                draw_grid()

        def sync_layer_options():
            flags = active_layer_settings()
            layer_floor_var.set(flags.get("has_floor", True))
            layer_ceiling_var.set(flags.get("has_ceiling", True))

        def add_layer():
            if len(editor_state["layers"]) >= MAX_LAYERS:
                status_var.set("Layer limit reached (16).")
                return
            push_undo_snapshot()
            editor_state["layers"].append(_make_blank_cells(editor_state["width"], editor_state["height"]))
            editor_state["active_layer"] = len(editor_state["layers"]) - 1
            mark_dirty()
            mark_side_panel_dirty()
            show_editor_page()
            status_var.set(f"Added layer {editor_state['active_layer'] + 1}.")

        def remove_layer():
            if len(editor_state["layers"]) <= 1 or editor_state["active_layer"] == 0:
                status_var.set("Base layer cannot be removed.")
                return
            push_undo_snapshot()
            editor_state["layers"].pop(editor_state["active_layer"])
            editor_state["active_layer"] = max(0, min(editor_state["active_layer"], len(editor_state["layers"]) - 1))
            mark_dirty()
            mark_side_panel_dirty()
            show_editor_page()

        def move_layer(step):
            current = editor_state["active_layer"]
            target = current + step
            if current == 0 or target <= 0 or target >= len(editor_state["layers"]):
                return
            push_undo_snapshot()
            layers = editor_state["layers"]
            layers[current], layers[target] = layers[target], layers[current]
            editor_state["active_layer"] = target
            mark_dirty()
            mark_side_panel_dirty()
            show_editor_page()

        def draw_layers_bar():
            _clear_children(layer_buttons_frame)
            _clear_children(layer_tools_frame)
            for idx in range(len(editor_state["layers"])):
                active = idx == editor_state["active_layer"]
                tk.Button(
                    layer_buttons_frame,
                    text=f"Layer {idx + 1}",
                    command=lambda i=idx: set_active_layer(i),
                    font=("Terminal", 10),
                    bg="#87aafc" if active else PANE_BG,
                    fg="black" if active else PANE_TEXT,
                    activebackground=PANE_ACTIVE,
                    activeforeground=PANE_TEXT,
                    relief="raised",
                    borderwidth=2,
                    anchor="w",
                    padx=10,
                ).pack(fill="x", pady=(0, 4))
            for text, command in (("+", add_layer), ("-", remove_layer), ("^", lambda: move_layer(-1)), ("v", lambda: move_layer(1))):
                tk.Button(layer_tools_frame, text=text, command=command, font=("Terminal", 10), width=3, bg=PANE_BG, fg=PANE_TEXT, activebackground=PANE_ACTIVE, activeforeground=PANE_TEXT, relief="raised", borderwidth=2).pack(side="left", padx=(0 if text == "+" else 4, 0))

            _clear_children(layer_options_row)
            tk.Label(layer_options_row, text=f"Active L{editor_state['active_layer'] + 1}", fg=PANE_TEXT_MUTED, bg=PANE_BG_DARK, font=("Terminal", 10), anchor="w").pack(fill="x", pady=(0, 6))
            floor_cb = tk.Checkbutton(
                layer_options_row,
                text="Floor",
                variable=layer_floor_var,
                command=apply_layer_flags,
                fg=PANE_TEXT,
                bg=PANE_BG_DARK,
                selectcolor=PANE_BG_DARK,
                activebackground=PANE_BG_DARK,
                activeforeground=PANE_TEXT,
                font=("Terminal", 10),
                anchor="w",
            )
            floor_cb.pack(fill="x")
            if editor_state["active_layer"] == 0:
                floor_cb.config(state="disabled")
            tk.Checkbutton(
                layer_options_row,
                text="Ceiling",
                variable=layer_ceiling_var,
                command=apply_layer_flags,
                fg=PANE_TEXT,
                bg=PANE_BG_DARK,
                selectcolor=PANE_BG_DARK,
                activebackground=PANE_BG_DARK,
                activeforeground=PANE_TEXT,
                font=("Terminal", 10),
                anchor="w",
            ).pack(fill="x")
            sync_layer_options()
            refresh_object_list()
            refresh_inspector()
            editor_state["side_panel_dirty"] = False

        object_search_entry.bind("<KeyRelease>", lambda _e: refresh_object_list())

        def draw_grid():
            canvas.delete("all")
            if editor_state["view_mode"] == "3d":
                now = time.perf_counter()
                frame_delta = max(1e-6, now - editor_state["last_3d_frame_time"])
                editor_state["last_3d_frame_time"] = now
                current_fps = 1.0 / frame_delta
                if editor_state["fps_3d"] <= 0.0:
                    editor_state["fps_3d"] = current_fps
                else:
                    editor_state["fps_3d"] = editor_state["fps_3d"] * 0.84 + current_fps * 0.16
                canvas.create_rectangle(0, 0, GRID_PIXEL_SIZE, GRID_PIXEL_SIZE, fill="#111417", outline="")
                canvas.create_rectangle(0, GRID_PIXEL_SIZE * 0.58, GRID_PIXEL_SIZE, GRID_PIXEL_SIZE, fill="#191D22", outline="")
                faces = []
                ui["move_gizmo_hits"] = []
                ui["resize_gizmo_hits"] = []
                ui["rotate_gizmo_hits"] = []
                ui["pick_candidates"] = []
                selected_object_id = editor_state.get("selected_object_id")
                object_entries = build_object_entries()
                ui["object_entries"] = object_entries
                object_lookup = {(entry["layer"], entry["x"], entry["y"]): entry for entry in object_entries}

                def add_face(points3d, fill, outline, width=1):
                    projected = []
                    depth_accum = 0.0
                    for px, py, pz in points3d:
                        projected_point = project_point(px, py, pz)
                        if projected_point is None:
                            return
                        sx, sy, depth = projected_point
                        projected.extend((sx, sy))
                        depth_accum += depth
                    faces.append((depth_accum / max(1, len(points3d)), projected, fill, outline, width))

                def rotate_point_around_center(point, center, cell):
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

                def get_object_center(x_pos, y_pos, base_z, cell, tile):
                    scale_z = float(cell.get("scale_z", 1.0))
                    center_x = x_pos + 0.5 + float(cell.get("offset_x", 0.0))
                    center_y = y_pos + 0.5 + float(cell.get("offset_y", 0.0))
                    if tile == "spawn":
                        center_z = base_z + float(cell.get("offset_z", 0.0)) + 0.18
                    else:
                        center_z = base_z + float(cell.get("offset_z", 0.0)) + (cell["height"] * scale_z * 0.5 if tile != "stair" else max(0.35, cell["height"] * scale_z * 0.5))
                    return center_x, center_y, center_z

                def get_box_corners(x_pos, y_pos, base_z, cell):
                    scale_x = float(cell.get("scale_x", 1.0))
                    scale_y = float(cell.get("scale_y", 1.0))
                    scale_z = float(cell.get("scale_z", 1.0))
                    half_x = 0.5 * scale_x
                    half_y = 0.5 * scale_y
                    center_x = x_pos + 0.5 + float(cell.get("offset_x", 0.0))
                    center_y = y_pos + 0.5 + float(cell.get("offset_y", 0.0))
                    base_floor = base_z + float(cell.get("offset_z", 0.0))
                    min_x = center_x - half_x
                    max_x = center_x + half_x
                    min_y = center_y - half_y
                    max_y = center_y + half_y
                    max_z = base_floor + cell["height"] * scale_z
                    center = (center_x, center_y, base_floor + cell["height"] * scale_z * 0.5)
                    corners = [
                        (min_x, min_y, base_floor), (max_x, min_y, base_floor), (max_x, max_y, base_floor), (min_x, max_y, base_floor),
                        (min_x, min_y, max_z), (max_x, min_y, max_z), (max_x, max_y, max_z), (min_x, max_y, max_z),
                    ]
                    return [rotate_point_around_center(point, center, cell) for point in corners], center

                def add_pick_candidate(entry, corners):
                    projected = [project_point(*point) for point in corners]
                    projected = [point for point in projected if point is not None]
                    if not projected:
                        return
                    xs = [point[0] for point in projected]
                    ys = [point[1] for point in projected]
                    depths = [point[2] for point in projected]
                    ui["pick_candidates"].append(
                        {
                            "id": entry["id"],
                            "x1": min(xs) - 10,
                            "y1": min(ys) - 10,
                            "x2": max(xs) + 10,
                            "y2": max(ys) + 10,
                            "depth": min(depths),
                        }
                    )

                def add_box(x_pos, y_pos, base_z, cell, fill):
                    corners, _center = get_box_corners(x_pos, y_pos, base_z, cell)
                    bottom = (corners[0], corners[1], corners[2], corners[3])
                    top = (corners[4], corners[5], corners[6], corners[7])
                    back = (corners[0], corners[1], corners[5], corners[4])
                    left = (corners[0], corners[3], corners[7], corners[4])
                    front = (corners[3], corners[2], corners[6], corners[7])
                    side = (corners[1], corners[2], corners[6], corners[5])
                    add_face(bottom, shade_color(fill, 0.46), "#171717")
                    add_face(back, shade_color(fill, 0.64), "#1B1B1B")
                    add_face(left, shade_color(fill, 0.54), "#1B1B1B")
                    add_face(front, shade_color(fill, 0.72), "#1B1B1B")
                    add_face(side, shade_color(fill, 0.58), "#1B1B1B")
                    add_face(top, shade_color(fill, 1.05), "#2A2A2A")

                def add_horizontal_face(x_pos, y_pos, z_pos, fill, outline):
                    add_face(
                        (
                            (x_pos, y_pos, z_pos),
                            (x_pos + 1.0, y_pos, z_pos),
                            (x_pos + 1.0, y_pos + 1.0, z_pos),
                            (x_pos, y_pos + 1.0, z_pos),
                        ),
                        fill,
                        outline,
                    )

                def add_stair(x_pos, y_pos, base_z, cell, fill):
                    scale_x = float(cell.get("scale_x", 1.0))
                    scale_y = float(cell.get("scale_y", 1.0))
                    scale_z = float(cell.get("scale_z", 1.0))
                    height = cell["height"] * scale_z
                    center_x = x_pos + 0.5 + float(cell.get("offset_x", 0.0))
                    center_y = y_pos + 0.5 + float(cell.get("offset_y", 0.0))
                    floor_z = base_z + float(cell.get("offset_z", 0.0))
                    min_x = center_x - 0.5 * scale_x
                    max_x = center_x + 0.5 * scale_x
                    min_y = center_y - 0.5 * scale_y
                    max_y = center_y + 0.5 * scale_y
                    rotation = cell.get("rotation", 0.0)
                    angle = math.radians(rotation % 360.0)
                    dir_x = math.cos(angle)
                    dir_y = math.sin(angle)
                    raw_corners = [
                        [min_x, min_y, 0.0 * dir_x + 0.0 * dir_y],
                        [max_x, min_y, scale_x * dir_x + 0.0 * dir_y],
                        [max_x, max_y, scale_x * dir_x + scale_y * dir_y],
                        [min_x, max_y, 0.0 * dir_x + scale_y * dir_y],
                    ]
                    dot_min = min(item[2] for item in raw_corners)
                    dot_max = max(item[2] for item in raw_corners)
                    dot_range = max(1e-6, dot_max - dot_min)
                    top = []
                    low = []
                    high = []
                    for cx, cy, dot in raw_corners:
                        cz = floor_z + ((dot - dot_min) / dot_range) * height
                        point = rotate_point_around_center((cx, cy, cz), (center_x, center_y, floor_z + height * 0.5), cell)
                        top.append(point)
                        if abs(cz - floor_z) < 1e-6:
                            low.append(point)
                        if abs(cz - (floor_z + height)) < 1e-6:
                            high.append(point)
                    add_face(top, shade_color(fill, 1.04), "#26402D")
                    if len(low) == 2:
                        add_face((low[0], low[1], (low[1][0], low[1][1], floor_z), (low[0][0], low[0][1], floor_z)), shade_color(fill, 0.62), "#1B1B1B")
                    if len(high) == 2:
                        add_face(((high[0][0], high[0][1], floor_z), (high[1][0], high[1][1], floor_z), high[1], high[0]), shade_color(fill, 0.78), "#1B1B1B")

                for layer_index, layer in enumerate(editor_state["layers"]):
                    base_z = layer_index * 1.0
                    for y in range(editor_state["height"]):
                        for x in range(editor_state["width"]):
                            cell = layer[y][x]
                            tile = cell["tile"]
                            if cell.get("has_floor", True):
                                add_horizontal_face(x, y, base_z, "#20252B", "#2B3138")
                            if cell.get("has_ceiling", tile != "stair"):
                                add_horizontal_face(x, y, base_z + 1.0, "#171C20", "#242B31")
                            if tile == "empty":
                                continue
                            fill = preview_color_for_cell(cell)
                            entry = object_lookup.get((layer_index, x, y))
                            if entry is not None and entry["id"] == selected_object_id:
                                fill = "#FFD84D"
                            if tile == "stair":
                                center_x, center_y, center_z = get_object_center(x, y, base_z, cell, tile)
                                corners = [
                                    rotate_point_around_center((x + cell.get("offset_x", 0.0), y + cell.get("offset_y", 0.0), base_z + cell.get("offset_z", 0.0)), (center_x, center_y, center_z), cell),
                                    rotate_point_around_center((x + 1.0 + cell.get("offset_x", 0.0), y + cell.get("offset_y", 0.0), base_z + cell.get("offset_z", 0.0)), (center_x, center_y, center_z), cell),
                                    rotate_point_around_center((x + 1.0 + cell.get("offset_x", 0.0), y + 1.0 + cell.get("offset_y", 0.0), base_z + cell.get("offset_z", 0.0) + cell["height"] * cell.get("scale_z", 1.0)), (center_x, center_y, center_z), cell),
                                    rotate_point_around_center((x + cell.get("offset_x", 0.0), y + 1.0 + cell.get("offset_y", 0.0), base_z + cell.get("offset_z", 0.0) + cell["height"] * cell.get("scale_z", 1.0)), (center_x, center_y, center_z), cell),
                                ]
                            else:
                                corners, _center = get_box_corners(x, y, base_z, cell)
                            if entry is not None:
                                add_pick_candidate(entry, corners)
                            if tile == "stair":
                                add_stair(x, y, base_z, cell, fill)
                            elif tile != "spawn":
                                add_box(x, y, base_z, cell, fill)
                            if tile in {"spawn", "mannequin", "hexagaze", "gun", "bomb"}:
                                center = project_point(*get_object_center(x, y, base_z, cell, tile))
                                if center is not None:
                                    sx, sy, depth = center
                                    size = max(8, min(24, int(42 / max(1.0, depth))))
                                    faces.append((depth - 0.01, [sx - size, sy - size, sx + size, sy + size], fill, "#FFFFFF", 0, tile))

                faces.sort(key=lambda item: item[0], reverse=True)
                for face in faces:
                    if len(face) == 6:
                        _depth, points, fill, outline, width, tile = face
                        canvas.create_oval(points[0], points[1], points[2], points[3], fill=fill, outline=outline, width=1)
                        canvas.create_text((points[0] + points[2]) * 0.5, (points[1] + points[3]) * 0.5, text=char_map.get(tile, "?"), fill="#101010", font=("Terminal", 9))
                    else:
                        _depth, points, fill, outline, width = face
                        canvas.create_polygon(points, fill=fill, outline=outline, width=width)
                if editor_state["active_tool"] in {"move", "resize", "rotate"}:
                    selected_entry = get_selected_object_entry()
                    selected_cell = None
                    if selected_entry is not None:
                        selected_cell = editor_state["layers"][selected_entry["layer"]][selected_entry["y"]][selected_entry["x"]]
                    if selected_entry is not None:
                        center = project_point(*selected_entry["focus"])
                        axis_specs = (
                            ("x", (selected_entry["focus"][0] + 1.35, selected_entry["focus"][1], selected_entry["focus"][2]), "#FF6464"),
                            ("y", (selected_entry["focus"][0], selected_entry["focus"][1] + 1.35, selected_entry["focus"][2]), "#66D37E"),
                            ("z", (selected_entry["focus"][0], selected_entry["focus"][1], selected_entry["focus"][2] + 1.35), "#62A8FF"),
                        )
                        if center is not None:
                            cx, cy, _ = center
                            for axis, world_end, color in axis_specs:
                                end = project_point(*world_end)
                                if end is None:
                                    continue
                                ex, ey, _ = end
                                if editor_state["active_tool"] == "move":
                                    ui["move_gizmo_hits"].append((axis, cx, cy, ex, ey))
                                    axis_width = 8 if editor_state.get("move_gizmo_axis") == axis else 5
                                    canvas.create_line(cx, cy, ex, ey, fill=color, width=axis_width, arrow="last", arrowshape=(18, 22, 8))
                                    canvas.create_text(ex + 12, ey, text=axis.upper(), fill=color, font=("Terminal", 11), anchor="w")
                                elif selected_cell is not None and not is_locked_transform_tile(selected_cell["tile"]):
                                    ui["resize_gizmo_hits"].append((axis, cx, cy, ex, ey))
                                    axis_width = 8 if editor_state.get("resize_gizmo_axis") == axis else 5
                                    canvas.create_line(cx, cy, ex, ey, fill=color, width=axis_width)
                                    square = 8 if editor_state.get("resize_gizmo_axis") == axis else 6
                                    canvas.create_rectangle(ex - square, ey - square, ex + square, ey + square, fill=color, outline="#F2F5F8", width=2)
                                    canvas.create_text(ex + 12, ey, text=axis.upper(), fill=color, font=("Terminal", 11), anchor="w")
                        if editor_state["active_tool"] == "rotate" and selected_cell is not None and not is_locked_transform_tile(selected_cell["tile"]):
                            rotate_specs = (
                                ("x", "#FF6464", 34.0, 0.72),
                                ("y", "#66D37E", 48.0, 0.78),
                                ("z", "#62A8FF", 62.0, 0.84),
                            )
                            for axis, color, radius, flatten in rotate_specs:
                                ui["rotate_gizmo_hits"].append((axis, cx, cy, radius))
                                width = 5 if editor_state.get("rotate_gizmo_axis") == axis else 3
                                canvas.create_oval(cx - radius, cy - radius * flatten, cx + radius, cy + radius * flatten, outline=color, width=width)
                                canvas.create_text(cx + radius + 12, cy - radius * flatten, text=axis.upper(), fill=color, font=("Terminal", 11), anchor="w")
                canvas.create_text(12, 12, anchor="nw", text=f"3D VIEW  FPS {editor_state['fps_3d']:.0f}", fill="#A9C6FF", font=("Terminal", 10))
                canvas.create_text(12, 28, anchor="nw", text=f"CAM {editor_state['camera_x']:.1f} {editor_state['camera_y']:.1f} {editor_state['camera_z']:.1f}", fill="#8FB0D8", font=("Terminal", 10))
                if editor_state.get("side_panel_dirty", True):
                    draw_layers_bar()
                refresh_menus()
                return
            cell_size, offset_x, offset_y = get_view_metrics()
            grid_w = cell_size * editor_state["width"]
            grid_h = cell_size * editor_state["height"]
            canvas.create_rectangle(offset_x, offset_y, offset_x + grid_w, offset_y + grid_h, outline="#707070")
            for y in range(editor_state["height"]):
                for x in range(editor_state["width"]):
                    display_tile = "empty"
                    display_height = 1
                    source_layer = -1
                    for idx, layer in enumerate(editor_state["layers"]):
                        cell = layer[y][x]
                        if cell["tile"] != "empty":
                            display_tile = cell["tile"]
                            display_height = cell["height"]
                            source_layer = idx
                    active_cell = active_cells()[y][x]
                    if active_cell["tile"] != "empty":
                        display_tile = active_cell["tile"]
                        display_height = active_cell["height"]
                        source_layer = editor_state["active_layer"]
                    x1 = offset_x + x * cell_size
                    y1 = offset_y + y * cell_size
                    x2 = x1 + cell_size
                    y2 = y1 + cell_size
                    selected = (x, y) in editor_state["selection"]
                    rotate_selected = editor_state.get("rotate_target") == (x, y)
                    display_source_cell = active_cell if active_cell["tile"] != "empty" else (editor_state["layers"][source_layer][y][x] if source_layer != -1 else {"tile": "empty"})
                    fill = preview_color_for_cell(display_source_cell)
                    if source_layer != -1 and source_layer != editor_state["active_layer"] and display_tile != "empty":
                        fill = "#3A4B62"
                    outline = "#FFD84D" if rotate_selected else ("#4B8CFF" if selected else "#3A3A3A")
                    outline_w = 3 if rotate_selected else (2 if selected else 1)
                    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=outline_w)
                    active_meta = active_cells()[y][x]
                    if editor_state["active_layer"] > 0:
                        if not active_meta.get("has_floor", True):
                            canvas.create_line(x1 + 4, y2 - 4, x2 - 4, y2 - 4, fill="#FF8A8A", width=2)
                        if not active_meta.get("has_ceiling", True):
                            canvas.create_line(x1 + 4, y1 + 4, x2 - 4, y1 + 4, fill="#7ED6FF", width=2)
                    if display_tile != "empty":
                        canvas.create_text(x1 + cell_size / 2, y1 + cell_size / 2 - min(5, cell_size * 0.12), text=char_map[display_tile], fill="white", font=("Terminal", max(7, int(cell_size * 0.24))))
                        canvas.create_text(x1 + cell_size / 2, y1 + cell_size / 2 + max(6, cell_size * 0.18), text=str(display_height), fill="#FFE68A", font=("Terminal", max(6, int(cell_size * 0.18))))
                        rotation_value = active_cell.get("rotation", 0.0) if active_cell["tile"] != "empty" else editor_state["layers"][source_layer][y][x].get("rotation", 0.0) if source_layer != -1 else 0.0
                        if abs(rotation_value) > 0.01:
                            canvas.create_text(x2 - max(10, cell_size * 0.18), y1 + max(8, cell_size * 0.16), text=str(int(round(rotation_value))), fill="#8FE8FF", font=("Terminal", max(6, int(cell_size * 0.14))))
            if editor_state["selection_rect"] is not None:
                x1, y1, x2, y2 = editor_state["selection_rect"]
                min_x, max_x = sorted((x1, x2))
                min_y, max_y = sorted((y1, y2))
                canvas.create_rectangle(offset_x + min_x * cell_size, offset_y + min_y * cell_size, offset_x + (max_x + 1) * cell_size, offset_y + (max_y + 1) * cell_size, outline="#4B8CFF", width=2, dash=(6, 4))
            if editor_state["rotate_target"] is not None:
                gx, gy = editor_state["rotate_target"]
                cell_size, x1, y1, x2, y2 = cell_bounds(gx, gy)
                cx = x2 + max(16.0, cell_size * 0.28)
                cy = (y1 + y2) * 0.5
                angle_rad = math.radians(active_cells()[gy][gx].get("rotation", 0.0))
                handle_len = max(26.0, cell_size * 0.82)
                handle_x = cx + math.cos(angle_rad) * handle_len
                handle_y = cy + math.sin(angle_rad) * handle_len
                canvas.create_line(cx, cy, handle_x, handle_y, fill="#FFD84D", width=4, arrow="last", arrowshape=(12, 14, 5))
                canvas.create_oval(handle_x - 8, handle_y - 8, handle_x + 8, handle_y + 8, fill="#FFD84D", outline="#FFF4A8", width=2)
            draw_layers_bar()
            refresh_menus()

        ui["draw_grid"] = draw_grid
        canvas.bind("<Button-1>", start_drag)
        canvas.bind("<B1-Motion>", drag)
        canvas.bind("<ButtonRelease-1>", stop_drag)
        canvas.bind("<ButtonPress-2>", start_middle_pan)
        canvas.bind("<B2-Motion>", middle_pan)
        canvas.bind("<ButtonRelease-2>", stop_middle_pan)
        canvas.bind("<MouseWheel>", handle_zoom)
        canvas.bind("<KeyPress>", on_key_press)
        canvas.bind("<KeyRelease>", on_key_release)
        win.bind("<Delete>", delete_selected_object)
        win.bind("<Control-z>", undo_action)
        win.bind("<Control-y>", redo_action)
        object_list.bind("<Delete>", delete_selected_object)
        canvas.focus_set()
        draw_grid()

    win.protocol("WM_DELETE_WINDOW", close_editor)
    reset_3d_camera()
    tick_3d_navigation()
    show_home_page()
    update_title()

