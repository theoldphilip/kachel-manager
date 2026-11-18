#!/usr/bin/env python3
"""Kachel Manager: the names this fork gives what Tessera calls esp_screens_* and "Tile settings" (CLAUDE.md, "Merging
from Tessera").

The Kachel Manager may run beside Tessera in one Home Assistant. So an event an automation fires for it starts with
kachel_ (kachel_show_alert, not esp_screens_show_alert), the sensor it publishes for a screen's layout is
sensor.kachel_<node>, and a screen's inbox is "Kachel inbox" (text.<screen>_kachel_inbox) instead of "Tile settings".
Tessera's sources say the old names, and every merge from it brings new ones: this script writes ours over them, in the
add-on, its translations, the editor and the tests. The export file's key `esp_screens_layout` stays, so a layout
exported from Tessera can be imported here. The ESP32 firmware (components/, packages/) and the docs are Tessera's and
are left alone. Tessera's GitHub workflows (TESSERA_WORKFLOWS) build every ESP32 board's firmware, its Docker image and
its WASM preview, which pushes commits of its own: a merge from Tessera brings them back, and this script takes them out
again (the fork is checked by .github/workflows/kachel-check.yml alone).

    tools/kachel_names.py            writes our names and removes Tessera's workflows
    tools/kachel_names.py --check    only lists what still has Tessera's names or workflows; exit status 1 when anything does

tests/test_kachel.py runs --check.
"""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

# Where our names go: (folder, file patterns). The editor's build output (screen_manager/app/static) is made by
# `npm run build` from web/src, not by this script.
PLACES = (
    ('screen_manager/app', ('*.py',)),
    ('screen_manager/translations', ('*.json',)),
    ('web/src', ('*.ts', '*.vue')),
    ('web/tests', ('*.ts',)),
    ('tests', ('*.py', '*.json')),
)
# Tessera's workflows, which this fork does not run (Philip, 2026-11-18).
TESSERA_WORKFLOWS = ('ci.yml', 'docker.yml', 'preview.yml', 'build-cache.yml', 'ha-source.yml')

# Files that talk about the names themselves.
SKIP = {'tools/kachel_names.py', 'tests/test_kachel.py', 'screen_manager/app/kachel.py'}

RULES = (
    # Events, the layout sensors and the notification: esp_screens_x -> kachel_x, but not the export file's key.
    (re.compile(r'esp_screens_(?!layout\b)'), 'kachel_'),
    # The inbox entity.
    (re.compile(r'Tile settings'), 'Kachel inbox'),
    (re.compile(r'tile_settings'), 'kachel_inbox'),
)
# The editor's keys in the browser's storage and its channel between tabs ("esp-screens.route", "esp-screens-mode:...")
# are Tessera's too, and both editors run under the one address of Home Assistant: ours start with kachel-manager. The
# build's own modules (virtual:esp-screens-theme) and the Claude skill's download name stay.
WEB_RULES = (
    (re.compile(r'(?<=["\'`])esp-screens(?=[.\-:])(?!\.zip)'), 'kachel-manager'),
)

def files():
    for folder, patterns in PLACES:
        base = ROOT / folder
        for pattern in patterns:
            for path in sorted(base.rglob(pattern)):
                relative = path.relative_to(ROOT).as_posix()
                if relative in SKIP or '/node_modules/' in relative or '/static/' in relative:
                    continue
                yield path, relative

def renamed(text, relative=''):
    for pattern, replacement in RULES + (WEB_RULES if relative.startswith('web/') else ()):
        text = pattern.sub(replacement, text)
    return text

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--check', action='store_true', help="only list the files that still have Tessera's names")
    args = parser.parse_args(argv)
    stale = []
    for path, relative in files():
        text = path.read_text(encoding='utf-8')
        new = renamed(text, relative)
        if new == text:
            continue
        stale.append(relative)
        if not args.check:
            path.write_text(new, encoding='utf-8')
    verb = "still has Tessera's names" if args.check else 'renamed'
    for relative in stale:
        print(f'{verb}: {relative}')
    workflows = [ROOT / '.github' / 'workflows' / name for name in TESSERA_WORKFLOWS]
    back = [path for path in workflows if path.exists()]
    for path in back:
        relative = path.relative_to(ROOT).as_posix()
        if args.check:
            print(f"Tessera's workflow is back: {relative}")
        else:
            path.unlink()
            print(f'removed: {relative} (git rm it, or commit the removal)')
    return 1 if args.check and (stale or back) else 0

if __name__ == '__main__':
    sys.exit(main())
