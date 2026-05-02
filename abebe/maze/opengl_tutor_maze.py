import copy
import math
import random
import time

from abebe.core.background_music import play_overlay_music, play_sound_effect, stop_overlay_music, update_music
from abebe.entities import bomb as bomb_logic
from abebe.entities import hexagaze as hexagaze_logic
from abebe.entities import mannequin as mannequin_logic
from abebe.entities import rob as rob_logic
from abebe.entities.bomb import load_gif_frames
from abebe.maze import deja_vu_system as deja_vu_logic
from abebe.maze import pause_menu as pause_menu_ui
from abebe.maze.opengl_maze_core import (
    PLAYER_EYE_HEIGHT,
    TARGET_FPS,
    acquire_opengl_display,
    begin_overlay,
    copy_framebuffer_to_texture,
    create_empty_texture,
    create_texture_from_pil,
    create_texture_from_surface,
    default_cell_color,
    delete_texture,
    draw_box,
    draw_ramp,
    draw_billboard,
    draw_bridge_plane,
    draw_floor_cell_outline,
    draw_floor_cell_fill,
    draw_floor_and_ceiling,
    draw_overlay_texture,
    end_overlay,
    fog_shade,
    release_opengl_display,
    require_opengl_dependencies,
    wrap_angle,
)
from abebe.maze.runtime_effects import (
    get_shot_hit_info as runtime_get_shot_hit_info,
    render_bullet_marks as runtime_render_bullet_marks,
    render_impact_particles as runtime_render_impact_particles,
    sample_image_color,
    spawn_bullet_mark as runtime_spawn_bullet_mark,
    spawn_impact_particles as runtime_spawn_impact_particles,
    update_bullet_marks as runtime_update_bullet_marks,
    update_impact_particles as runtime_update_impact_particles,
)
from abebe.maze.runtime_overlay import (
    clamp01 as runtime_clamp01,
    draw_rect as runtime_draw_rect,
    draw_text as runtime_draw_text,
    ease_out_cubic as runtime_ease_out_cubic,
    make_font as runtime_make_font,
    run_pause_menu_opengl as runtime_run_pause_menu_opengl,
)
from abebe.maze.runtime_world import (
    draw_runtime_floor_and_ceiling as runtime_draw_runtime_floor_and_ceiling,
    get_player_spawn as runtime_get_player_spawn,
    has_line_of_sight as runtime_has_line_of_sight,
    iter_runtime_stair_links as runtime_iter_runtime_stair_links,
    iter_runtime_stairs as runtime_iter_runtime_stairs,
    iter_runtime_walls as runtime_iter_runtime_walls,
    render_world_sprites as runtime_render_world_sprites,
)
from abebe.maze.opengl_human_model import collect_human_markers, draw_human_model
from abebe.maze.opengl_rob_talk_model import draw_animated_human_model, draw_rob_talk_model, get_animated_human_duration
from abebe.maze.opengl_player_body import draw_player_body
from PIL import Image, ImageDraw, ImageFont
from abebe.maze.tutor_maze import (
    DEJA_VU_FAST_CHARGE_CAP,
    DEJA_VU_FAST_CHARGE_TIME,
    DEJA_VU_ENTER_FADE,
    DEJA_VU_GHOST_INTERVAL,
    DEJA_VU_GHOST_LIFETIME,
    DEJA_VU_MAX_CHARGE,
    DEJA_VU_MIN_ACTIVATION,
    DEJA_VU_RECHARGE_DELAY,
    DEJA_VU_RETURN_FADE,
    DEJA_VU_SLOW_CHARGE_TIME,
    DEJA_VU_SPEED_BOOST,
    HEXAGAZE_BLOCK_RADIUS,
    HEXAGAZE_BURST_SIZE,
    HEXAGAZE_CLOSE_SIGHT_RADIUS,
    HEXAGAZE_ENTRY_BURST_COUNT,
    HEXAGAZE_ENTRY_BURST_SPEED,
    HEXAGAZE_FIRST_SHOT_DELAY,
    HEXAGAZE_HOMING_TURN_RATE,
    HEXAGAZE_PLAYER_HIT_RADIUS,
    HEXAGAZE_POST_ATTACK_WAIT,
    HEXAGAZE_PROJECTILE_DAMAGE,
    HEXAGAZE_PROJECTILE_SPEED,
    HEXAGAZE_RADIUS_CELLS,
    HEXAGAZE_RADIUS_MAX,
    HEXAGAZE_RADIUS_MIN,
    HEXAGAZE_ROLL_DURATION,
    HEXAGAZE_SNAKE_TURN_RATE,
    HEXAGAZE_SNAKE_WAVE_AMPLITUDE,
    HEXAGAZE_SNAKE_WAVE_SPEED,
    MAP,
    MOUSE_SENSITIVITY,
    PLAYER_MAX_HEALTH,
    PUNCH_AIM_TOLERANCE,
    PUNCH_COOLDOWN,
    PUNCH_DAMAGE,
    PUNCH_RANGE_CELLS,
    SPEED,
    can_occupy_position,
    get_ceiling_height,
    get_floor_height,
    get_walk_support_height,
    has_upper_wall,
    get_wav_duration,
    is_wall,
    resource_path,
)
from abebe.core.user_settings import (
    get_flash_enabled,
    get_bullet_marks_enabled,
    get_game_view_size,
    get_impact_particles_enabled,
    get_rear_world_culling_enabled,
    get_screen_effects_enabled,
    get_show_fps,
    get_view_bob,
    save_settings,
)


try:
    import pygame
    from OpenGL.GL import (
        GL_BLEND,
        GL_COLOR_BUFFER_BIT,
        GL_COMPILE,
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST,
        GL_MODELVIEW,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_PROJECTION,
        GL_QUADS,
        GL_SRC_ALPHA,
        GL_TEXTURE_2D,
        glBegin,
        glClear,
        glClearColor,
        glColor4f,
        glBlendFunc,
        glBindTexture,
        glDisable,
        glCallList,
        glDeleteLists,
        glEnd,
        glEnable,
        glEndList,
        glGenLists,
        glLoadIdentity,
        glMatrixMode,
        glNewList,
        glRotatef,
        glTexCoord2f,
        glTranslatef,
        glVertex2f,
        glVertex3f,
        glViewport,
    )
    from OpenGL.GLU import gluPerspective
except Exception:  # pragma: no cover
    pygame = None


CUSTOM_RUNTIME_GEOMETRY = None
_TEXT_TEXTURE_CACHE = {}


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _ease_out_cubic(x):
    x = _clamp01(x)
    return 1.0 - (1.0 - x) ** 3


def _make_font(size, bold=False):
    font_candidates = [
        "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/courbd.ttf" if bold else "C:/Windows/Fonts/cour.ttf",
    ]
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def get_cached_text_texture(font, text, color):
    key = (id(font), text, tuple(color))
    cached = _TEXT_TEXTURE_CACHE.get(key)
    if cached is not None:
        return cached
    bbox = font.getbbox(text)
    text_w = max(1, bbox[2] - bbox[0] + 2)
    text_h = max(1, bbox[3] - bbox[1] + 2)
    image = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((1 - bbox[0], 1 - bbox[1]), text, font=font, fill=tuple(color))
    cached = create_texture_from_pil(image)
    if len(_TEXT_TEXTURE_CACHE) > 256:
        oldest_key = next(iter(_TEXT_TEXTURE_CACHE))
        oldest_texture_id, _old_w, _old_h = _TEXT_TEXTURE_CACHE.pop(oldest_key)
        delete_texture(oldest_texture_id)
    _TEXT_TEXTURE_CACHE[key] = cached
    return cached


def clear_cached_text_textures():
    for texture_id, _w, _h in _TEXT_TEXTURE_CACHE.values():
        delete_texture(texture_id)
    _TEXT_TEXTURE_CACHE.clear()


def _draw_text(font, text, color, x, y):
    texture_id, text_w, text_h = get_cached_text_texture(font, text, color)
    draw_overlay_texture(texture_id, x, y, text_w, text_h)
    return text_w, text_h


