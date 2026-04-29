"""
Generate professional background images for all 6 themes.
Run from repo root: python scripts/generate_theme_images.py
Outputs:
  app/assets/themes/{id}_bg.png   — embedded in PPTX (960x540)
  ../../pitchmind-frontend/public/themes/{id}.png — ThemePicker thumbnails
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

W, H = 960, 540


def _lerp(a, b, t):
    return int(a + (b - a) * max(0.0, min(1.0, t)))


def _lerp_color(c1, c2, t):
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t), _lerp(c1[2], c2[2], t))


def _hex(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def vertical_gradient(w, h, top_color, bottom_color):
    base = Image.new("RGB", (1, 2))
    base.putpixel((0, 0), top_color)
    base.putpixel((0, 1), bottom_color)
    return base.resize((w, h), Image.BICUBIC)


def diagonal_gradient(w, h, c1, c2):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.6 + y / h * 0.4)
            px[x, y] = _lerp_color(c1, c2, t)
    return img


# ── Theme generators ──────────────────────────────────────────────────────────

def make_clean_slate():
    """Dark slate — subtle diagonal grid lines, minimal dots."""
    c1, c2 = _hex("#1E2A3A"), _hex("#0D1520")
    img = diagonal_gradient(W, H, c1, c2)
    draw = ImageDraw.Draw(img)

    # Subtle diagonal grid
    line_color = (40, 60, 85, 60)
    step = 60
    for i in range(-H, W + H, step):
        draw.line([(i, 0), (i + H, H)], fill=(40, 60, 85), width=1)

    # Accent dots — top-right cluster
    for dx, dy in [(820, 80), (860, 120), (900, 60), (880, 160), (840, 200),
                   (760, 90), (920, 140), (940, 80), (780, 140)]:
        r = 2
        draw.ellipse([dx - r, dy - r, dx + r, dy + r], fill=(96, 165, 250))

    # Soft blue glow top-right
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for radius in range(200, 0, -10):
        alpha = int(18 * (1 - radius / 200))
        gdraw.ellipse([W - radius - 20, -radius + 40, W + radius - 20, radius + 40],
                      fill=(30, 80, 180))
    img = Image.blend(img, glow, 0.35)

    return img


def make_navy_gold():
    """Deep navy — gold particle dots and a soft radial glow."""
    c1, c2 = _hex("#0A1628"), _hex("#071020")
    img = vertical_gradient(W, H, c1, c2)
    draw = ImageDraw.Draw(img)

    # Gold particles
    import random
    random.seed(42)
    for _ in range(120):
        x = random.randint(0, W)
        y = random.randint(0, H)
        size = random.choice([1, 1, 1, 2])
        alpha = random.randint(120, 220)
        gold = (_lerp(180, 212, random.random()), _lerp(130, 160, random.random()), 20)
        draw.ellipse([x - size, y - size, x + size, y + size], fill=gold)

    # Horizontal gold accent line
    draw.rectangle([0, H // 2 - 1, W, H // 2], fill=(212, 160, 23))

    # Radial glow left-center
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    cx, cy = int(W * 0.25), H // 2
    for radius in range(280, 0, -8):
        t = 1 - radius / 280
        r = _lerp(15, 45, t)
        g = _lerp(25, 70, t)
        b = _lerp(80, 120, t)
        gdraw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(r, g, b))
    img = Image.blend(img, glow, 0.5)

    return img


def make_dark_tech():
    """Near-black — cyan hexagonal dot grid and side glow."""
    img = Image.new("RGB", (W, H), _hex("#0D1117"))
    draw = ImageDraw.Draw(img)

    # Hexagonal dot grid
    hex_r = 28
    cols = W // (hex_r * 2) + 2
    rows = H // (hex_r * 2) + 2
    for row in range(rows):
        for col in range(cols):
            cx = col * hex_r * 2 + (hex_r if row % 2 else 0)
            cy = row * int(hex_r * 1.73)
            dist_from_center = math.sqrt((cx - W * 0.5) ** 2 + (cy - H * 0.5) ** 2)
            brightness = max(0, 1 - dist_from_center / (W * 0.6))
            dot_r = 1 if brightness < 0.3 else 2
            alpha = int(brightness * 120 + 20)
            color = (0, min(255, alpha * 2), min(255, alpha * 3))
            draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=color)

    # Cyan glow — left side
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for radius in range(300, 0, -6):
        t = 1 - radius / 300
        gdraw.ellipse([-radius + 100, H // 2 - radius, radius + 100, H // 2 + radius],
                      fill=(0, _lerp(0, 100, t), _lerp(0, 180, t)))
    img = Image.blend(img, glow, 0.6)

    # Thin horizontal lines
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(6, 182, 212, 30), width=1)

    return img


def make_charcoal_amber():
    """Dark charcoal — amber radial glow from bottom-left corner."""
    c1, c2 = _hex("#1C2030"), _hex("#0F1218")
    img = diagonal_gradient(W, H, c1, c2)
    draw = ImageDraw.Draw(img)

    # Amber glow from bottom-left
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for radius in range(400, 0, -8):
        t = 1 - radius / 400
        r = _lerp(20, 200, t * t)
        g = _lerp(10, 90, t * t)
        b = 0
        gdraw.ellipse([-radius + 80, H - 40 + 80 - radius, radius + 80, H - 40 + 80 + radius],
                      fill=(r, g, b))
    img = Image.blend(img, glow, 0.65)

    # Subtle grid lines
    for x in range(0, W, 90):
        draw.line([(x, 0), (x, H)], fill=(50, 40, 30), width=1)
    for y in range(0, H, 90):
        draw.line([(0, y), (W, y)], fill=(50, 40, 30), width=1)

    # Small amber dots
    import random
    random.seed(7)
    for _ in range(60):
        x = random.randint(0, W // 2)
        y = random.randint(H // 3, H)
        r = random.choice([1, 1, 2])
        brightness = random.randint(100, 200)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(brightness, brightness // 3, 0))

    return img


def make_steel_blue():
    """Steel blue — geometric triangle shapes and diagonal streaks."""
    c1, c2 = _hex("#1A3050"), _hex("#0E1D33")
    img = diagonal_gradient(W, H, c2, c1)
    draw = ImageDraw.Draw(img)

    # Geometric triangles (faint outlines)
    triangles = [
        [(700, 50), (850, 280), (560, 290)],
        [(820, 180), (950, 380), (700, 370)],
        [(600, 10), (730, 180), (480, 170)],
    ]
    for tri in triangles:
        draw.polygon(tri, outline=(96, 165, 250, 40), fill=None)

    # Diagonal light streaks
    for i, offset in enumerate([0, 120, 240]):
        x0 = W - 300 + offset
        draw.line([(x0, 0), (x0 + H, H)], fill=(60, 100, 160), width=1)

    # Right-side blue glow
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for radius in range(350, 0, -7):
        t = 1 - radius / 350
        gdraw.ellipse([W - 50 - radius, H // 2 - radius, W - 50 + radius, H // 2 + radius],
                      fill=(_lerp(10, 40, t), _lerp(30, 80, t), _lerp(80, 180, t)))
    img = Image.blend(img, glow, 0.45)

    # Small light-blue dots — right half
    import random
    random.seed(3)
    for _ in range(80):
        x = random.randint(W // 2, W)
        y = random.randint(0, H)
        r = 1
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(140, 190, 255))

    return img


def make_forest_pro():
    """Deep forest green — organic flowing arcs and mint particles."""
    c1, c2 = _hex("#04321E"), _hex("#021810")
    img = vertical_gradient(W, H, c1, c2)
    draw = ImageDraw.Draw(img)

    # Flowing arcs
    for i in range(8):
        y_offset = 80 + i * 60
        pts = []
        for x in range(0, W + 1, 10):
            y = y_offset + int(30 * math.sin(x / 120 + i * 0.7))
            pts.append((x, y))
        if len(pts) >= 2:
            for j in range(len(pts) - 1):
                draw.line([pts[j], pts[j + 1]], fill=(10, 60, 40), width=1)

    # Mint/emerald radial glow — center-right
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for radius in range(300, 0, -6):
        t = 1 - radius / 300
        gdraw.ellipse([W * 3 // 4 - radius, H // 2 - radius,
                       W * 3 // 4 + radius, H // 2 + radius],
                      fill=(0, _lerp(0, 80, t), _lerp(0, 60, t)))
    img = Image.blend(img, glow, 0.5)

    # Mint particles
    import random
    random.seed(11)
    for _ in range(100):
        x = random.randint(0, W)
        y = random.randint(0, H)
        r = random.choice([1, 1, 2])
        g_val = random.randint(160, 220)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(10, g_val, 100))

    return img


# ── Main ──────────────────────────────────────────────────────────────────────

THEMES = [
    ("clean_slate",    make_clean_slate),
    ("navy_gold",      make_navy_gold),
    ("dark_tech",      make_dark_tech),
    ("charcoal_amber", make_charcoal_amber),
    ("steel_blue",     make_steel_blue),
    ("forest_pro",     make_forest_pro),
]

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_root = os.path.dirname(script_dir)
    frontend_root = os.path.join(os.path.dirname(backend_root), "pitchmind-frontend")

    bg_dir = os.path.join(backend_root, "app", "assets", "themes")
    thumb_dir = os.path.join(frontend_root, "public", "themes")
    os.makedirs(bg_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)

    for theme_id, generator in THEMES:
        print(f"Generating {theme_id}...", end=" ", flush=True)
        img = generator()

        # Full size for PPTX
        bg_path = os.path.join(bg_dir, f"{theme_id}_bg.png")
        img.save(bg_path, "PNG", optimize=True)

        # Thumbnail for frontend (320x180)
        thumb = img.resize((320, 180), Image.LANCZOS)
        thumb_path = os.path.join(thumb_dir, f"{theme_id}.png")
        thumb.save(thumb_path, "PNG", optimize=True)

        print(f"done  ({os.path.getsize(bg_path) // 1024} KB)")

    print("\nAll theme images generated successfully.")


if __name__ == "__main__":
    main()
