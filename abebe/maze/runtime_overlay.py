import math

import pygame
from PIL import Image, ImageDraw, ImageFont

from abebe.maze import pause_menu as pause_menu_ui
from abebe.maze.opengl_maze_core import (
    begin_overlay,
    create_texture_from_pil,
    delete_texture,
    draw_overlay_texture,
    end_overlay,
)


def clamp01(value):
    return max(0.0, min(1.0, float(value)))


def ease_out_cubic(x):
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 3


def make_font(size, bold=False):
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


def draw_text(font, text, color, x, y):
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


def draw_rect(texture_id, x, y, width, height, color, alpha=1.0):
    tint = (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
    draw_overlay_texture(texture_id, x, y, width, height, tint=tint, alpha=alpha)


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
