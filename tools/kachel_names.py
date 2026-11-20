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

Where Tessera's words mean this app ("Tessera adds it to Home Assistant"), the app says Kachel Manager: tools/
kachel_texts.json holds those texts in English and German, and puts "Kachel Manager" for "Tessera" in the other
languages (for a text of our own, all_languages, the English one). Its "keep" list is where Tessera stays: the ESP32 parts (off here), and what goes to Tessera's own website
(reports, feedback, the plugin catalogue). A new text with "Tessera" in neither is reported by --check, to decide.
The automations this app makes are "Kachel: <name>" with ids kachel_..., so neither app takes the other's.

    tools/kachel_names.py            writes our names and removes Tessera's workflows
    tools/kachel_names.py --check    only lists what still has Tessera's names or workflows; exit status 1 when anything does

tests/test_kachel.py runs --check.
"""
import argparse
import json
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

# Our automations: "Kachel: <name>", ids kachel_doorbell_... (Tessera's are "Tessera: " and tessera_...).
AUTOMATION_FILES = {'screen_manager/app/automations.py', 'web/src/model/automation.ts', 'tests/test_doorbell.py',
                    'web/tests/automation.spec.ts'}
AUTOMATION_RULES = (
    (re.compile(r'\bTessera\b'), 'Kachel'),
    (re.compile(r'\btessera(?=[:_])'), 'kachel'),
)
# Single places that show the app's name.
FILE_RULES = {
    'web/src/App.vue': ((re.compile(r'<b>Tessera</b>'), '<b>Kachel</b>'),),
    # Tests that quote a text of tools/kachel_texts.json.
    'tests/test_addon_translations.py': ((re.compile(r'Identify, from Tessera'), 'Identify, from the Kachel Manager'),),
    'web/tests/layoutbot.spec.ts': ((re.compile(r'Update the Tessera app:'), 'Update the Kachel Manager:'),),
    'web/tests/alerts-cheatsheet.spec.ts': ((re.compile(r'toBe\("All screens"\)'), 'toBe("All devices")'),),
}
# A device's entities under ESPHome or under the Kachel integration (kachel.PLATFORMS, kachel.ours): the registry checks
# of Tessera's sources that ask for platform 'esphome'. firmware.py's `platform: esphome` is YAML, not the registry.
PLATFORM_FILES = {'screen_manager/app/core.py', 'screen_manager/app/server.py', 'screen_manager/app/entity_settings.py',
                  'screen_manager/app/calls.py'}
PLATFORM_RULES = (
    (re.compile(r"""item\.get\((['"])platform\1\) == (['"])esphome\2"""), 'kachel.ours(item)'),
    (re.compile(r"""item\.get\((['"])platform\1\) != (['"])esphome\2"""), 'not kachel.ours(item)'),
)
TEXTS = ROOT / 'tools' / 'kachel_texts.json'
TRANSLATIONS = ROOT / 'screen_manager' / 'translations'


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
    rules = RULES + (WEB_RULES if relative.startswith('web/') else ())
    rules += AUTOMATION_RULES if relative in AUTOMATION_FILES else ()
    rules += FILE_RULES.get(relative, ())
    rules += PLATFORM_RULES if relative in PLATFORM_FILES else ()
    for pattern, replacement in rules:
        text = pattern.sub(replacement, text)
    return text


def strings(tree, path=''):
    """Every text of a translation file with its dotted key."""
    if isinstance(tree, dict):
        for key, value in tree.items():
            yield from strings(value, f'{path}.{key}' if path else key)
    elif isinstance(tree, str):
        yield path, tree


def ours(text, language, key, table):
    """What the key says in the Kachel Manager: the table's text in English and German, "Kachel Manager" for "Tessera"
    elsewhere."""
    if key in table.get(language, {}):
        return table[language][key]
    if language.startswith('en') and key in table['en']:
        return table['en'][key]
    if key in table.get('all_languages', ()):
        return table['en'][key]  # a text of our own, which the other languages have no words for yet
    return re.sub(r'Tessera(?: Screen Manager)?', 'Kachel Manager', text)


def texts(check):
    """Writes the table's texts into the translation files (only those strings, the file otherwise as it is). Returns
    the files that were not up to date, and the keys with "Tessera" that are neither ours nor kept."""
    table = json.loads(TEXTS.read_text(encoding='utf-8'))
    keep = tuple(table['keep'])
    stale, unknown = [], []
    for path in sorted(TRANSLATIONS.glob('*.json')):
        language = path.stem
        text = path.read_text(encoding='utf-8')
        new = text
        by_path = {}
        for key, value in strings(json.loads(text)):
            if key.startswith(keep):
                continue
            if key not in table['en']:
                if 'Tessera' in value:
                    unknown.append(f'{path.name} {key}')
                continue
            want = ours(value, language, key, table)
            if want == value:
                continue
            last = key.rsplit('.', 1)[-1]
            old = f'{json.dumps(last)}: {json.dumps(value, ensure_ascii=False)}'
            if new.count(old) != 1:
                by_path[key] = want   # the same words under another key too: set it by its path below
                continue
            new = new.replace(old, f'{json.dumps(last)}: {json.dumps(want, ensure_ascii=False)}')
        if by_path:
            # Kachel Manager: a text whose words stand under other keys as well ("Bildschirme" as a heading and a group)
            # is set by its dotted path, when the file is written as json.dumps writes it (indent 2), so nothing else moves.
            tree = json.loads(new)
            if json.dumps(tree, ensure_ascii=False, indent=2) + '\n' != new:
                unknown.extend(f'{path.name} {key} (not found once)' for key in by_path)
            else:
                for key, want in by_path.items():
                    node = tree
                    *parents, last = key.split('.')
                    for part in parents:
                        node = node[part]
                    node[last] = want
                new = json.dumps(tree, ensure_ascii=False, indent=2) + '\n'
        if new != text:
            stale.append(path.relative_to(ROOT).as_posix())
            if not check:
                path.write_text(new, encoding='utf-8')
    return stale, unknown

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
    words, unknown = texts(args.check)
    stale += words
    for name in unknown:
        print(f"says Tessera, neither ours nor kept (tools/kachel_texts.json): {name}")
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
    return 1 if (args.check and (stale or back)) or unknown else 0

if __name__ == '__main__':
    sys.exit(main())
