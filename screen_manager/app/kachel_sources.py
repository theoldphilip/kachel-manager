"""Kachel Manager: the sources of a Spezialanzeige (a device with its own display for one task, such as the treadmill's),
agreed with fire-app and laufband-app on 2026-11-24 (SCHRITTE A1).

A Spezialanzeige shows no pages of tiles. Instead its task needs a few things of Home Assistant (the room's temperature,
the light, the power meter …). The device says which in its hello: `kind` ("special", or "tiles" for a tablet with
pages), the word `sources` among its features, and its `sources`, each {key, name {de, en}, domains, device_class,
required}. Here a person picks an entity for each (the editor's tab Sources), and the room's name, which is the area of
the device in Home Assistant unless one is typed.

The device has no Home Assistant token, so this app does the rest in the device's session, as it does for the presence
(kachel_functions):
- {"op":"sources","sources":{key: entity},"names":{key: name},"room": "..."} once after every hello and on every change;
  a source that is not set up is missing (its button is then hidden), `room` is always there ("" for none);
- {"op":"source_state","key","state","unit"} for each source set up, after the hello, on a change and at least every
  KEEPALIVE seconds (the device counts 90 s of silence as unknown);
- a button of the device fires the event `screen_source` {key, action} (esphome.screen_source, or kachel.screen_source
  read as its twin), and this app performs the action that fits the entity: only for a source set up on that device.

The choice is kept per inbox in FILE, together with what the device last offered, so the editor shows the tab while the
device is away, and by the device's MAC address: a device that comes back under a new inbox (a factory reset, a move from
ESPHome to the Kachel integration) gets its sources again, as its pages (kachel_keep). Routes: GET/PUT /api/screens/{inbox}/kachel/sources.
"""
import asyncio
import json
import logging
import re
import time
from copy import deepcopy
from pathlib import Path

from aiohttp import web

import atomic
import kachel_device
import kachel_keep
from i18n import t

LOG = logging.getLogger('screen_manager')

FILE = 'kachel_sources.json'
FEATURE = 'sources'
SPECIAL = 'special'
EVENT = 'esphome.screen_source'
KEEPALIVE = 60
MAX_SOURCES = 16
MAX_ROOM = 60
_KEY = re.compile(r'^[a-z0-9_]{1,32}$')
# What a button of the device does with the entity of its source, by the entity's domain.
ACTIONS = {'switch': 'toggle', 'light': 'toggle', 'fan': 'toggle', 'input_boolean': 'toggle', 'script': 'turn_on',
           'scene': 'turn_on', 'button': 'press', 'input_button': 'press'}
PRESSES = ('toggle', 'press')


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def hello(answer):
    """{kind, sources} of a device's hello: what it is and the sources it asks for (as many as MAX_SOURCES, each checked);
    an unreadable entry is left out, never the hello."""
    answer = answer if isinstance(answer, dict) else {}
    kind = SPECIAL if answer.get('kind') == SPECIAL else 'tiles'
    offered, seen = [], set()
    for item in answer.get('sources') if isinstance(answer.get('sources'), list) else []:
        if not isinstance(item, dict) or not isinstance(item.get('key'), str) or not _KEY.match(item['key']) or item['key'] in seen:
            continue
        domains = [d for d in item.get('domains') or [] if isinstance(d, str) and re.fullmatch(r'[a-z_]{1,32}', d)]
        if not domains:
            continue
        classes = [c for c in item.get('device_class') or [] if isinstance(c, str) and re.fullmatch(r'[a-z_]{1,32}', c)]
        names = item.get('name') if isinstance(item.get('name'), dict) else {}
        name = {lang: _text(text, 40) for lang, text in names.items() if lang in ('de', 'en') and _text(text, 40)}
        seen.add(item['key'])
        offered.append({'key': item['key'], 'name': name, 'domains': domains, 'device_class': classes,
                        'required': item.get('required') is True})
        if len(offered) == MAX_SOURCES:
            break
    return {'kind': kind, 'sources': offered}


def fits(source, entity, states):
    """Whether an entity may be a source's: one of its domains and, when it names device classes, one of those."""
    if not isinstance(entity, str) or '.' not in entity or len(entity) > 120:
        return False
    if entity.split('.', 1)[0] not in source['domains']:
        return False
    if source.get('device_class'):
        return ((states.get(entity) or {}).get('attributes') or {}).get('device_class') in source['device_class']
    return True


def clean(data, offered, states):
    """The choice as the device takes it, from what the editor sent: {sources, room}. ValueError for a key the device did
    not offer or an entity that does not fit it."""
    refused = t('addon.errors.kachel_sources.request')
    if not isinstance(data, dict):
        raise ValueError(refused)
    by_key = {source['key']: source for source in offered}
    chosen = {}
    sources = data.get('sources') or {}
    if not isinstance(sources, dict):
        raise ValueError(refused)
    for key, entity in sources.items():
        if entity in (None, ''):
            continue
        if key not in by_key or not fits(by_key[key], entity, states):
            raise ValueError(refused)
        chosen[key] = entity
    room = data.get('room')
    if room is not None and not isinstance(room, str):
        raise ValueError(refused)
    return {'sources': chosen, 'room': _text(room, MAX_ROOM)}


