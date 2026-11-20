"""Kachel Manager: what a Kachel device is, as the editor names it: its Kachel version and its device (Fire HD 8 Plus),
in place of Tessera's firmware number and ESP32 board, which mean nothing on a tablet (Philip, 2026-11-20).

echod reports both as sensors of the tablet, found by their names as everywhere (kachel_device.py): "Kachel version"
(else the installed version of its update entity "Firmware") and "Kachel board" (fire8, a12s, gta3xl). The board's
word becomes the device's name through DEVICES; a board this table does not know keeps its word.
"""
import kachel
import kachel_device

# The Kachel boards and the devices they are (echod's layout.Board).
DEVICES = {
    'fire8': 'Amazon Fire HD 8 Plus',
    'a12s': 'Samsung Galaxy A12',
    'gta3xl': 'Samsung Galaxy Tab A 10.1',
}
GONE = (None, '', 'unknown', 'unavailable')


def info(manager, screen):
    """{version, board, device} of a screen's tablet, each None when it does not say; None for no Kachel device."""
    ids = kachel_device.devices_of(manager, screen)
    if not ids:
        return None
    states = getattr(manager.ha, 'states', {}) or {}
    found = {}
    for item in getattr(manager.ha, 'registry', None) or []:
        if not (isinstance(item, dict) and item.get('device_id') in ids and kachel.ours(item)):
            continue
        entity = item.get('entity_id') or ''
        state = states.get(entity) or {}
        name, domain = item.get('original_name'), entity.split('.', 1)[0]
        if name == 'Kachel version' and domain == 'sensor' and state.get('state') not in GONE:
            found['version'] = state['state']
        elif name == 'Kachel board' and domain == 'sensor' and state.get('state') not in GONE:
            found['board'] = state['state']
        elif name == 'Firmware' and domain == 'update':
            installed = (state.get('attributes') or {}).get('installed_version')
            if isinstance(installed, str) and installed:
                found.setdefault('installed', installed)
    version = found.get('version') or found.get('installed')
    board = found.get('board')
    if not version and not board:
        return None
    return {'version': version, 'board': board, 'device': DEVICES.get(board, board) if board else None}