def _draw_text_perspective(font, text, color, x, y, depth=4, shrink=0.08, drift_x=-12, drift_y=-6):
    texture_id, text_w, text_h = get_cached_text_texture(font, text, color)
    base_tint = (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
    for layer in range(depth, 0, -1):
        t = layer / max(1, depth)
        scale = max(0.6, 1.0 - shrink * layer)
        draw_w = max(1, int(text_w * scale))
        draw_h = max(1, int(text_h * scale))
        layer_x = x + int(drift_x * t)
        layer_y = y + int(drift_y * t)
        alpha = 0.08 + 0.08 * (1.0 - t)
        draw_overlay_texture(texture_id, layer_x, layer_y, draw_w, draw_h, tint=(0.0, 0.28 + 0.18 * (1.0 - t), 0.0), alpha=alpha)
    draw_overlay_texture(texture_id, x, y, text_w, text_h, tint=base_tint, alpha=1.0)
    return text_w, text_h


def _draw_rect(texture_id, x, y, width, height, color, alpha=1.0):
    tint = (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
    draw_overlay_texture(texture_id, x, y, width, height, tint=tint, alpha=alpha)


def _draw_overlay_texture_quad(texture_id, points, tint=(1.0, 1.0, 1.0), alpha=1.0):
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glColor4f(tint[0], tint[1], tint[2], alpha)
    glBegin(GL_QUADS)
    glTexCoord2f(0.0, 1.0)
    glVertex2f(points[0][0], points[0][1])
    glTexCoord2f(1.0, 1.0)
    glVertex2f(points[1][0], points[1][1])
    glTexCoord2f(1.0, 0.0)
    glVertex2f(points[2][0], points[2][1])
    glTexCoord2f(0.0, 0.0)
    glVertex2f(points[3][0], points[3][1])
    glEnd()


def _draw_billboard_sprite(sprite_batch, player_x, player_y, x, y, bottom_z, pil_image, height_world, alpha=1.0, tint=(1.0, 1.0, 1.0)):
    if pil_image is None:
        return
    sprite_batch.append(
        {
            "dist": math.hypot(x - player_x, y - player_y),
            "x": x,
            "y": y,
            "bottom_z": bottom_z,
            "image": pil_image,
            "height_world": height_world,
            "alpha": alpha,
            "tint": tint,
        }
    )


def run_pause_menu_opengl(clock, width, height, title="Paused"):
    previous_mouse_visible = pygame.mouse.get_visible()
    pygame.mouse.set_visible(True)

    title_font = pygame.font.SysFont("consolas", 32, bold=True)
    button_font = pygame.font.SysFont("consolas", 20)
    info_font = pygame.font.SysFont("consolas", 16)
    row_font = pygame.font.SysFont("consolas", 18)

    button_w = 280
    button_h = 52
    gap = 14
    start_y = height // 2 - 110
    left = width // 2 - button_w // 2

    buttons = [
        ("return", pygame.Rect(left, start_y, button_w, button_h), "Return"),
        ("settings", pygame.Rect(left, start_y + (button_h + gap), button_w, button_h), "Settings"),
        ("restart", pygame.Rect(left, start_y + 2 * (button_h + gap), button_w, button_h), "Restart"),
        ("quit", pygame.Rect(left, start_y + 3 * (button_h + gap), button_w, button_h), "Quit"),
    ]

    settings_sections = {
        "Graphics": [
            ("pixel_preset", "Pixel Resolution"),
            ("brightness", "Brightness"),
            ("view_bob", "View Bob"),
            ("fov_degrees", "FOV"),
            ("screen_effects_enabled", "Screen Effects"),
            ("rear_world_culling_enabled", "Rear World Culling"),
        ],
        "Audio": [
            ("music_enabled", "Music Enabled"),
            ("master_volume", "Master"),
            ("sfx_volume", "Sound Effects"),
            ("music_volume", "Music"),
        ],
        "General": [
            ("flash_enabled", "Flash"),
            ("mouse_wheel_weapon_switch", "Mouse Wheel Weapon"),
            ("impact_particles_enabled", "Impact Particles"),
            ("bullet_marks_enabled", "Bullet Marks"),
            ("show_fps", "Show FPS"),
            ("show_debug_stats", "Show Debug Stats"),
        ],
    }

    confirm_quit = False
    page = "main"
    settings_section = "Graphics"
    settings = pause_menu_ui.load_settings()

    while True:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.mouse.set_visible(previous_mouse_visible)
                return "quit"

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if confirm_quit:
                    confirm_quit = False
                elif page == "settings":
                    page = "main"
                else:
                    pygame.mouse.set_visible(previous_mouse_visible)
                    return "resume"

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if confirm_quit:
                    yes_rect = pygame.Rect(width // 2 - 150, height // 2 + 118, 130, 46)
                    no_rect = pygame.Rect(width // 2 + 20, height // 2 + 118, 130, 46)
                    if yes_rect.collidepoint(mouse_pos):
                        pygame.mouse.set_visible(previous_mouse_visible)
                        return "quit"
                    if no_rect.collidepoint(mouse_pos):
                        confirm_quit = False
                    continue

                if page == "settings":
                    tab_y = height // 2 - 120
                    tab_w = 140
                    for i, section_name in enumerate(settings_sections):
                        tab_rect = pygame.Rect(width // 2 - 220 + i * (tab_w + 10), tab_y, tab_w, 38)
                        if tab_rect.collidepoint(mouse_pos):
                            settings_section = section_name
                            break

                    row_y = height // 2 - 70
                    for key, _label in settings_sections[settings_section]:
                        row_rect = pygame.Rect(width // 2 - 220, row_y, 440, 44)
                        minus_rect = pygame.Rect(row_rect.right - 120, row_rect.y + 5, 34, row_rect.height - 10)
                        plus_rect = pygame.Rect(row_rect.right - 40, row_rect.y + 5, 34, row_rect.height - 10)
                        value_rect = pygame.Rect(row_rect.right - 84, row_rect.y + 5, 40, row_rect.height - 10)
                        if minus_rect.collidepoint(mouse_pos):
                            pause_menu_ui._apply_setting_change(settings, key, -1)
                            break
                        if plus_rect.collidepoint(mouse_pos):
                            pause_menu_ui._apply_setting_change(settings, key, 1)
                            break
                        if value_rect.collidepoint(mouse_pos) and isinstance(settings[key], bool):
                            pause_menu_ui._apply_setting_change(settings, key, 1)
                            break
                        row_y += 52

                    back_rect = pygame.Rect(width // 2 - 90, height // 2 + 150, 180, 46)
                    if back_rect.collidepoint(mouse_pos):
                        page = "main"
                    continue

                for action, rect, _ in buttons:
                    if not rect.collidepoint(mouse_pos):
                        continue
                    if action == "return":
                        pygame.mouse.set_visible(previous_mouse_visible)
                        return "resume"
                    if action == "settings":
                        settings = pause_menu_ui.load_settings()
                        page = "settings"
                        break
                    if action == "restart":
                        pygame.mouse.set_visible(previous_mouse_visible)
                        return "restart"
                    if action == "quit":
                        confirm_quit = True
                        break

        menu_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        menu_surface.blit(overlay, (0, 0))

        panel = pygame.Rect(width // 2 - 250, height // 2 - 200, 500, 430)
        pygame.draw.rect(menu_surface, (0, 0, 0), panel)
        pygame.draw.rect(menu_surface, (0, 255, 0), panel, width=2)

        title_surf = title_font.render("Settings" if page == "settings" else title, True, (0, 255, 0))
        menu_surface.blit(title_surf, title_surf.get_rect(center=(width // 2, height // 2 - 150)))

        if confirm_quit:
            prompt = info_font.render("Are you sure you want to quit to main menu?", True, (255, 255, 255))
            menu_surface.blit(prompt, prompt.get_rect(center=(width // 2, height // 2 + 70)))
            yes_rect = pygame.Rect(width // 2 - 150, height // 2 + 118, 130, 46)
            no_rect = pygame.Rect(width // 2 + 20, height // 2 + 118, 130, 46)
            pause_menu_ui._draw_button(menu_surface, yes_rect, "Yes", button_font, yes_rect.collidepoint(mouse_pos))
            pause_menu_ui._draw_button(menu_surface, no_rect, "No", button_font, no_rect.collidepoint(mouse_pos))
        elif page == "settings":
            tab_y = height // 2 - 120
            tab_w = 140
            for i, section_name in enumerate(settings_sections):
                tab_rect = pygame.Rect(width // 2 - 220 + i * (tab_w + 10), tab_y, tab_w, 38)
                pause_menu_ui._draw_button(
                    menu_surface,
                    tab_rect,
                    section_name,
                    info_font,
                    tab_rect.collidepoint(mouse_pos) or section_name == settings_section,
                )

            row_y = height // 2 - 70
            for key, label in settings_sections[settings_section]:
                row_rect = pygame.Rect(width // 2 - 220, row_y, 440, 44)
                minus_rect = pygame.Rect(row_rect.right - 120, row_rect.y + 5, 34, row_rect.height - 10)
                plus_rect = pygame.Rect(row_rect.right - 40, row_rect.y + 5, 34, row_rect.height - 10)
                pause_menu_ui._draw_setting_row(
                    menu_surface,
                    row_rect,
                    label,
                    pause_menu_ui._format_value(key, settings[key]),
                    row_font,
                    minus_rect.collidepoint(mouse_pos),
                    plus_rect.collidepoint(mouse_pos),
                    isinstance(settings[key], bool),
                )
                row_y += 52

            note = "Pixel Resolution applies after restart."
            note_surf = info_font.render(note, True, (170, 170, 170))
            menu_surface.blit(note_surf, note_surf.get_rect(center=(width // 2, height // 2 + 128)))
            back_rect = pygame.Rect(width // 2 - 90, height // 2 + 150, 180, 46)
            pause_menu_ui._draw_button(menu_surface, back_rect, "Back", button_font, back_rect.collidepoint(mouse_pos))
        else:
            hint_surf = info_font.render("Press ESC to resume", True, (170, 170, 170))
            menu_surface.blit(hint_surf, hint_surf.get_rect(center=(width // 2, height // 2 - 108)))
            for _action, rect, label in buttons:
                pause_menu_ui._draw_button(menu_surface, rect, label, button_font, rect.collidepoint(mouse_pos))

        menu_bytes = pygame.image.tostring(menu_surface, "RGBA", False)
        menu_image = Image.frombytes("RGBA", (width, height), menu_bytes)
        texture_id, tex_w, tex_h = create_texture_from_pil(menu_image)
        projection, viewport = begin_overlay(width, height)
        try:
            draw_overlay_texture(texture_id, 0, 0, tex_w, tex_h)
        finally:
            end_overlay(projection, viewport)
            delete_texture(texture_id)
        pygame.display.flip()
        clock.tick(60)


def has_line_of_sight(x1, y1, x2, y2, step=0.1):
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist <= 0.01:
        return True
    steps = max(1, int(dist / step))
    for i in range(1, steps):
        px = x1 + dx * (i / steps)
        py = y1 + dy * (i / steps)
        if is_wall(px, py):
            return False
    return True


def sample_image_color(image, u=0.5, v=0.5):
    if image is None:
        return (0.8, 0.8, 0.8)
    width, height = image.size
    px = max(0, min(width - 1, int(u * width)))
    py = max(0, min(height - 1, int(v * height)))
    r, g, b, *rest = image.getpixel((px, py))
    return (r / 255.0, g / 255.0, b / 255.0)


def is_walkable_cell(cell_x, cell_y):
    if cell_x < 0 or cell_y < 0:
        return False
    if cell_y >= len(MAP) or cell_x >= len(MAP[0]):
        return False
    return MAP[cell_y][cell_x] != "#"


def get_player_spawn():
    if CUSTOM_RUNTIME_GEOMETRY is not None:
        spawn_x, spawn_y = CUSTOM_RUNTIME_GEOMETRY["spawn_cell"]
        return spawn_x + 0.5, spawn_y + 0.5
    for y, row in enumerate(MAP):
        for x, cell in enumerate(row):
            if cell == "P":
                return x + 0.5, y + 0.5
    return 10.5, 2.5


def draw_runtime_floor_and_ceiling(viewer_x, viewer_y, viewer_angle, rear_cull):
    if CUSTOM_RUNTIME_GEOMETRY is None:
        draw_floor_and_ceiling(
            MAP,
            get_floor_height,
            ceiling_height_fn=get_ceiling_height,
            viewer_x=viewer_x,
            viewer_y=viewer_y,
            viewer_angle=viewer_angle,
            rear_cull=rear_cull,
        )
        return

    for surface in CUSTOM_RUNTIME_GEOMETRY["floor_surfaces"]:
        cell_x = surface["x"]
        cell_y = surface["y"]
        floor_z = surface["z"]
        if rear_cull:
            dx = (cell_x + 0.5) - viewer_x
            dy = (cell_y + 0.5) - viewer_y
            dist = math.hypot(dx, dy)
            if dist > 1.4:
                facing = (dx * math.cos(viewer_angle) + dy * math.sin(viewer_angle)) / max(0.0001, dist)
                if facing < -0.28:
                    continue
        dist = math.hypot((cell_x + 0.5) - viewer_x, (cell_y + 0.5) - viewer_y)
        shade = fog_shade(dist, min_light=0.28)
        draw_floor_cell_fill(cell_x, cell_y, floor_z, color=((0.16 + floor_z * 0.10) * shade, (0.16 + floor_z * 0.03) * shade, 0.18 * shade), alpha=1.0)

    for surface in CUSTOM_RUNTIME_GEOMETRY["ceiling_surfaces"]:
        cell_x = surface["x"]
        cell_y = surface["y"]
        ceiling_z = surface["z"]
        if rear_cull:
            dx = (cell_x + 0.5) - viewer_x
            dy = (cell_y + 0.5) - viewer_y
            dist = math.hypot(dx, dy)
            if dist > 1.4:
                facing = (dx * math.cos(viewer_angle) + dy * math.sin(viewer_angle)) / max(0.0001, dist)
                if facing < -0.28:
                    continue
        dist = math.hypot((cell_x + 0.5) - viewer_x, (cell_y + 0.5) - viewer_y)
        ceiling_shade = max(0.18, fog_shade(dist, min_light=0.28) * 0.85)
        draw_floor_cell_fill(cell_x, cell_y, ceiling_z, color=(0.08 * ceiling_shade, 0.08 * ceiling_shade, 0.10 * ceiling_shade), alpha=0.95, lift=-0.006)


def iter_runtime_walls():
    if CUSTOM_RUNTIME_GEOMETRY is None:
        for y, row in enumerate(MAP):
            for x, cell in enumerate(row):
                if cell != "#":
                    continue
                yield {"x": x, "y": y, "base_z": 0.0, "height": 1.0, "cell": cell}
                if has_upper_wall(x, y):
                    yield {"x": x, "y": y, "base_z": 1.0, "height": 1.0, "cell": cell}
        return

    for wall in CUSTOM_RUNTIME_GEOMETRY["wall_columns"]:
        yield {
            "x": wall["x"],
            "y": wall["y"],
            "base_z": wall["base_z"],
            "height": wall["height"],
            "cell": "#",
            "scale_x": wall.get("scale_x", 1.0),
            "scale_y": wall.get("scale_y", 1.0),
            "scale_z": wall.get("scale_z", 1.0),
            "offset_x": wall.get("offset_x", 0.0),
            "offset_y": wall.get("offset_y", 0.0),
            "offset_z": wall.get("offset_z", 0.0),
            "rotation": wall.get("rotation", 0.0),
            "rotation_x": wall.get("rotation_x", 0.0),
            "rotation_y": wall.get("rotation_y", 0.0),
        }


def iter_runtime_stairs():
    if CUSTOM_RUNTIME_GEOMETRY is None:
        return
    for stair in CUSTOM_RUNTIME_GEOMETRY.get("stairs", []):
        yield stair


def iter_runtime_stair_links():
    if CUSTOM_RUNTIME_GEOMETRY is None:
        return
    for link in CUSTOM_RUNTIME_GEOMETRY.get("stair_links", []):
        yield link


def build_runtime_display_lists(runtime_geometry, wall_texture_id):
    if runtime_geometry is None:
        return {}

    display_lists = {}

    floor_list = glGenLists(1)
    glNewList(floor_list, GL_COMPILE)
    for surface in runtime_geometry.get("floor_surfaces", []):
        cell_x = surface["x"]
        cell_y = surface["y"]
        floor_z = surface["z"]
        draw_floor_cell_fill(
            cell_x,
            cell_y,
            floor_z,
            color=(0.16 + floor_z * 0.10, 0.16 + floor_z * 0.03, 0.18),
            alpha=1.0,
        )
    for surface in runtime_geometry.get("ceiling_surfaces", []):
        cell_x = surface["x"]
        cell_y = surface["y"]
        ceiling_z = surface["z"]
        draw_floor_cell_fill(
            cell_x,
            cell_y,
            ceiling_z,
            color=(0.08, 0.08, 0.10),
            alpha=0.95,
            lift=-0.006,
        )
    glEndList()
    display_lists["floor"] = floor_list

    world_list = glGenLists(1)
    glNewList(world_list, GL_COMPILE)
    for wall in runtime_iter_runtime_walls(runtime_geometry, MAP, has_upper_wall):
        draw_box(
            wall["x"],
            wall["base_z"],
            wall["y"],
            1.0,
            wall["height"],
            default_cell_color(wall["cell"]),
            texture_id=wall_texture_id,
            shade=1.0,
            scale_x=wall.get("scale_x", 1.0),
            scale_y=wall.get("scale_y", 1.0),
            scale_z=1.0,
            offset_x=wall.get("offset_x", 0.0),
            offset_y=wall.get("offset_y", 0.0),
            offset_z=wall.get("offset_z", 0.0),
            rotation_x=wall.get("rotation_x", 0.0),
            rotation_y=wall.get("rotation_y", 0.0),
            rotation_z=wall.get("rotation", 0.0),
        )
    for stair in runtime_iter_runtime_stairs(runtime_geometry):
        draw_ramp(
            stair["x"],
            stair["base_z"],
            stair["y"],
            1.0,
            stair["height"],
            stair["rotation"],
            default_cell_color("I"),
            texture_id=wall_texture_id,
            shade=1.0,
            scale_x=stair.get("scale_x", 1.0),
            scale_y=stair.get("scale_y", 1.0),
            scale_z=1.0,
            offset_x=stair.get("offset_x", 0.0),
            offset_y=stair.get("offset_y", 0.0),
            offset_z=stair.get("offset_z", 0.0),
            rotation_x=stair.get("rotation_x", 0.0),
            rotation_y=stair.get("rotation_y", 0.0),
        )
    for link in runtime_iter_runtime_stair_links(runtime_geometry):
        draw_bridge_plane(
            link["start_x"],
            link["start_z"],
            link["start_y"],
            link["end_x"],
            link["end_z"],
            link["end_y"],
            link.get("width", 0.34),
            default_cell_color("I"),
            texture_id=wall_texture_id,
            shade=1.0,
        )
    glEndList()
    display_lists["world"] = world_list

    return display_lists


def delete_runtime_display_lists(display_lists):
    for list_id in display_lists.values():
        if list_id:
            glDeleteLists(int(list_id), 1)


def render_world_sprites(state, player_x, player_y, player_angle, textures, bomb_world_frame_index, is_render_point_visible):
    sprite_batch = []

    if state["deja_vu_active"]:
        for sentry in state["sentries"]:
            if sentry["health"] <= 0:
                continue
            safe_cells = sentry["zone_cells"] - sentry["visible_cells"]
            for cell_x, cell_y in safe_cells:
                if not is_render_point_visible(cell_x + 0.5, cell_y + 0.5, near_dist=1.2, back_margin=-0.22):
                    continue
                floor_z = get_floor_height(cell_x + 0.5, cell_y + 0.5)
                draw_floor_cell_fill(cell_x, cell_y, floor_z, color=(0.18, 0.9, 0.36), alpha=0.18)
                draw_floor_cell_outline(cell_x, cell_y, floor_z, color=(0.28, 1.0, 0.42), inset=0.10, thickness=0.03)
            for cell_x, cell_y in sentry["visible_cells"]:
                if not is_render_point_visible(cell_x + 0.5, cell_y + 0.5, near_dist=1.2, back_margin=-0.22):
                    continue
                floor_z = get_floor_height(cell_x + 0.5, cell_y + 0.5)
                draw_floor_cell_fill(cell_x, cell_y, floor_z, color=(1.0, 0.12, 0.12), alpha=0.18)
                draw_floor_cell_outline(cell_x, cell_y, floor_z, color=(1.0, 0.28, 0.22), inset=0.10, thickness=0.03)

    for gx, gy in state["gun_pickups"]:
        if not is_render_point_visible(gx, gy):
            continue
        _draw_billboard_sprite(sprite_batch, player_x, player_y, gx, gy, get_floor_height(gx, gy), textures["gun_pickup"], 0.42)

    for bx, by in state["bomb_pickups"]:
        if not is_render_point_visible(bx, by):
            continue
        _draw_billboard_sprite(sprite_batch, player_x, player_y, bx, by, get_floor_height(bx, by), textures["bomb_pickup"], 0.40)

    if state["placed_bombs"]:
        bomb_frames = textures["bombon_frames"]
        bomb_frame = bomb_frames[bomb_world_frame_index % len(bomb_frames)]
        for bomb in state["placed_bombs"]:
            if not is_render_point_visible(bomb["x"], bomb["y"]):
                continue
            _draw_billboard_sprite(sprite_batch, player_x, player_y, bomb["x"], bomb["y"], get_floor_height(bomb["x"], bomb["y"]), bomb_frame, 0.42)

    for explosion in state["active_explosions"]:
        if not is_render_point_visible(explosion["x"], explosion["y"], near_dist=1.0, back_margin=-0.12):
            continue
        frame_index = min(explosion["frame_index"], len(textures["boom_frames"]) - 1)
        _draw_billboard_sprite(
            sprite_batch,
            player_x,
            player_y,
            explosion["x"],
            explosion["y"],
            get_floor_height(explosion["x"], explosion["y"]),
            textures["boom_frames"][frame_index],
            1.0,
        )

    for orb in state["orbs"]:
        if orb["health"] <= 0:
            continue
        if not is_render_point_visible(orb["x"], orb["y"]):
            continue
        bob = math.sin(time.time() * 2.0 + orb["x"]) * 0.08
        _draw_billboard_sprite(
            sprite_batch,
            player_x,
            player_y,
            orb["x"],
            orb["y"],
            get_floor_height(orb["x"], orb["y"]) + 0.14 + bob,
            textures["orbs"][orb["color"]],
            0.34,
        )

    for sentry in state["sentries"]:
        if sentry["health"] <= 0:
            continue
        if not is_render_point_visible(sentry["x"], sentry["y"]):
            continue
        roll_name = sentry.get("queued_roll")
        roll_frames = textures["hexagaze_rolls"].get(roll_name) if roll_name else None
        if roll_frames and sentry["burst_shots_left"] <= 0 and time.time() < sentry.get("roll_visible_until", 0.0):
            elapsed = max(0.0, time.time() - sentry.get("roll_started_at", 0.0))
            frame_index = int(elapsed / 0.06) % max(1, len(roll_frames))
            sentry_frame = roll_frames[frame_index]
        else:
            frame_index = mannequin_logic.get_directional_frame_index(
                sentry["x"],
                sentry["y"],
                player_x,
                player_y,
                len(textures["hexagaze_frames"]),
            )
            sentry_frame = textures["hexagaze_frames"][frame_index]
        _draw_billboard_sprite(sprite_batch, player_x, player_y, sentry["x"], sentry["y"], get_floor_height(sentry["x"], sentry["y"]), sentry_frame, 0.72)

    for projectile in state["sentry_projectiles"]:
        if not is_render_point_visible(projectile["x"], projectile["y"], near_dist=1.0, back_margin=-0.10):
            continue
        _draw_billboard_sprite(
            sprite_batch,
            player_x,
            player_y,
            projectile["x"],
            projectile["y"],
            get_floor_height(projectile["x"], projectile["y"]) + 0.15,
            textures["orbs"][projectile["color"]],
            0.18,
        )

    mannequin_state = state["mannequin_state"]
    if mannequin_state["alive"] and mannequin_state["x"] is not None and mannequin_state["y"] is not None:
        if is_render_point_visible(mannequin_state["x"], mannequin_state["y"]):
            mannequin_frame_index = mannequin_logic.get_frame_index(mannequin_state, player_x, player_y, len(textures["mannequin_frames"]))
            mannequin_frame = textures["mannequin_frames"][mannequin_frame_index]
            _draw_billboard_sprite(
                sprite_batch,
                player_x,
                player_y,
                mannequin_state["x"],
                mannequin_state["y"],
                get_floor_height(mannequin_state["x"], mannequin_state["y"]),
                mannequin_frame,
                0.95,
            )

    for ghost in state["deja_vu_ghost_trail"]:
        life_ratio = 1.0 - ((time.time() - ghost["spawned_at"]) / DEJA_VU_GHOST_LIFETIME)
        if life_ratio <= 0.0:
            continue
        if not is_render_point_visible(ghost["x"], ghost["y"], near_dist=0.9, back_margin=-0.08):
            continue
        frame_index = min(len(textures["ghost_frames"]) - 1, int((1.0 - life_ratio) * len(textures["ghost_frames"])))
        _draw_billboard_sprite(
            sprite_batch,
            player_x,
            player_y,
            ghost["x"],
            ghost["y"],
            get_floor_height(ghost["x"], ghost["y"]) + 0.04,
            textures["ghost_frames"][frame_index],
            0.22,
            alpha=max(0.15, life_ratio * 0.7),
            tint=(0.72, 1.0, 0.96),
        )

    sprite_batch.sort(key=lambda item: item["dist"], reverse=True)
    for sprite in sprite_batch:
        texture_id, tex_w, tex_h = textures["texture_cache"](sprite["image"])
        width_world = sprite["height_world"] * (tex_w / max(1, tex_h))
        draw_billboard(
            sprite["x"],
            sprite["y"],
            sprite["bottom_z"],
            width_world,
            sprite["height_world"],
            texture_id,
            viewer_x=player_x,
            viewer_y=player_y,
            tint=sprite["tint"],
            alpha=sprite["alpha"],
        )

    if state["selected_slot"] == 2 and state["slot2_item"] == "bomb" and state["target_cell"] is not None:
        tx, ty = state["target_cell"]
        if is_render_point_visible(tx + 0.5, ty + 0.5, near_dist=0.9, back_margin=-0.12):
            floor_z = get_floor_height(tx + 0.5, ty + 0.5)
            draw_floor_cell_outline(tx, ty, floor_z, color=(1.0, 0.9, 0.18))


def start_tutor_maze_opengl(root=None):
    require_opengl_dependencies()

    custom_runtime_active = CUSTOM_RUNTIME_GEOMETRY is not None
    player_spawn_x, player_spawn_y = runtime_get_player_spawn(CUSTOM_RUNTIME_GEOMETRY, MAP)
    player_start_cutscene_offset = 0.0 if custom_runtime_active else 2.0
    player_x = player_spawn_x - player_start_cutscene_offset
    player_y = player_spawn_y
    player_z = get_floor_height(player_x, player_y)
    player_angle = 0.0
    player_pitch = 0.0
    PITCH_LIMIT_DOWN = math.radians(80.0)
    PITCH_LIMIT_UP = math.radians(25.0)
    PITCH_SENSITIVITY = MOUSE_SENSITIVITY * 0.35
    bob_strength = get_view_bob()
    impact_particles_enabled = get_impact_particles_enabled()
    bullet_marks_enabled = get_bullet_marks_enabled()
    screen_effects_enabled = get_screen_effects_enabled()
    rear_world_culling_enabled = get_rear_world_culling_enabled()
    bob_phase = 0.0
    bob_vertical = 0.0
    bob_side = 0.0
    crouch_amount = 0.0
    CROUCH_MAX = 0.30
    CROUCH_SPEED = 7.5
    vertical_velocity = 0.0
    JUMP_SPEED = 1.22
    CROUCH_JUMP_BONUS = 0.0
    GRAVITY = 3.9
    STEP_HEIGHT = 0.34
    GROUND_SNAP_DISTANCE = 0.04
    JUMP_CLIMB_HEIGHT = 0.62

    screen, width, height = acquire_opengl_display()
    clock = pygame.time.Clock()
    render_width, render_height = get_game_view_size()
    render_width = max(64, min(render_width, width))
    render_height = max(64, min(render_height, height))

    glViewport(0, 0, render_width, render_height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(75.0, render_width / max(1, render_height), 0.05, 160.0)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glClearColor(0.03, 0.03, 0.045, 1.0)

    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)
    pygame.mouse.get_rel()

    font_title = runtime_make_font(14, bold=True)
    font_hud = runtime_make_font(16)
    font_hud_big = runtime_make_font(18)
    font_clock = runtime_make_font(13, bold=True)
    font_slot = runtime_make_font(11)
    font_task = runtime_make_font(18)
    font_intro = runtime_make_font(42)
    font_stats = runtime_make_font(24)
    font_stats_small = runtime_make_font(18)
    hud_start_time = time.time()
    flash_enabled = get_flash_enabled()

    intro_active = True
    intro_text = "CASE 0.0.0 /// TRAINING_SIM"
    intro_index = 0
    intro_start = time.time()
    intro_duration = 11.0
    pixel_size = 28
    pixel_grid = []
    for grid_x in range(0, width, pixel_size):
        for grid_y in range(0, height, pixel_size):
            pixel_grid.append([grid_x, grid_y, True])
    random.shuffle(pixel_grid)
    pixel_grid_full = [(point[0], point[1]) for point in pixel_grid]
    pixel_grid = pixel_grid[:1200]
    intro_fade_started = False

    texture_cache = {}
    hand_texture_cache = {}

    def get_cached_texture(pil_image):
        key = id(pil_image)
        cached = texture_cache.get(key)
        if cached is None:
            cached = create_texture_from_pil(pil_image)
            texture_cache[key] = cached
        return cached

    def get_cached_hand_texture(pil_frame, item_id):
        key = (item_id, id(pil_frame))
        cached = hand_texture_cache.get(key)
        if cached is not None:
            return cached
        hand_image = build_hand_image(pil_frame, item_id)
        cached = create_texture_from_pil(hand_image)
        if len(hand_texture_cache) > 32:
            oldest_key = next(iter(hand_texture_cache))
            old_texture_id, _old_w, _old_h = hand_texture_cache.pop(oldest_key)
            delete_texture(old_texture_id)
        hand_texture_cache[key] = cached
        return cached

    white_texture_id, _, _ = create_texture_from_pil(Image.new("RGBA", (1, 1), (255, 255, 255, 255)))
    deja_screen_texture = create_empty_texture(render_width, render_height)
    scene_texture = create_empty_texture(render_width, render_height)
    crt_overlay_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    crt_draw = ImageDraw.Draw(crt_overlay_image)
    for y in range(0, height, 3):
        crt_draw.rectangle((0, y, width, min(height, y + 1)), fill=(0, 0, 0, 28))
    edge = max(18, min(width, height) // 28)
    for i in range(edge):
        alpha = int(10 + (i / max(1, edge - 1)) * 28)
        crt_draw.rectangle((i, i, width - 1 - i, height - 1 - i), outline=(0, 0, 0, alpha))
    crt_overlay_texture = create_texture_from_pil(crt_overlay_image)

    def cleanup_textures():
        for texture_id, _w, _h in texture_cache.values():
            delete_texture(texture_id)
        texture_cache.clear()
        clear_cached_text_textures()
        for texture_id, _w, _h in hand_texture_cache.values():
            delete_texture(texture_id)
        hand_texture_cache.clear()
        delete_texture(white_texture_id)
        delete_texture(deja_screen_texture[0])
        delete_texture(scene_texture[0])
        delete_texture(crt_overlay_texture[0])

    gun_img_raw = Image.open(resource_path("data/gifs/hands/gun.png")).convert("RGBA")
    gunshoot_frames_raw = load_gif_frames(resource_path("data/gifs/hands/gunshoot.gif"))
    gunreload_frames_raw = load_gif_frames(resource_path("data/gifs/hands/gunreload.gif"))
    punch_img_raw = Image.open(resource_path("data/gifs/hands/punch.png")).convert("RGBA")
    left_punch_frames_raw = load_gif_frames(resource_path("data/gifs/hands/LPunch.gif"))
    right_punch_frames_raw = load_gif_frames(resource_path("data/gifs/hands/RPunch.gif"))
    hud_raw = Image.open(resource_path("data/hud.png")).convert("RGBA")
    wall_tex_raw = Image.open(resource_path("data/unknown.png")).convert("RGBA")
    task_stub_src = wall_tex_raw.copy()
    gunitem_raw = Image.open(resource_path("data/gunitem.png")).convert("RGBA")
    activator_icon_raw = Image.open(resource_path("data/gifs/hands/activatoricon.png")).convert("RGBA")
    orb_textures = {
        "yellow": Image.open(resource_path("data/orbs/orb_yellow.png")).convert("RGBA"),
        "red": Image.open(resource_path("data/orbs/orb_red.png")).convert("RGBA"),
        "green": Image.open(resource_path("data/orbs/orb_green.png")).convert("RGBA"),
        "violet": Image.open(resource_path("data/orbs/orb_violet.png")).convert("RGBA"),
    }

    deja_vu_ghost_frames = []
    for alpha in (255, 210, 165, 120, 80, 45):
        ghost_frame = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
        ghost_draw = ImageDraw.Draw(ghost_frame)
        ghost_draw.ellipse((2, 2, 22, 22), fill=(120, 255, 240, max(10, alpha // 5)))
        ghost_draw.ellipse((6, 6, 18, 18), fill=(170, 255, 250, max(20, alpha // 2)))
        ghost_draw.ellipse((9, 9, 15, 15), fill=(240, 255, 255, alpha))
        deja_vu_ghost_frames.append(ghost_frame)

    GUN_SCALE = 0.25
    PUNCH_SCALE = 0.38
    PUNCH_WIDTH_MULT = 1.28
    PUNCH_HEIGHT_MULT = 1.30
    TASK_ICON_SIZE = 44
    HAND_SWAP_DURATION = 0.18

    bomb_assets = bomb_logic.load_bomb_assets(resource_path, 320, lambda img: img)
    boom_sound_path = bomb_assets["boom_sound_path"]
    HUD_SCALE_X = 3.8
    HUD_SCALE_Y = 3.2
    hud_w = int(128 * HUD_SCALE_X)
    hud_h = int(48 * HUD_SCALE_Y)
    hud_texture = create_texture_from_pil(hud_raw.resize((hud_w, hud_h), Image.NEAREST))
    wall_texture_id, _, _ = create_texture_from_pil(wall_tex_raw.resize((64, 64), Image.NEAREST))
    runtime_display_lists = build_runtime_display_lists(CUSTOM_RUNTIME_GEOMETRY, wall_texture_id)
    task_stub_small = task_stub_src.resize((TASK_ICON_SIZE, TASK_ICON_SIZE), Image.NEAREST)
    gunitem_small = gunitem_raw.resize((40, 40), Image.NEAREST)
    bomb_icon_small = bomb_assets["bomb_icon_raw"].resize((40, 40), Image.NEAREST)
    activator_icon_small = activator_icon_raw.resize((40, 40), Image.NEAREST)
    stats_icon_raw = Image.open(resource_path("data/unknown.png")).convert("RGBA")
    door_left_tex = Image.open(resource_path("data/Lelevatordoor.png")).convert("RGBA")
    door_right_tex = Image.open(resource_path("data/Relevatordoor.png")).convert("RGBA")
    DOOR_CLOSE_STEPS = 12
    DOOR_PIL_H = 64
    DOOR_PIL_W_MIN = 48
    DOOR_PIL_W_MAX = DOOR_PIL_H
    door_left_frames = []
    door_right_frames = []
    for i in range(DOOR_CLOSE_STEPS):
        close_t = i / max(1, DOOR_CLOSE_STEPS - 1)
        thin_t = _clamp01((close_t - 0.65) / 0.35)
        door_w = int(DOOR_PIL_W_MAX * (1.0 - thin_t) + DOOR_PIL_W_MIN * thin_t)
        door_w = max(1, door_w)
        door_left_frames.append(door_left_tex.resize((door_w, DOOR_PIL_H), Image.NEAREST))
        door_right_frames.append(door_right_tex.resize((door_w, DOOR_PIL_H), Image.NEAREST))

    hexagaze_assets = hexagaze_logic.load_hexagaze_assets(resource_path)
    orb_cycle = ["red", "violet", "yellow", "green"]
    sentries = hexagaze_logic.collect_sentries(MAP, HEXAGAZE_RADIUS_MIN, HEXAGAZE_RADIUS_MAX, orb_cycle)
    sentry_projectiles = []
    hexagaze_config = {
        "radius_cells": HEXAGAZE_RADIUS_CELLS,
        "close_sight_radius": HEXAGAZE_CLOSE_SIGHT_RADIUS,
        "roll_durations": hexagaze_assets["roll_durations"],
        "roll_duration": HEXAGAZE_ROLL_DURATION,
        "burst_size": HEXAGAZE_BURST_SIZE,
        "first_shot_delay": HEXAGAZE_FIRST_SHOT_DELAY,
        "burst_delay": 0.14,
        "post_attack_wait": HEXAGAZE_POST_ATTACK_WAIT,
        "projectile_speed": HEXAGAZE_PROJECTILE_SPEED,
        "player_hit_radius": HEXAGAZE_PLAYER_HIT_RADIUS,
        "projectile_damage": HEXAGAZE_PROJECTILE_DAMAGE,
        "entry_burst_count": HEXAGAZE_ENTRY_BURST_COUNT,
        "entry_burst_speed": HEXAGAZE_ENTRY_BURST_SPEED,
        "homing_turn_rate": HEXAGAZE_HOMING_TURN_RATE,
        "snake_turn_rate": HEXAGAZE_SNAKE_TURN_RATE,
        "snake_wave_speed": HEXAGAZE_SNAKE_WAVE_SPEED,
        "snake_wave_amplitude": HEXAGAZE_SNAKE_WAVE_AMPLITUDE,
        "orb_cycle": orb_cycle,
    }
    mannequin_assets = mannequin_logic.load_mannequin_assets(resource_path, get_wav_duration)
    mannequin_state = mannequin_logic.create_mannequin_state(CUSTOM_RUNTIME_GEOMETRY or MAP)

    gun_pickups = []
    if CUSTOM_RUNTIME_GEOMETRY is not None:
        gun_pickups = list(CUSTOM_RUNTIME_GEOMETRY.get("gun_pickups", []))
    else:
        for y, row in enumerate(MAP):
            for x, c in enumerate(row):
                if c == "G":
                    gun_pickups.append((x + 0.5, y + 0.5))

    bomb_pickups = bomb_logic.collect_bomb_pickups(CUSTOM_RUNTIME_GEOMETRY or MAP)
    human_markers = collect_human_markers(MAP)
    rob_state = rob_logic.create_rob_state(MAP)
    lift_tiles = {(x, y) for y, row in enumerate(MAP) for x, c in enumerate(row) if c == "N"}
    orbs = [
        {"x": 5.5, "y": 5.5, "color": "yellow", "health": 20, "max_health": 20},
        {"x": 7.5, "y": 3.5, "color": "red", "health": 20, "max_health": 20},
        {"x": 9.5, "y": 6.5, "color": "green", "health": 20, "max_health": 20},
        {"x": 12.5, "y": 4.5, "color": "violet", "health": 20, "max_health": 20},
    ]
    lights = [(x + 0.5, y + 0.5) for y, row in enumerate(MAP) for x, c in enumerate(row) if c == "L"]
    light_states = {(lx, ly): True for lx, ly in lights}
    light_timers = {(lx, ly): time.time() for lx, ly in lights}

    state = {
        "selected_slot": 1,
        "has_gun": False,
        "slot2_item": None,
        "ammo": 17,
        "max_ammo": 17,
        "reloading": False,
        "reload_started_at": 0.0,
        "placed_bombs": [],
        "active_explosions": [],
        "gun_pickups": gun_pickups,
        "bomb_pickups": bomb_pickups,
        "human_markers": human_markers,
        "rob_state": rob_state,
        "orbs": orbs,
        "sentries": sentries,
        "sentry_projectiles": sentry_projectiles,
        "mannequin_state": mannequin_state,
        "player_health": PLAYER_MAX_HEALTH,
        "player_restart_at": None,
        "mannequin_restart_at": None,
        "next_punch_time": 0.0,
        "target_cell": None,
        **deja_vu_logic.build_deja_vu_state(DEJA_VU_MAX_CHARGE),
        "lights": lights,
        "light_states": light_states,
        "light_timers": light_timers,
        "start_cutscene_active": not custom_runtime_active,
        "start_cutscene_started": False,
        "start_cutscene_start_time": 0.0,
        "start_cutscene_open_t": 0.0,
        "start_cutscene_close_t": 0.0,
        "elevator_active": False,
        "elevator_start_time": 0.0,
        "elevator_from_angle": 0.0,
        "elevator_target_angle": 0.0,
        "elevator_close_t": 0.0,
        "elevator_enter_time": 0.0,
        "elevator_transition_to_testing": False,
        "stats_window_active": False,
        "dev_debug_window_active": False,
        "stats_animation_start": 0.0,
        "stats_counting_active": False,
        "stats_count_start": 0.0,
        "stats_can_skip": False,
        "stats_completed": False,
        "stats_flash_active": False,
        "stats_flash_start": 0.0,
        "stats_icon_active": False,
        "stats_icon_pulse_time": 0.0,
        "stats_progress_bar_current": 0.0,
        "stats_window_y": 0.0,
        "stats_shake_offset": 0.0,
        "stats_float_offset_x": 0.0,
        "stats_float_offset_y": 0.0,
        "stats_float_time": 0.0,
        "enemies_killed": 0,
        "flashback_last_kill_count": 0,
        "total_shots_fired": 0,
        "total_shots_hit": 0,
        "impact_particles": [],
        "bullet_marks": [],
    }

    start_door_anchor_x = player_x + math.cos(player_angle) * 0.62
    start_door_anchor_y = player_y + math.sin(player_angle) * 0.62
    ELEV_ROT_DUR = 1.0
    ELEV_DOOR_CLOSE_DUR = 2.0
    ELEV_DOOR_HOLD_DUR = 2.0
    ELEV_SHAKE_DUR = 2.0
    ELEV_TOTAL_DUR = ELEV_DOOR_CLOSE_DUR + ELEV_DOOR_HOLD_DUR + ELEV_SHAKE_DUR
    START_DOOR_WAIT_DUR = 3.0
    START_DOOR_OPEN_DUR = 0.55
    START_MOVE_DUR = 0.7
    START_DOOR_CLOSE_DUR = 0.45
    stats_count_duration = 2.0
    stats_flash_duration = 0.3
    stats_icon_base_size = 48
    stats_icon_max_size = 72
    stats_progress_bar_target = 67.0

    gunshoot_animating = False
    gunshoot_frame_index = 0
    shoot_acc = 0.0
    reload_anim_index = 0
    reload_anim_active = False
    reload_acc = 0.0
    activator_click_animating = False
    activator_click_frame_index = 0
    activator_click_acc = 0.0
    bomb_world_frame_index = 0
    bomb_world_anim_acc = 0.0
    hand_target_item_id = "fists"
    hand_previous_item_id = None
    hand_swap_progress = 1.0
    hand_swap_active = False
    punch_animating = False
    punch_frame_index = 0
    punch_acc = 0.0
    punch_side = "left"

    mannequin_attack_sound_path = mannequin_assets["attack_sound_path"]
    mannequin_attack_duration = mannequin_assets["attack_duration"]
    next_action = None
    fps_display = 0
    fps_timer = 0.0
    caption_timer = 0.0
    show_fps_overlay = get_show_fps()
    textures = {
        "texture_cache": get_cached_texture,
        "gun_pickup": gunitem_raw,
        "bomb_pickup": bomb_assets["bomb_icon_raw"],
        "target_marker": bomb_assets["target_marker_frames"][0],
        "bombon_frames": bomb_assets["bombon_frames_raw"],
        "boom_frames": bomb_assets["boom_frames_raw"],
        "orbs": orb_textures,
        "hexagaze_frames": hexagaze_assets["frames"],
        "hexagaze_rolls": hexagaze_assets["roll_animations"],
        "sentry_danger": hexagaze_assets["danger_frames"][0],
        "sentry_safe": hexagaze_assets["safe_frames"][0],
        "mannequin_frames": mannequin_assets["frames"],
        "ghost_frames": deja_vu_ghost_frames,
    }

    def restart_pending():
        return state["mannequin_restart_at"] is not None or state["player_restart_at"] is not None

    def rob_dialog_active():
        return state["rob_state"].get("active") and state["rob_state"].get("dialog_active", False)

    def rob_interaction_locked(now_value):
        if not state["rob_state"].get("active"):
            return False
        if state["rob_state"].get("dialog_active", False):
            return True
        return now_value < state["rob_state"].get("reaction_hold_until", 0.0)

    def is_render_point_visible(world_x, world_y, near_dist=1.3, back_margin=-0.18):
        if not rear_world_culling_enabled:
            return True
        dx = world_x - player_x
        dy = world_y - player_y
        dist = math.hypot(dx, dy)
        if dist <= near_dist:
            return True
        facing = (dx * math.cos(player_angle) + dy * math.sin(player_angle)) / max(0.0001, dist)
        return facing >= back_margin

    def trigger_player_death(now_value):
        if state["player_restart_at"] is not None or state["deja_vu_death_return_pending"]:
            return
        if state["deja_vu_active"] and state["deja_vu_snapshot"] is not None:
            deja_vu_logic.trigger_death_break(state, now_value=now_value)
            return
        state["player_restart_at"] = now_value + 0.35

    def damage_player(amount, now_value):
        if state["player_restart_at"] is not None:
            return
        if state["flashback_active"]:
            amount = max(0.0, amount - deja_vu_logic.FLASHBACK_DAMAGE_SHIELD)
        state["player_health"] = max(0, state["player_health"] - amount)
        if state["player_health"] <= 0:
            trigger_player_death(now_value)

    def damage_mannequin(amount):
        mannequin_state["restart_at"] = state["mannequin_restart_at"]
        killed = mannequin_logic.damage(mannequin_state, amount)
        if killed:
            state["enemies_killed"] += 1

    def player_can_see_mannequin():
        return mannequin_logic.player_can_see(mannequin_state, player_x, player_y, player_angle, has_line_of_sight)

    def push_mannequin_back():
        mannequin_logic.push_back(mannequin_state, MAP, player_x, player_y, player_angle, has_line_of_sight, is_walkable_cell)

    def damage_mannequin_from_player_attack(amount, register_shot_hit=False):
        if not mannequin_state["alive"]:
            return False
        mannequin_state["health"] = max(0, mannequin_state["health"] - amount)
        if register_shot_hit:
            state["total_shots_hit"] += 1
        mannequin_state["hidden_active"] = False
        mannequin_state["next_hidden_step_at"] = None
        mannequin_state["last_seen_by_player"] = True
        if mannequin_state["health"] <= 0:
            mannequin_state["alive"] = False
            state["enemies_killed"] += 1
        else:
            push_mannequin_back()
        return True

    def try_damage_target_under_cursor(amount, max_distance_cells):
        best_target = None
        best_dist = float("inf")
        if mannequin_state["alive"] and mannequin_state["x"] is not None and mannequin_state["y"] is not None:
            dx = mannequin_state["x"] - player_x
            dy = mannequin_state["y"] - player_y
            dist = math.hypot(dx, dy)
            angle_diff = wrap_angle(math.atan2(dy, dx) - player_angle)
            if dist <= max_distance_cells and abs(angle_diff) <= PUNCH_AIM_TOLERANCE and has_line_of_sight(player_x, player_y, mannequin_state["x"], mannequin_state["y"]):
                best_target = ("mannequin", None)
                best_dist = dist

        for orb_index, orb in enumerate(state["orbs"]):
            if orb["health"] <= 0:
                continue
            dx = orb["x"] - player_x
            dy = orb["y"] - player_y
            dist = math.hypot(dx, dy)
            angle_diff = wrap_angle(math.atan2(dy, dx) - player_angle)
            if dist <= max_distance_cells and abs(angle_diff) <= PUNCH_AIM_TOLERANCE and has_line_of_sight(player_x, player_y, orb["x"], orb["y"]) and dist < best_dist:
                best_target = ("orb", orb_index)
                best_dist = dist

        for sentry_index, sentry in enumerate(state["sentries"]):
            if sentry["health"] <= 0:
                continue
            dx = sentry["x"] - player_x
            dy = sentry["y"] - player_y
            dist = math.hypot(dx, dy)
            angle_diff = wrap_angle(math.atan2(dy, dx) - player_angle)
            if dist <= max_distance_cells and abs(angle_diff) <= PUNCH_AIM_TOLERANCE and has_line_of_sight(player_x, player_y, sentry["x"], sentry["y"]) and dist < best_dist:
                best_target = ("sentry", sentry_index)
                best_dist = dist

        if best_target is None:
            return False

        kind, idx = best_target
        if kind == "mannequin":
            return damage_mannequin_from_player_attack(amount)
        if kind == "orb":
            orb = state["orbs"][idx]
            previous_health = orb["health"]
            orb["health"] = max(0, orb["health"] - amount)
            if previous_health > 0 and orb["health"] <= 0:
                state["enemies_killed"] += 1
            return True

        sentry = state["sentries"][idx]
        previous_health = sentry["health"]
        sentry["health"] = max(0, sentry["health"] - amount)
        if previous_health > 0 and sentry["health"] <= 0:
            sentry["burst_shots_left"] = 0
            state["enemies_killed"] += 1
        return True

    def damage_entities_in_bomb_area(center_cell, radius_cells, now_value):
        min_x = center_cell[0] - radius_cells
        max_x = center_cell[0] + radius_cells
        min_y = center_cell[1] - radius_cells
        max_y = center_cell[1] + radius_cells
        player_cell = (int(player_x), int(player_y))
        if min_x <= player_cell[0] <= max_x and min_y <= player_cell[1] <= max_y:
            damage_player(5, now_value)
        mannequin_cell = (int(mannequin_state["x"]), int(mannequin_state["y"])) if mannequin_state["x"] is not None and mannequin_state["y"] is not None else None
        if mannequin_cell is not None and min_x <= mannequin_cell[0] <= max_x and min_y <= mannequin_cell[1] <= max_y:
            damage_mannequin(5)
        for orb in state["orbs"]:
            if orb["health"] <= 0:
                continue
            orb_cell = (int(orb["x"]), int(orb["y"]))
            if min_x <= orb_cell[0] <= max_x and min_y <= orb_cell[1] <= max_y:
                orb["health"] = max(0, orb["health"] - 5)
                if orb["health"] <= 0:
                    state["enemies_killed"] += 1
        for sentry in state["sentries"]:
            if sentry["health"] <= 0:
                continue
            sentry_cell = (int(sentry["x"]), int(sentry["y"]))
            if min_x <= sentry_cell[0] <= max_x and min_y <= sentry_cell[1] <= max_y:
                sentry["health"] = max(0, sentry["health"] - 5)
                if sentry["health"] <= 0:
                    sentry["burst_shots_left"] = 0
                    state["enemies_killed"] += 1

    def spawn_impact_particles(x, y, z, color, count=8, speed=0.9):
        if not impact_particles_enabled:
            return
        for _ in range(count):
            angle = random.uniform(0.0, math.tau)
            lateral_speed = random.uniform(0.06, 0.34) * speed
            upward_bias = random.uniform(-0.08, 0.34) * speed
            state["impact_particles"].append(
                {
                    "x": x + random.uniform(-0.035, 0.035),
                    "y": y + random.uniform(-0.035, 0.035),
                    "z": z + random.uniform(-0.025, 0.05),
                    "vx": math.cos(angle) * lateral_speed + random.uniform(-0.08, 0.08),
                    "vy": math.sin(angle) * lateral_speed + random.uniform(-0.08, 0.08),
                    "vz": upward_bias,
                    "size": random.uniform(0.014, 0.042),
                    "color": color,
                    "life": random.uniform(0.28, 0.82),
                    "gravity": random.uniform(1.4, 2.7),
                    "drag": random.uniform(0.84, 0.94),
                    "bounce": random.uniform(0.08, 0.26),
                }
            )

    def spawn_player_break_effect():
        base_x = player_x + math.cos(player_angle) * 0.24
        base_y = player_y + math.sin(player_angle) * 0.24
        base_z = player_z + PLAYER_EYE_HEIGHT * 0.58
        for color in ((1.0, 0.30, 0.24), (0.22, 0.72, 1.0), (0.95, 0.98, 1.0)):
            runtime_spawn_impact_particles(
                state,
                impact_particles_enabled,
                base_x + random.uniform(-0.05, 0.05),
                base_y + random.uniform(-0.05, 0.05),
                base_z + random.uniform(-0.07, 0.04),
                color,
                count=11,
                speed=1.25,
            )

    def start_break_sequence_from_debug(now_value):
        state["deja_vu_break_level"] = deja_vu_logic.DEJA_VU_BREAK_MAX_LEVEL
        state["deja_vu_blackout_started_at"] = None
        state["deja_vu_blackout_until"] = 0.0
        state["deja_vu_death_return_pending"] = False
        state["deja_vu_critical_freeze_until"] = now_value + deja_vu_logic.DEJA_VU_CRITICAL_FREEZE_DURATION
        state["deja_vu_critical_break_times"] = [
            now_value + 0.25,
            now_value + 0.95,
            now_value + 1.55,
        ]
        state["deja_vu_critical_break_index"] = 0
        state["flashback_pending"] = True

    def spawn_bullet_mark(hit_type, x, y, z):
        if not bullet_marks_enabled:
            return
        state["bullet_marks"].append(
            {
                "type": hit_type,
                "x": x,
                "y": y,
                "z": z,
                "life": 20.0,
                "size": random.uniform(0.028, 0.05),
                "alpha": random.uniform(0.18, 0.32),
                "expire_fast": False,
            }
        )
        overflow = len(state["bullet_marks"]) - 50
        if overflow > 0:
            for mark in state["bullet_marks"][:overflow]:
                mark["expire_fast"] = True

    def update_impact_particles(delta_time):
        kept = []
        for particle in state["impact_particles"]:
            particle["life"] -= delta_time
            if particle["life"] <= 0.0:
                continue
            particle["vz"] -= particle["gravity"] * delta_time
            particle["x"] += particle["vx"] * delta_time
            particle["y"] += particle["vy"] * delta_time
            particle["z"] += particle["vz"] * delta_time
            drag = particle["drag"] ** max(1.0, delta_time * 60.0)
            particle["vx"] *= drag
            particle["vy"] *= drag
            floor_here = get_floor_height(particle["x"], particle["y"])
            if particle["z"] <= floor_here:
                particle["z"] = floor_here
                particle["vx"] *= 0.55
                particle["vy"] *= 0.55
                particle["vz"] *= -particle["bounce"]
            kept.append(particle)
        state["impact_particles"] = kept

    def update_bullet_marks(delta_time):
        kept = []
        for mark in state["bullet_marks"]:
            life_decay = 4.5 if mark.get("expire_fast") else 1.0
            mark["life"] -= delta_time * life_decay
            if mark["life"] > 0.0:
                kept.append(mark)
        state["bullet_marks"] = kept

    def get_camera_origin():
        camera_right_x = math.cos(player_angle + math.pi / 2)
        camera_right_y = math.sin(player_angle + math.pi / 2)
        return (
            player_x + camera_right_x * bob_side,
            player_y + camera_right_y * bob_side,
            player_z + PLAYER_EYE_HEIGHT + bob_vertical - crouch_amount,
        )

    def get_view_ray():
        horizontal = math.cos(player_pitch)
        return (
            math.cos(player_angle) * horizontal,
            math.sin(player_angle) * horizontal,
            -math.sin(player_pitch),
        )

    def get_floor_particle_color(floor_z):
        return (
            min(1.0, 0.16 + floor_z * 0.10),
            min(1.0, 0.16 + floor_z * 0.03),
            0.18,
        )

    def get_ceiling_particle_color(ceiling_z):
        ceiling_tint = max(0.0, min(1.0, (ceiling_z - 1.3) / 2.2))
        return (0.08 + ceiling_tint * 0.03, 0.08 + ceiling_tint * 0.03, 0.10 + ceiling_tint * 0.04)

    def get_wall_sample_uv(hit_x, hit_y, hit_z):
        cell_x = math.floor(hit_x)
        cell_y = math.floor(hit_y)
        local_x = hit_x - cell_x
        local_y = hit_y - cell_y
        if min(local_x, 1.0 - local_x) < min(local_y, 1.0 - local_y):
            u = local_y
        else:
            u = local_x
        v = 1.0 - max(0.0, min(0.999, hit_z))
        return u % 1.0, v

    def get_entity_hit_info(sample_x, sample_y, sample_z):
        mannequin_state = state["mannequin_state"]
        if mannequin_state["alive"] and mannequin_state["x"] is not None and mannequin_state["y"] is not None:
            base_z = get_floor_height(mannequin_state["x"], mannequin_state["y"])
            if math.hypot(sample_x - mannequin_state["x"], sample_y - mannequin_state["y"]) <= 0.26 and base_z + 0.06 <= sample_z <= base_z + 0.98:
                frame_index = mannequin_logic.get_frame_index(mannequin_state, player_x, player_y, len(textures["mannequin_frames"]))
                frame = textures["mannequin_frames"][frame_index]
                hit_v = 1.0 - max(0.0, min(0.999, (sample_z - base_z) / 0.98))
                return {
                    "type": "mannequin",
                    "x": sample_x,
                    "y": sample_y,
                    "z": sample_z,
                    "color": sample_image_color(frame, 0.5, hit_v),
                }

        for orb in state["orbs"]:
            if orb["health"] <= 0:
                continue
            base_z = get_floor_height(orb["x"], orb["y"]) + 0.14
            radius = 0.18
            if math.hypot(sample_x - orb["x"], sample_y - orb["y"]) <= radius and base_z - 0.02 <= sample_z <= base_z + 0.34:
                hit_u = 0.5 + (sample_x - orb["x"]) / (radius * 2.0)
                hit_v = 1.0 - max(0.0, min(0.999, (sample_z - (base_z - 0.02)) / 0.36))
                return {
                    "type": "orb",
                    "entity": orb,
                    "x": sample_x,
                    "y": sample_y,
                    "z": sample_z,
                    "color": sample_image_color(textures["orbs"][orb["color"]], max(0.0, min(0.999, hit_u)), hit_v),
                }

        for sentry in state["sentries"]:
            if sentry["health"] <= 0:
                continue
            base_z = get_floor_height(sentry["x"], sentry["y"])
            if math.hypot(sample_x - sentry["x"], sample_y - sentry["y"]) <= 0.24 and base_z + 0.03 <= sample_z <= base_z + 0.74:
                roll_name = sentry.get("queued_roll")
                roll_frames = textures["hexagaze_rolls"].get(roll_name) if roll_name else None
                if roll_frames and sentry["burst_shots_left"] <= 0 and time.time() < sentry.get("roll_visible_until", 0.0):
                    elapsed = max(0.0, time.time() - sentry.get("roll_started_at", 0.0))
                    frame_index = int(elapsed / 0.06) % max(1, len(roll_frames))
                    frame = roll_frames[frame_index]
                else:
                    frame_index = hexagaze_logic.get_frame_index(sentry, player_x, player_y, len(textures["hexagaze_frames"]))
                    frame = textures["hexagaze_frames"][frame_index]
                hit_v = 1.0 - max(0.0, min(0.999, (sample_z - base_z) / 0.74))
                return {
                    "type": "sentry",
                    "entity": sentry,
                    "x": sample_x,
                    "y": sample_y,
                    "z": sample_z,
                    "color": sample_image_color(frame, 0.5, hit_v),
                }
        return None

    def get_shot_hit_info(max_distance=12.0, step=0.025):
        origin_x, origin_y, origin_z = get_camera_origin()
        ray_x, ray_y, ray_z = get_view_ray()
        distance = 0.05
        while distance <= max_distance:
            sample_x = origin_x + ray_x * distance
            sample_y = origin_y + ray_y * distance
            sample_z = origin_z + ray_z * distance

            entity_hit = get_entity_hit_info(sample_x, sample_y, sample_z)
            if entity_hit is not None:
                entity_hit["dist"] = distance
                return entity_hit

            if is_wall(sample_x, sample_y, sample_z):
                u, v = get_wall_sample_uv(sample_x, sample_y, sample_z)
                return {
                    "type": "wall",
                    "x": sample_x,
                    "y": sample_y,
                    "z": sample_z,
                    "u": u,
                    "v": v,
                    "dist": distance,
                }

            floor_z = get_floor_height(sample_x, sample_y, z_hint=sample_z)
            if sample_z <= floor_z + 0.01 and not is_wall(sample_x, sample_y, sample_z):
                return {
                    "type": "floor",
                    "x": sample_x,
                    "y": sample_y,
                    "z": floor_z,
                    "dist": distance,
                    "color": get_floor_particle_color(floor_z),
                }

            ceiling_here = get_ceiling_height(sample_x, sample_y, z_hint=sample_z)
            if sample_z >= ceiling_here - 0.01 and not is_wall(sample_x, sample_y, sample_z):
                return {
                    "type": "ceiling",
                    "x": sample_x,
                    "y": sample_y,
                    "z": ceiling_here,
                    "dist": distance,
                    "color": get_ceiling_particle_color(ceiling_here),
                }
            distance += step
        return None

    def build_hand_image(pil_frame, item_id):
        width_px, height_px = pil_frame.size
        hand_scale = PUNCH_SCALE if item_id == "fists" else GUN_SCALE
        new_w = int(width * hand_scale)
        new_h = int(height_px * (new_w / max(1, width_px)))
        if item_id == "fists":
            new_w = int(new_w * PUNCH_WIDTH_MULT)
            new_h = int(new_h * PUNCH_HEIGHT_MULT)
        return pil_frame.resize((max(1, new_w), max(1, new_h)), Image.NEAREST)

    def get_hand_pil_for_item(item_id):
        if item_id == "gun":
            if state["reloading"] and reload_anim_active:
                return gunreload_frames_raw[min(reload_anim_index, len(gunreload_frames_raw) - 1)]
            if gunshoot_animating:
                return gunshoot_frames_raw[min(gunshoot_frame_index, len(gunshoot_frames_raw) - 1)]
            return gun_img_raw
        if item_id == "fists":
            if punch_animating:
                frames = right_punch_frames_raw if punch_side == "right" else left_punch_frames_raw
                return frames[min(punch_frame_index, len(frames) - 1)]
            return punch_img_raw
        if item_id in {"bomb", "activator"}:
            return bomb_logic.get_hand_pil(item_id, bomb_assets, activator_click_animating, activator_click_frame_index)
        return None

    def get_selected_inventory_item_id():
        if state["selected_slot"] == 1 and state["has_gun"]:
            return "gun"
        if state["selected_slot"] == 2 and state["slot2_item"] == "bomb":
            return "bomb"
        if state["selected_slot"] == 2 and state["slot2_item"] == "activator":
            return "activator"
        return None

    def get_current_hand_item_id():
        if state["elevator_active"] or state["start_cutscene_active"]:
            return None
        return get_selected_inventory_item_id() or "fists"

    def update_hand_swap(delta_time):
        nonlocal hand_target_item_id, hand_previous_item_id, hand_swap_progress, hand_swap_active
        target_item_id = get_current_hand_item_id()
        if target_item_id != hand_target_item_id:
            hand_previous_item_id = hand_target_item_id
            hand_target_item_id = target_item_id
            if hand_previous_item_id != hand_target_item_id:
                hand_swap_progress = 0.0
                hand_swap_active = True
        if hand_swap_active:
            hand_swap_progress += delta_time / max(0.001, HAND_SWAP_DURATION)
            if hand_swap_progress >= 1.0:
                hand_swap_progress = 1.0
                hand_swap_active = False
                hand_previous_item_id = None

    def get_targeted_floor_cell(max_distance=3.2, step=0.03):
        return bomb_logic.get_targeted_floor_cell(player_x, player_y, player_angle, is_wall, state["placed_bombs"], max_distance=max_distance, step=step)

    def place_bomb():
        state["slot2_item"], _ = bomb_logic.place_bomb(
            state["selected_slot"],
            state["slot2_item"],
            state["placed_bombs"],
            player_x,
            player_y,
            player_angle,
            is_wall,
        )

    def trigger_activator():
        nonlocal activator_click_animating, activator_click_frame_index, activator_click_acc
        activator_click_animating, activator_click_frame_index, activator_click_acc, _ = bomb_logic.trigger_activator(
            state["selected_slot"],
            state["slot2_item"],
            state["placed_bombs"],
            activator_click_animating,
            time.time(),
        )

    def shoot_gun():
        nonlocal gunshoot_animating, gunshoot_frame_index, shoot_acc
        if state["selected_slot"] != 1 or not state["has_gun"] or state["reloading"]:
            return
        if state["ammo"] <= 0:
            start_reload()
            return
        state["ammo"] -= 1
        state["total_shots_fired"] += 1
        gunshoot_animating = True
        gunshoot_frame_index = 0
        shoot_acc = 0.0
        shot_hit = runtime_get_shot_hit_info(
            get_camera_origin,
            get_view_ray,
            state,
            textures,
            player_x,
            player_y,
            get_floor_height,
            get_ceiling_height,
            is_wall,
        )
        if shot_hit is None:
            return

        if shot_hit["type"] == "mannequin":
            if mannequin_state["alive"] and mannequin_state["mode"] == "observe" and player_can_see_mannequin():
                damage_mannequin_from_player_attack(1, register_shot_hit=True)
                runtime_spawn_impact_particles(state, impact_particles_enabled, shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=10)
            return

        if shot_hit["type"] == "orb":
            orb = shot_hit["entity"]
            orb["health"] -= 10
            state["total_shots_hit"] += 1
            runtime_spawn_impact_particles(state, impact_particles_enabled, shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=9)
            if orb["health"] <= 0:
                state["enemies_killed"] += 1
            return

        if shot_hit["type"] == "sentry":
            sentry = shot_hit["entity"]
            sentry["health"] -= 1
            state["total_shots_hit"] += 1
            runtime_spawn_impact_particles(state, impact_particles_enabled, shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=10)
            if sentry["health"] <= 0:
                sentry["health"] = 0
                sentry["burst_shots_left"] = 0
                state["enemies_killed"] += 1
            return

        if shot_hit["type"] == "wall":
            hit_color = sample_image_color(wall_tex_raw, shot_hit["u"], shot_hit["v"])
            runtime_spawn_impact_particles(state, impact_particles_enabled, shot_hit["x"], shot_hit["y"], shot_hit["z"], hit_color, count=8, speed=0.8)
            runtime_spawn_bullet_mark(state, bullet_marks_enabled, "wall", shot_hit["x"], shot_hit["y"], shot_hit["z"])
            return

        if shot_hit["type"] == "floor":
            runtime_spawn_impact_particles(state, impact_particles_enabled, shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=7, speed=0.72)
            runtime_spawn_bullet_mark(state, bullet_marks_enabled, "floor", shot_hit["x"], shot_hit["y"], shot_hit["z"])
            return

        if shot_hit["type"] == "ceiling":
            runtime_spawn_impact_particles(state, impact_particles_enabled, shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=7, speed=0.72)
            runtime_spawn_bullet_mark(state, bullet_marks_enabled, "ceiling", shot_hit["x"], shot_hit["y"], shot_hit["z"])

    def start_reload():
        nonlocal reload_anim_index, reload_anim_active, reload_acc
        if state["reloading"] or not state["has_gun"]:
            return
        state["reloading"] = True
        state["reload_started_at"] = time.time()
        reload_anim_active = True
        reload_anim_index = 0
        reload_acc = 0.0

    def punch_with_fists(mouse_button):
        nonlocal punch_animating, punch_frame_index, punch_acc, punch_side
        now_value = time.time()
        if now_value < state["next_punch_time"]:
            return
        state["next_punch_time"] = now_value + PUNCH_COOLDOWN
        punch_side = "right" if mouse_button == 3 else "left"
        punch_animating = True
        punch_frame_index = 0
        punch_acc = 0.0
        try_damage_target_under_cursor(PUNCH_DAMAGE, PUNCH_RANGE_CELLS)

    def use_selected_item(mouse_button):
        selected_item = None
        if state["selected_slot"] == 1 and state["has_gun"]:
            selected_item = "gun"
        elif state["selected_slot"] == 2 and state["slot2_item"] == "bomb":
            selected_item = "bomb"
        elif state["selected_slot"] == 2 and state["slot2_item"] == "activator":
            selected_item = "activator"

        if selected_item is None:
            if mouse_button in (1, 3):
                punch_with_fists(mouse_button)
            return
        if mouse_button != 1:
            return
        if selected_item == "gun":
            shoot_gun()
        elif selected_item == "bomb":
            place_bomb()
        else:
            trigger_activator()

    def deja_vu_available():
        return deja_vu_logic.is_available(
            state,
            blocked=(
                state["start_cutscene_active"]
                or state["elevator_active"]
                or restart_pending()
                or state["deja_vu_death_return_pending"]
                or deja_vu_logic.deja_vu_locked(state)
                or deja_vu_logic.critical_freeze_active(state, now_value=time.time())
            ),
            min_activation=DEJA_VU_MIN_ACTIVATION,
        )

    def player_can_see_enemy_point(enemy_x, enemy_y):
        return deja_vu_logic.can_see_enemy_point(
            player_x,
            player_y,
            player_angle,
            enemy_x,
            enemy_y,
            wrap_angle,
            has_line_of_sight,
        )

    def update_deja_vu_enemy_rewards(delta_time):
        visible_enemy_ids = set()
        if mannequin_state["alive"] and mannequin_state["x"] is not None and mannequin_state["y"] is not None and player_can_see_mannequin():
            visible_enemy_ids.add(("mannequin", 0))

        for orb_index, orb in enumerate(state["orbs"]):
            if orb["health"] <= 0:
                continue
            if player_can_see_enemy_point(orb["x"], orb["y"]):
                visible_enemy_ids.add(("orb", orb_index))

        for sentry_index, sentry in enumerate(state["sentries"]):
            if sentry["health"] <= 0:
                continue
            if player_can_see_enemy_point(sentry["x"], sentry["y"]):
                visible_enemy_ids.add(("sentry", sentry_index))
        deja_vu_logic.update_enemy_rewards(state, delta_time=delta_time, visible_enemy_ids=visible_enemy_ids)

    def capture_deja_vu_snapshot():
        return {
            "player_x": player_x,
            "player_y": player_y,
            "player_z": player_z,
            "player_angle": player_angle,
            "player_pitch": player_pitch,
            "bob_phase": bob_phase,
            "bob_vertical": bob_vertical,
            "bob_side": bob_side,
            "crouch_amount": crouch_amount,
            "vertical_velocity": vertical_velocity,
            "player_health": state["player_health"],
            "selected_slot": state["selected_slot"],
            "ammo": state["ammo"],
            "has_gun": state["has_gun"],
            "slot2_item": state["slot2_item"],
            "gun_pickups": list(state["gun_pickups"]),
            "bomb_pickups": list(state["bomb_pickups"]),
            "placed_bombs": copy.deepcopy(state["placed_bombs"]),
            "active_explosions": copy.deepcopy(state["active_explosions"]),
            "orbs": copy.deepcopy(state["orbs"]),
            "sentries": copy.deepcopy(state["sentries"]),
            "sentry_projectiles": copy.deepcopy(state["sentry_projectiles"]),
            "light_states": dict(state["light_states"]),
            "light_timers": dict(state["light_timers"]),
            "mannequin_state": copy.deepcopy(mannequin_state),
            "rob_state": copy.deepcopy(state["rob_state"]),
            "total_shots_fired": state["total_shots_fired"],
            "total_shots_hit": state["total_shots_hit"],
            "enemies_killed": state["enemies_killed"],
        }

    def restore_deja_vu_snapshot(snapshot):
        nonlocal player_x, player_y, player_z, player_angle, player_pitch
        nonlocal bob_phase, bob_vertical, bob_side, crouch_amount, vertical_velocity
        player_x = snapshot["player_x"]
        player_y = snapshot["player_y"]
        player_z = snapshot["player_z"]
        player_angle = snapshot["player_angle"]
        player_pitch = snapshot.get("player_pitch", 0.0)
        bob_phase = snapshot.get("bob_phase", 0.0)
        bob_vertical = snapshot.get("bob_vertical", 0.0)
        bob_side = snapshot.get("bob_side", 0.0)
        crouch_amount = snapshot.get("crouch_amount", 0.0)
        vertical_velocity = snapshot.get("vertical_velocity", 0.0)
        state["player_health"] = snapshot["player_health"]
        state["selected_slot"] = snapshot["selected_slot"]
        state["ammo"] = snapshot["ammo"]
        state["has_gun"] = snapshot["has_gun"]
        state["slot2_item"] = snapshot["slot2_item"]
        state["gun_pickups"] = list(snapshot["gun_pickups"])
        state["bomb_pickups"] = list(snapshot["bomb_pickups"])
        state["placed_bombs"] = copy.deepcopy(snapshot["placed_bombs"])
        state["active_explosions"] = copy.deepcopy(snapshot["active_explosions"])
        state["orbs"] = copy.deepcopy(snapshot["orbs"])
        state["sentries"] = copy.deepcopy(snapshot["sentries"])
        state["sentry_projectiles"] = copy.deepcopy(snapshot["sentry_projectiles"])
        state["light_states"] = dict(snapshot["light_states"])
        state["light_timers"] = dict(snapshot["light_timers"])
        mannequin_state.clear()
        mannequin_state.update(copy.deepcopy(snapshot["mannequin_state"]))
        state["rob_state"] = copy.deepcopy(snapshot.get("rob_state", state["rob_state"]))
        state["total_shots_fired"] = snapshot["total_shots_fired"]
        state["total_shots_hit"] = snapshot["total_shots_hit"]
        state["enemies_killed"] = snapshot["enemies_killed"]

    def activate_deja_vu():
        if not deja_vu_available():
            return
        now_local = time.time()
        deja_vu_logic.activate(
            state,
            now_value=now_local,
            snapshot=capture_deja_vu_snapshot(),
            player_x=player_x,
            player_y=player_y,
        )

    def finish_deja_vu(now_value=None):
        now_local = time.time() if now_value is None else now_value
        result = deja_vu_logic.finish(
            state,
            now_value=now_local,
            max_charge=DEJA_VU_MAX_CHARGE,
            recharge_delay=DEJA_VU_RECHARGE_DELAY,
        )
        if result["snapshot"] is None:
            return
        restore_deja_vu_snapshot(result["snapshot"])
        if result["heal"] > 0 and state["player_health"] < PLAYER_MAX_HEALTH:
            state["player_health"] = min(PLAYER_MAX_HEALTH, state["player_health"] + result["heal"])

    def update_deja_vu(delta_time):
        now_local = time.time()
        if state["deja_vu_death_return_pending"]:
            return
        deja_vu_logic.update_return_fade(state, now_value=now_local, return_fade=DEJA_VU_RETURN_FADE)
        if state["deja_vu_active"]:
            update_deja_vu_enemy_rewards(delta_time)
        if deja_vu_logic.update_runtime(
            state,
            now_value=now_local,
            delta_time=delta_time,
            max_charge=DEJA_VU_MAX_CHARGE,
            fast_charge_cap=DEJA_VU_FAST_CHARGE_CAP,
            fast_charge_time=DEJA_VU_FAST_CHARGE_TIME,
            slow_charge_time=DEJA_VU_SLOW_CHARGE_TIME,
            ghost_lifetime=DEJA_VU_GHOST_LIFETIME,
            ghost_interval=DEJA_VU_GHOST_INTERVAL,
            player_x=player_x,
            player_y=player_y,
        ):
            finish_deja_vu(now_local)

    def get_deja_vu_visual_mix(now_value):
        if state["deja_vu_active"]:
            return _clamp01((now_value - state["deja_vu_started_at"]) / DEJA_VU_ENTER_FADE)
        if state["deja_vu_return_started_at"] is not None:
            return 1.0 - _clamp01((now_value - state["deja_vu_return_started_at"]) / DEJA_VU_RETURN_FADE)
        return 0.0

    def draw_deja_vu_world_overlay(now_value):
        if not screen_effects_enabled:
            return
        deja_vu_visual_mix = get_deja_vu_visual_mix(now_value)
        if deja_vu_visual_mix <= 0.001:
            return

        overlay_w = render_width
        overlay_h = render_height
        copy_framebuffer_to_texture(deja_screen_texture[0], overlay_w, overlay_h)
        projection, viewport = begin_overlay(overlay_w, overlay_h)
        try:
            if state["deja_vu_active"]:
                split_alpha = 0.13 + 0.18 * deja_vu_visual_mix
                split_shift = max(1, int(4 + 9 * deja_vu_visual_mix))
                draw_overlay_texture(deja_screen_texture[0], -split_shift, 0, overlay_w, overlay_h, tint=(1.0, 0.28, 0.22), alpha=split_alpha)
                draw_overlay_texture(deja_screen_texture[0], split_shift, 0, overlay_w, overlay_h, tint=(0.24, 0.55, 1.0), alpha=split_alpha)
                _draw_rect(white_texture_id, 0, 0, overlay_w, overlay_h, (32, 18, 24), alpha=0.06 + 0.08 * deja_vu_visual_mix)
                pulse = (math.sin((now_value - state["deja_vu_started_at"]) * 8.0) + 1.0) * 0.5
                border_alpha = 0.10 + pulse * 0.16 * deja_vu_visual_mix
                _draw_rect(white_texture_id, 10, 10, overlay_w - 20, 3, (120, 255, 235), alpha=border_alpha)
                _draw_rect(white_texture_id, 10, overlay_h - 13, overlay_w - 20, 3, (120, 255, 235), alpha=border_alpha)
                _draw_rect(white_texture_id, 10, 10, 3, overlay_h - 20, (120, 255, 235), alpha=border_alpha)
                _draw_rect(white_texture_id, overlay_w - 13, 10, 3, overlay_h - 20, (120, 255, 235), alpha=border_alpha)
            elif state["deja_vu_return_started_at"] is not None:
                rewind_progress = _clamp01((now_value - state["deja_vu_return_started_at"]) / DEJA_VU_RETURN_FADE)
                collapse_strength = 1.0 - rewind_progress
                collapse_shift = max(0, int(14 * collapse_strength))
                collapse_alpha = 0.22 * collapse_strength
                if collapse_shift > 0:
                    draw_overlay_texture(deja_screen_texture[0], -collapse_shift, 0, overlay_w, overlay_h, tint=(1.0, 0.32, 0.26), alpha=collapse_alpha)
                    draw_overlay_texture(deja_screen_texture[0], collapse_shift, 0, overlay_w, overlay_h, tint=(0.28, 0.62, 1.0), alpha=collapse_alpha)
                center_w = max(16, int(overlay_w * (0.22 + 0.78 * collapse_strength)))
                center_h = max(16, int(overlay_h * (0.22 + 0.78 * collapse_strength)))
                center_x = (overlay_w - center_w) // 2
                center_y = (overlay_h - center_h) // 2
                frame_alpha = 0.24 * collapse_strength
                fill_alpha = 0.13 * collapse_strength
                _draw_rect(white_texture_id, center_x, center_y, center_w, center_h, (210, 255, 250), alpha=fill_alpha)
                _draw_rect(white_texture_id, center_x, center_y, center_w, 3, (210, 255, 250), alpha=frame_alpha)
                _draw_rect(white_texture_id, center_x, center_y + center_h - 3, center_w, 3, (210, 255, 250), alpha=frame_alpha)
                _draw_rect(white_texture_id, center_x, center_y, 3, center_h, (210, 255, 250), alpha=frame_alpha)
                _draw_rect(white_texture_id, center_x + center_w - 3, center_y, 3, center_h, (210, 255, 250), alpha=frame_alpha)
        finally:
            end_overlay(projection, viewport)

    def draw_deja_vu_failure_overlay(now_value):
        blackout_active = deja_vu_logic.blackout_active(state, now_value=now_value)
        freeze_active = deja_vu_logic.critical_freeze_active(state, now_value=now_value)
        break_strength = deja_vu_logic.break_overlay_strength(state)
        if not blackout_active and not freeze_active and break_strength <= 0.001:
            return

        projection, viewport = begin_overlay(width, height)
        try:
            if blackout_active:
                _draw_rect(white_texture_id, 0, 0, width, height, (0, 0, 0), alpha=0.98)
                blackout_start = state["deja_vu_blackout_started_at"] or now_value
                blackout_ratio = _clamp01((now_value - blackout_start) / max(0.001, deja_vu_logic.DEJA_VU_BLACKOUT_DURATION))
                for bar_index in range(12):
                    band_y = int((height / 12) * bar_index + math.sin(now_value * 10.0 + bar_index) * 8.0)
                    band_h = 8 + (bar_index % 3) * 6
                    band_alpha = 0.06 + 0.14 * abs(math.sin(now_value * 7.0 + bar_index * 1.7))
                    band_color = (255, 70 + (bar_index % 4) * 28, 52) if bar_index % 2 == 0 else (70, 190, 255)
                    _draw_rect(white_texture_id, 0, band_y, width, band_h, band_color, alpha=band_alpha)
                crack_w = max(40, int(width * (0.18 + blackout_ratio * 0.34)))
                crack_h = max(16, int(height * (0.02 + blackout_ratio * 0.05)))
                center_x = width // 2 - crack_w // 2
                center_y = height // 2 - crack_h // 2
                _draw_rect(white_texture_id, center_x, center_y, crack_w, crack_h, (240, 245, 255), alpha=0.24 + 0.18 * blackout_ratio)
                for shard_index in range(7):
                    shard_x = int(width * 0.5 + math.sin(now_value * 11.0 + shard_index * 0.9) * (80 + shard_index * 18))
                    shard_y = int(height * 0.5 + math.cos(now_value * 9.0 + shard_index * 1.2) * (30 + shard_index * 10))
                    _draw_rect(white_texture_id, shard_x, shard_y, 2 + (shard_index % 2), 16 + shard_index * 4, (255, 255, 255), alpha=0.16)
                return

            copy_framebuffer_to_texture(deja_screen_texture[0], width, height)
            interference_alpha = 0.03 + break_strength * 0.14
            shift = max(1, int(2 + break_strength * 9 + (3 if freeze_active else 0)))
            draw_overlay_texture(deja_screen_texture[0], -shift, 0, width, height, tint=(1.0, 0.36, 0.28), alpha=interference_alpha)
            draw_overlay_texture(deja_screen_texture[0], shift, 0, width, height, tint=(0.28, 0.70, 1.0), alpha=interference_alpha)
            line_count = 5 + int(break_strength * 18)
            for line_index in range(line_count):
                line_y = int((height / max(1, line_count)) * line_index + math.sin(now_value * 4.5 + line_index * 1.8) * 9.0)
                line_h = 1 + (line_index % 3)
                alpha = 0.03 + break_strength * 0.06
                _draw_rect(white_texture_id, 0, line_y, width, line_h, (180, 255, 250), alpha=alpha)
            if freeze_active:
                pulse = (math.sin(now_value * 13.0) + 1.0) * 0.5
                _draw_rect(white_texture_id, 0, 0, width, height, (22, 30, 36), alpha=0.12 + pulse * 0.1)
                border_alpha = 0.14 + pulse * 0.12
                _draw_rect(white_texture_id, 0, 0, width, 3, (255, 90, 70), alpha=border_alpha)
                _draw_rect(white_texture_id, 0, height - 3, width, 3, (110, 220, 255), alpha=border_alpha)
                _draw_rect(white_texture_id, 0, 0, 3, height, (255, 90, 70), alpha=border_alpha)
                _draw_rect(white_texture_id, width - 3, 0, 3, height, (110, 220, 255), alpha=border_alpha)
        finally:
            end_overlay(projection, viewport)

    def draw_flashback_overlay(now_value):
        if not (state["flashback_active"] or state["flashback_post_active"] or state["flashback_death_active"]):
            return
        projection, viewport = begin_overlay(width, height)
        try:
            fade_strength = deja_vu_logic.flashback_fade_strength(state, now_value=now_value)
            if state["flashback_active"] or fade_strength > 0.001:
                pulse = (math.sin(now_value * 8.0) + 1.0) * 0.5
                active_mix = 1.0 if state["flashback_active"] else fade_strength
                _draw_rect(white_texture_id, 0, 0, width, height, (132, 0, 0), alpha=(0.24 + pulse * 0.17) * active_mix)
                _draw_rect(white_texture_id, 0, 0, width, height, (58, 0, 0), alpha=0.18 * active_mix)
                copy_framebuffer_to_texture(deja_screen_texture[0], width, height)
                glitch_shift = 3 + int(pulse * 6)
                glitch_alpha = (0.08 + pulse * 0.07) * active_mix
                draw_overlay_texture(deja_screen_texture[0], -glitch_shift, 0, width, height, tint=(1.0, 0.18, 0.18), alpha=glitch_alpha)
                draw_overlay_texture(deja_screen_texture[0], glitch_shift, 0, width, height, tint=(1.0, 0.48, 0.18), alpha=glitch_alpha * 0.85)
                band_count = 10
                for band_index in range(band_count):
                    band_y = int((height / band_count) * band_index + math.sin(now_value * 7.0 + band_index * 1.9) * 12.0)
                    band_h = 2 + (band_index % 3) * 2
                    _draw_rect(white_texture_id, 0, band_y, width, band_h, (255, 90, 70), alpha=(0.03 + pulse * 0.045) * active_mix)
                for shard_index in range(8):
                    shard_x = int((shard_index / 7.0) * width + math.sin(now_value * 9.0 + shard_index) * 26.0)
                    shard_y = int(height * 0.18 + shard_index * (height * 0.075))
                    _draw_rect(white_texture_id, shard_x, shard_y, 2, 18 + shard_index * 3, (255, 210, 210), alpha=0.08 * active_mix)
            if state["flashback_post_active"]:
                remaining = max(0.0, state["flashback_post_remaining"])
                whole_seconds = max(0, int(math.ceil(remaining)))
                danger = remaining <= 10.0
                second_phase = 1.0 - (remaining % 1.0)
                pulse_window = max(0.0, 1.0 - second_phase * (1.7 if danger else 1.25))
                pulse = 1.0 + pulse_window * (0.30 if danger else 0.18)
                timer_text = f"{whole_seconds:02d}s"
                timer_color = (255, 88, 72) if danger else (255, 214, 214)
                timer_y = 26 - int((pulse - 1.0) * 12)
                _draw_text(font_hud_big, timer_text, timer_color, width // 2 - 20, timer_y)
            if state["flashback_death_active"]:
                progress = deja_vu_logic.flashback_death_progress(state, now_value=now_value)
                _draw_rect(white_texture_id, 0, 0, width, height, (10, 0, 0), alpha=0.18 + progress * 0.52)
        finally:
            end_overlay(projection, viewport)

    def draw_crt_overlay(now_value):
        if not screen_effects_enabled:
            return
        projection, viewport = begin_overlay(width, height)
        try:
            draw_overlay_texture(crt_overlay_texture[0], 0, 0, width, height, alpha=1.0)
            pulse = 0.03 + ((math.sin(now_value * 1.7) + 1.0) * 0.5) * 0.035
            _draw_rect(white_texture_id, 0, 0, width, height, (10, 18, 10), alpha=pulse)
        finally:
            end_overlay(projection, viewport)

    def render_impact_particles():
        if not impact_particles_enabled:
            return
        for particle in state["impact_particles"]:
            if math.hypot(particle["x"] - player_x, particle["y"] - player_y) > 12.0:
                continue
            if not is_render_point_visible(particle["x"], particle["y"], near_dist=0.9, back_margin=-0.08):
                continue
            size = particle["size"]
            life_alpha = max(0.18, min(1.0, particle["life"] / 0.7))
            draw_box(
                particle["x"] - size * 0.5,
                particle["z"],
                particle["y"] - size * 0.5,
                size,
                size,
                particle["color"],
                alpha=life_alpha,
            )

    def render_bullet_marks():
        if not bullet_marks_enabled or not state["bullet_marks"]:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        try:
            for mark in state["bullet_marks"]:
                if math.hypot(mark["x"] - player_x, mark["y"] - player_y) > 6.0:
                    continue
                if not is_render_point_visible(mark["x"], mark["y"], near_dist=0.9, back_margin=-0.08):
                    continue
                size = mark["size"]
                half = size * 0.5
                fade = 1.0 if mark["life"] > 4.0 else max(0.0, mark["life"] / 4.0)
                alpha = mark["alpha"] * fade
                if alpha <= 0.0:
                    continue
                glColor4f(0.08, 0.08, 0.08, alpha)
                glBegin(GL_QUADS)
                if mark["type"] == "floor":
                    z = mark["z"] + 0.006
                    glVertex3f(mark["x"] - half, z, mark["y"] - half)
                    glVertex3f(mark["x"] + half, z, mark["y"] - half)
                    glVertex3f(mark["x"] + half, z, mark["y"] + half)
                    glVertex3f(mark["x"] - half, z, mark["y"] + half)
                elif mark["type"] == "ceiling":
                    z = mark["z"] - 0.006
                    glVertex3f(mark["x"] - half, z, mark["y"] + half)
                    glVertex3f(mark["x"] + half, z, mark["y"] + half)
                    glVertex3f(mark["x"] + half, z, mark["y"] - half)
                    glVertex3f(mark["x"] - half, z, mark["y"] - half)
                else:
                    cell_x = math.floor(mark["x"])
                    cell_y = math.floor(mark["y"])
                    local_x = mark["x"] - cell_x
                    local_y = mark["y"] - cell_y
                    inset = 0.006
                    if min(local_x, 1.0 - local_x) < min(local_y, 1.0 - local_y):
                        wall_x = cell_x + (inset if local_x < 0.5 else 1.0 - inset)
                        glVertex3f(wall_x, mark["z"] - half, mark["y"] - half)
                        glVertex3f(wall_x, mark["z"] + half, mark["y"] - half)
                        glVertex3f(wall_x, mark["z"] + half, mark["y"] + half)
                        glVertex3f(wall_x, mark["z"] - half, mark["y"] + half)
                    else:
                        wall_y = cell_y + (inset if local_y < 0.5 else 1.0 - inset)
                        glVertex3f(mark["x"] - half, mark["z"] - half, wall_y)
                        glVertex3f(mark["x"] + half, mark["z"] - half, wall_y)
                        glVertex3f(mark["x"] + half, mark["z"] + half, wall_y)
                        glVertex3f(mark["x"] - half, mark["z"] + half, wall_y)
                glEnd()
        finally:
            glEnable(GL_DEPTH_TEST)

    def draw_hud_overlay():
        projection, viewport = begin_overlay(width, height)
        try:
            if show_fps_overlay:
                fps_box_w = 96
                fps_box_h = 34
                fps_box_x = width - fps_box_w - 20
                fps_box_y = 20
                _draw_rect(white_texture_id, fps_box_x, fps_box_y, fps_box_w, fps_box_h, (4, 10, 4), alpha=0.82)
                _draw_rect(white_texture_id, fps_box_x, fps_box_y, fps_box_w, 2, (0, 255, 0))
                _draw_rect(white_texture_id, fps_box_x, fps_box_y + fps_box_h - 2, fps_box_w, 2, (0, 255, 0))
                _draw_rect(white_texture_id, fps_box_x, fps_box_y, 2, fps_box_h, (0, 255, 0))
                _draw_rect(white_texture_id, fps_box_x + fps_box_w - 2, fps_box_y, 2, fps_box_h, (0, 255, 0))
                _draw_text(font_hud, f"FPS: {fps_display}", (0, 255, 0), fps_box_x + 10, fps_box_y + 8)

            task_margin = 20
            task_pad = 10
            task_box_w = 340
            task_box_h = 92
            if not state["has_gun"]:
                _draw_rect(white_texture_id, task_margin, task_margin, task_box_w, task_box_h, (5, 8, 5), alpha=0.82)
                _draw_rect(white_texture_id, task_margin, task_margin, task_box_w, 2, (0, 255, 0))
                _draw_rect(white_texture_id, task_margin, task_margin + task_box_h - 2, task_box_w, 2, (0, 255, 0))
                _draw_rect(white_texture_id, task_margin, task_margin, 2, task_box_h, (0, 255, 0))
                _draw_rect(white_texture_id, task_margin + task_box_w - 2, task_margin, 2, task_box_h, (0, 255, 0))
                task_icon_texture_id, _, _ = get_cached_texture(task_stub_small)
                _draw_text(font_title, "TASK", (0, 255, 0), task_margin + task_pad, task_margin + task_pad)
                draw_overlay_texture(task_icon_texture_id, task_margin + task_pad, task_margin + 32, TASK_ICON_SIZE, TASK_ICON_SIZE)
            deja_now = time.time()
            if state["deja_vu_active"]:
                deja_display_charge = max(0.0, state["deja_vu_active_budget"] - (deja_now - state["deja_vu_started_at"]))
            else:
                deja_display_charge = state["deja_vu_charge"]
            deja_ready = deja_display_charge >= DEJA_VU_MIN_ACTIVATION and deja_vu_available()
            if deja_vu_logic.deja_vu_locked(state):
                deja_state = "LOCKED"
                deja_color = (180, 96, 96)
            elif state["deja_vu_active"] or deja_ready:
                deja_color = (120, 255, 235)
                deja_state = f"{deja_display_charge:04.1f}s"
            else:
                deja_color = (110, 130, 130)
                if deja_now < state["deja_vu_recharge_available_at"]:
                    deja_state = f"WAIT {max(0.0, state['deja_vu_recharge_available_at'] - deja_now):03.1f}s"
                else:
                    deja_state = f"{deja_display_charge:04.1f}s"

            hud_x = width - hud_w - 20
            hud_y = height - hud_h - 20
            draw_overlay_texture(hud_texture[0], hud_x, hud_y, hud_w, hud_h)
            _draw_text(font_hud, "AMMO:", (0, 255, 0), hud_x + 26, hud_y + 28)
            _draw_text(font_hud_big, f"{state['ammo']}/{state['max_ammo']}", (0, 255, 0), hud_x + 23, hud_y + 48)

            hp_percent = state["player_health"] / max(1, PLAYER_MAX_HEALTH)
            filled_blocks = int(10 * hp_percent)
            start_hp_x = hud_x + hud_w // 2 + 20
            start_hp_y = hud_y + 40
            for i in range(10):
                col = (255, 0, 0) if i < filled_blocks else (34, 0, 0)
                _draw_rect(white_texture_id, start_hp_x + i * 13, start_hp_y, 10, 10, col, alpha=0.95)
            _draw_text(font_hud, "HP:", (0, 255, 0), start_hp_x, start_hp_y - 14)

            elapsed = time.time() - hud_start_time
            minutes = int(elapsed // 60) % 60
            seconds = int(elapsed % 60)
            milliseconds = int((elapsed % 1) * 1000)
            _draw_rect(white_texture_id, hud_x + 30, hud_y + hud_h - 55, 80, 28, (0, 0, 0), alpha=0.8)
            _draw_text(font_clock, f"{minutes:02}:{seconds:02}:{milliseconds:03}", (0, 255, 0), hud_x + 35, hud_y + hud_h - 49)

            deja_x = hud_x - 220
            deja_y = hud_y + 20
            _draw_rect(white_texture_id, deja_x, deja_y, 190, 56, (0, 18, 18), alpha=0.86)
            _draw_rect(white_texture_id, deja_x, deja_y, 190, 2, deja_color)
            _draw_rect(white_texture_id, deja_x, deja_y + 54, 190, 2, deja_color)
            _draw_rect(white_texture_id, deja_x, deja_y, 2, 56, deja_color)
            _draw_rect(white_texture_id, deja_x + 188, deja_y, 2, 56, deja_color)
            _draw_text(font_hud, "DEJA VU [V]", deja_color, deja_x + 12, deja_y + 6)
            _draw_text(font_hud_big, deja_state, deja_color, deja_x + 12, deja_y + 26)
            _draw_rect(white_texture_id, deja_x + 12, deja_y + 46, 166, 4, (20, 40, 40), alpha=0.95)
            _draw_rect(white_texture_id, deja_x + 12, deja_y + 46, int(166 * max(0.0, min(1.0, deja_display_charge / DEJA_VU_MAX_CHARGE))), 4, deja_color, alpha=0.95)

            slot_size = 32
            slot_spacing = 6
            start_x = hud_x + hud_w // 2 - (2 * slot_size + 1.5 * slot_spacing)
            start_y = hud_y + hud_h - slot_size - 35
            for i in range(5):
                slot_x = start_x + i * (slot_size + slot_spacing)
                if (i + 1) == state["selected_slot"]:
                    _draw_rect(white_texture_id, slot_x - 2, start_y - 2, slot_size + 4, slot_size + 4, (255, 255, 0), alpha=0.95)
                _draw_rect(white_texture_id, slot_x, start_y, slot_size, slot_size, (40, 40, 40), alpha=0.88)
                _draw_text(font_slot, str(i + 1), (0, 255, 0), slot_x + 11, start_y + slot_size + 8)

            gun_icon_id, _, _ = get_cached_texture(gunitem_small)
            bomb_icon_id, _, _ = get_cached_texture(bomb_icon_small)
            activator_icon_id, _, _ = get_cached_texture(activator_icon_small)
            if state["has_gun"]:
                draw_overlay_texture(gun_icon_id, start_x - 4, start_y - 4, 40, 40)
            if state["slot2_item"] == "bomb":
                draw_overlay_texture(bomb_icon_id, start_x + slot_size + slot_spacing - 4, start_y - 4, 40, 40)
            elif state["slot2_item"] == "activator":
                draw_overlay_texture(activator_icon_id, start_x + slot_size + slot_spacing - 4, start_y - 4, 40, 40)

            if mannequin_state["alive"] and mannequin_state["mode"] == "observe" and player_can_see_mannequin():
                mannequin_bar_w = 140
                mannequin_bar_h = 16
                mannequin_bar_x = width // 2 - mannequin_bar_w // 2
                mannequin_bar_y = height // 2 - 90
                _draw_rect(white_texture_id, mannequin_bar_x, mannequin_bar_y, mannequin_bar_w, mannequin_bar_h, (25, 0, 0), alpha=0.9)
                fill_w = int(mannequin_bar_w * (mannequin_state["health"] / max(1, mannequin_state["max_health"])))
                _draw_rect(white_texture_id, mannequin_bar_x, mannequin_bar_y, fill_w, mannequin_bar_h, (220, 40, 40), alpha=0.95)
                _draw_text(font_hud, "MANNEQUIN", (255, 255, 255), width // 2 - 44, mannequin_bar_y - 20)

            _draw_rect(white_texture_id, width // 2 - 10, height // 2, 20, 2, (255, 255, 255))
            _draw_rect(white_texture_id, width // 2, height // 2 - 10, 2, 20, (255, 255, 255))

            if not state["elevator_active"] and not state["start_cutscene_active"]:
                gun_y = height - 20
                hand_slide_distance = int(height * 0.58)
                hand_swap_eased = _ease_out_cubic(hand_swap_progress)
                if hand_swap_active and hand_previous_item_id is not None:
                    previous_pil = get_hand_pil_for_item(hand_previous_item_id)
                    if previous_pil is not None:
                        prev_texture_id, prev_w, prev_h = get_cached_hand_texture(previous_pil, hand_previous_item_id)
                        previous_y = gun_y + int(hand_slide_distance * hand_swap_eased)
                        draw_overlay_texture(prev_texture_id, width // 2 - prev_w // 2, previous_y - prev_h, prev_w, prev_h)
                current_pil = get_hand_pil_for_item(hand_target_item_id)
                if current_pil is not None:
                    current_texture_id, current_w, current_h = get_cached_hand_texture(current_pil, hand_target_item_id)
                    current_y = gun_y if not hand_swap_active else gun_y + int(hand_slide_distance * (1.0 - hand_swap_eased))
                    draw_overlay_texture(current_texture_id, width // 2 - current_w // 2, current_y - current_h, current_w, current_h)
        finally:
            end_overlay(projection, viewport)

    def draw_intro_overlay():
        nonlocal intro_active, intro_index, intro_fade_started
        if not intro_active:
            return
        progress = (time.time() - intro_start) / intro_duration
        if progress >= 1.0:
            intro_active = False
            return
        backdrop_alpha = max(0.22, 0.55 - progress * 0.28)
        _draw_rect(white_texture_id, 0, 0, width, height, (0, 0, 0), alpha=backdrop_alpha)
        for pixel in pixel_grid:
            px, py, enabled = pixel
            if enabled and random.random() < progress * 0.2:
                pixel[2] = False
            if pixel[2]:
                shade = random.randint(0, 120)
                _draw_rect(white_texture_id, px, py, pixel_size, pixel_size, (shade, shade, shade), alpha=0.92)
        if intro_index < len(intro_text):
            intro_index += 1
        shown = intro_text[:intro_index]
        if intro_index >= len(intro_text):
            intro_fade_started = True
        current_font = font_intro
        if intro_fade_started:
            fade_time = max(0.0, time.time() - intro_start - 2.0)
            remain_ratio = max(0.0, 1.0 - fade_time * 0.25)
            visible_len = int(len(shown) * remain_ratio)
            shown = shown[:visible_len]
            chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@!?$%"
            glitched = []
            for ch in shown:
                glitched.append(random.choice(chars) if random.random() < 0.15 * fade_time else ch)
            shown = "".join(glitched)
            font_size = int(42 * remain_ratio)
            if font_size <= 6 or visible_len <= 0:
                intro_active = False
                return
            current_font = runtime_make_font(font_size)
        if shown:
            bbox = current_font.getbbox(shown)
            text_w = max(1, bbox[2] - bbox[0] + 2)
            text_h = max(1, bbox[3] - bbox[1] + 2)
            panel_x = width // 2 - text_w // 2 - 28
            panel_y = height // 2 - text_h // 2 - 18
            panel_w = text_w + 56
            panel_h = text_h + 36
            _draw_rect(white_texture_id, panel_x, panel_y, panel_w, panel_h, (0, 12, 0), alpha=0.82)
            _draw_rect(white_texture_id, panel_x, panel_y, panel_w, 2, (0, 255, 136), alpha=1.0)
            _draw_rect(white_texture_id, panel_x, panel_y + panel_h - 2, panel_w, 2, (0, 255, 136), alpha=1.0)
            _draw_rect(white_texture_id, panel_x, panel_y, 2, panel_h, (0, 255, 136), alpha=1.0)
            _draw_rect(white_texture_id, panel_x + panel_w - 2, panel_y, 2, panel_h, (0, 255, 136), alpha=1.0)
            _draw_text(current_font, shown, (0, 255, 136), width // 2 - text_w // 2, height // 2 - text_h // 2)

    def draw_door_overlay(progress):
        progress = _clamp01(progress)
        frame_index = int(progress * (len(door_left_frames) - 1))
        left_image = door_left_frames[frame_index].resize((max(1, width // 2), height), Image.NEAREST)
        right_image = door_right_frames[frame_index].resize((max(1, width // 2), height), Image.NEAREST)
        left_texture_id, left_w, left_h = create_texture_from_pil(left_image)
        right_texture_id, right_w, right_h = create_texture_from_pil(right_image)
        try:
            seam_gap = int((1.0 - progress) * width * 0.36)
            seam_gap = max(int(width * 0.02), seam_gap)
            left_x = -(left_w - (width // 2 - seam_gap // 2))
            right_x = width // 2 + seam_gap // 2
            draw_overlay_texture(left_texture_id, left_x, 0, left_w, left_h)
            draw_overlay_texture(right_texture_id, right_x, 0, right_w, right_h)
        finally:
            delete_texture(left_texture_id)
            delete_texture(right_texture_id)

    def draw_elevator_glitch_overlay(now_value):
        if not (state["elevator_active"] or state["stats_window_active"]) or state["elevator_start_time"] <= 0.0:
            return
        elapsed = now_value - state["elevator_start_time"]
        shake_start = ELEV_DOOR_CLOSE_DUR
        if elapsed < shake_start:
            return
        shake_effective = max(1e-6, ELEV_TOTAL_DUR - shake_start)
        ratio = _clamp01((elapsed - shake_start) / shake_effective)
        if ratio >= 1.0 and state["stats_window_active"]:
            ratio = 1.0
        jitter_alpha = min(0.28, 0.08 + ratio * 0.18)
        jitter_shift = max(1, int(2 + ratio * 3))
        draw_overlay_texture(scene_texture[0], -jitter_shift, 0, width, height, alpha=jitter_alpha)
        draw_overlay_texture(scene_texture[0], jitter_shift, 0, width, height, alpha=jitter_alpha)
        fill_ratio = _clamp01(ratio ** 0.35)
        if ratio >= 1.0 and state["stats_window_active"]:
            fill_ratio = 1.0
        fill_count = int(len(pixel_grid_full) * fill_ratio)
        stride = 2 if fill_count > 900 else 1
        extra = int(160 * fill_ratio)
        for idx in range(0, fill_count, stride):
            px, py = pixel_grid_full[idx]
            shade = max(0, min(255, random.randint(0, 120) + extra))
            _draw_rect(white_texture_id, px, py, pixel_size, pixel_size, (shade, shade, shade), alpha=0.92)

    def draw_statistics_overlay(now_value):
        if not state["stats_window_active"]:
            return
        if state["stats_counting_active"]:
            count_elapsed = now_value - state["stats_count_start"]
            if count_elapsed >= stats_count_duration:
                state["stats_counting_active"] = False
                state["stats_completed"] = True
                if flash_enabled:
                    state["stats_flash_active"] = True
                    state["stats_flash_start"] = now_value
                else:
                    state["stats_icon_active"] = True
                    state["stats_icon_pulse_time"] = 0.0
        if state["stats_flash_active"] and now_value - state["stats_flash_start"] >= stats_flash_duration:
            state["stats_flash_active"] = False
            state["stats_icon_active"] = True
            state["stats_icon_pulse_time"] = 0.0
        if state["stats_animation_start"] == 0.0:
            state["stats_animation_start"] = now_value
        anim_elapsed = now_value - state["stats_animation_start"]
        slide_progress = _clamp01(anim_elapsed / 1.2)
        slide_eased = _ease_out_cubic(slide_progress)
        if slide_progress > 0.3:
            shake_progress = (slide_progress - 0.3) / 0.7
            shake_intensity = math.sin(shake_progress * math.pi * 4.0) * 5.0 * (1.0 - shake_progress * 0.5)
            state["stats_shake_offset"] = random.uniform(-shake_intensity, shake_intensity)
        state["stats_float_time"] += delta
        state["stats_float_offset_x"] = math.sin(state["stats_float_time"] * 2.0) * 3.0
        state["stats_float_offset_y"] = math.sin(state["stats_float_time"] * 2.6 + math.pi / 4.0) * 2.0
        window_w = 500
        window_h = 400
        target_y = height // 2 - window_h // 2
        start_y = -window_h
        state["stats_window_y"] = start_y + (target_y - start_y) * slide_eased + state["stats_shake_offset"] + state["stats_float_offset_y"]
        window_x = width // 2 - window_w // 2 + state["stats_float_offset_x"]
        window_y = state["stats_window_y"]
        if state["elevator_start_time"] > 0.0:
            elevator_elapsed = now_value - state["elevator_start_time"]
            pixel_fill_ratio = 0.0
            if elevator_elapsed >= (ELEV_DOOR_CLOSE_DUR + ELEV_DOOR_HOLD_DUR):
                shake_start = ELEV_DOOR_CLOSE_DUR
                effective = max(1e-6, ELEV_TOTAL_DUR - shake_start)
                pixel_fill_ratio = _clamp01(((elevator_elapsed - shake_start) / effective) ** 0.35)
                if state["stats_window_active"]:
                    pixel_fill_ratio = 1.0
        else:
            pixel_fill_ratio = 1.0
        if pixel_fill_ratio <= 0.01 or slide_progress <= 0.01:
            return
        if flash_enabled and state["stats_flash_active"]:
            flash_alpha = 1.0 - ((now_value - state["stats_flash_start"]) / stats_flash_duration)
            _draw_rect(white_texture_id, 0, 0, width, height, (255, 255, 255), alpha=max(0.0, min(1.0, flash_alpha)))
        _draw_rect(white_texture_id, 0, 0, width, height, (0, 0, 0), alpha=min(0.72, 0.18 + slide_progress * 0.5))
        _draw_rect(white_texture_id, window_x, window_y, window_w, window_h, (0, 255, 0), alpha=1.0)
        _draw_rect(white_texture_id, window_x + 3, window_y + 3, window_w - 6, window_h - 6, (0, 0, 0), alpha=1.0)
        title = "LEVEL COMPLETE"
        title_bbox = font_stats.getbbox(title)
        title_w = max(1, title_bbox[2] - title_bbox[0] + 2)
        _draw_text(font_stats, title, (0, 255, 0), int(window_x + window_w // 2 - title_w // 2), int(window_y + 30))
        stats_y = int(window_y + 80)
        line_height = 35
        if state["stats_counting_active"]:
            count_elapsed = now_value - state["stats_count_start"]
            count_progress = _clamp01(count_elapsed / stats_count_duration)
            current_time = state["elevator_enter_time"] * count_progress
            enemies_defeated = int(state["enemies_killed"] * count_progress)
            items_collected = int(1 * count_progress)
            shots_fired = int(state["total_shots_fired"] * count_progress)
            shots_hit = int(state["total_shots_hit"] * count_progress)
            accuracy_full = int((state["total_shots_hit"] / max(1, state["total_shots_fired"])) * 100) if state["total_shots_fired"] > 0 else 0
            accuracy = int(accuracy_full * count_progress)
            state["stats_progress_bar_current"] = stats_progress_bar_target * count_progress
        else:
            current_time = state["elevator_enter_time"]
            enemies_defeated = state["enemies_killed"]
            items_collected = 1
            shots_fired = state["total_shots_fired"]
            shots_hit = state["total_shots_hit"]
            accuracy = int((state["total_shots_hit"] / max(1, state["total_shots_fired"])) * 100) if state["total_shots_fired"] > 0 else 0
            state["stats_progress_bar_current"] = stats_progress_bar_target
        entry_minutes = int(current_time // 60) % 60
        entry_seconds = int(current_time % 60)
        entry_milliseconds = int((current_time % 1) * 1000)
        lines = [
            f"Entry Time: {entry_minutes:02}:{entry_seconds:02}:{entry_milliseconds:03}",
            f"Enemies Defeated: {enemies_defeated}",
            f"Items Collected: {items_collected}",
            f"Shots Fired: {shots_fired}",
            f"Shots Hit: {shots_hit}",
            f"Accuracy: {accuracy}%",
            "Rank: TRAINEE",
        ]
        for idx, line in enumerate(lines):
            _draw_text(font_stats_small, line, (0, 255, 0), int(window_x + 40), stats_y + line_height * idx)
        progress_x = int(window_x + window_w - 60)
        progress_y = stats_y + 10
        progress_w = 20
        progress_h = 160
        _draw_rect(white_texture_id, progress_x, progress_y, progress_w, progress_h, (50, 50, 50), alpha=0.9)
        fill_height = int((state["stats_progress_bar_current"] / 100.0) * progress_h)
        if fill_height > 0:
            _draw_rect(white_texture_id, progress_x, progress_y + progress_h - fill_height, progress_w, fill_height, (0, 255, 0), alpha=0.95)
        _draw_text(font_stats_small, f"{int(state['stats_progress_bar_current'])}%", (0, 255, 0), progress_x - 10, progress_y - 25)
        if state["stats_completed"]:
            button_w = 120
            button_h = 40
            button_x = int(window_x + window_w // 2 - button_w // 2)
            button_y = int(window_y + window_h - 70)
            _draw_rect(white_texture_id, button_x, button_y, button_w, 2, (0, 255, 0), alpha=1.0)
            _draw_rect(white_texture_id, button_x, button_y + button_h - 2, button_w, 2, (0, 255, 0), alpha=1.0)
            _draw_rect(white_texture_id, button_x, button_y, 2, button_h, (0, 255, 0), alpha=1.0)
            _draw_rect(white_texture_id, button_x + button_w - 2, button_y, 2, button_h, (0, 255, 0), alpha=1.0)
            ok_bbox = font_stats.getbbox("OK")
            ok_w = max(1, ok_bbox[2] - ok_bbox[0] + 2)
            _draw_text(font_stats, "OK", (0, 255, 0), button_x + button_w // 2 - ok_w // 2, button_y + 6)
            hint = "Press ENTER or SPACE to continue"
        else:
            hint = "Click to skip animation"
        hint_bbox = font_stats_small.getbbox(hint)
        hint_w = max(1, hint_bbox[2] - hint_bbox[0] + 2)
        _draw_text(font_stats_small, hint, (0, 255, 0), int(window_x + window_w // 2 - hint_w // 2), int(window_y + window_h - 25))
        if state["stats_icon_active"]:
            state["stats_icon_pulse_time"] += delta
            pulse_ratio = (math.sin(state["stats_icon_pulse_time"] * 3.0) + 1.0) / 2.0
            icon_size = int(stats_icon_base_size + (stats_icon_max_size - stats_icon_base_size) * pulse_ratio)
            icon_image = stats_icon_raw.rotate(45, expand=True).resize((icon_size, icon_size), Image.NEAREST)
            icon_texture_id, icon_w, icon_h = create_texture_from_pil(icon_image)
            try:
                draw_overlay_texture(icon_texture_id, int(window_x + window_w - icon_w * 0.5), int(window_y - icon_h * 0.35), icon_w, icon_h)
            finally:
                delete_texture(icon_texture_id)

    def draw_dev_debug_overlay():
        if not state["dev_debug_window_active"]:
            return
        projection, viewport = begin_overlay(width, height)
        try:
            panel_w = 560
            panel_h = 250
            panel_x = width // 2 - panel_w // 2
            panel_y = height // 2 - panel_h // 2
            _draw_rect(white_texture_id, 0, 0, width, height, (0, 0, 0), alpha=0.72)
            _draw_rect(white_texture_id, panel_x, panel_y, panel_w, panel_h, (0, 18, 18), alpha=0.96)
            _draw_rect(white_texture_id, panel_x, panel_y, panel_w, 2, (120, 255, 235), alpha=1.0)
            _draw_rect(white_texture_id, panel_x, panel_y + panel_h - 2, panel_w, 2, (120, 255, 235), alpha=1.0)
            _draw_rect(white_texture_id, panel_x, panel_y, 2, panel_h, (120, 255, 235), alpha=1.0)
            _draw_rect(white_texture_id, panel_x + panel_w - 2, panel_y, 2, panel_h, (120, 255, 235), alpha=1.0)

            _draw_text(font_hud_big, "DEVELOPER DEBUG", (120, 255, 235), panel_x + 20, panel_y + 18)
            _draw_text(font_hud, "Deja Vu break level", (210, 240, 238), panel_x + 22, panel_y + 66)

            current_level = int(max(0, min(deja_vu_logic.DEJA_VU_BREAK_MAX_LEVEL, state["deja_vu_break_level"])))
            bar_x = panel_x + 24
            bar_y = panel_y + 108
            slot_w = 56
            slot_h = 42
            slot_gap = 8
            for level in range(deja_vu_logic.DEJA_VU_BREAK_MAX_LEVEL + 1):
                x = bar_x + level * (slot_w + slot_gap)
                active = level == current_level
                filled = level <= current_level
                fill_color = (255, 104, 76) if filled else (28, 40, 40)
                border_color = (255, 190, 180) if active else (120, 255, 235)
                _draw_rect(white_texture_id, x, bar_y, slot_w, slot_h, fill_color, alpha=0.82 if filled else 0.48)
                _draw_rect(white_texture_id, x, bar_y, slot_w, 2, border_color, alpha=1.0)
                _draw_rect(white_texture_id, x, bar_y + slot_h - 2, slot_w, 2, border_color, alpha=1.0)
                _draw_rect(white_texture_id, x, bar_y, 2, slot_h, border_color, alpha=1.0)
                _draw_rect(white_texture_id, x + slot_w - 2, bar_y, 2, slot_h, border_color, alpha=1.0)
                text_x = x + 20 if level < 10 else x + 14
                _draw_text(font_hud, str(level), (255, 255, 255), text_x, bar_y + 10)

            _draw_text(font_hud_big, f"CURRENT: {current_level}/8", (255, 220, 210), panel_x + 22, panel_y + 166)
            _draw_text(font_slot, "0-8 set level  |  Left/Right adjust  |  ` or ESC close", (170, 220, 216), panel_x + 22, panel_y + 212)
        finally:
            end_overlay(projection, viewport)

    def draw_rob_dialog_overlay():
        if not rob_dialog_active():
            return
        current_dialog = state["rob_state"].get("current_dialog") or rob_logic.INTRO_DIALOG
        choices = list(current_dialog.get("choices", ()))
        if len(choices) < 2:
            return
        projection, viewport = begin_overlay(width, height)
        try:
            panel_w = 720
            panel_h = 270
            panel_x = width // 2 - panel_w // 2
            panel_y = height - panel_h - 56
            _draw_rect(white_texture_id, 0, 0, width, height, (0, 0, 0), alpha=0.38)
            _draw_rect(white_texture_id, panel_x, panel_y, panel_w, panel_h, (6, 16, 10), alpha=0.96)
            _draw_rect(white_texture_id, panel_x, panel_y, panel_w, 2, (120, 255, 150), alpha=1.0)
            _draw_rect(white_texture_id, panel_x, panel_y + panel_h - 2, panel_w, 2, (120, 255, 150), alpha=1.0)
            _draw_rect(white_texture_id, panel_x, panel_y, 2, panel_h, (120, 255, 150), alpha=1.0)
            _draw_rect(white_texture_id, panel_x + panel_w - 2, panel_y, 2, panel_h, (120, 255, 150), alpha=1.0)
            _draw_text(font_hud_big, "ROB", (120, 255, 150), panel_x + 26, panel_y + 18)
            _draw_text(font_hud, current_dialog["prompt"], (230, 245, 232), panel_x + 28, panel_y + 64)
            bad_rect = pygame.Rect(panel_x + 28, panel_y + 128, panel_w - 56, 44)
            good_rect = pygame.Rect(panel_x + 28, panel_y + 186, panel_w - 56, 44)
            mouse_pos = pygame.mouse.get_pos()
            for rect, label, hovered in (
                (bad_rect, f"1. {choices[0]['text']}", bad_rect.collidepoint(mouse_pos)),
                (good_rect, f"2. {choices[1]['text']}", good_rect.collidepoint(mouse_pos)),
            ):
                fill = (28, 56, 34) if hovered else (10, 22, 14)
                edge = (190, 120, 120) if rect == bad_rect else (120, 255, 180)
                _draw_rect(white_texture_id, rect.x, rect.y, rect.width, rect.height, fill, alpha=0.98)
                _draw_rect(white_texture_id, rect.x, rect.y, rect.width, 2, edge, alpha=1.0)
                _draw_rect(white_texture_id, rect.x, rect.y + rect.height - 2, rect.width, 2, edge, alpha=1.0)
                _draw_rect(white_texture_id, rect.x, rect.y, 2, rect.height, edge, alpha=1.0)
                _draw_rect(white_texture_id, rect.x + rect.width - 2, rect.y, 2, rect.height, edge, alpha=1.0)
                _draw_text(font_hud, label, (240, 245, 240), rect.x + 12, rect.y + 12)
        finally:
            end_overlay(projection, viewport)

    def choose_rob_dialog_option(option_index):
        choices = list((state["rob_state"].get("current_dialog") or rob_logic.INTRO_DIALOG).get("choices", ()))
        if option_index < 0 or option_index >= len(choices):
            return
        result = rob_logic.resolve_dialog_choice(state["rob_state"], player_x, player_y, time.time(), choices[option_index]["id"])
        heal_amount = int(result.get("heal_player", 0))
        if heal_amount > 0 and state["player_health"] < PLAYER_MAX_HEALTH:
            state["player_health"] = min(PLAYER_MAX_HEALTH, state["player_health"] + heal_amount)

    def trigger_mannequin_attack(now_value):
        if state["mannequin_restart_at"] is not None:
            return
        play_sound_effect(mannequin_attack_sound_path)
        state["mannequin_restart_at"] = now_value + max(0.2, mannequin_attack_duration)

    for sentry in state["sentries"]:
        hexagaze_logic.build_visible_cells(sentry, MAP, has_line_of_sight)

    running = True
    while running:
        delta = clock.tick(TARGET_FPS) / 1000.0
        update_music(delta)
        delta = max(1.0 / 240.0, min(delta, 0.05))
        now = time.time()
        if deja_vu_logic.should_complete_death_break(state, now_value=now):
            finish_deja_vu(now)
            deja_vu_logic.complete_death_break(state, now_value=now)
        if state["flashback_pending"] and not deja_vu_logic.critical_freeze_active(state, now_value=now):
            deja_vu_logic.start_flashback(state, now_value=now)
            state["flashback_last_kill_count"] = state["enemies_killed"]
        if deja_vu_logic.flashback_should_end(state, now_value=now):
            deja_vu_logic.finish_flashback(state, now_value=now)
            state["flashback_last_kill_count"] = state["enemies_killed"]
        if state["flashback_post_active"] and state["enemies_killed"] > state["flashback_last_kill_count"]:
            kill_delta = state["enemies_killed"] - state["flashback_last_kill_count"]
            deja_vu_logic.add_flashback_post_time(state, extra_seconds=kill_delta * deja_vu_logic.FLASHBACK_KILL_BONUS)
            state["flashback_last_kill_count"] = state["enemies_killed"]
        elif not state["flashback_post_active"]:
            state["flashback_last_kill_count"] = state["enemies_killed"]
        if deja_vu_logic.update_flashback_post(state, delta_time=delta):
            deja_vu_logic.start_flashback_death(state, now_value=now)
        if deja_vu_logic.flashback_death_finished(state, now_value=now):
            next_action = "restart"
            running = False
            continue
        for _ in range(deja_vu_logic.consume_critical_break_effects(state, now_value=now)):
            spawn_player_break_effect()
        deja_vu_blackout_active = deja_vu_logic.blackout_active(state, now_value=now)
        deja_vu_freeze_active = deja_vu_logic.critical_freeze_active(state, now_value=now)
        gameplay_hard_pause = (
            deja_vu_blackout_active
            or deja_vu_freeze_active
            or state["dev_debug_window_active"]
            or state["flashback_death_active"]
        )
        rob_dialog_pause = rob_interaction_locked(now)
        if rob_dialog_pause:
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)
        elif not state["stats_window_active"]:
            pygame.event.set_grab(True)
            pygame.mouse.set_visible(False)

        if not state["deja_vu_active"] and not state["deja_vu_death_return_pending"] and (
            (state["mannequin_restart_at"] is not None and now >= state["mannequin_restart_at"])
            or (state["player_restart_at"] is not None and now >= state["player_restart_at"])
        ):
            next_action = "restart"
            running = False
            continue

        fps_timer += delta
        caption_timer += delta
        if fps_timer >= 0.2:
            fps_display = int(clock.get_fps())
            fps_timer = 0.0

        if not gameplay_hard_pause:
            update_hand_swap(delta)

            if gunshoot_animating:
                shoot_acc += delta
                while shoot_acc >= 0.05 and gunshoot_animating:
                    shoot_acc -= 0.05
                    gunshoot_frame_index += 1
                    if gunshoot_frame_index >= len(gunshoot_frames_raw):
                        gunshoot_animating = False
                        gunshoot_frame_index = 0

            if reload_anim_active and state["reloading"]:
                reload_acc += delta
                while reload_acc >= 0.06 and state["reloading"]:
                    reload_acc -= 0.06
                    reload_anim_index += 1
                    if reload_anim_index >= len(gunreload_frames_raw):
                        state["reloading"] = False
                        reload_anim_active = False
                        reload_anim_index = 0
                        state["ammo"] = state["max_ammo"]

            if punch_animating:
                punch_acc += delta
                punch_frames = right_punch_frames_raw if punch_side == "right" else left_punch_frames_raw
                while punch_acc >= 0.05 and punch_animating:
                    punch_acc -= 0.05
                    punch_frame_index += 1
                    if punch_frame_index >= len(punch_frames):
                        punch_animating = False
                        punch_frame_index = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if rob_dialog_pause:
                    if event.key == pygame.K_1:
                        choose_rob_dialog_option(0)
                    elif event.key == pygame.K_2:
                        choose_rob_dialog_option(1)
                    continue
                if event.key == pygame.K_BACKQUOTE or event.unicode in {"`", "~", "ё", "Ё"}:
                    was_active = state["dev_debug_window_active"]
                    state["dev_debug_window_active"] = not state["dev_debug_window_active"]
                    if was_active and not state["dev_debug_window_active"] and state["deja_vu_break_level"] >= deja_vu_logic.DEJA_VU_BREAK_MAX_LEVEL:
                        start_break_sequence_from_debug(now)
                    continue
                if event.key == pygame.K_ESCAPE:
                    if state["dev_debug_window_active"]:
                        state["dev_debug_window_active"] = False
                        if state["deja_vu_break_level"] >= deja_vu_logic.DEJA_VU_BREAK_MAX_LEVEL:
                            start_break_sequence_from_debug(now)
                        continue
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                    pause_action = runtime_run_pause_menu_opengl(clock, width, height, title="Paused")
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    pygame.mouse.get_rel()
                    if pause_action == "restart":
                        next_action = "restart"
                        running = False
                    elif pause_action == "quit":
                        next_action = "quit"
                        running = False
                    continue
                elif state["dev_debug_window_active"]:
                    if event.key == pygame.K_LEFT:
                        state["deja_vu_break_level"] = max(0, state["deja_vu_break_level"] - 1)
                    elif event.key == pygame.K_RIGHT:
                        state["deja_vu_break_level"] = min(deja_vu_logic.DEJA_VU_BREAK_MAX_LEVEL, state["deja_vu_break_level"] + 1)
                    elif event.unicode and event.unicode in "012345678":
                        state["deja_vu_break_level"] = int(event.unicode)
                    continue
                elif gameplay_hard_pause:
                    continue
                elif state["stats_window_active"]:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if state["stats_completed"]:
                            state["stats_window_active"] = False
                            state["elevator_active"] = False
                            state["elevator_transition_to_testing"] = True
                            running = False
                        elif state["stats_can_skip"]:
                            state["stats_completed"] = True
                            state["stats_counting_active"] = False
                            state["stats_progress_bar_current"] = stats_progress_bar_target
                            if flash_enabled:
                                state["stats_flash_active"] = True
                                state["stats_flash_start"] = time.time()
                            else:
                                state["stats_icon_active"] = True
                                state["stats_icon_pulse_time"] = 0.0
                    continue
                elif event.key == pygame.K_SPACE:
                    if (
                        not restart_pending()
                        and not state["elevator_active"]
                        and not state["start_cutscene_active"]
                        and not state["stats_window_active"]
                    ):
                        ground_z = get_walk_support_height(player_x, player_y, z_hint=player_z)
                        if player_z <= ground_z + 0.02:
                            jump_speed = JUMP_SPEED + (CROUCH_JUMP_BONUS if crouch_amount > CROUCH_MAX * 0.35 else 0.0)
                            vertical_velocity = jump_speed
                elif restart_pending():
                    continue
                elif state["elevator_active"] or state["start_cutscene_active"] or state["stats_window_active"]:
                    continue
                elif event.unicode and event.unicode in "12345":
                    state["selected_slot"] = int(event.unicode)
                elif event.key == pygame.K_v:
                    activate_deja_vu()
                elif event.key == pygame.K_r:
                    start_reload()
                elif event.key == pygame.K_f:
                    show_fps_overlay = not show_fps_overlay
                    save_settings({"show_fps": show_fps_overlay})
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if rob_dialog_pause:
                    if event.button == 1:
                        panel_w = 720
                        panel_h = 270
                        panel_x = width // 2 - panel_w // 2
                        panel_y = height - panel_h - 56
                        bad_rect = pygame.Rect(panel_x + 28, panel_y + 128, panel_w - 56, 44)
                        good_rect = pygame.Rect(panel_x + 28, panel_y + 186, panel_w - 56, 44)
                        if bad_rect.collidepoint(event.pos):
                            choose_rob_dialog_option(0)
                        elif good_rect.collidepoint(event.pos):
                            choose_rob_dialog_option(1)
                    continue
                if gameplay_hard_pause:
                    continue
                if state["stats_window_active"]:
                    if state["stats_can_skip"] and not state["stats_completed"]:
                        state["stats_completed"] = True
                        state["stats_counting_active"] = False
                        state["stats_progress_bar_current"] = stats_progress_bar_target
                        if flash_enabled:
                            state["stats_flash_active"] = True
                            state["stats_flash_start"] = time.time()
                        else:
                            state["stats_icon_active"] = True
                            state["stats_icon_pulse_time"] = 0.0
                    continue
                if state["elevator_active"] or state["start_cutscene_active"] or restart_pending():
                    continue
                if event.button in (1, 3):
                    use_selected_item(event.button)
            elif event.type == pygame.MOUSEWHEEL:
                if rob_dialog_pause or gameplay_hard_pause:
                    continue
                if state["elevator_active"] or state["start_cutscene_active"] or state["stats_window_active"] or restart_pending():
                    continue
                if event.y > 0:
                    state["selected_slot"] -= 1
                else:
                    state["selected_slot"] += 1
                if state["selected_slot"] < 1:
                    state["selected_slot"] = 5
                if state["selected_slot"] > 5:
                    state["selected_slot"] = 1

        move_x = 0.0
        move_y = 0.0
        moving = False
        if rob_dialog_pause:
            rob_target_angle = math.atan2(state["rob_state"]["y"] - player_y, state["rob_state"]["x"] - player_x)
            player_angle = wrap_angle(player_angle + wrap_angle(rob_target_angle - player_angle) * min(1.0, delta * 8.5))
        elif state["start_cutscene_active"]:
            if not state["start_cutscene_started"]:
                state["start_cutscene_started"] = True
                state["start_cutscene_start_time"] = time.time()
            elapsed = max(0.0, time.time() - state["start_cutscene_start_time"])
            state["start_cutscene_open_t"] = 0.0
            state["start_cutscene_close_t"] = 0.0
            if elapsed < START_DOOR_WAIT_DUR:
                state["start_cutscene_open_t"] = 0.0
            elif elapsed < START_DOOR_WAIT_DUR + START_DOOR_OPEN_DUR + START_MOVE_DUR:
                open_elapsed = elapsed - START_DOOR_WAIT_DUR
                state["start_cutscene_open_t"] = _clamp01(open_elapsed / START_DOOR_OPEN_DUR)
                if open_elapsed >= START_DOOR_OPEN_DUR:
                    move_ratio = _ease_out_cubic((open_elapsed - START_DOOR_OPEN_DUR) / START_MOVE_DUR)
                    player_x = player_spawn_x - player_start_cutscene_offset + player_start_cutscene_offset * move_ratio
                    player_y = player_spawn_y
            elif elapsed < START_DOOR_WAIT_DUR + START_DOOR_OPEN_DUR + START_MOVE_DUR + START_DOOR_CLOSE_DUR:
                player_x = player_spawn_x + 0.02
                player_y = player_spawn_y
                state["start_cutscene_open_t"] = 1.0
                state["start_cutscene_close_t"] = _clamp01((elapsed - START_DOOR_WAIT_DUR - START_DOOR_OPEN_DUR - START_MOVE_DUR) / START_DOOR_CLOSE_DUR)
            else:
                player_x = player_spawn_x
                player_y = player_spawn_y
                state["start_cutscene_active"] = False
                state["start_cutscene_open_t"] = 0.0
                state["start_cutscene_close_t"] = 1.0
        elif state["elevator_active"]:
            elapsed = time.time() - state["elevator_start_time"]
            if elapsed < ELEV_ROT_DUR:
                ratio = elapsed / ELEV_ROT_DUR
                player_angle = state["elevator_from_angle"] + math.pi * _ease_out_cubic(ratio)
            else:
                player_angle = state["elevator_target_angle"]
            state["elevator_close_t"] = _clamp01(elapsed / ELEV_DOOR_CLOSE_DUR)
            if elapsed >= ELEV_TOTAL_DUR and not state["stats_window_active"]:
                state["stats_window_active"] = True
                state["stats_animation_start"] = time.time()
                state["stats_counting_active"] = True
                state["stats_count_start"] = time.time()
                state["stats_can_skip"] = True
        elif gameplay_hard_pause:
            move_x = 0.0
            move_y = 0.0
            moving = False
            vertical_velocity = 0.0
            if state["flashback_death_active"]:
                death_progress = deja_vu_logic.flashback_death_progress(state, now_value=now)
                target_pitch = -min(math.radians(28.0), PITCH_LIMIT_UP * 2.8)
                pitch_speed = 10.5 - death_progress * 3.0
                player_pitch = max(target_pitch, player_pitch + (target_pitch - player_pitch) * min(1.0, delta * pitch_speed))
        else:
            keys = pygame.key.get_pressed()
            crouching = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]
            forward_x = math.cos(player_angle)
            forward_y = math.sin(player_angle)
            right_x = math.cos(player_angle + math.pi / 2)
            right_y = math.sin(player_angle + math.pi / 2)
            if keys[pygame.K_w]:
                move_x += forward_x
                move_y += forward_y
            if keys[pygame.K_s]:
                move_x -= forward_x
                move_y -= forward_y
            if keys[pygame.K_a]:
                move_x -= right_x
                move_y -= right_y
            if keys[pygame.K_d]:
                move_x += right_x
                move_y += right_y
            move_len = math.hypot(move_x, move_y)
            if move_len > 0.0:
                moving = True
                speed_mul = DEJA_VU_SPEED_BOOST if state["deja_vu_active"] else 1.0
                if state["flashback_active"]:
                    speed_mul *= deja_vu_logic.FLASHBACK_SPEED_BOOST
                current_speed = SPEED * 14.0 * speed_mul * delta
                move_x = move_x / move_len * current_speed
                move_y = move_y / move_len * current_speed
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            if mouse_dx:
                player_angle = wrap_angle(player_angle + mouse_dx * MOUSE_SENSITIVITY)
            if mouse_dy:
                player_pitch = max(-PITCH_LIMIT_UP, min(PITCH_LIMIT_DOWN, player_pitch + mouse_dy * PITCH_SENSITIVITY))
            tx = int(player_x)
            ty = int(player_y)
            if (not state["deja_vu_active"]) and (tx, ty) in lift_tiles:
                player_x -= math.cos(player_angle) * 0.32
                player_y -= math.sin(player_angle) * 0.32
                state["elevator_active"] = True
                state["elevator_start_time"] = time.time()
                state["elevator_enter_time"] = time.time() - hud_start_time
                state["elevator_from_angle"] = player_angle
                state["elevator_target_angle"] = player_angle + math.pi
                state["elevator_close_t"] = 0.0
                play_overlay_music(resource_path("data/music/LocalCodepastElevator.wav"), fade_ms=1200)

            ceiling_z_here = get_ceiling_height(player_x, player_y, z_hint=player_z)
            required_crouch = max(0.0, min(CROUCH_MAX, (player_z + PLAYER_EYE_HEIGHT + 0.02) - ceiling_z_here))
            target_crouch = max(CROUCH_MAX if crouching else 0.0, required_crouch)
            if crouch_amount < target_crouch:
                crouch_amount = min(target_crouch, crouch_amount + delta * CROUCH_SPEED * CROUCH_MAX)
            else:
                crouch_amount = max(target_crouch, crouch_amount - delta * CROUCH_SPEED * CROUCH_MAX)

        if rob_dialog_pause:
            rob_floor = get_floor_height(state["rob_state"]["x"], state["rob_state"]["y"])
            rob_dx = state["rob_state"]["x"] - player_x
            rob_dy = state["rob_state"]["y"] - player_y
            rob_dist = math.hypot(rob_dx, rob_dy)
            target_pitch = math.atan2((rob_floor + 0.72) - (player_z + PLAYER_EYE_HEIGHT + bob_vertical - crouch_amount), max(0.001, rob_dist))
            target_pitch = max(-PITCH_LIMIT_UP, min(PITCH_LIMIT_DOWN, target_pitch))
            player_pitch = player_pitch + (target_pitch - player_pitch) * min(1.0, delta * 7.5)
        if not gameplay_hard_pause and not rob_dialog_pause:
            for lk in state["light_states"]:
                if time.time() - state["light_timers"][lk] > 0.15:
                    state["light_timers"][lk] = time.time()
                    if random.random() < 0.2:
                        state["light_states"][lk] = not state["light_states"][lk]

        if not gameplay_hard_pause and not rob_dialog_pause and not state["elevator_active"] and not state["start_cutscene_active"] and not state["stats_window_active"]:
            nx = player_x + move_x
            ny = player_y + move_y

            def is_blocked_by_sentry(x_pos, y_pos):
                return hexagaze_logic.is_blocked_by_sentry(state["sentries"], x_pos, y_pos, HEXAGAZE_BLOCK_RADIUS)

            def can_walk_to(x_pos, y_pos):
                can_stand, target_ground = can_occupy_position(
                    x_pos,
                    y_pos,
                    player_z,
                    blocker_fn=is_blocked_by_sentry,
                    body_height=max(0.4, PLAYER_EYE_HEIGHT - crouch_amount),
                )
                climb_limit = JUMP_CLIMB_HEIGHT if vertical_velocity > 0.0 else STEP_HEIGHT
                if target_ground - player_z > climb_limit:
                    return False
                return can_stand

            if can_walk_to(nx, player_y):
                player_x = nx
            if can_walk_to(player_x, ny):
                player_y = ny
            ground_z = get_walk_support_height(player_x, player_y, z_hint=player_z)
            if player_z < ground_z or (vertical_velocity <= 0.0 and abs(player_z - ground_z) <= GROUND_SNAP_DISTANCE):
                player_z = ground_z
                vertical_velocity = 0.0

        if not gameplay_hard_pause and not rob_dialog_pause and not state["elevator_active"] and not state["start_cutscene_active"] and not state["stats_window_active"]:
            ground_z = get_walk_support_height(player_x, player_y, z_hint=player_z)
            ceiling_z = get_ceiling_height(player_x, player_y, z_hint=player_z)
            vertical_velocity -= GRAVITY * delta
            player_z += vertical_velocity * delta
            if player_z <= ground_z or (vertical_velocity <= 0.0 and abs(player_z - ground_z) <= GROUND_SNAP_DISTANCE):
                player_z = ground_z
                vertical_velocity = 0.0
            if player_z + PLAYER_EYE_HEIGHT - crouch_amount >= ceiling_z:
                player_z = max(ground_z, ceiling_z - PLAYER_EYE_HEIGHT + crouch_amount)
                vertical_velocity = min(0.0, vertical_velocity)
            required_crouch = max(0.0, min(CROUCH_MAX, (player_z + PLAYER_EYE_HEIGHT + 0.02) - ceiling_z))
            if crouch_amount < required_crouch:
                crouch_amount = required_crouch
        else:
            vertical_velocity = 0.0
            player_z = get_floor_height(player_x, player_y, z_hint=player_z)

        if moving and not gameplay_hard_pause and not rob_dialog_pause and not state["elevator_active"] and not state["start_cutscene_active"] and not state["stats_window_active"]:
            bob_phase += delta * 11.0
            bob_vertical = math.sin(bob_phase) * 0.055 * bob_strength
            bob_side = math.cos(bob_phase * 0.5) * 0.018 * bob_strength
        else:
            bob_phase += delta * 6.0
            bob_vertical *= max(0.0, 1.0 - delta * 10.0)
            bob_side *= max(0.0, 1.0 - delta * 10.0)

        if state["elevator_active"] or state["start_cutscene_active"] or state["stats_window_active"] or gameplay_hard_pause or rob_dialog_pause:
            crouch_amount = max(0.0, crouch_amount - delta * CROUCH_SPEED * CROUCH_MAX)

        pickup_radius = 0.55
        if not gameplay_hard_pause and not rob_dialog_pause and state["gun_pickups"]:
            kept = []
            for gx, gy in state["gun_pickups"]:
                if math.hypot(player_x - gx, player_y - gy) < pickup_radius:
                    state["has_gun"] = True
                else:
                    kept.append((gx, gy))
            state["gun_pickups"] = kept

        if not gameplay_hard_pause and not rob_dialog_pause and state["bomb_pickups"]:
            state["bomb_pickups"], picked_bomb = bomb_logic.pickup_bombs(state["bomb_pickups"], player_x, player_y, pickup_radius)
            if picked_bomb:
                state["slot2_item"] = "bomb"

        if not gameplay_hard_pause:
            mannequin_state["restart_at"] = state["mannequin_restart_at"]
            mannequin_logic.update_state(
                mannequin_state,
                MAP,
                delta,
                now,
                player_x,
                player_y,
                player_angle,
                lambda x1, y1, x2, y2: runtime_has_line_of_sight(x1, y1, x2, y2, is_wall),
                is_walkable_cell,
                state["elevator_active"] or state["start_cutscene_active"],
                trigger_mannequin_attack,
            )

            hexagaze_logic.update_sentries(
                state["sentries"],
                state["sentry_projectiles"],
                delta,
                now,
                player_x,
                player_y,
                is_wall,
                lambda x1, y1, x2, y2: runtime_has_line_of_sight(x1, y1, x2, y2, is_wall),
                state["elevator_active"] or state["start_cutscene_active"] or restart_pending(),
                damage_player,
                hexagaze_config,
            )

            mannequin_cell = (int(mannequin_state["x"]), int(mannequin_state["y"])) if mannequin_state["x"] is not None and mannequin_state["y"] is not None else None
            bomb_update = bomb_logic.update_bomb_system(
                state["placed_bombs"],
                state["active_explosions"],
                bomb_assets,
                delta,
                now,
                (int(player_x), int(player_y)),
                mannequin_cell,
                mannequin_state["alive"],
                damage_entities_in_bomb_area,
                bomb_world_frame_index,
                bomb_world_anim_acc,
                activator_click_animating,
                activator_click_frame_index,
                activator_click_acc,
            )
            bomb_world_frame_index = bomb_update["bomb_world_frame_index"]
            bomb_world_anim_acc = bomb_update["bomb_world_anim_acc"]
            activator_click_animating = bomb_update["activator_click_animating"]
            activator_click_frame_index = bomb_update["activator_click_frame_index"]
            activator_click_acc = bomb_update["activator_click_acc"]

        rob_logic.update_rob(
            state["rob_state"],
            delta,
            now,
            player_x,
            player_y,
            lambda tx, ty: not is_wall(tx, ty, get_floor_height(tx, ty, z_hint=player_z) + 0.1),
            lambda x1, y1, x2, y2: runtime_has_line_of_sight(x1, y1, x2, y2, is_wall),
        )

        update_deja_vu(delta)
        if not deja_vu_blackout_active:
            runtime_update_impact_particles(state, delta, get_floor_height)
            runtime_update_bullet_marks(state, delta)

        state["target_cell"] = get_targeted_floor_cell() if state["selected_slot"] == 2 and state["slot2_item"] == "bomb" else None

        glViewport(0, 0, render_width, render_height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(75.0, render_width / max(1, render_height), 0.05, 160.0)
        glMatrixMode(GL_MODELVIEW)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glRotatef(math.degrees(player_pitch), 1.0, 0.0, 0.0)
        glRotatef(math.degrees(player_angle) + 90.0, 0.0, 1.0, 0.0)
        camera_right_x = math.cos(player_angle + math.pi / 2)
        camera_right_y = math.sin(player_angle + math.pi / 2)
        cam_x = player_x + camera_right_x * bob_side
        cam_y = player_y + camera_right_y * bob_side
        cam_z = player_z + PLAYER_EYE_HEIGHT + bob_vertical - crouch_amount
        glTranslatef(-cam_x, -cam_z, -cam_y)
        if runtime_display_lists:
            glCallList(runtime_display_lists["floor"])
            glCallList(runtime_display_lists["world"])
        else:
            runtime_draw_runtime_floor_and_ceiling(CUSTOM_RUNTIME_GEOMETRY, MAP, get_floor_height, get_ceiling_height, player_x, player_y, player_angle, rear_world_culling_enabled)

            for wall in runtime_iter_runtime_walls(CUSTOM_RUNTIME_GEOMETRY, MAP, has_upper_wall):
                x = wall["x"]
                y = wall["y"]
                if not is_render_point_visible(x + 0.5, y + 0.5, near_dist=1.6, back_margin=-0.30):
                    continue
                wall_dist = math.hypot((x + 0.5) - player_x, (y + 0.5) - player_y)
                draw_box(
                    x,
                    wall["base_z"],
                    y,
                    1.0,
                    wall["height"],
                    default_cell_color(wall["cell"]),
                    texture_id=wall_texture_id,
                    shade=fog_shade(wall_dist, min_light=0.24),
                    scale_x=wall.get("scale_x", 1.0),
                    scale_y=wall.get("scale_y", 1.0),
                    scale_z=1.0,
                    offset_x=wall.get("offset_x", 0.0),
                    offset_y=wall.get("offset_y", 0.0),
                    offset_z=wall.get("offset_z", 0.0),
                    rotation_x=wall.get("rotation_x", 0.0),
                    rotation_y=wall.get("rotation_y", 0.0),
                    rotation_z=wall.get("rotation", 0.0),
                )

            for stair in runtime_iter_runtime_stairs(CUSTOM_RUNTIME_GEOMETRY):
                x = stair["x"]
                y = stair["y"]
                if not is_render_point_visible(x + 0.5, y + 0.5, near_dist=1.2, back_margin=-0.30):
                    continue
                stair_dist = math.hypot((x + 0.5) - player_x, (y + 0.5) - player_y)
                draw_ramp(
                    x,
                    stair["base_z"],
                    y,
                    1.0,
                    stair["height"],
                    stair["rotation"],
                    default_cell_color("I"),
                    texture_id=wall_texture_id,
                    shade=fog_shade(stair_dist, min_light=0.28),
                    scale_x=stair.get("scale_x", 1.0),
                    scale_y=stair.get("scale_y", 1.0),
                    scale_z=1.0,
                    offset_x=stair.get("offset_x", 0.0),
                    offset_y=stair.get("offset_y", 0.0),
                    offset_z=stair.get("offset_z", 0.0),
                    rotation_x=stair.get("rotation_x", 0.0),
                    rotation_y=stair.get("rotation_y", 0.0),
                )

            for link in runtime_iter_runtime_stair_links(CUSTOM_RUNTIME_GEOMETRY):
                center_x = (link["start_x"] + link["end_x"]) * 0.5
                center_y = (link["start_y"] + link["end_y"]) * 0.5
                if not is_render_point_visible(center_x, center_y, near_dist=1.0, back_margin=-0.30):
                    continue
                link_dist = math.hypot(center_x - player_x, center_y - player_y)
                draw_bridge_plane(
                    link["start_x"],
                    link["start_z"],
                    link["start_y"],
                    link["end_x"],
                    link["end_z"],
                    link["end_y"],
                    link.get("width", 0.34),
                    default_cell_color("I"),
                    texture_id=wall_texture_id,
                    shade=fog_shade(link_dist, min_light=0.28),
                )

        for human_x, human_y in state["human_markers"]:
            if not is_render_point_visible(human_x, human_y, near_dist=1.0, back_margin=-0.25):
                continue
            human_dist = math.hypot(human_x - player_x, human_y - player_y)
            draw_human_model(
                human_x,
                get_floor_height(human_x, human_y),
                human_y,
                scale=0.78,
                yaw_degrees=180.0,
                shade=fog_shade(human_dist, min_light=0.24),
            )

        if (
            state["rob_state"].get("active")
            and now >= state["rob_state"].get("invisible_until", 0.0)
            and is_render_point_visible(state["rob_state"]["x"], state["rob_state"]["y"], near_dist=1.0, back_margin=-0.25)
        ):
            rob_dist = math.hypot(state["rob_state"]["x"] - player_x, state["rob_state"]["y"] - player_y)
            rob_floor = get_floor_height(state["rob_state"]["x"], state["rob_state"]["y"])
            rob_yaw = math.degrees(state["rob_state"].get("facing_angle", 0.0)) - 90.0
            rob_shade = fog_shade(rob_dist, min_light=0.24)
            rob_alpha = 0.55 if state["rob_state"].get("phase_shift_active") else 1.0
            rob_tint = (0.84, 0.92, 0.72) if state["rob_state"].get("kindness_points", 0) >= state["rob_state"].get("anger_points", 0) else (0.92, 0.72, 0.72)
            reaction_anim_path = state["rob_state"].get("reaction_animation")
            reaction_anim_started_at = state["rob_state"].get("reaction_animation_started_at", 0.0)
            reaction_anim_active = False
            use_static_rob_lod = False
            if reaction_anim_path:
                try:
                    reaction_anim_duration = get_animated_human_duration(reaction_anim_path)
                except Exception:
                    reaction_anim_duration = 0.0
                if now - reaction_anim_started_at <= reaction_anim_duration:
                    reaction_anim_active = True
                else:
                    state["rob_state"]["reaction_animation"] = None
                    state["rob_state"]["reaction_animation_started_at"] = 0.0
            if state["rob_state"].get("dialog_active"):
                draw_rob_talk_model(
                    state["rob_state"]["x"],
                    rob_floor,
                    state["rob_state"]["y"],
                    elapsed_time=max(0.0, now - state["rob_state"].get("dialog_started_at", now)),
                    scale=0.82,
                    yaw_degrees=rob_yaw,
                    shade=rob_shade,
                    alpha=rob_alpha,
                    tint=rob_tint,
                )
            elif reaction_anim_active:
                if use_static_rob_lod:
                    draw_human_model(
                        state["rob_state"]["x"],
                        rob_floor,
                        state["rob_state"]["y"],
                        scale=0.82,
                        yaw_degrees=rob_yaw,
                        shade=rob_shade,
                        alpha=rob_alpha,
                        tint=rob_tint,
                    )
                else:
                    draw_animated_human_model(
                        state["rob_state"]["x"],
                        rob_floor,
                        state["rob_state"]["y"],
                        model_path=reaction_anim_path,
                        elapsed_time=max(0.0, now - reaction_anim_started_at),
                        loop=False,
                        scale=0.82,
                        yaw_degrees=rob_yaw,
                        shade=rob_shade,
                        alpha=rob_alpha,
                        tint=rob_tint,
                        pose_fps=10.0,
                    )
            else:
                rob_mode = state["rob_state"].get("mode")
                locomotion_anim_path = None
                locomotion_pose_fps = 8.0
                if rob_mode in {"wander", "chase", "flee"}:
                    locomotion_anim_path = rob_logic.ROB_WALK_ANIM
                    locomotion_pose_fps = 10.0
                elif rob_mode == "idle":
                    locomotion_anim_path = rob_logic.ROB_IDLE_ANIM
                    locomotion_pose_fps = 6.0

                if locomotion_anim_path and not use_static_rob_lod:
                    draw_animated_human_model(
                        state["rob_state"]["x"],
                        rob_floor,
                        state["rob_state"]["y"],
                        model_path=locomotion_anim_path,
                        elapsed_time=now,
                        loop=True,
                        scale=0.82,
                        yaw_degrees=rob_yaw,
                        shade=rob_shade,
                        alpha=rob_alpha,
                        tint=rob_tint,
                        pose_fps=locomotion_pose_fps,
                    )
                else:
                    draw_human_model(
                        state["rob_state"]["x"],
                        rob_floor,
                        state["rob_state"]["y"],
                        scale=0.82,
                        yaw_degrees=rob_yaw,
                        shade=rob_shade,
                        alpha=rob_alpha,
                        tint=rob_tint,
                    )

        draw_player_body(
            cam_x,
            cam_y,
            cam_z,
            player_angle,
            player_pitch,
            bob_side=bob_side,
        )

        runtime_render_bullet_marks(state, bullet_marks_enabled, player_x, player_y, is_render_point_visible)
        runtime_render_world_sprites(state, player_x, player_y, player_angle, textures, bomb_world_frame_index, is_render_point_visible, CUSTOM_RUNTIME_GEOMETRY, get_floor_height)
        runtime_render_impact_particles(state, impact_particles_enabled, player_x, player_y, is_render_point_visible)
        draw_deja_vu_world_overlay(now)

        copy_framebuffer_to_texture(scene_texture[0], render_width, render_height)
        glViewport(0, 0, width, height)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if screen_effects_enabled:
            jitter_x = int(round(math.sin(now * 5.1) * 2.0))
            jitter_y = int(round(math.cos(now * 4.3) * 2.0))
        else:
            jitter_x = 0
            jitter_y = 0
        projection, viewport = begin_overlay(width, height)
        try:
            draw_overlay_texture(scene_texture[0], jitter_x, jitter_y, width, height)
        finally:
            end_overlay(projection, viewport)
        projection, viewport = begin_overlay(width, height)
        try:
            if state["start_cutscene_active"]:
                if state["start_cutscene_open_t"] < 1.0:
                    door_progress = 1.0 - _ease_out_cubic(state["start_cutscene_open_t"])
                elif state["start_cutscene_close_t"] > 0.0:
                    door_progress = _ease_out_cubic(state["start_cutscene_close_t"])
                else:
                    door_progress = 0.0
                draw_door_overlay(door_progress)
            elif state["elevator_active"]:
                draw_door_overlay(_ease_out_cubic(state["elevator_close_t"]))
            draw_elevator_glitch_overlay(now)
            draw_intro_overlay()
            draw_statistics_overlay(now)
        finally:
            end_overlay(projection, viewport)
        draw_crt_overlay(now)
        draw_hud_overlay()
        draw_rob_dialog_overlay()
        draw_deja_vu_failure_overlay(now)
        draw_flashback_overlay(now)
        draw_dev_debug_overlay()

        if caption_timer >= 0.25:
            pygame.display.set_caption(
                f"TUTOR OPENGL | FPS {fps_display} | HP {state['player_health']} | "
                f"AMMO {state['ammo']}/{state['max_ammo']} | SLOT {state['selected_slot']} | "
                f"KILLS {state['enemies_killed']} | {'DEJA' if state['deja_vu_active'] else 'NORMAL'}"
            )
            caption_timer = 0.0
        pygame.display.flip()

    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)
    delete_runtime_display_lists(runtime_display_lists)
    cleanup_textures()
    delete_texture(hud_texture[0])
    delete_texture(wall_texture_id)
    release_opengl_display()
    pygame.quit()

    if next_action == "restart":
        return start_tutor_maze_opengl(None)
    if state["elevator_transition_to_testing"]:
        from abebe.maze.opengl_testing_maze import start_testing_maze_opengl

        return start_testing_maze_opengl(None)


start_game = start_tutor_maze_opengl

