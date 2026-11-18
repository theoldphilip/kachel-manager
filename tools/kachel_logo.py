#!/usr/bin/env python3
"""Kachel Manager: draws the add-on's icon and logo for the Home Assistant store (screen_manager/icon.png, 128 x 128,
and screen_manager/logo.png, 500 x 200). They replace Tessera's mosaic, which is Tessera's own mark.

The mark is one page of a Kachel screen: a dark glazed tile with a wide tile on top and two below, the right one in
terracotta. The logo puts the name beside it, in Roboto from the add-on's own fonts.

    tools/kachel_logo.py    (needs Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'screen_manager' / 'app' / 'fonts' / 'Roboto-500.ttf'
GLAZE, CREAM, TERRACOTTA, INK = '#16404A', '#F3EEE4', '#D9693A', '#2B7A87'
SCALE = 4  # drawn four times larger, then shrunk: smooth edges


def mark(draw, x, y, size):
    s = size
    draw.rounded_rectangle((x, y, x + s, y + s), radius=s * 0.22, fill=GLAZE)
    pad, gap, r = s * 0.17, s * 0.07, s * 0.08
    inner = s - 2 * pad
    top = inner * 0.42
    x0, y0 = x + pad, y + pad
    draw.rounded_rectangle((x0, y0, x0 + inner, y0 + top), radius=r, fill=CREAM)
    half = (inner - gap) / 2
    y1 = y0 + top + gap
    draw.rounded_rectangle((x0, y1, x0 + half, y0 + inner), radius=r, fill=CREAM)
    draw.rounded_rectangle((x0 + half + gap, y1, x0 + inner, y0 + inner), radius=r, fill=TERRACOTTA)


def icon():
    size = 128 * SCALE
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    mark(ImageDraw.Draw(image), size * 0.03, size * 0.03, size * 0.94)
    return image.resize((128, 128), Image.LANCZOS)


def logo():
    w, h = 500 * SCALE, 200 * SCALE
    image = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    side = h * 0.72
    left = h * 0.14
    mark(draw, left, (h - side) / 2, side)
    text_x = left + side + h * 0.12
    big = ImageFont.truetype(str(FONT), int(h * 0.27))
    small = ImageFont.truetype(str(FONT), int(h * 0.15))
    draw.text((text_x, h * 0.50), 'Kachel', font=big, fill=INK, anchor='ls')
    draw.text((text_x, h * 0.73), 'Manager', font=small, fill=TERRACOTTA, anchor='ls')
    return image.resize((500, 200), Image.LANCZOS)


if __name__ == '__main__':
    icon().save(ROOT / 'screen_manager' / 'icon.png', optimize=True)
    logo().save(ROOT / 'screen_manager' / 'logo.png', optimize=True)
    print('written: screen_manager/icon.png, screen_manager/logo.png')
