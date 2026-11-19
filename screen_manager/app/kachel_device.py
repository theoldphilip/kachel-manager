"""Kachel Manager: a Kachel screen's own device, under Screen settings, Device (CLAUDE.md, Kachel-Zentrale plan step 2a).

What a Kachel tablet is besides its pages: its updates, its battery and its screen. echod has these as ESPHome entities of
the tablet (its update, the update channel, a button that looks for updates, the battery's sensors, the screen as a
light), and this module shows them in the editor and changes them through Home Assistant, the way Tessera's board
extras do (entity_settings.py): one value on the tablet, in Home Assistant and here, and every setting also usable in an
automation. Nothing here talks to the tablet itself.

The tablet's entities are found by the name echod gives them (`original_name`, which a rename in Home Assistant leaves
alone) on the screen's devices: the device of its inbox ("Kachel inbox" sits on a sub-device of the tablet), the tablet
the sub-device belongs to, and the tablet's other sub-devices. A row the tablet does not have is left out: the Fire, for one, has no switch that installs updates by itself.

Only what is in SECTIONS can be changed, and only in the way its kind takes: an update installed, a switch, a choice, a
button pressed, the screen on, off or at a brightness. Tested by tests/test_kachel_device.py.
"""
import asyncio
import json

from aiohttp import web

import core
import kachel
import entity_settings
from i18n import english, t

# (section, [(key, name, domain, writable)]): `name` is the entity's name in echod (its `original_name`, what it is
# found by; echod's object ids sometimes differ, such as screen_night_hours for "Night hours"), `key` the row's own id
# and the key of its words (addon.labels.kachel_device). echod 2.6.1 on the living room tablet has all of them.
SECTIONS = (
    ('updates', (('firmware', 'Firmware', 'update', True),
                 ('update_channel', 'Update channel', 'select', True),
                 ('check_for_updates', 'Check for updates', 'button', True),
                 ('update_status', 'Update status', 'sensor', False),
                 ('update_automatically', 'Install updates automatically', 'switch', True),
                 ('other_slot_version', 'Other slot version', 'sensor', False),
                 ('update_outcome', 'Update outcome', 'event', False))),
    ('battery', (('battery_level', 'Battery level', 'sensor', False),
                 ('charger_connected', 'Charger connected', 'binary_sensor', False),
                 ('battery_charging', 'Battery charging', 'binary_sensor', False),
                 ('battery_protection', 'Battery protection', 'switch', True),
                 ('battery_care', 'Battery care', 'binary_sensor', False),
                 ('full_performance', 'Full performance', 'switch', True))),
    ('screen', (('screen', 'Screen', 'light', True),
                ('screen_power', 'Screen power', 'switch', True),
                ('dim_after_idle', 'Dim after idle', 'select', True),
                ('night_mode', 'Night mode', 'switch', True),
                ('night_hours', 'Night hours', 'select', True),
                ('night_starts', 'Night starts', 'select', True),
                ('night_ends', 'Night ends', 'select', True),
                ('weekend_night_starts', 'Weekend night starts', 'select', True),
                ('weekend_night_ends', 'Weekend night ends', 'select', True),
                ('off_when_the_room_is_empty', 'Off when the room is empty', 'select', True),
                ('screen_off_when_nobody_is_near', 'Screen off when nobody is near', 'switch', True),
                ('text_size', 'Screen text size', 'select', True),
                ('clock_format', 'Clock format', 'select', True),
                ('theme_mode', 'Theme mode', 'select', True),
                ('language', 'Screen language', 'select', True),
                ('settings_lock', 'Settings lock', 'switch', True))),
    ('pages', (('start_page', 'Start page', 'select', True),
               ('back_to_start_page', 'Back to start page', 'select', True),
               ('turn_pages_with', 'Turn pages with', 'select', True))),
)
WANTED = {key: (domain, writable) for _, rows in SECTIONS for key, _, domain, writable in rows}
BY_NAME = {(name, domain): key for _, rows in SECTIONS for key, name, domain, _ in rows}
# A row left out while another one says the same and can change it: the battery care reading beside its switch.
SHOWN_BY = {'battery_care': 'battery_protection'}
# The words a reading has no translation of are shown as Home Assistant has them.
GONE = (None, '', 'unknown', 'unavailable')
# What echod's "Update outcome" event says about the last update (internal/feature/firmware).
OUTCOMES = ('installed', 'rolled_back', 'failed')


