#!/usr/bin/env python3
"""
Georgia Tech Buzz logo -> Apple II lo-res (40x48), no dithering.
A hand-tuned classifier maps navy -> dark blue, gold -> brown/yellow,
white -> white, so the shapes stay clean at this resolution.

Usage: python3 04_buzz.py [image.png | image.zip]
Output: buzz.wav, buzz_preview.png
"""

import colorsys
import sys
import numpy as np
from PIL import Image, ImageEnhance
from apple2tape import LORES_PALETTE, load_image, pack_lores, \
    screen_image_lines, write_basic_tape, save_lores_preview


def classify(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if v < 0.12:
        return 0                              # black
    if v > 0.80 and s < 0.15:
        return 15                             # white
    if s < 0.15 and 0.35 < v < 0.80:
        return 5                              # grey (antialiasing)
    if b > r and b > g and v < 0.50:
        return 0 if v < 0.20 else 2           # GT navy -> dark blue
    if r > b and g > b:                       # GT gold
        brightness = (r + g + b) / 3
        if brightness < 60:
            return 0
        return 8 if brightness < 170 else 13  # brown / yellow
    if s < 0.3 and v > 0.6 and b >= r:
        return 7                              # light blue highlights
    return min(range(16), key=lambda i: sum((c - p) ** 2 for c, p in
                                            zip((r, g, b), LORES_PALETTE[i])))


def convert(img):
    img = img.convert("RGBA")
    rgb = ImageEnhance.Contrast(img.convert("RGB")).enhance(1.3)
    flat = Image.new("RGB", img.size, (0, 0, 0))
    flat.paste(rgb, mask=img.split()[3])      # transparent -> black

    scale = min(40 / flat.width, 48 / flat.height)
    w, h = int(flat.width * scale), int(flat.height * scale)
    canvas = Image.new("RGB", (40, 48), (0, 0, 0))
    canvas.paste(flat.resize((w, h), Image.LANCZOS), ((40 - w) // 2, (48 - h) // 2))

    px = np.array(canvas)
    return [[classify(*map(int, px[y, x])) for x in range(40)] for y in range(48)]


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "Georgia_Tech_s_Buzz_logo_svg_png.zip"
    pixels = convert(load_image(src))
    write_basic_tape(screen_image_lines(pack_lores(pixels)), "buzz.wav")
    save_lores_preview(pixels, "buzz_preview.png")
