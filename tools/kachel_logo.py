#!/usr/bin/env python3
"""Kachel Manager: the add-on's icon and logo for the Home Assistant store (screen_manager/icon.png, 128 x 128, and
screen_manager/logo.png, 500 x 200). They replace Tessera's mosaic, which is Tessera's own mark.

Both are cut from the picture the Kachel tablets show while they start (echod, echod/internal/feature/display/assets/
kachel.png, 1920 x 1200): the four tiles with the teal one, and "Kachel" beside them. So the store shows the same mark
as the tablet. The icon is the four tiles alone; on the logo "Manager" takes the place of "für Tessera", in the same
teal. echod belongs to wohnzimmer-app: read it from a throwaway clone (CLAUDE.md, "Grenzen").

    tools/kachel_logo.py <echod clone>    (needs Pillow and the Noto Sans font)
"""
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SPLASH = 'echod/internal/feature/display/assets/kachel.png'
FONT = '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'
TEAL = (43, 179, 163)

# Where things are on the splash, in its own pixels.
TILES = (483, 455, 733, 706)        # the four tiles
SUBTITLE = (830, 630, 1175, 715)    # "für Tessera"
SUBTITLE_AT = (837, 693)            # its left end and baseline


def rounded(image, radius):
    mask = Image.new('L', image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius=radius, fill=255)
    image = image.convert('RGBA')
    image.putalpha(mask)
    return image


def main(clone):
    splash = Image.open(Path(clone) / SPLASH).convert('RGB')
    background = splash.getpixel((10, 10))

    x0, y0, x1, y1 = TILES
    pad = 55
    icon = splash.crop((x0 - pad, y0 - pad, x1 + pad, y0 - pad + (x1 - x0) + 2 * pad))
    icon = icon.resize((512, 512), Image.LANCZOS)
    rounded(icon, 112).resize((128, 128), Image.LANCZOS).save(ROOT / 'screen_manager' / 'icon.png', optimize=True)

    words = splash.copy()
    draw = ImageDraw.Draw(words)
    draw.rectangle(SUBTITLE, fill=background)
    draw.text(SUBTITLE_AT, 'Manager', font=ImageFont.truetype(FONT, 70), fill=TEAL, anchor='ls')
    left, right = x0 - 60, 1508
    height = round((right - left) / 2.5)
    middle = (y0 + y1) // 2
    logo = words.crop((left, middle - height // 2, right, middle - height // 2 + height))
    logo = logo.resize((1000, 400), Image.LANCZOS)
    rounded(logo, 48).resize((500, 200), Image.LANCZOS).save(ROOT / 'screen_manager' / 'logo.png', optimize=True)
    print('written: screen_manager/icon.png, screen_manager/logo.png')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__.split('\n\n')[-1].strip())
    main(sys.argv[1])
