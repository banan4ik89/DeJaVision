# generate_retro_orb.py

from PIL import Image
import math


def generate_retro_orb(size=256, base_color=(194, 160, 90), pixel_size=32):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = img.load()

    cx = cy = size // 2
    radius = size // 2 - 2

    # направление света (сверху-слева)
    light_dir = (-0.6, -0.8)

    # === рисуем сферу с освещением ===
    for y in range(size):
        for x in range(size):
            dx = (x - cx) / radius
            dy = (y - cy) / radius
            dist = dx * dx + dy * dy

            if dist <= 1.0:
                dz = math.sqrt(1 - dist)

                # Ламбертово освещение
                light = dx * light_dir[0] + dy * light_dir[1] + dz * 0.8
                light = max(0, min(1, light))

                # Затемнение по краям
                shade = 1 - math.sqrt(dist)

                intensity = light * 0.7 + shade * 0.3

                r = int(base_color[0] * intensity)
                g = int(base_color[1] * intensity)
                b = int(base_color[2] * intensity)

                pixels[x, y] = (r, g, b, 255)

    # === рассеянный блик ===
    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hp = highlight.load()

    hx = cx - size // 4
    hy = cy - size // 4
    hradius = size // 5

    for y in range(size):
        for x in range(size):
            dx = x - hx
            dy = y - hy
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < hradius:
                t = 1 - (dist / hradius)
                alpha = int(220 * (t ** 1.5))  # мягкое рассеивание

                hp[x, y] = (255, 255, 255, alpha)

    img = Image.alpha_composite(img, highlight)

    # === пикселизация ===
    small = img.resize((pixel_size, pixel_size), Image.NEAREST)
    pixelated = small.resize((size, size), Image.NEAREST)

    return pixelated


if __name__ == "__main__":
    # Меняй цвет при желании:
    # (194,160,90) — золотой
    # (60,200,80) — зелёный
    # (160,80,200) — фиолетовый
    # (200,60,60) — красный

    orb = generate_retro_orb(
        size=256,
        base_color=(255,254,233),
        pixel_size=32
    )

    orb.save("retro_orb.png")
    print("Готово! Сохранено как retro_orb.png")