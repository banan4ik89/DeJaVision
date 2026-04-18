"""Common helpers for pygame maze scenes."""
import time

import pygame

from abebe.core.user_settings import get_brightness


GAME_VIEW_W = 320
GAME_VIEW_H = 200


def blit_game_view_upscaled(game_surface, screen, window_w, window_h):
    """Nearest-neighbor upscale for the 3D scene."""
    scaled = pygame.transform.scale(game_surface, (window_w, window_h))
    screen.blit(scaled, (0, 0))

    brightness = get_brightness()
    if brightness < 0.99:
        overlay = pygame.Surface((window_w, window_h))
        overlay.set_alpha(int((1.0 - brightness) * 220))
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))
    elif brightness > 1.01:
        overlay = pygame.Surface((window_w, window_h))
        overlay.set_alpha(int((brightness - 1.0) * 180))
        overlay.fill((255, 255, 255))
        screen.blit(overlay, (0, 0))


def make_font(size, bold=False):
    for name in ("consolas", "couriernew", "courier", "lucidaconsole"):
        try:
            return pygame.font.SysFont(name, size, bold=bold)
        except Exception:
            continue
    return pygame.font.Font(None, size)


def draw_hud_base(
    screen,
    hud_img,
    hud_x,
    hud_y,
    hud_w,
    hud_h,
    font_hud,
    font_hud_big,
    font_clock,
    font_slot,
    ammo,
    max_ammo,
    hud_start_time,
    selected_slot,
    gunitem_img,
    show_gun_icon,
):
    screen.blit(hud_img, (hud_x, hud_y))
    screen.blit(font_hud.render("AMMO:", True, (0, 255, 0)), (hud_x + 26, hud_y + 28))
    screen.blit(font_hud_big.render(f"{ammo}/{max_ammo}", True, (0, 255, 0)), (hud_x + 23, hud_y + 48))

    hp_percent = 1.0
    max_blocks = 10
    filled_blocks = int(max_blocks * hp_percent)
    block_size = 10
    block_spacing = 3
    start_hp_x = hud_x + hud_w // 2 + 20
    start_hp_y = hud_y + 40
    for i in range(max_blocks):
        x = start_hp_x + i * (block_size + block_spacing)
        y = start_hp_y
        col = (255, 0, 0) if i < filled_blocks else (34, 0, 0)
        pygame.draw.rect(screen, col, (x, y, block_size, block_size), width=1)
    screen.blit(font_hud.render("HP:", True, (0, 255, 0)), (start_hp_x, start_hp_y - 10))

    elapsed = time.time() - hud_start_time
    minutes = int(elapsed // 60) % 60
    seconds = int(elapsed % 60)
    milliseconds = int((elapsed % 1) * 1000)
    time_text = f"{minutes:02}:{seconds:02}:{milliseconds:03}"
    clock_offset_x = 30
    clock_offset_y = hud_h - 55
    clock_width = 80
    clock_height = 28
    pygame.draw.rect(
        screen,
        (0, 0, 0),
        (hud_x + clock_offset_x, hud_y + clock_offset_y, clock_width, clock_height),
        width=2,
    )
    tsurf = font_clock.render(time_text, True, (0, 255, 0))
    screen.blit(
        tsurf,
        (
            hud_x + clock_offset_x + clock_width // 2 - tsurf.get_width() // 2,
            hud_y + clock_offset_y + clock_height // 2 - tsurf.get_height() // 2,
        ),
    )

    slot_size = 32
    slot_spacing = 6
    start_x = hud_x + hud_w // 2 - (2 * slot_size + 1.5 * slot_spacing)
    start_y = hud_y + hud_h - slot_size - 35
    for i in range(5):
        x = start_x + i * (slot_size + slot_spacing)
        y = start_y
        if (i + 1) == selected_slot:
            pygame.draw.rect(screen, (255, 255, 0), (x - 2, y - 2, slot_size + 4, slot_size + 4), width=2)
        pygame.draw.rect(screen, (102, 102, 102), (x, y, slot_size, slot_size), width=2)
        ns = font_slot.render(str(i + 1), True, (0, 255, 0))
        screen.blit(ns, (x + slot_size // 2 - ns.get_width() // 2, y + slot_size + 10))
    if show_gun_icon:
        screen.blit(gunitem_img, gunitem_img.get_rect(center=(start_x + slot_size // 2, start_y + slot_size // 2)))


def draw_boss_bar(screen, font_boss, enemy_state, enemy_health, enemy_max_health, W):
    if enemy_state != "walking":
        return
    bar_width = 400
    bar_height = 25
    x = W // 2 - bar_width // 2
    y = 40
    pygame.draw.rect(screen, (51, 0, 0), (x, y, bar_width, bar_height), width=1)
    hp_ratio = enemy_health / enemy_max_health
    pygame.draw.rect(screen, (255, 0, 0), (x, y, int(bar_width * hp_ratio), bar_height))
    bs = font_boss.render("Dr. Hale", True, (255, 255, 255))
    screen.blit(bs, (W // 2 - bs.get_width() // 2, y - 22))