def devices_of(manager, screen):
    """The ids of a screen's devices: its inbox's device, the tablet that device belongs to (`via_device_id`), and the
    tablet's other sub-devices."""
    own = (screen or {}).get('device_id')
    if not own:
        return set()
    devices = [device for device in getattr(manager.ha, 'devices', None) or [] if isinstance(device, dict)]
    by_id = {device.get('id'): device for device in devices}
    top = (by_id.get(own) or {}).get('via_device_id') or own
    return {own, top} | {device.get('id') for device in devices if device.get('via_device_id') == top}


def entities(manager, screen):
    """{key: entity_id} of the rows this screen's tablet has (entity_settings.entities, on all of the tablet's devices)."""
    ids = devices_of(manager, screen)
    found = {}
    for item in getattr(manager.ha, 'registry', None) or []:
        if not (isinstance(item, dict) and isinstance(item.get('entity_id'), str) and item.get('device_id') in ids
                and kachel.ours(item) and item.get('original_name') and not item.get('disabled_by')):
            continue
        key = BY_NAME.get((item['original_name'], item['entity_id'].split('.')[0]))
        if key and key not in found:
            found[key] = item['entity_id']
    return found


def _label(key, language):
    base = f'addon.labels.kachel_device.{key}'
    return {'en': english(base), language: t(base)}


def _row(key, eid, states, language, online):
    """One row: {key, entity, kind, label, value, available, ...}; switches, choices and buttons as Extras draw them."""
    state = states.get(eid) or {}
    attrs = state.get('attributes') or {}
    domain = eid.split('.')[0]
    value = state.get('state')
    writable = WANTED[key][1]
    if domain in ('switch', 'select', 'button'):
        out = entity_settings.row({'key': key}, {key: eid}, states, _label(key, language), None, online)
        out['writable'] = writable
        if domain == 'select':
            # Every choice: a night's start and end come in quarters of an hour, 96 of them (Extras keep 48).
            out['options'] = [o for o in attrs.get('options') or [] if isinstance(o, str)][:200]
        return out
    available = bool(online) and value not in (None, 'unavailable')
    out = {'key': key, 'entity': eid, 'label': _label(key, language), 'available': available, 'writable': writable}
    if domain == 'update':
        progress = attrs.get('update_percentage')
        out.update(kind='update', value=attrs.get('installed_version'), latest=attrs.get('latest_version'),
                   pending=value == 'on', installing=bool(attrs.get('in_progress')),
                   progress=progress if isinstance(progress, (int, float)) else None,
                   title=core.short(attrs.get('title'), 64) if isinstance(attrs.get('title'), str) else None)
    elif domain == 'light':
        level = attrs.get('brightness')
        out.update(kind='light', value=value == 'on',
                   brightness=round(level / 255 * 100) if isinstance(level, (int, float)) else None)
    elif domain == 'event':
        # The last update's outcome (echod: installed, rolled_back, failed) and when it came; an event's state is its time.
        kind = attrs.get('event_type')
        out.update(kind='outcome', value=kind if kind in OUTCOMES else None,
                   at=value if isinstance(value, str) and value not in GONE else None)
    elif domain == 'binary_sensor':
        out.update(kind='flag', value=value == 'on' if value not in GONE else None)
    else:
        unit = attrs.get('unit_of_measurement')
        out.update(kind='reading', value=core.short(value, 64) if value not in GONE else None,
                   unit=unit if isinstance(unit, str) else '')
    return out


