import copy
import math
import random
import time

from abebe.core.background_music import play_overlay_music, play_sound_effect, stop_overlay_music, update_music
from abebe.entities import bomb as bomb_logic
from abebe.entities import hexagaze as hexagaze_logic
from abebe.entities import mannequin as mannequin_logic
from abebe.entities.bomb import load_gif_frames
from abebe.maze import pause_menu as pause_menu_ui
from abebe.maze.opengl_maze_core import (
    PLAYER_EYE_HEIGHT,
    TARGET_FPS,
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
    require_opengl_dependencies,
    wrap_angle,
)
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
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST,
        GL_MODELVIEW,
        GL_ONE_MINUS_SRC_ALPHA,
        GL_PROJECTION,
        GL_QUADS,
        GL_SRC_ALPHA,
        glBegin,
        glClear,
        glClearColor,
        glColor4f,
        glBlendFunc,
        glDisable,
        glEnd,
        glEnable,
        glLoadIdentity,
        glMatrixMode,
        glRotatef,
        glTranslatef,
        glVertex3f,
        glViewport,
    )
    from OpenGL.GLU import gluPerspective
except Exception:  # pragma: no cover
    pygame = None


CUSTOM_RUNTIME_GEOMETRY = None


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


def _draw_text(font, text, color, x, y):
    bbox = font.getbbox(text)
    text_w = max(1, bbox[2] - bbox[0] + 2)
    text_h = max(1, bbox[3] - bbox[1] + 2)
    image = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((1 - bbox[0], 1 - bbox[1]), text, font=font, fill=tuple(color))
    texture_id, _w, _h = create_texture_from_pil(image)
    draw_overlay_texture(texture_id, x, y, text_w, text_h)
    delete_texture(texture_id)
    return text_w, text_h


