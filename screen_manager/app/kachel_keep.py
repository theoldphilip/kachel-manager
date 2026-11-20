"""Kachel Manager: a Kachel device's pages outlast its leaving Home Assistant (Fire test, 2026-11-20).

Remove (the editor's, or a device's factory reset asking to leave, kachel.wants_removal) forgets everything kept for a
screen, its pages too (Manager.forget_inbox). A Kachel device is often removed only to come back: from ESPHome to the
Kachel integration, or after a factory reset. Under its new entry Home Assistant gives it a new device and new entity
ids, so the add-on knew it as a new screen without tiles.

So before a Kachel device is forgotten its page record is kept here, by the device's MAC address (kachel._mac_of, the
same under ESPHome and under the Kachel integration). When a screen with that MAC comes back without pages of its own,
the sync loop gives it the kept record (`restore`), once, and the record leaves this file. A screen that has pages
already keeps them. At most KEEP devices are kept, the oldest go first.
"""
import json
import logging
import time
from copy import deepcopy
from pathlib import Path

import atomic
import kachel

LOG = logging.getLogger('screen_manager')

FILE = 'kachel_kept_pages.json'
KEEP = 20


def _path(manager):
    return Path(manager.path).parent / FILE


def _read(path):
    try:
        data = json.loads(path.read_text(encoding='utf8'))
    except (OSError, ValueError):
        return {}
    return {mac: entry for mac, entry in data.items()
            if isinstance(mac, str) and isinstance(entry, dict) and isinstance(entry.get('record'), dict)} \
        if isinstance(data, dict) else {}


def _write(path, kept):
    atomic.write_text(path, json.dumps(kept, ensure_ascii=False))


def mac_of(manager, screen):
    """The 12 hex digits of the MAC address Home Assistant knows for this screen's device, or None."""
    devices = getattr(manager.ha, 'devices', None) or []
    device = next((d for d in devices if isinstance(d, dict) and d.get('id') == (screen or {}).get('device_id')), None)
    return kachel._mac_of(device, devices)


def keep(manager, screen, inbox):
    """Keep the pages of a screen that is about to be forgotten, by its MAC. Nothing without a MAC or without pages."""
    mac = mac_of(manager, screen)
    record = manager.store.get(inbox)
    if not mac or not isinstance(record, dict):
        return False
    path = _path(manager)
    kept = _read(path)
    kept[mac] = {'record': deepcopy(record), 'name': (screen or {}).get('name'), 'node': (screen or {}).get('node'),
                 'kept': int(time.time())}
    if len(kept) > KEEP:
        for old in sorted(kept, key=lambda key: kept[key].get('kept', 0))[:len(kept) - KEEP]:
            kept.pop(old)
    try:
        _write(path, kept)
    except OSError as error:
        LOG.warning('The pages of %s could not be kept (%s)', (screen or {}).get('name') or inbox, error)
        return False
    LOG.info('Kept the pages of %s for when it comes back', (screen or {}).get('name') or inbox)
    return True


def restore(manager, screen):
    """Give a screen without pages the pages kept for its MAC, once. True when it got them."""
    inbox = (screen or {}).get('id')
    path = _path(manager)
    if not inbox or not path.exists():
        return False
    kept = _read(path)
    mac = mac_of(manager, screen) if kept else None
    if not mac or mac not in kept:
        return False
    store = manager.store
    with store._locked():
        store._reload()
        if inbox in store._records:
            return False
        try:
            record = deepcopy(kept[mac]['record'])
            store._validate_records({inbox: record})
            store._replace({**store._records, inbox: record})
        except Exception as error:  # noqa: BLE001 - a record the store refuses stays kept, the screen starts empty
            LOG.warning('The kept pages of %s could not be given back (%s)', screen.get('name') or inbox, error)
            return False
    entry = kept.pop(mac)
    try:
        _write(path, kept)
    except OSError:
        pass
    LOG.info('%s is back: it got the pages it had as %s', screen.get('name') or inbox, entry.get('name') or entry.get('node'))
    return True