def device_for(manager, inbox, language='en'):
    """A Kachel screen's device as the editor draws it: [{section, rows}], the sections without a row left out."""
    screen = manager.screen(inbox)
    if screen is None:
        raise ValueError(t('addon.errors.not_paired'))
    found = entities(manager, screen)
    states = getattr(manager.ha, 'states', {}) or {}
    out = []
    for section, rows in SECTIONS:
        drawn = [_row(key, found[key], states, language, screen.get('online')) for key, _, _, _ in rows
                 if key in found and SHOWN_BY.get(key) not in found]
        if drawn:
            out.append({'section': section, 'rows': drawn})
    return out


async def change(manager, inbox, entity, value):
    """Change one row of this screen's tablet through Home Assistant: only an entity of its own devices that SECTIONS
    lists as writable, and only in the way its kind takes."""
    screen = manager.screen(inbox)
    if screen is None:
        raise ValueError(t('addon.errors.not_paired'))
    refused = t('addon.errors.kachel_device.request')
    found = {eid: key for key, eid in entities(manager, screen).items()}
    key = found.get(entity) if isinstance(entity, str) else None
    if key is None or not WANTED[key][1]:
        raise ValueError(refused)
    domain = entity.split('.')[0]
    if domain == 'update':
        if value != 'install':
            raise ValueError(refused)
        await manager.ha.call_service('update', 'install', {'entity_id': entity})
        return {'ok': True}
    if domain == 'light':
        if isinstance(value, bool):
            await manager.ha.call_service('light', 'turn_on' if value else 'turn_off', {'entity_id': entity})
        elif isinstance(value, (int, float)) and 1 <= value <= 100:
            await manager.ha.call_service('light', 'turn_on', {'entity_id': entity, 'brightness_pct': round(value)})
        else:
            raise ValueError(refused)
        return {'ok': True}
    return await entity_settings.change(manager, entity, value, refused)


async def stream(manager, request, language):
    """The rows again whenever Home Assistant reports a change of one of the tablet's entities (entity_settings.stream,
    for all of the tablet's devices). The first answer is the rows as they are; an idle connection gets keepalives."""
    inbox = request.match_info['inbox']
    device_for(manager, inbox, language)   # refuse an unknown screen before the stream starts
    response = web.StreamResponse(headers={'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store',
                                           'X-Accel-Buffering': 'no', 'X-Content-Type-Options': 'nosniff'})
    wake = asyncio.Event()
    changes = manager.ha.state_events
    manager.listeners.add(wake)
    wake.set()
    sent = None
    try:
        await response.prepare(request)
        while True:
            try:
                await asyncio.wait_for(wake.wait(), 15)
            except TimeoutError:
                await response.write(b': keepalive\n\n')
                continue
            wake.clear()
            screen = manager.screen(inbox)
            if screen is None:
                await response.write(b'data: []\n\n')
                break
            changes.listeners[wake] = frozenset(entities(manager, screen).values())
            body = json.dumps(device_for(manager, inbox, language), ensure_ascii=False)
            if body != sent:
                await response.write(f'data: {body}\n\n'.encode())
                sent = body
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        manager.listeners.discard(wake)
        changes.listeners.pop(wake, None)
    return response


def routes(app, manager, language_of):
    """GET /api/screens/{inbox}/kachel/device (and /events), POST to change one row. `language_of()` is the request's."""
    async def view(request):
        return web.json_response(device_for(manager, request.match_info['inbox'], language_of()))

    async def events(request):
        return await stream(manager, request, language_of())

    async def act(request):
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError(t('addon.errors.kachel_device.request'))
        return web.json_response(await change(manager, request.match_info['inbox'], data.get('entity'), data.get('value')))

    app.router.add_get('/api/screens/{inbox}/kachel/device', view)
    app.router.add_get('/api/screens/{inbox}/kachel/device/events', events)
    app.router.add_post('/api/screens/{inbox}/kachel/device', act)
