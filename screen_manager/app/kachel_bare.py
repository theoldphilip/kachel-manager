"""Kachel Manager: a Kachel device that has no "Kachel inbox" (yet) is shown all the same (Philip, 2026-11-25, Laufband test).

The app knows a screen by its inbox (core.NAME_TILE_SETTINGS), and only through the inbox do the hello, the functions
and the sources go. A Spezialanzeige such as the treadmill display came without one (its sub-device "Seiten", which
carries the inbox, is left out), so it was missing from the editor altogether. Philip: "wir brauchen mindestens die
Ansichten Gerät, Funktionen, Protokoll auch für special devices".

So every device under the Kachel integration (or under ESPHome with the sensor "Kachel board") that no screen of this
app covers is listed as a bare entry: id `kachel:<device id>`, a Spezialanzeige with no pages (`kachel_kind` special,
`kachel_bare`). Its Device and Log tabs work through Home Assistant alone (kachel_device, kachel_log); Functions and
Sources say they wait for the device's inbox. Manager.screen answers for such an id (`screen`), nothing else of the app
does: no pages go to it and the sync loop never sees it. Once the device reports its inbox it is a screen like any other
and its bare entry goes.
"""
import re

import kachel
import kachel_board
import kachel_device

PREFIX = 'kachel:'
BOARD_SENSOR = 'Kachel board'
GONE = ('unavailable', 'unknown', None)


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '_', str(text or '').lower()).strip('_')


def _kachel_devices(ha):
    """The top devices of Kachel devices: those with an entity of the Kachel integration, or an ESPHome device whose
    entities include the sensor "Kachel board" (a Kachel device not moved over yet; never a Tessera ESP32 screen)."""
    devices = {d.get('id'): d for d in getattr(ha, 'devices', None) or [] if isinstance(d, dict) and d.get('id')}
    found = set()
    for item in getattr(ha, 'registry', None) or ():
        if not isinstance(item, dict) or item.get('disabled_by') or item.get('device_id') not in devices:
            continue
        platform = item.get('platform')
        if platform == 'kachel' or (platform == 'esphome' and item.get('original_name') == BOARD_SENSOR
                                    and str(item.get('entity_id', '')).startswith('sensor.')):
            device = devices[item['device_id']]
            found.add(device.get('via_device_id') if device.get('via_device_id') in devices else device['id'])
    return [devices[i] for i in found]


def node_of(ha, device):
    """The node of a device's actions (`<domain>.<node>_screen_message`, `_log`): the one named like the device, else
    the one that ends with the last six digits of its MAC, as kachel.message_node does. None when there is none."""
    services = getattr(ha, 'services', None) or {}
    nodes = {}
    for domain in kachel.PLATFORMS:
        for name in services.get(domain) or {}:
            for suffix in (kachel.MESSAGE_SUFFIX, '_log'):
                if isinstance(name, str) and name.endswith(suffix):
                    nodes.setdefault(name[:-len(suffix)], domain)
    for name in (device.get('name_by_user'), device.get('name')):
        if _slug(name) in nodes:
            return _slug(name), nodes[_slug(name)]
    mac = kachel._mac_of(device, getattr(ha, 'devices', None) or [])
    hits = [node for node in nodes if mac and (node == mac[-6:] or node.endswith('_' + mac[-6:]))]
    return (hits[0], nodes[hits[0]]) if len(hits) == 1 else (None, None)


def _online(ha, device_ids):
    states = getattr(ha, 'states', {}) or {}
    mine = [item.get('entity_id') for item in getattr(ha, 'registry', None) or ()
            if isinstance(item, dict) and item.get('device_id') in device_ids]
    return any((states.get(entity) or {}).get('state') not in GONE for entity in mine)


def _area(ha, device):
    areas = {a.get('area_id'): a.get('name') for a in getattr(ha, 'areas', None) or () if isinstance(a, dict)}
    return areas.get(device.get('area_id'))


def bare(manager, screens=None):
    """The Kachel devices no screen of this app covers, as screen-like entries for Manager.screen and the editor."""
    ha = manager.ha
    covered = set()
    for screen in manager.screens() if screens is None else screens:
        covered |= kachel_device.devices_of(manager, screen)
    out = []
    for device in _kachel_devices(ha):
        if device['id'] in covered:
            continue
        name = device.get('name_by_user') or device.get('name') or device['id']
        node, domain = node_of(ha, device)
        if node:
            kachel.NODE_DOMAINS[node] = domain
        ids = {device['id']} | {d.get('id') for d in getattr(ha, 'devices', None) or [] if isinstance(d, dict) and d.get('via_device_id') == device['id']}
        entry = {'id': PREFIX + device['id'], 'device_id': device['id'], 'name': name, 'node': node,
                 'area': _area(ha, device), 'online': _online(ha, ids), 'kachel_bare': True, 'kachel_kind': 'special'}
        entry['kachel'] = kachel_board.info(manager, entry)
        out.append(entry)
    return sorted(out, key=lambda entry: str(entry['name']).lower())


def screen(manager, inbox):
    """The bare entry for an id `kachel:<device id>`, or None."""
    if not isinstance(inbox, str) or not inbox.startswith(PREFIX):
        return None
    return next((entry for entry in bare(manager) if entry['id'] == inbox), None)


def inventory_entries(manager, screens):
    """The bare entries as the editor's inventory lists screens: a Spezialanzeige without pages, nothing to send."""
    out = []
    for entry in bare(manager, screens):
        out.append({**entry, 'firmware': None, 'board': 'unknown', 'package': None,
                    # A grid, though no page goes to it: the editor opens a screen only with one (its document's
                    # layout needs a grid), and without it showed the empty page instead of the tabs (Laufband, 0.1.14).
                    'shape': {'width': 1600, 'height': 720, 'columns': 4, 'rows': 2}, 'source_grid': {'columns': 4, 'rows': 2},
                    'layout': {'title': entry['name'], 'tiles': []}, 'page_document': None,
                    'page_capability': 'offline', 'page_last_capability': None, 'page_delivery': 'waiting',
                    'delivery': '', 'in_sync': True, 'settings': None, 'screensaver': None, 'update': None,
                    'feedback': None, 'plugin_ask': None, 'tile_sizes': ['single', 'wide', 'full'], 'memory': None,
                    'bar_limit': 0, 'grids': None, 'hang': None})
    return out


def adopt(manager, screen):
    """A device that reports its inbox now takes over what was saved for it as a bare entry (its functions, its
    sources): kept under `kachel:<device id>` until then. True when something moved."""
    moved = False
    for device_id in kachel_device.devices_of(manager, screen):
        old = PREFIX + str(device_id)
        for keeper in (getattr(manager, 'kachel_functions', None), getattr(manager, 'kachel_sources', None)):
            if keeper is not None and old in getattr(keeper, 'chosen', {}) and screen['id'] not in keeper.chosen:
                keeper.renamed(old, screen['id'])
                moved = True
    return moved
