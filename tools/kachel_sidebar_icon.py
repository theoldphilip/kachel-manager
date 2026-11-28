"""Kachel Manager: drafts of the sidebar icon (24x24, one colour like every icon of the Home Assistant sidebar).

Home Assistant draws a panel's icon with <ha-icon>: `mdi:…` or a custom icon set that a frontend module registers as
window.customIcons[prefix] = {getIcon(name) -> {path, secondaryPath?, viewBox?}}. The path takes the text colour
(selected: the primary colour), secondaryPath the same at half opacity. So the mark is a path, not a picture.
`python3 tools/kachel_sidebar_icon.py <out folder>` writes each draft as SVG, its path data as JSON and a preview PNG."""
import json
import sys
from pathlib import Path


def rect(x, y, w, h, r, clockwise=True):
    """A rounded rectangle as path data; counter-clockwise cuts a hole out of a clockwise one (nonzero fill)."""
    if clockwise:
        return (f'M{x + r} {y}H{x + w - r}A{r} {r} 0 0 1 {x + w} {y + r}V{y + h - r}A{r} {r} 0 0 1 {x + w - r} {y + h}'
                f'H{x + r}A{r} {r} 0 0 1 {x} {y + h - r}V{y + r}A{r} {r} 0 0 1 {x + r} {y}Z')
    return (f'M{x + r} {y}A{r} {r} 0 0 0 {x} {y + r}V{y + h - r}A{r} {r} 0 0 0 {x + r} {y + h}H{x + w - r}'
            f'A{r} {r} 0 0 0 {x + w} {y + h - r}V{y + r}A{r} {r} 0 0 0 {x + w - r} {y}Z')


def ring(x, y, w, h, r, s):
    return rect(x, y, w, h, r) + rect(x + s, y + s, w - 2 * s, h - 2 * s, max(r - s, 0.5), clockwise=False)


def r(v):
    return round(v, 2)


# (name, German label, shapes); a shape is (layer, x, y, w, h, radius, stroke or None); layer main|secondary
A, B = 2, 13          # tile starts in a 2..22 square, tiles 9 wide, gap 2
S = 1.8
DRAFTS = [
    ('mark', 'Kachel-Zeichen (wie im Kopf des Kachel Managers)',
     [('main', A, A, 9, 9, 2.5, None), ('main', B, A, 9, 9, 2.5, S), ('main', A, B, 9, 9, 2.5, S), ('main', B, B, 9, 9, 2.5, S)]),
    ('duo', 'Zweiton: alle Kacheln voll, eine kräftig',
     [('main', A, A, 9, 9, 2.5, None), ('secondary', B, A, 9, 9, 2.5, None), ('secondary', A, B, 9, 9, 2.5, None),
      ('secondary', B, B, 9, 9, 2.5, None)]),
    ('tablet', 'Tablet: Rahmen mit vier Kacheln',
     [('main', 1, 1, 22, 22, 5, 1.8), ('main', 4.6, 4.6, 6.6, 6.6, 1.8, None), ('main', 12.8, 4.6, 6.6, 6.6, 1.8, 1.4),
      ('main', 4.6, 12.8, 6.6, 6.6, 1.8, 1.4), ('main', 12.8, 12.8, 6.6, 6.6, 1.8, 1.4)]),
]


def paths(shapes):
    out = {'main': '', 'secondary': ''}
    for layer, x, y, w, h, rad, stroke in shapes:
        out[layer] += ring(r(x), r(y), r(w), r(h), r(rad), stroke) if stroke else rect(r(x), r(y), r(w), r(h), r(rad))
    return out


def svg(p, colour='currentColor'):
    second = f'<path d="{p["secondary"]}" fill="{colour}" opacity="0.5"/>' if p['secondary'] else ''
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{p["main"]}" fill="{colour}"/>{second}</svg>\n'


def preview(out):
    """One PNG: each draft large, and at sidebar size on a light and a dark sidebar, normal and selected."""
    from PIL import Image, ImageDraw, ImageFont
    big, scale = 192, 8
    themes = [((250, 250, 250), (68, 68, 68), (3, 169, 244)), ((28, 28, 28), (225, 225, 225), (43, 179, 163))]
    image = Image.new('RGB', (len(DRAFTS) * 260 + 20, 470), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 15)
    except OSError:
        font = ImageFont.load_default()

    def icon(size, colour, background, shapes):
        k = 4  # draw 4x and shrink, for smooth edges at 24 px
        tile = Image.new('RGB', (size * k, size * k), background)
        d = ImageDraw.Draw(tile)
        f = size * k / 24
        for layer, x, y, w, h, rad, stroke in shapes:
            c = colour if layer == 'main' else tuple((a + b) // 2 for a, b in zip(colour, background))
            box = [x * f, y * f, (x + w) * f, (y + h) * f]
            if stroke:
                d.rounded_rectangle(box, rad * f, outline=c, width=max(1, round(stroke * f)))
            else:
                d.rounded_rectangle(box, rad * f, fill=c)
        return tile.resize((size, size), Image.LANCZOS)

    for i, (name, label, shapes) in enumerate(DRAFTS):
        x = 20 + i * 260
        draw.text((x, 10), f'{"ABC"[i]}  {name}', fill=(0, 0, 0), font=font)
        image.paste(icon(big, (43, 179, 163), (255, 255, 255), shapes), (x + 14, 36))
        for j, (bg, fg, sel) in enumerate(themes):
            y = 250 + j * 100
            draw.rectangle([x, y, x + 220, y + 90], fill=bg)
            for k, (colour, title) in enumerate(((fg, 'Kachel'), (sel, 'Kachel'))):
                yy = y + 10 + k * 40
                if k:
                    draw.rounded_rectangle([x + 4, yy - 6, x + 216, yy + 30], 8,
                                           fill=tuple((a * 7 + b * 3) // 10 for a, b in zip(bg, sel)))
                image.paste(icon(24, colour, image.getpixel((x + 6, yy)), shapes), (x + 14, yy))
                draw.text((x + 54, yy + 3), title, fill=colour if k else fg, font=font)
    image.save(out / 'seitenleiste-entwuerfe.png')


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    data = {}
    for name, label, shapes in DRAFTS:
        p = paths(shapes)
        data[name] = {'label': label, 'path': p['main'], **({'secondaryPath': p['secondary']} if p['secondary'] else {})}
        (out / f'kachel-{name}.svg').write_text(svg(p))
    (out / 'paths.json').write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    preview(out)


if __name__ == '__main__':
    main(Path(sys.argv[1] if len(sys.argv) > 1 else 'design/seitenleiste'))