class Sources:
    """Each device's choice and what it last offered, kept in FILE, and what was last told to each device."""

    def __init__(self, folder):
        self.path = Path(folder) / FILE
        try:
            data = json.loads(self.path.read_text(encoding='utf8'))
        except (OSError, ValueError):
            data = {}
        data = data if isinstance(data, dict) else {}
        self.chosen = {k: v for k, v in (data.get('chosen') or {}).items() if isinstance(v, dict)}
        self.offered = {k: v for k, v in (data.get('offered') or {}).items() if isinstance(v, dict)}
        self.by_mac = {k: v for k, v in (data.get('by_mac') or {}).items() if isinstance(v, dict)}
        # inbox: (session, json of the sources message) and inbox: {key: (session, state, unit, when)}.
        self.told, self.values = {}, {}

    def save(self):
        atomic.write_text(self.path, json.dumps({'chosen': self.chosen, 'offered': self.offered, 'by_mac': self.by_mac}, ensure_ascii=False))

    def get(self, inbox):
        return deepcopy(self.chosen.get(inbox) or {'sources': {}, 'room': None})

    def put(self, inbox, choice, mac=None):
        self.chosen[inbox] = choice
        if mac:
            self.by_mac[mac] = choice
        self.save()
        self.told.pop(inbox, None)
        self.values.pop(inbox, None)

    def heard(self, inbox, said):
        """What a device's hello offered: kept when it is new."""
        if said and self.offered.get(inbox) != said:
            self.offered[inbox] = said
            self.save()

    def restore(self, inbox, mac):
        """A device back under a new inbox gets the sources kept for its MAC, when it has none of its own."""
        if mac and inbox not in self.chosen and mac in self.by_mac:
            self.chosen[inbox] = deepcopy(self.by_mac[mac])
            self.save()
            LOG.info('%s is back: it got the sources it had', inbox)
            return True
        return False

    def kind(self, inbox):
        return (self.offered.get(inbox) or {}).get('kind') or 'tiles'

    def renamed(self, old, new):
        changed = False
        for store in (self.chosen, self.offered):
            if old in store and new not in store:
                store[new] = store.pop(old)
                changed = True
        if changed:
            self.save()

    def watched(self):
        """The entities of every source set up: the sync loop wakes when one changes."""
        return {e for value in self.chosen.values() for e in (value.get('sources') or {}).values()}


def area_name(manager, screen):
    """The name of the area the device is in, in Home Assistant: its tablet's area first, then its inbox's own; None."""
    devices = {d.get('id'): d for d in getattr(manager.ha, 'devices', None) or [] if isinstance(d, dict)}
    own = devices.get((screen or {}).get('device_id')) or {}
    top = devices.get(own.get('via_device_id')) or {}
    areas = {a.get('area_id'): a.get('name') for a in getattr(manager.ha, 'areas', None) or [] if isinstance(a, dict)}
    for device in (top, own):
        name = areas.get(device.get('area_id'))
        if isinstance(name, str) and name:
            return name
    return None


def message(manager, inbox, screen):
    """The sources message as it goes to the device: only keys it offers, the names as Home Assistant shows them."""
    keeper = manager.kachel_sources
    choice = keeper.get(inbox)
    offered = {s['key'] for s in (keeper.offered.get(inbox) or {}).get('sources') or []}
    states = getattr(manager.ha, 'states', {}) or {}
    sources = {k: e for k, e in sorted(choice['sources'].items()) if k in offered}
    names = {k: str(((states.get(e) or {}).get('attributes') or {}).get('friendly_name') or e) for k, e in sources.items()}
    room = choice.get('room') or area_name(manager, screen) or ''
    return {'op': 'sources', 'sources': sources, 'names': names, 'room': room}


def value_of(entity, states):
    """(state, unit) of a source's entity as the device shows it: 'unavailable' for one Home Assistant does not have."""
    state = states.get(entity) or {}
    unit = (state.get('attributes') or {}).get('unit_of_measurement')
    return str(state.get('state') or 'unavailable'), unit if isinstance(unit, str) else ''


