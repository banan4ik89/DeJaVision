import pygame

from abebe.core.background_music import apply_music_settings, resume_music, stop_music
from abebe.core.user_settings import PIXEL_PRESETS, load_settings, save_settings


def _draw_button(screen, rect, text, font, hovered):
    border = (0, 255, 0) if hovered else (90, 180, 90)
    fill = (10, 18, 10) if hovered else (0, 0, 0)
    pygame.draw.rect(screen, fill, rect)
    pygame.draw.rect(screen, border, rect, width=2)
    surf = font.render(text, True, (220, 255, 220) if hovered else (0, 255, 0))
    screen.blit(surf, surf.get_rect(center=rect.center))


def _format_value(key, value):
    if key == "pixel_preset":
        return value.split(" - ", 1)[-1]
    if isinstance(value, bool):
        return "On" if value else "Off"
    if key == "fov_degrees":
        return f"{int(round(value))} deg"
    if key in {"brightness", "view_bob", "music_volume", "master_volume", "sfx_volume"}:
        return f"{int(round(value * 100))}%"
    return str(value)


def _apply_setting_change(settings, key, direction):
    new_value = settings[key]
    if key == "pixel_preset":
        presets = list(PIXEL_PRESETS.keys())
        idx = presets.index(settings[key])
        idx = (idx + direction) % len(presets)
        new_value = presets[idx]
    elif key in {"music_enabled", "flash_enabled", "mouse_wheel_weapon_switch", "show_fps", "show_debug_stats"}:
        new_value = not settings[key]
    elif key in {"brightness", "view_bob", "music_volume", "master_volume", "sfx_volume"}:
        new_value = max(0.0, min(1.5 if key == "view_bob" else 1.0, settings[key] + direction * 0.05))
    elif key == "fov_degrees":
        new_value = max(45.0, min(110.0, settings[key] + direction * 5.0))

    settings[key] = new_value
    save_settings({key: new_value})

    if key in {"music_enabled", "music_volume", "master_volume"}:
        apply_music_settings()
        if settings["music_enabled"]:
            resume_music()
        else:
            stop_music()


def _draw_setting_row(screen, rect, label, value_text, font, hovered_minus, hovered_plus, clickable_value):
    pygame.draw.rect(screen, (0, 0, 0), rect)
    pygame.draw.rect(screen, (0, 110, 0), rect, width=1)
    name_surf = font.render(label, True, (220, 255, 220))
    screen.blit(name_surf, (rect.x + 14, rect.y + 8))

    minus_rect = pygame.Rect(rect.right - 120, rect.y + 5, 34, rect.height - 10)
    plus_rect = pygame.Rect(rect.right - 40, rect.y + 5, 34, rect.height - 10)
    value_rect = pygame.Rect(rect.right - 84, rect.y + 5, 40, rect.height - 10)

    _draw_button(screen, minus_rect, "<", font, hovered_minus)
    _draw_button(screen, plus_rect, ">", font, hovered_plus)

    value_border = (0, 255, 0) if clickable_value else (70, 120, 70)
    pygame.draw.rect(screen, (8, 8, 8), value_rect)
    pygame.draw.rect(screen, value_border, value_rect, width=1)
    value_surf = font.render(value_text, True, (255, 255, 255))
    screen.blit(value_surf, value_surf.get_rect(center=value_rect.center))
    return minus_rect, plus_rect, value_rect


