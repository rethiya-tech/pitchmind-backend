"""
Generate professional background images for all 18 themes.
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


# ── Professional theme generators ─────────────────────────────────────────────

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


# ── Creative theme generators ──────────────────────────────────────────────────
# Visual language: bold diagonal bands, large overlapping abstract shapes,
# high-contrast color clashes, energetic — clearly distinct from Professional.

def make_vivid_purple():
    """Purple-to-magenta bold diagonal split with large overlapping rings."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    # Dramatic diagonal gradient: deep purple → vivid magenta
    for y in range(H):
        for x in range(W):
            t = (x / W * 0.55 + y / H * 0.45)
            r = _lerp(21, 160, t)
            g = _lerp(2, 0, t)
            b = _lerp(40, 200, t)
            px[x, y] = (r, g, b)

    draw = ImageDraw.Draw(img)

    # Large bold overlapping circles (outlines only — abstract art feel)
    circles = [
        (W * 0.75, H * 0.25, 220, (200, 40, 255, 60)),
        (W * 0.55, H * 0.65, 180, (160, 0, 220, 50)),
        (W * 0.85, H * 0.7, 140, (220, 80, 255, 45)),
        (W * 0.15, H * 0.3, 160, (120, 0, 180, 40)),
    ]
    for cx, cy, r, color in circles:
        for dr in range(0, 18, 3):
            draw.ellipse([cx-r+dr, cy-r+dr, cx+r-dr, cy+r-dr],
                         outline=(color[0], color[1], color[2]), width=2)

    # Bold diagonal accent band
    band_pts = [(0, H*0.6), (W*0.4, 0), (W*0.4+60, 0), (60, H*0.6)]
    draw.polygon(band_pts, fill=(168, 85, 247, 30))

    return img


def make_sunset_orange():
    """Warm sunset: bold horizontal gradient bands from deep crimson to amber."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    # Top = near-black, bottom-center = vivid amber/orange
    for y in range(H):
        for x in range(W):
            # Horizontal + vertical mix for warmth in center-bottom
            dist_center = abs(x / W - 0.5)
            warm = max(0.0, 1.0 - dist_center * 1.4) * (y / H)
            r = _lerp(20, 240, warm)
            g = _lerp(3, 100, warm * 0.7)
            b = _lerp(5, 10, warm * 0.3)
            px[x, y] = (min(255, r), min(255, g), min(255, b))

    draw = ImageDraw.Draw(img)

    # Horizontal horizon glow band
    for thickness, alpha_frac in [(60, 0.6), (120, 0.35), (200, 0.15)]:
        y0 = int(H * 0.62) - thickness // 2
        for dy in range(thickness):
            t = 1.0 - abs(dy - thickness / 2) / (thickness / 2)
            r = int(255 * t * alpha_frac)
            g = int(120 * t * alpha_frac)
            b = 0
            cur_row = y0 + dy
            if 0 <= cur_row < H:
                row_img = Image.new("RGB", (W, 1), (r, g, b))
                img.paste(Image.blend(img.crop((0, cur_row, W, cur_row+1)), row_img, 0.4),
                          (0, cur_row))

    draw = ImageDraw.Draw(img)
    # Starburst lines from horizon center
    cx, cy = W // 2, int(H * 0.62)
    for angle_deg in range(0, 360, 20):
        angle = math.radians(angle_deg)
        ex = int(cx + math.cos(angle) * 600)
        ey = int(cy + math.sin(angle) * 400)
        draw.line([(cx, cy), (ex, ey)], fill=(200, 80, 0), width=1)

    return img


def make_ocean_teal():
    """Deep ocean: bold curved wave bands, layered from dark to bright teal."""
    img = Image.new("RGB", (W, H), _hex("#001818"))
    draw = ImageDraw.Draw(img)

    # Bold layered wave bands — thicker and higher contrast than professional
    for i in range(14):
        y_center = int(H * (0.1 + i * 0.08))
        amplitude = 35 + i * 4
        freq = 0.012 - i * 0.0003
        green = 40 + i * 14
        blue = 50 + i * 12
        thickness = 2 + (i % 3)
        pts = []
        for x in range(0, W + 1, 4):
            y = y_center + int(amplitude * math.sin(x * freq + i * 1.1))
            pts.append((x, y))
        for j in range(len(pts) - 1):
            draw.line([pts[j], pts[j+1]], fill=(0, min(255, green), min(255, blue)), width=thickness)

    # Large bold circle outline — "portal" shape, top-right
    draw.ellipse([W*2//3, -60, W+120, H//2+60], outline=(20, 200, 180), width=4)
    draw.ellipse([W*2//3+30, -30, W+90, H//2+30], outline=(10, 160, 150), width=2)

    return img


def make_neon_blue():
    """Cyberpunk grid: bright neon grid lines on near-black with scanline glow."""
    img = Image.new("RGB", (W, H), _hex("#000A16"))
    draw = ImageDraw.Draw(img)

    # Perspective grid — vanishing point at center
    cx, cy = W // 2, H // 2

    # Horizontal grid lines (converging slightly)
    for i, y in enumerate(range(0, H + 1, 30)):
        t = abs(y - cy) / (H / 2)
        brightness = max(20, int(90 * (1 - t * 0.7)))
        draw.line([(0, y), (W, y)], fill=(0, brightness // 2, brightness), width=1)

    # Vertical grid lines
    for x in range(0, W + 1, 40):
        t = abs(x - cx) / (W / 2)
        brightness = max(20, int(80 * (1 - t * 0.5)))
        draw.line([(x, 0), (x, H)], fill=(0, brightness // 3, brightness), width=1)

    # Bright neon horizontal accent lines (scanlines)
    for y_accent in [H // 3, H // 2, H * 2 // 3]:
        draw.line([(0, y_accent), (W, y_accent)], fill=(0, 180, 255), width=2)
        draw.line([(0, y_accent - 1), (W, y_accent - 1)], fill=(0, 80, 120), width=1)
        draw.line([(0, y_accent + 1), (W, y_accent + 1)], fill=(0, 80, 120), width=1)

    # Neon corner bracket — top-left
    bracket_size = 80
    draw.line([(20, 20), (20 + bracket_size, 20)], fill=(56, 189, 248), width=3)
    draw.line([(20, 20), (20, 20 + bracket_size)], fill=(56, 189, 248), width=3)
    # bottom-right
    draw.line([(W-20-bracket_size, H-20), (W-20, H-20)], fill=(56, 189, 248), width=3)
    draw.line([(W-20, H-20-bracket_size), (W-20, H-20)], fill=(56, 189, 248), width=3)

    return img


def make_ruby_red():
    """Bold red: large diamond & triangle shapes, strong diagonal energy."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    # Left-to-right diagonal: deep maroon → vivid crimson
    for y in range(H):
        for x in range(W):
            t = x / W * 0.7 + y / H * 0.3
            r = _lerp(22, 200, t)
            g = _lerp(0, 10, t)
            b = _lerp(0, 25, t)
            px[x, y] = (min(255, r), g, b)

    draw = ImageDraw.Draw(img)

    # Large diamond shapes (filled, semi-transparent — simulate with repeated draw)
    diamonds = [
        (W * 0.72, H * 0.35, 200),   # large right
        (W * 0.85, H * 0.72, 120),   # medium bottom-right
        (W * 0.52, H * 0.15, 90),    # small top-center
    ]
    for cx, cy, size in diamonds:
        pts = [(cx, cy - size), (cx + size * 0.6, cy),
               (cx, cy + size), (cx - size * 0.6, cy)]
        # Outline only — bold and layered
        draw.polygon(pts, outline=(244, 63, 94), fill=None)
        inner = [(cx, cy - size * 0.7), (cx + size * 0.42, cy),
                 (cx, cy + size * 0.7), (cx - size * 0.42, cy)]
        draw.polygon(inner, outline=(200, 30, 60), fill=None)

    # Bold diagonal cut line
    draw.line([(0, H * 0.4), (W * 0.6, 0)], fill=(180, 30, 50), width=3)
    draw.line([(0, H * 0.4 + 6), (W * 0.6 + 6, 0)], fill=(100, 15, 25), width=1)

    return img


