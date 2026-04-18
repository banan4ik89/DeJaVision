import pygame
import math
import time
from PIL import Image
from abebe.maze.raycast_engine import pil_to_surface
from abebe.core.user_settings import get_flash_enabled

class StatisticsWindow:
    def __init__(self, W, H, elevator_enter_time, stats, fonts, resource_path_func):
        self.W = W
        self.H = H
        self.elevator_enter_time = elevator_enter_time
        self.stats = stats  # dict: enemies_killed, total_shots_fired, total_shots_hit, etc.
        self.fonts = fonts  # dict: 'title', 'small', 'main'
        self.resource_path = resource_path_func
        self.active = False
        self.animation_start = 0.0
        self.window_y = 0.0
        self.shake_offset = 0.0
        self.float_offset_x = 0.0
        self.float_offset_y = 0.0
        self.float_time = 0.0
        self.counting_active = False
        self.count_start = 0.0
        self.flash_active = False
        self.flash_start = 0.0
        self.count_duration = 2.0
        self.flash_duration = 0.3
        self.can_skip = False
        self.completed = False
        self.icon_active = False
        self.icon_start = 0.0
        self.icon_pulse_time = 0.0
        self.icon_base_size = 48
        self.icon_max_size = 72
        self.progress_bar_target = 67
        self.progress_bar_current = 0.0
        self.flash_enabled = get_flash_enabled()

    def start(self):
        self.flash_enabled = get_flash_enabled()
        self.active = True
        self.animation_start = time.time()
        self.counting_active = True
        self.count_start = time.time()
        self.can_skip = True
        self.completed = False
        self.flash_active = False
        self.icon_active = False
        self.icon_pulse_time = 0.0

    def handle_event(self, event):
        if not self.active:
            return False
        if event.type == pygame.KEYDOWN:
            if (event.key == pygame.K_RETURN or event.key == pygame.K_SPACE) and self.completed:
                self.active = False
                return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.can_skip and not self.completed:
                self.completed = True
                if self.flash_enabled:
                    self.flash_active = True
                    self.flash_start = time.time()
                else:
                    self.icon_active = True
                    self.icon_start = time.time()
                    self.icon_pulse_time = 0.0
                self.counting_active = False
        return False

    def update(self, delta):
        if not self.active:
            return
        self.float_time += delta
        if self.counting_active:
            count_elapsed = time.time() - self.count_start
            if count_elapsed >= self.count_duration:
                self.counting_active = False
                self.completed = True
                if self.flash_enabled:
                    self.flash_active = True
                    self.flash_start = time.time()
                else:
                    self.icon_active = True
                    self.icon_start = time.time()
                    self.icon_pulse_time = 0.0
        if self.flash_active:
            flash_elapsed = time.time() - self.flash_start
            if flash_elapsed >= self.flash_duration:
                self.flash_active = False
                self.icon_active = True
                self.icon_start = time.time()
                self.icon_pulse_time = 0.0
        if self.icon_active:
            self.icon_pulse_time += delta

    def draw(self, screen):
        if not self.active:
            return
        # Animation calculations (simplified)
        anim_elapsed = time.time() - self.animation_start
        anim_duration = 1.2
        slide_progress = min(1.0, anim_elapsed / anim_duration)
        slide_eased = 1.0 - (1.0 - slide_progress) ** 3
        shake_intensity = 0.0
        if slide_progress > 0.3:
            shake_progress = (slide_progress - 0.3) / 0.7
            shake_intensity = math.sin(shake_progress * math.pi * 4) * 5.0 * (1.0 - shake_progress * 0.5)
            self.shake_offset = math.sin(time.time() * 20) * shake_intensity
        window_w = 500
        window_h = 400
        target_y = self.H // 2 - window_h // 2
        start_y = -window_h
        self.window_y = start_y + (target_y - start_y) * slide_eased + self.shake_offset + self.float_offset_y
        window_x = self.W // 2 - window_w // 2 + self.float_offset_x
        # Draw window
        pygame.draw.rect(screen, (0, 255, 0), (window_x, self.window_y, window_w, window_h), width=3)
        pygame.draw.rect(screen, (0, 0, 0), (window_x + 3, self.window_y + 3, window_w - 6, window_h - 6))
        # Title
        title_surf = self.fonts['title'].render("LEVEL COMPLETE", True, (0, 255, 0))
        screen.blit(title_surf, (window_x + window_w // 2 - title_surf.get_width() // 2, self.window_y + 30))
        # Stats
        stats_y = self.window_y + 80
        line_height = 35
        if self.counting_active:
            count_elapsed = time.time() - self.count_start
            count_progress = min(1.0, count_elapsed / self.count_duration)
            current_time = self.elevator_enter_time * count_progress
            enemies_defeated = int(self.stats['enemies_killed'] * count_progress)
            items_collected = int(1 * count_progress)
            shots_fired = int(self.stats['total_shots_fired'] * count_progress)
            shots_hit = int(self.stats['total_shots_hit'] * count_progress)
            accuracy = int((self.stats['total_shots_hit'] / max(1, self.stats['total_shots_fired'])) * 100 * count_progress) if self.stats['total_shots_fired'] > 0 else 0
            self.progress_bar_current = self.progress_bar_target * count_progress
        else:
            current_time = self.elevator_enter_time
            enemies_defeated = self.stats['enemies_killed']
            items_collected = 1
            shots_fired = self.stats['total_shots_fired']
            shots_hit = self.stats['total_shots_hit']
            accuracy = int((self.stats['total_shots_hit'] / max(1, self.stats['total_shots_fired'])) * 100) if self.stats['total_shots_fired'] > 0 else 0
            self.progress_bar_current = self.progress_bar_target
        entry_minutes = int(current_time // 60) % 60
        entry_seconds = int(current_time % 60)
        entry_milliseconds = int((current_time % 1) * 1000)
        entry_time_text = f"Entry Time: {entry_minutes:02}:{entry_seconds:02}:{entry_milliseconds:03}"
        entry_surf = self.fonts['small'].render(entry_time_text, True, (0, 255, 0))
        screen.blit(entry_surf, (window_x + 40, stats_y))
        other_stats = [
            f"Enemies Defeated: {enemies_defeated}",
            f"Items Collected: {items_collected}",
            f"Shots Fired: {shots_fired}",
            f"Shots Hit: {shots_hit}",
            f"Accuracy: {accuracy}%",
            "Rank: TRAINEE"
        ]
        for i, stat_text in enumerate(other_stats):
            stat_surf = self.fonts['small'].render(stat_text, True, (0, 255, 0))
            screen.blit(stat_surf, (window_x + 40, stats_y + line_height * (i + 1)))
        # Progress bar
        progress_bar_x = window_x + window_w - 60
        progress_bar_y = stats_y + 10
        progress_bar_width = 20
        progress_bar_height = 160
        pygame.draw.rect(screen, (50, 50, 50), (progress_bar_x, progress_bar_y, progress_bar_width, progress_bar_height))
        fill_height = int((self.progress_bar_current / 100.0) * progress_bar_height)
        fill_y = progress_bar_y + progress_bar_height - fill_height
        pygame.draw.rect(screen, (0, 255, 0), (progress_bar_x, fill_y, progress_bar_width, fill_height))
        pygame.draw.rect(screen, (0, 255, 0), (progress_bar_x, progress_bar_y, progress_bar_width, progress_bar_height), width=2)
        percent_text = f"{int(self.progress_bar_current)}%"
        percent_surf = self.fonts['small'].render(percent_text, True, (0, 255, 0))
        screen.blit(percent_surf, (progress_bar_x + progress_bar_width // 2 - percent_surf.get_width() // 2, progress_bar_y - 25))
        # OK button
        if self.completed:
            button_w = 120
            button_h = 40
            button_x = window_x + window_w // 2 - button_w // 2
            button_y = self.window_y + window_h - 70
            pygame.draw.rect(screen, (0, 255, 0), (button_x, button_y, button_w, button_h), width=2)
            ok_surf = self.fonts['title'].render("OK", True, (0, 255, 0))
            screen.blit(ok_surf, (button_x + button_w // 2 - ok_surf.get_width() // 2, button_y + button_h // 2 - ok_surf.get_height() // 2))
            inst_text = "Press ENTER or SPACE to continue"
            inst_surf = self.fonts['small'].render(inst_text, True, (0, 255, 0))
            screen.blit(inst_surf, (window_x + window_w // 2 - inst_surf.get_width() // 2, self.window_y + window_h - 25))
        else:
            inst_text = "Click to skip animation"
            inst_surf = self.fonts['small'].render(inst_text, True, (0, 255, 0))
            screen.blit(inst_surf, (window_x + window_w // 2 - inst_surf.get_width() // 2, self.window_y + window_h - 25))
        # Icon animation
        if self.icon_active:
            pulse_speed = 3.0
            pulse_ratio = (math.sin(self.icon_pulse_time * pulse_speed) + 1.0) / 2.0
            current_size = int(self.icon_base_size + (self.icon_max_size - self.icon_base_size) * pulse_ratio)
            icon_x = window_x + window_w - current_size // 2
            icon_y = self.window_y - current_size // 3
            try:
                icon_img = Image.open(self.resource_path("data/unknown.png")).convert("RGBA")
                icon_img = icon_img.rotate(45, expand=True)
                icon_img = icon_img.resize((current_size, current_size), Image.NEAREST)
                icon_surface = pil_to_surface(icon_img)
                screen.blit(icon_surface, (icon_x, icon_y))
            except Exception:
                center_x = icon_x + current_size // 2
                center_y = icon_y + current_size // 2
                half_size = current_size // 2
                angle_rad = math.radians(45)
                corners = []
                for dx, dy in [(-half_size, -half_size), (half_size, -half_size), (half_size, half_size), (-half_size, half_size)]:
                    rot_x = dx * math.cos(angle_rad) - dy * math.sin(angle_rad)
                    rot_y = dx * math.sin(angle_rad) + dy * math.cos(angle_rad)
                    corners.append((center_x + rot_x, center_y + rot_y))
                pygame.draw.polygon(screen, (0, 255, 0), corners, 2)