async def sync(manager, inbox):
    """Hand a device its sources and their values in its session: True when something went out."""
    keeper = getattr(manager, 'kachel_sources', None)
    sender = manager.page_senders.get(inbox)
    if keeper is None or sender is None:
        return False
    keeper.heard(inbox, getattr(sender, 'kachel', None))
    keeper.restore(inbox, kachel_keep.mac_of(manager, manager.screen(inbox)))
    if not sender.session or not sender.confirmed or FEATURE not in (sender.features or ()):
        return False
    outgoing = message(manager, inbox, manager.screen(inbox))
    body = json.dumps(outgoing, sort_keys=True, ensure_ascii=False)
    went = False
    if keeper.told.get(inbox) != (sender.session, body):
        if await sender.auxiliary(outgoing, session=sender.session, revision=sender.confirmed):
            keeper.told[inbox] = (sender.session, body)
            LOG.info('%s: sources set up: %s', sender.name or inbox, ', '.join(outgoing['sources']) or 'none')
            went = True
    states = getattr(manager.ha, 'states', {}) or {}
    last = keeper.values.setdefault(inbox, {})
    for key, entity in outgoing['sources'].items():
        state, unit = value_of(entity, states)
        before = last.get(key)
        if before and before[:3] == (sender.session, state, unit) and time.monotonic() - before[3] <= KEEPALIVE:
            continue
        if await sender.auxiliary({'op': 'source_state', 'key': key, 'state': state, 'unit': unit},
                                  session=sender.session, revision=sender.confirmed):
            last[key] = (sender.session, state, unit, time.monotonic())
            went = True
    return went


def screen_of_device(manager, device_id):
    """The inbox of the screen a device belongs to (its inbox's device, its tablet or another sub-device), or None."""
    if not device_id:
        return None
    for screen in manager.screens():
        if device_id in kachel_device.devices_of(manager, screen):
            return screen.get('id')
    return None


async def press(manager, body):
    """A button of a device: perform the action of the entity set up for its source. True when one was performed."""
    if not isinstance(body, dict) or body.get('action') not in PRESSES:
        return False
    inbox = screen_of_device(manager, body.get('device_id'))
    if inbox is None:
        LOG.info('A source button came from a device this app does not know (%s)', body.get('device_id'))
        return False
    entity = manager.kachel_sources.get(inbox)['sources'].get(body.get('key'))
    if not entity:
        LOG.info('%s: its button %s has no source set up', inbox, body.get('key'))
        return False
    domain = entity.split('.', 1)[0]
    service = ACTIONS.get(domain)
    if service is None:
        LOG.warning('%s: no action fits %s for its button %s', inbox, entity, body.get('key'))
        return False
    await manager.ha.call_service(domain, service, {'entity_id': entity})
    LOG.info('%s: button %s → %s.%s %s', inbox, body.get('key'), domain, service, entity)
    return True


async def loop(manager):
    """The devices' source buttons (HA client's kachel_source_events): one at a time."""
    queue = manager.ha.kachel_source_events
    while True:
        body = await queue.get()
        try:
            await press(manager, body)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - one failed button must not stop the next
            LOG.warning('A source button could not be performed (%s)', error)


def choices(offered, states, limit=300):
    """{key: [[entity, name], ...]} the entities that fit each source, by name: what the editor offers."""
    out = {}
    for source in offered:
        found = [(e, str((s.get('attributes') or {}).get('friendly_name') or e)) for e, s in states.items()
                 if isinstance(s, dict) and fits(source, e, states)]
        out[source['key']] = [list(pair) for pair in sorted(found, key=lambda pair: pair[1].lower())[:limit]]
    return out


def view(manager, inbox):
    screen = manager.screen(inbox)
    if screen is None:
        raise ValueError(t('addon.errors.not_paired'))
    keeper = manager.kachel_sources
    sender = manager.page_senders.get(inbox)
    offered = keeper.offered.get(inbox) or {'kind': 'tiles', 'sources': []}
    told = keeper.told.get(inbox)
    current = json.dumps(message(manager, inbox, screen), sort_keys=True, ensure_ascii=False)
    return {'kind': offered.get('kind'), 'offered': offered.get('sources') or [], **keeper.get(inbox),
            'area': area_name(manager, screen),
            'choices': choices(offered.get('sources') or [], getattr(manager.ha, 'states', {}) or {}),
            'supported': FEATURE in (getattr(sender, 'features', None) or ()),
            'delivered': bool(told and sender and told[0] == sender.session and told[1] == current)}


def routes(app, manager):
    async def get(request):
        return web.json_response(view(manager, request.match_info['inbox']))

    async def put(request):
        inbox = request.match_info['inbox']
        if manager.screen(inbox) is None:
            raise ValueError(t('addon.errors.not_paired'))
        offered = (manager.kachel_sources.offered.get(inbox) or {}).get('sources') or []
        manager.kachel_sources.put(inbox, clean(await request.json(), offered, getattr(manager.ha, 'states', {}) or {}),
                                   kachel_keep.mac_of(manager, manager.screen(inbox)))
        manager.ha.changed.set()
        return web.json_response(view(manager, inbox))

    app.router.add_get('/api/screens/{inbox}/kachel/sources', get)
    app.router.add_put('/api/screens/{inbox}/kachel/sources', put)