def make_cosmic_indigo():
    """Nebula: bold multi-color cloud washes, dramatic deep space feel."""
    img = Image.new("RGB", (W, H), _hex("#000818"))
    draw = ImageDraw.Draw(img)

    # Layered nebula clouds — multiple large blurred ellipses of different colors
    clouds = [
        # (cx, cy, rx, ry, color, passes)
        (int(W * 0.3), int(H * 0.4), 320, 240, (80, 0, 180), 40),    # purple left
        (int(W * 0.7), int(H * 0.55), 280, 200, (30, 0, 130), 35),   # deep blue right
        (int(W * 0.5), int(H * 0.2), 200, 150, (120, 40, 200), 30),  # violet top-center
        (int(W * 0.15), int(H * 0.75), 180, 140, (60, 20, 160), 25), # dark indigo bottom-left
    ]
    for cx, cy, rx, ry, color, passes in clouds:
        for i in range(passes, 0, -1):
            t = i / passes
            scale = t
            r_val = min(255, int(color[0] * (1 - t * 0.8)))
            g_val = min(255, int(color[1] * (1 - t * 0.5)))
            b_val = min(255, int(color[2] * (1 - t * 0.4)))
            ex0 = int(cx - rx * scale)
            ey0 = int(cy - ry * scale)
            ex1 = int(cx + rx * scale)
            ey1 = int(cy + ry * scale)
            draw.ellipse([ex0, ey0, ex1, ey1], fill=(r_val, g_val, b_val))

    # Star field on top
    import random; random.seed(99)
    for _ in range(250):
        x = random.randint(0, W); y = random.randint(0, H)
        b_val = random.randint(120, 255)
        purple_tint = random.randint(0, 80)
        size = random.choice([1, 1, 1, 2])
        draw.ellipse([x-size, y-size, x+size, y+size], fill=(b_val, purple_tint, b_val))

    # Blur the whole thing for a painterly nebula effect
    img = img.filter(ImageFilter.GaussianBlur(radius=3))

    # Re-draw sharp stars on top after blur
    draw = ImageDraw.Draw(img)
    random.seed(77)
    for _ in range(80):
        x = random.randint(0, W); y = random.randint(0, H)
        draw.ellipse([x, y, x+1, y+1], fill=(255, 200, 255))

    return img


