#!/usr/bin/env python3
"""
Lumon logo bouncing around the lo-res screen, DVD-screensaver style.
White in the source = sprite pixel, black = transparent. The color
changes on every wall bounce.

Usage: python3 05_lumon_bounce.py [image.png | image.zip]
Output: lumon_bounce.wav
"""

import sys
import numpy as np
from PIL import Image, ImageEnhance
from apple2tape import load_image, data_lines, write_basic_tape

SPRITE_W, SPRITE_H = 24, 12
THRESHOLD = 100
BOUNCE_COLORS = [15, 13, 9, 1, 3, 6, 14, 12]  # white, yellow, orange, magenta,
                                              # purple, med blue, aqua, green


def extract_sprite(img):
    img = img.convert("L")
    px = np.array(img)
    rows = np.where(np.any(px > 30, axis=1))[0]
    cols = np.where(np.any(px > 30, axis=0))[0]
    crop = img.crop((max(0, cols[0] - 10), max(0, rows[0] - 10),
                     min(img.width, cols[-1] + 10), min(img.height, rows[-1] + 10)))
    crop = ImageEnhance.Contrast(crop).enhance(3.0)
    bw = np.array(crop.resize((SPRITE_W, SPRITE_H), Image.LANCZOS)) > THRESHOLD
    for y in range(SPRITE_H):
        print("  " + "".join("██" if bw[y, x] else "  " for x in range(SPRITE_W)))
    return [(x, y) for y in range(SPRITE_H) for x in range(SPRITE_W) if bw[y, x]]


def build_lines(sprite):
    n = len(sprite) - 1
    nc = len(BOUNCE_COLORS) - 1
    max_x, max_y = 40 - SPRITE_W, 48 - SPRITE_H
    lines = [
        (5, "GR: POKE -16302,0"),
        (10, f"N={n}: DIM A({n}),B({n})"),
        (15, "FOR I=0 TO N: READ A(I),B(I): NEXT"),
        (20, f"NC={nc}: DIM CL({nc})"),
        (25, "FOR I=0 TO NC: READ CL(I): NEXT"),
        (30, "X=3: Y=5: DX=1: DY=1: CI=0"),
        (100, "COLOR=0: FOR I=0 TO N: PLOT A(I)+X,B(I)+Y: NEXT"),
        (110, "NX=X+DX: NY=Y+DY: BN=0"),
        (120, f"IF NX<0 OR NX>{max_x} THEN DX=-DX: NX=X+DX: BN=1"),
        (130, f"IF NY<0 OR NY>{max_y} THEN DY=-DY: NY=Y+DY: BN=1"),
        (140, "X=NX: Y=NY"),
        (150, "IF BN THEN CI=CI+1: IF CI>NC THEN CI=0"),
        (160, "COLOR=CL(CI): FOR I=0 TO N: PLOT A(I)+X,B(I)+Y: NEXT"),
        (170, "GOTO 100"),
    ]
    coords = [v for xy in sprite for v in xy]
    new, ln = data_lines(coords, 1000)
    lines += new
    new, _ = data_lines(BOUNCE_COLORS, ln)
    lines += new
    return lines


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else \
        "lumon-logo-water-drop-or-candle-flame-v0-kpw0i3ktfx7e1_png.zip"
    sprite = extract_sprite(load_image(src))
    print(f"Sprite: {SPRITE_W}x{SPRITE_H}, {len(sprite)} pixels")
    write_basic_tape(build_lines(sprite), "lumon_bounce.wav")