def _draw_rect(texture_id, x, y, width, height, color, alpha=1.0):
    tint = (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
    draw_overlay_texture(texture_id, x, y, width, height, tint=tint, alpha=alpha)


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
    player_spawn_x, player_spawn_y = get_player_spawn()
    player_start_cutscene_offset = 0.0 if custom_runtime_active else 2.0
    player_x = player_spawn_x - player_start_cutscene_offset
    player_y = player_spawn_y
    player_z = get_floor_height(player_x, player_y)
    player_angle = 0.0
    player_pitch = 0.0
    PITCH_LIMIT = math.radians(10.0)
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

    pygame.init()
    info = pygame.display.Info()
    width, height = info.current_w, info.current_h
    screen = pygame.display.set_mode((width, height), pygame.DOUBLEBUF | pygame.OPENGL | pygame.FULLSCREEN)
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

    font_title = _make_font(14, bold=True)
    font_hud = _make_font(16)
    font_hud_big = _make_font(18)
    font_clock = _make_font(13, bold=True)
    font_slot = _make_font(11)
    font_task = _make_font(18)
    hud_start_time = time.time()

    texture_cache = {}

    def get_cached_texture(pil_image):
        key = id(pil_image)
        cached = texture_cache.get(key)
        if cached is None:
            cached = create_texture_from_pil(pil_image)
            texture_cache[key] = cached
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
    task_stub_small = task_stub_src.resize((TASK_ICON_SIZE, TASK_ICON_SIZE), Image.NEAREST)
    gunitem_small = gunitem_raw.resize((40, 40), Image.NEAREST)
    bomb_icon_small = bomb_assets["bomb_icon_raw"].resize((40, 40), Image.NEAREST)
    activator_icon_small = activator_icon_raw.resize((40, 40), Image.NEAREST)

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
        "orbs": orbs,
        "sentries": sentries,
        "sentry_projectiles": sentry_projectiles,
        "mannequin_state": mannequin_state,
        "player_health": PLAYER_MAX_HEALTH,
        "player_restart_at": None,
        "mannequin_restart_at": None,
        "next_punch_time": 0.0,
        "target_cell": None,
        "deja_vu_active": False,
        "deja_vu_started_at": 0.0,
        "deja_vu_charge": DEJA_VU_MAX_CHARGE,
        "deja_vu_recharge_available_at": 0.0,
        "deja_vu_snapshot": None,
        "deja_vu_ghost_trail": [],
        "deja_vu_ghost_acc": 0.0,
        "deja_vu_return_started_at": None,
        "deja_vu_active_budget": 0.0,
        "lights": lights,
        "light_states": light_states,
        "light_timers": light_timers,
        "start_cutscene_active": not custom_runtime_active,
        "start_cutscene_started": False,
        "start_cutscene_start_time": 0.0,
        "elevator_active": False,
        "elevator_start_time": 0.0,
        "elevator_from_angle": 0.0,
        "elevator_target_angle": 0.0,
        "elevator_transition_to_testing": False,
        "enemies_killed": 0,
        "total_shots_fired": 0,
        "total_shots_hit": 0,
        "impact_particles": [],
        "bullet_marks": [],
    }

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
        if state["player_restart_at"] is None:
            state["player_restart_at"] = now_value + 0.35

    def damage_player(amount, now_value):
        if state["player_restart_at"] is not None:
            return
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
        shot_hit = get_shot_hit_info()
        if shot_hit is None:
            return

        if shot_hit["type"] == "mannequin":
            if mannequin_state["alive"] and mannequin_state["mode"] == "observe" and player_can_see_mannequin():
                damage_mannequin_from_player_attack(1, register_shot_hit=True)
                spawn_impact_particles(shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=10)
            return

        if shot_hit["type"] == "orb":
            orb = shot_hit["entity"]
            orb["health"] -= 10
            state["total_shots_hit"] += 1
            spawn_impact_particles(shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=9)
            if orb["health"] <= 0:
                state["enemies_killed"] += 1
            return

        if shot_hit["type"] == "sentry":
            sentry = shot_hit["entity"]
            sentry["health"] -= 1
            state["total_shots_hit"] += 1
            spawn_impact_particles(shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=10)
            if sentry["health"] <= 0:
                sentry["health"] = 0
                sentry["burst_shots_left"] = 0
                state["enemies_killed"] += 1
            return

        if shot_hit["type"] == "wall":
            hit_color = sample_image_color(wall_tex_raw, shot_hit["u"], shot_hit["v"])
            spawn_impact_particles(shot_hit["x"], shot_hit["y"], shot_hit["z"], hit_color, count=8, speed=0.8)
            spawn_bullet_mark("wall", shot_hit["x"], shot_hit["y"], shot_hit["z"])
            return

        if shot_hit["type"] == "floor":
            spawn_impact_particles(shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=7, speed=0.72)
            spawn_bullet_mark("floor", shot_hit["x"], shot_hit["y"], shot_hit["z"])
            return

        if shot_hit["type"] == "ceiling":
            spawn_impact_particles(shot_hit["x"], shot_hit["y"], shot_hit["z"], shot_hit["color"], count=7, speed=0.72)
            spawn_bullet_mark("ceiling", shot_hit["x"], shot_hit["y"], shot_hit["z"])

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
        return (
            not state["deja_vu_active"]
            and not state["start_cutscene_active"]
            and not state["elevator_active"]
            and not restart_pending()
            and state["deja_vu_charge"] >= DEJA_VU_MIN_ACTIVATION
        )

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
        state["total_shots_fired"] = snapshot["total_shots_fired"]
        state["total_shots_hit"] = snapshot["total_shots_hit"]
        state["enemies_killed"] = snapshot["enemies_killed"]

    def activate_deja_vu():
        if not deja_vu_available():
            return
        now_local = time.time()
        state["deja_vu_snapshot"] = capture_deja_vu_snapshot()
        state["deja_vu_active"] = True
        state["deja_vu_started_at"] = now_local
        state["deja_vu_active_budget"] = state["deja_vu_charge"]
        state["deja_vu_ghost_trail"] = [{"x": player_x, "y": player_y, "spawned_at": now_local}]
        state["deja_vu_ghost_acc"] = 0.0
        state["deja_vu_return_started_at"] = None

    def finish_deja_vu():
        if state["deja_vu_snapshot"] is None:
            state["deja_vu_active"] = False
            return
        elapsed = max(0.0, time.time() - state["deja_vu_started_at"])
        state["deja_vu_charge"] = max(0.0, min(DEJA_VU_MAX_CHARGE, state["deja_vu_active_budget"] - elapsed))
        state["deja_vu_recharge_available_at"] = time.time() + DEJA_VU_RECHARGE_DELAY
        restore_deja_vu_snapshot(state["deja_vu_snapshot"])
        state["deja_vu_active"] = False
        state["deja_vu_snapshot"] = None
        state["deja_vu_ghost_acc"] = 0.0
        state["deja_vu_active_budget"] = 0.0
        state["deja_vu_return_started_at"] = time.time()

    def update_deja_vu(delta_time):
        now_local = time.time()
        state["deja_vu_ghost_trail"] = [
            point for point in state["deja_vu_ghost_trail"]
            if now_local - point["spawned_at"] < DEJA_VU_GHOST_LIFETIME
        ]
        if not state["deja_vu_active"] and now_local >= state["deja_vu_recharge_available_at"] and state["deja_vu_charge"] < DEJA_VU_MAX_CHARGE:
            fast_rate = DEJA_VU_FAST_CHARGE_CAP / DEJA_VU_FAST_CHARGE_TIME
            slow_charge_amount = max(0.0, DEJA_VU_MAX_CHARGE - DEJA_VU_FAST_CHARGE_CAP)
            slow_rate = slow_charge_amount / DEJA_VU_SLOW_CHARGE_TIME if slow_charge_amount > 0 else fast_rate
            recharge_left = max(0.0, delta_time)
            if state["deja_vu_charge"] < DEJA_VU_FAST_CHARGE_CAP and recharge_left > 0.0:
                fast_missing = DEJA_VU_FAST_CHARGE_CAP - state["deja_vu_charge"]
                fast_gain = min(fast_missing, recharge_left * fast_rate)
                state["deja_vu_charge"] += fast_gain
                recharge_left -= fast_gain / fast_rate
            if state["deja_vu_charge"] >= DEJA_VU_FAST_CHARGE_CAP and recharge_left > 0.0:
                state["deja_vu_charge"] = min(DEJA_VU_MAX_CHARGE, state["deja_vu_charge"] + recharge_left * slow_rate)
        if state["deja_vu_return_started_at"] is not None:
            rewind_progress = (now_local - state["deja_vu_return_started_at"]) / DEJA_VU_RETURN_FADE
            if rewind_progress >= 1.0:
                state["deja_vu_return_started_at"] = None
        if not state["deja_vu_active"]:
            return
        state["deja_vu_ghost_acc"] += delta_time
        if state["deja_vu_ghost_acc"] >= DEJA_VU_GHOST_INTERVAL:
            state["deja_vu_ghost_acc"] = 0.0
            if not state["deja_vu_ghost_trail"] or math.hypot(player_x - state["deja_vu_ghost_trail"][-1]["x"], player_y - state["deja_vu_ghost_trail"][-1]["y"]) > 0.08:
                state["deja_vu_ghost_trail"].append({"x": player_x, "y": player_y, "spawned_at": now_local})
        if now_local - state["deja_vu_started_at"] >= state["deja_vu_active_budget"]:
            finish_deja_vu()

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
                _draw_text(font_task, "FIND A WEAPON", (0, 255, 0), task_margin + task_pad + TASK_ICON_SIZE + 10, task_margin + 44)

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

            deja_now = time.time()
            if state["deja_vu_active"]:
                deja_display_charge = max(0.0, state["deja_vu_active_budget"] - (deja_now - state["deja_vu_started_at"]))
            else:
                deja_display_charge = state["deja_vu_charge"]
            deja_ready = deja_display_charge >= DEJA_VU_MIN_ACTIVATION and deja_vu_available()
            if state["deja_vu_active"] or deja_ready:
                deja_color = (120, 255, 235)
                deja_state = f"{deja_display_charge:04.1f}s"
            else:
                deja_color = (110, 130, 130)
                if deja_now < state["deja_vu_recharge_available_at"]:
                    deja_state = f"WAIT {max(0.0, state['deja_vu_recharge_available_at'] - deja_now):03.1f}s"
                else:
                    deja_state = f"{deja_display_charge:04.1f}s"
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
                        prev_image = build_hand_image(previous_pil, hand_previous_item_id)
                        prev_texture_id, prev_w, prev_h = create_texture_from_pil(prev_image)
                        previous_y = gun_y + int(hand_slide_distance * hand_swap_eased)
                        draw_overlay_texture(prev_texture_id, width // 2 - prev_w // 2, previous_y - prev_h, prev_w, prev_h)
                        delete_texture(prev_texture_id)
                current_pil = get_hand_pil_for_item(hand_target_item_id)
                if current_pil is not None:
                    current_image = build_hand_image(current_pil, hand_target_item_id)
                    current_texture_id, current_w, current_h = create_texture_from_pil(current_image)
                    current_y = gun_y if not hand_swap_active else gun_y + int(hand_slide_distance * (1.0 - hand_swap_eased))
                    draw_overlay_texture(current_texture_id, width // 2 - current_w // 2, current_y - current_h, current_w, current_h)
                    delete_texture(current_texture_id)
        finally:
            end_overlay(projection, viewport)

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

        if not state["deja_vu_active"] and (
            (state["mannequin_restart_at"] is not None and now >= state["mannequin_restart_at"])
            or (state["player_restart_at"] is not None and now >= state["player_restart_at"])
        ):
            next_action = "restart"
            running = False
            continue

        fps_timer += delta
        if fps_timer >= 0.2:
            fps_display = int(clock.get_fps())
            fps_timer = 0.0

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
                if event.key == pygame.K_ESCAPE:
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                    pause_action = run_pause_menu_opengl(clock, width, height, title="Paused")
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
                elif event.key == pygame.K_SPACE:
                    if (
                        not restart_pending()
                        and not state["elevator_active"]
                        and not state["start_cutscene_active"]
                    ):
                        ground_z = get_walk_support_height(player_x, player_y, z_hint=player_z)
                        if player_z <= ground_z + 0.02:
                            jump_speed = JUMP_SPEED + (CROUCH_JUMP_BONUS if crouch_amount > CROUCH_MAX * 0.35 else 0.0)
                            vertical_velocity = jump_speed
                elif restart_pending():
                    continue
                elif state["elevator_active"] or state["start_cutscene_active"]:
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
                if state["elevator_active"] or state["start_cutscene_active"] or restart_pending():
                    continue
                if event.button in (1, 3):
                    use_selected_item(event.button)
            elif event.type == pygame.MOUSEWHEEL:
                if state["elevator_active"] or state["start_cutscene_active"] or restart_pending():
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
        if state["start_cutscene_active"]:
            if not state["start_cutscene_started"]:
                state["start_cutscene_started"] = True
                state["start_cutscene_start_time"] = time.time()
            elapsed = max(0.0, time.time() - state["start_cutscene_start_time"])
            if elapsed < 0.55 + 0.7:
                if elapsed >= 0.55:
                    move_ratio = _ease_out_cubic((elapsed - 0.55) / 0.7)
                    player_x = player_spawn_x - player_start_cutscene_offset + player_start_cutscene_offset * move_ratio
                    player_y = player_spawn_y
            elif elapsed < 0.55 + 0.7 + 0.45:
                player_x = player_spawn_x + 0.02
                player_y = player_spawn_y
            else:
                player_x = player_spawn_x
                player_y = player_spawn_y
                state["start_cutscene_active"] = False
        elif state["elevator_active"]:
            elapsed = time.time() - state["elevator_start_time"]
            if elapsed < 1.0:
                ratio = elapsed / 1.0
                player_angle = state["elevator_from_angle"] + math.pi * _ease_out_cubic(ratio)
            else:
                player_angle = state["elevator_target_angle"]
            if elapsed >= 6.0:
                state["elevator_transition_to_testing"] = True
                running = False
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
                current_speed = SPEED * 14.0 * speed_mul * delta
                move_x = move_x / move_len * current_speed
                move_y = move_y / move_len * current_speed
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            if mouse_dx:
                player_angle = wrap_angle(player_angle + mouse_dx * MOUSE_SENSITIVITY)
            if mouse_dy:
                player_pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, player_pitch + mouse_dy * PITCH_SENSITIVITY))
            tx = int(player_x)
            ty = int(player_y)
            if (not state["deja_vu_active"]) and (tx, ty) in lift_tiles:
                player_x -= math.cos(player_angle) * 0.32
                player_y -= math.sin(player_angle) * 0.32
                state["elevator_active"] = True
                state["elevator_start_time"] = time.time()
                state["elevator_from_angle"] = player_angle
                state["elevator_target_angle"] = player_angle + math.pi
                play_overlay_music(resource_path("data/music/LocalCodepastElevator.wav"), fade_ms=1200)

            ceiling_z_here = get_ceiling_height(player_x, player_y, z_hint=player_z)
            required_crouch = max(0.0, min(CROUCH_MAX, (player_z + PLAYER_EYE_HEIGHT + 0.02) - ceiling_z_here))
            target_crouch = max(CROUCH_MAX if crouching else 0.0, required_crouch)
            if crouch_amount < target_crouch:
                crouch_amount = min(target_crouch, crouch_amount + delta * CROUCH_SPEED * CROUCH_MAX)
            else:
                crouch_amount = max(target_crouch, crouch_amount - delta * CROUCH_SPEED * CROUCH_MAX)

        for lk in state["light_states"]:
            if time.time() - state["light_timers"][lk] > 0.15:
                state["light_timers"][lk] = time.time()
                if random.random() < 0.2:
                    state["light_states"][lk] = not state["light_states"][lk]

        if not state["elevator_active"] and not state["start_cutscene_active"]:
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

        if not state["elevator_active"] and not state["start_cutscene_active"]:
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

        if moving and not state["elevator_active"] and not state["start_cutscene_active"]:
            bob_phase += delta * 11.0
            bob_vertical = math.sin(bob_phase) * 0.055 * bob_strength
            bob_side = math.cos(bob_phase * 0.5) * 0.018 * bob_strength
        else:
            bob_phase += delta * 6.0
            bob_vertical *= max(0.0, 1.0 - delta * 10.0)
            bob_side *= max(0.0, 1.0 - delta * 10.0)

        if state["elevator_active"] or state["start_cutscene_active"]:
            crouch_amount = max(0.0, crouch_amount - delta * CROUCH_SPEED * CROUCH_MAX)

        pickup_radius = 0.55
        if state["gun_pickups"]:
            kept = []
            for gx, gy in state["gun_pickups"]:
                if math.hypot(player_x - gx, player_y - gy) < pickup_radius:
                    state["has_gun"] = True
                else:
                    kept.append((gx, gy))
            state["gun_pickups"] = kept

        if state["bomb_pickups"]:
            state["bomb_pickups"], picked_bomb = bomb_logic.pickup_bombs(state["bomb_pickups"], player_x, player_y, pickup_radius)
            if picked_bomb:
                state["slot2_item"] = "bomb"

        mannequin_state["restart_at"] = state["mannequin_restart_at"]
        mannequin_logic.update_state(
            mannequin_state,
            MAP,
            delta,
            now,
            player_x,
            player_y,
            player_angle,
            has_line_of_sight,
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
            has_line_of_sight,
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

        update_deja_vu(delta)
        update_impact_particles(delta)
        update_bullet_marks(delta)

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
        draw_runtime_floor_and_ceiling(player_x, player_y, player_angle, rear_world_culling_enabled)

        for wall in iter_runtime_walls():
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

        for stair in iter_runtime_stairs():
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

        for link in iter_runtime_stair_links():
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

        render_bullet_marks()
        render_world_sprites(state, player_x, player_y, player_angle, textures, bomb_world_frame_index, is_render_point_visible)
        render_impact_particles()
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
        draw_crt_overlay(now)
        draw_hud_overlay()

        pygame.display.set_caption(
            f"TUTOR OPENGL | FPS {fps_display} | HP {state['player_health']} | "
            f"AMMO {state['ammo']}/{state['max_ammo']} | SLOT {state['selected_slot']} | "
            f"KILLS {state['enemies_killed']} | {'DEJA' if state['deja_vu_active'] else 'NORMAL'}"
        )
        pygame.display.flip()

    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)
    cleanup_textures()
    delete_texture(hud_texture[0])
    delete_texture(wall_texture_id)
    pygame.quit()

    if next_action == "restart":
        return start_tutor_maze_opengl(None)
    if state["elevator_transition_to_testing"]:
        from abebe.maze.opengl_testing_maze import start_testing_maze_opengl

        return start_testing_maze_opengl(None)


start_game = start_tutor_maze_opengl