# ── Minimal theme generators ───────────────────────────────────────────────────

def make_pure_white():
    img = vertical_gradient(W, H, _hex("#FFFFFF"), _hex("#F5F6F8"))
    draw = ImageDraw.Draw(img)
    for i in range(-H, W+H, 50):
        draw.line([(i, 0), (i+H, H)], fill=(220, 222, 226), width=1)
    import random; random.seed(5)
    for _ in range(40):
        x = random.randint(W*2//3, W); y = random.randint(0, H//3)
        r = random.choice([2, 3])
        draw.ellipse([x-r, y-r, x+r, y+r], fill=(180, 195, 230))
    return img


def make_warm_ivory():
    img = vertical_gradient(W, H, _hex("#FFFDF5"), _hex("#FFF5E0"))
    draw = ImageDraw.Draw(img)
    for cx, cy, r in [(int(W*0.8), int(H*0.2), 180), (int(W*0.1), int(H*0.8), 120), (int(W*0.9), int(H*0.7), 80)]:
        for dr in range(r, 0, -10):
            t = 1 - dr/r
            color = (_lerp(255, 240, t*0.3), _lerp(245, 210, t*0.3), _lerp(220, 160, t*0.3))
            draw.ellipse([cx-dr, cy-dr, cx+dr, cy+dr], outline=color)
    return img


def make_soft_grey():
    img = vertical_gradient(W, H, _hex("#F8F9FA"), _hex("#EDEFF2"))
    draw = ImageDraw.Draw(img)
    for y in range(60, H, 60):
        draw.line([(0, y), (W, y)], fill=(210, 214, 220), width=1)
    draw.rectangle([W - 8, 0, W, H], fill=(190, 200, 215))
    import random; random.seed(3)
    for _ in range(30):
        x = random.randint(0, W); y = random.randint(0, H//4)
        draw.ellipse([x-2, y-2, x+2, y+2], fill=(185, 195, 210))
    return img


def make_light_pearl():
    img = vertical_gradient(W, H, _hex("#EEF2FF"), _hex("#E8EDFF"))
    draw = ImageDraw.Draw(img)
    for cx, cy, r, color in [
        (int(W*0.85), int(H*0.15), 200, (200, 210, 240)),
        (int(W*0.1), int(H*0.85), 160, (195, 208, 238)),
        (int(W*0.5), int(H*0.5), 120, (205, 215, 242)),
    ]:
        for dr in range(r, max(0, r-40), -5):
            draw.ellipse([cx-dr, cy-dr, cx+dr, cy+dr], outline=color)
    return img


def make_sage_mist():
    img = vertical_gradient(W, H, _hex("#F2F7F2"), _hex("#E8F2E8"))
    draw = ImageDraw.Draw(img)
    for i in range(6):
        y_base = 80 + i * 70
        pts = [(x, y_base + int(25 * math.sin(x / 130 + i * 0.8))) for x in range(0, W+1, 10)]
        for j in range(len(pts)-1):
            draw.line([pts[j], pts[j+1]], fill=(180, 210, 180), width=1)
    import random; random.seed(17)
    for _ in range(50):
        x = random.randint(0, W); y = random.randint(0, H)
        draw.ellipse([x-2, y-2, x+2, y+2], fill=(160, 200, 160))
    return img


def make_warm_slate():
    img = vertical_gradient(W, H, _hex("#F4F6F8"), _hex("#E8ECF1"))
    draw = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=(210, 216, 225), width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(210, 216, 225), width=1)
    draw.line([(0, H), (W*2//3, 0)], fill=(190, 200, 215), width=2)
    for cx, cy in [(0, 0), (W, 0), (0, H), (W, H)]:
        for r in range(60, 20, -15):
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(195, 205, 218))
    return img


# ── Main ──────────────────────────────────────────────────────────────────────

THEMES = [
    # Professional
    ("clean_slate",    make_clean_slate),
    ("navy_gold",      make_navy_gold),
    ("dark_tech",      make_dark_tech),
    ("charcoal_amber", make_charcoal_amber),
    ("steel_blue",     make_steel_blue),
    ("forest_pro",     make_forest_pro),
    # Creative
    ("vivid_purple",   make_vivid_purple),
    ("sunset_orange",  make_sunset_orange),
    ("ocean_teal",     make_ocean_teal),
    ("neon_blue",      make_neon_blue),
    ("ruby_red",       make_ruby_red),
    ("cosmic_indigo",  make_cosmic_indigo),
    # Minimal
    ("pure_white",     make_pure_white),
    ("warm_ivory",     make_warm_ivory),
    ("soft_grey",      make_soft_grey),
    ("light_pearl",    make_light_pearl),
    ("sage_mist",      make_sage_mist),
    ("warm_slate",     make_warm_slate),
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