def run_pause_menu(screen, clock, root, width, height, title="Paused"):
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
            ("show_fps", "Show FPS"),
            ("show_debug_stats", "Show Debug Stats"),
        ],
    }

    confirm_quit = False
    page = "main"
    settings_section = "Graphics"
    settings = load_settings()

    while True:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.mouse.set_visible(previous_mouse_visible)
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
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
                    for key, label in settings_sections[settings_section]:
                        row_rect = pygame.Rect(width // 2 - 220, row_y, 440, 44)
                        minus_rect = pygame.Rect(row_rect.right - 120, row_rect.y + 5, 34, row_rect.height - 10)
                        plus_rect = pygame.Rect(row_rect.right - 40, row_rect.y + 5, 34, row_rect.height - 10)
                        value_rect = pygame.Rect(row_rect.right - 84, row_rect.y + 5, 40, row_rect.height - 10)
                        if minus_rect.collidepoint(mouse_pos):
                            _apply_setting_change(settings, key, -1)
                            break
                        if plus_rect.collidepoint(mouse_pos):
                            _apply_setting_change(settings, key, 1)
                            break
                        if value_rect.collidepoint(mouse_pos) and isinstance(settings[key], bool):
                            _apply_setting_change(settings, key, 1)
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
                        settings = load_settings()
                        page = "settings"
                        break
                    if action == "restart":
                        pygame.mouse.set_visible(previous_mouse_visible)
                        return "restart"
                    if action == "quit":
                        confirm_quit = True
                        break

        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        screen.blit(overlay, (0, 0))

        panel = pygame.Rect(width // 2 - 250, height // 2 - 200, 500, 430)
        pygame.draw.rect(screen, (0, 0, 0), panel)
        pygame.draw.rect(screen, (0, 255, 0), panel, width=2)

        title_surf = title_font.render("Settings" if page == "settings" else title, True, (0, 255, 0))
        screen.blit(title_surf, title_surf.get_rect(center=(width // 2, height // 2 - 150)))

        if confirm_quit:
            prompt = info_font.render("Are you sure you want to quit to main menu?", True, (255, 255, 255))
            screen.blit(prompt, prompt.get_rect(center=(width // 2, height // 2 + 70)))
            yes_rect = pygame.Rect(width // 2 - 150, height // 2 + 118, 130, 46)
            no_rect = pygame.Rect(width // 2 + 20, height // 2 + 118, 130, 46)
            _draw_button(screen, yes_rect, "Yes", button_font, yes_rect.collidepoint(mouse_pos))
            _draw_button(screen, no_rect, "No", button_font, no_rect.collidepoint(mouse_pos))
        elif page == "settings":
            tab_y = height // 2 - 120
            tab_w = 140
            for i, section_name in enumerate(settings_sections):
                tab_rect = pygame.Rect(width // 2 - 220 + i * (tab_w + 10), tab_y, tab_w, 38)
                _draw_button(screen, tab_rect, section_name, info_font, tab_rect.collidepoint(mouse_pos) or section_name == settings_section)

            row_y = height // 2 - 70
            for key, label in settings_sections[settings_section]:
                row_rect = pygame.Rect(width // 2 - 220, row_y, 440, 44)
                minus_rect = pygame.Rect(row_rect.right - 120, row_rect.y + 5, 34, row_rect.height - 10)
                plus_rect = pygame.Rect(row_rect.right - 40, row_rect.y + 5, 34, row_rect.height - 10)
                _draw_setting_row(
                    screen,
                    row_rect,
                    label,
                    _format_value(key, settings[key]),
                    row_font,
                    minus_rect.collidepoint(mouse_pos),
                    plus_rect.collidepoint(mouse_pos),
                    isinstance(settings[key], bool),
                )
                row_y += 52

            note = "Pixel Resolution applies after restart."
            note_surf = info_font.render(note, True, (170, 170, 170))
            screen.blit(note_surf, note_surf.get_rect(center=(width // 2, height // 2 + 128)))
            back_rect = pygame.Rect(width // 2 - 90, height // 2 + 150, 180, 46)
            _draw_button(screen, back_rect, "Back", button_font, back_rect.collidepoint(mouse_pos))
        else:
            hint_surf = info_font.render("Press ESC to resume", True, (170, 170, 170))
            screen.blit(hint_surf, hint_surf.get_rect(center=(width // 2, height // 2 - 108)))
            for action, rect, label in buttons:
                _draw_button(screen, rect, label, button_font, rect.collidepoint(mouse_pos))

        pygame.display.flip()
        clock.tick(60)

