#!/usr/bin/env python3
"""
Red monkey image -> Apple II lo-res (40x48). The source is almost pure red,
so it's treated as a luminance image, gamma-corrected, and Bayer-dithered
onto a warm 5-level ramp (black, magenta, orange, pink, white).

Usage: python3 03_red_monkey.py [image.png | image.zip]
Output: red_monkey.wav, red_monkey_preview.png
"""

import sys
import numpy as np
from PIL import Image
from apple2tape import load_image, pack_lores, screen_image_lines, \
    write_basic_tape, save_lores_preview

RAMP = [0, 1, 9, 11, 15]              # Black, Magenta, Orange, Pink, White
RAMP_LEVELS = [0.0, 0.30, 0.55, 0.75, 1.0]
GAMMA = 0.65
BAYER_4 = np.array([[0, 8, 2, 10],
                    [12, 4, 14, 6],
                    [3, 11, 1, 9],
                    [15, 7, 13, 5]], dtype=float) / 16.0


def convert(img):
    img = img.convert("RGB").resize((40, 48), Image.LANCZOS)
    lum = np.array(img)[:, :, 0].astype(float)          # red channel
    lum = np.power(lum / max(lum.max(), 1), GAMMA)

    out = np.zeros((48, 40), dtype=int)
    for y in range(48):
        for x in range(40):
            v = lum[y, x]
            level = max(i for i in range(len(RAMP_LEVELS) - 1) if v >= RAMP_LEVELS[i])
            lo, hi = RAMP_LEVELS[level], RAMP_LEVELS[level + 1]
            frac = (v - lo) / (hi - lo)
            out[y, x] = RAMP[level + 1] if frac > BAYER_4[y % 4, x % 4] else RAMP[level]
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "red-monkey-red_png.zip"
    pixels = convert(load_image(src))
    write_basic_tape(screen_image_lines(pack_lores(pixels)), "red_monkey.wav")
    save_lores_preview(pixels, "red_monkey_preview.png")
