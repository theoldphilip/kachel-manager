"""Kachel Manager: what is set up for a Kachel device, its functions (fire-app, protocol of 2026-11-19, `functions` v2).

The tablet shows a setting only when its function is set up here (Philip's rule from the walk through the settings):
the presence sensor that turns the screen off, the ways to turn pages, the voice assistant, the kinds of notices. This
module keeps each screen's choice (FILE, by inbox), checks it (`clean`), and the sync loop hands it to the screen in its
session (`sync`): once after every hello, then whenever it changes. What is missing is off; an empty message turns
everything off. Only a screen whose hello lists the word `functions` gets it.

Presence: the tablet does not ask Home Assistant. While presence is set up, the screen hears {"op":"presence","present"}
after its hello, at every change of the sensors, and at least every KEEPALIVE seconds (it counts 90 s of silence as
"unknown" and keeps the screen on).

Routes: GET/PUT /api/screens/{inbox}/kachel/functions.
"""
import json
import logging
import time
from copy import deepcopy
from pathlib import Path

from aiohttp import web

import atomic
from i18n import t

LOG = logging.getLogger('screen_manager')

FILE = 'kachel_functions.json'
FEATURE = 'functions'
KEEPALIVE = 60
PAGE_WAYS = ('swipe', 'buttons', 'remote')
ASSIST_WAYS = ('tap_clock', 'wake_word')
# A notice's source: the domains its entity may be of.
NOTICES = {'doorbell': ('event', 'binary_sensor'), 'post': ('sensor', 'binary_sensor', 'calendar'),
           'parcels': ('sensor', 'calendar'), 'waste': ('calendar', 'sensor'), 'weather': ('weather',)}
MAX_PRESENCE = 4


def _entity(value, domains):
    return isinstance(value, str) and len(value) <= 120 and '.' in value and value.split('.', 1)[0] in domains


def clean(data):
    """The functions as the tablet takes them, from what the editor sent; ValueError for what is not one of them."""
    refused = t('addon.errors.kachel_functions.request')
    if not isinstance(data, dict):
        raise ValueError(refused)
    out = {}
    presence = data.get('presence')
    if presence:
        entities = presence.get('entities') if isinstance(presence, dict) else None
        if not isinstance(entities, list) or not entities or len(entities) > MAX_PRESENCE \
                or not all(_entity(e, ('binary_sensor',)) for e in entities):
            raise ValueError(refused)
        out['presence'] = {'entities': list(dict.fromkeys(entities))}
    turn = data.get('page_turn')
    if turn:
        ways = turn.get('ways') if isinstance(turn, dict) else None
        if not isinstance(ways, list) or not ways or any(way not in PAGE_WAYS for way in ways):
            raise ValueError(refused)
        out['page_turn'] = {'ways': [way for way in PAGE_WAYS if way in ways]}
    assist = data.get('assist')
    if assist:
        ways = assist.get('ways') if isinstance(assist, dict) else None
        if not isinstance(ways, list) or any(way not in ASSIST_WAYS for way in ways):
            raise ValueError(refused)
        out['assist'] = {'ways': [way for way in ASSIST_WAYS if way in ways]}
        pipeline = assist.get('pipeline')
        if isinstance(pipeline, str) and pipeline.strip():
            out['assist']['pipeline'] = pipeline.strip()[:80]
    notices = data.get('notices')
    if notices:
        if not isinstance(notices, dict):
            raise ValueError(refused)
        kept = {}
        for kind, value in notices.items():
            if kind == 'missed':
                if value is True:
                    kept['missed'] = True
            elif kind in NOTICES:
                if value in (None, ''):
                    continue
                if not _entity(value, NOTICES[kind]):
                    raise ValueError(refused)
                kept[kind] = value
            else:
                raise ValueError(refused)
        if kept:
            out['notices'] = kept
    return out


class Functions:
    """Each screen's functions, kept in FILE beside the add-on's other data, and what was last told to each screen."""

    def __init__(self, folder):
        self.path = Path(folder) / FILE
        try:
            data = json.loads(self.path.read_text(encoding='utf8'))
        except (OSError, ValueError):
            data = {}
        self.chosen = {inbox: value for inbox, value in data.items() if isinstance(value, dict)} if isinstance(data, dict) else {}
        # inbox: (session, json of the functions) the screen confirmed, and (session, present, when) of the presence.
        self.told, self.presence = {}, {}

    def get(self, inbox):
        return deepcopy(self.chosen.get(inbox, {}))

    def put(self, inbox, functions):
        self.chosen[inbox] = functions
        atomic.write_text(self.path, json.dumps(self.chosen, ensure_ascii=False))
        self.told.pop(inbox, None)
        self.presence.pop(inbox, None)

    def renamed(self, old, new):
        if old in self.chosen and new not in self.chosen:
            self.chosen[new] = self.chosen.pop(old)
            atomic.write_text(self.path, json.dumps(self.chosen, ensure_ascii=False))

    def watched(self):
        """The presence sensors of every screen: the sync loop wakes when one changes."""
        return {e for value in self.chosen.values() for e in (value.get('presence') or {}).get('entities', ())}


def present(functions, states):
    """Whether someone is near: any of the screen's presence sensors on; None while none of them says."""
    seen = [(states.get(e) or {}).get('state') for e in (functions.get('presence') or {}).get('entities', ())]
    known = [state for state in seen if state in ('on', 'off')]
    return any(state == 'on' for state in known) if known else None


async def sync(manager, inbox):
    """Hand a screen its functions and its presence in its session: True when something went out."""
    sender = manager.page_senders.get(inbox)
    keeper = getattr(manager, 'kachel_functions', None)
    if keeper is None or sender is None or not sender.session or not sender.confirmed or FEATURE not in (sender.features or ()):
        return False
    functions = keeper.get(inbox)
    body = json.dumps(functions, sort_keys=True)
    went = False
    if keeper.told.get(inbox) != (sender.session, body):
        if await sender.auxiliary({'op': 'functions', **functions}, session=sender.session, revision=sender.confirmed):
            keeper.told[inbox] = (sender.session, body)
            LOG.info('%s: functions set up: %s', sender.name or inbox, ', '.join(sorted(functions)) or 'none')
            went = True
    if functions.get('presence'):
        now = present(functions, getattr(manager.ha, 'states', {}) or {})
        last = keeper.presence.get(inbox)
        if now is not None and (last is None or last[0] != sender.session or last[1] != now or time.monotonic() - last[2] > KEEPALIVE):
            if await sender.auxiliary({'op': 'presence', 'present': now}, session=sender.session, revision=sender.confirmed):
                keeper.presence[inbox] = (sender.session, now, time.monotonic())
                went = True
    return went


def view(manager, inbox):
    screen = manager.screen(inbox)
    if screen is None:
        raise ValueError(t('addon.errors.not_paired'))
    sender = manager.page_senders.get(inbox)
    can = FEATURE in (getattr(sender, 'features', None) or ())
    told = manager.kachel_functions.told.get(inbox)
    current = json.dumps(manager.kachel_functions.get(inbox), sort_keys=True)
    return {'functions': manager.kachel_functions.get(inbox), 'supported': can,
            'delivered': bool(told and told[1] == current and sender and told[0] == sender.session)}


def routes(app, manager):
    async def get(request):
        return web.json_response(view(manager, request.match_info['inbox']))

    async def put(request):
        inbox = request.match_info['inbox']
        if manager.screen(inbox) is None:
            raise ValueError(t('addon.errors.not_paired'))
        manager.kachel_functions.put(inbox, clean(await request.json()))
        manager.ha.changed.set()
        return web.json_response(view(manager, inbox))

    app.router.add_get('/api/screens/{inbox}/kachel/functions', get)
    app.router.add_put('/api/screens/{inbox}/kachel/functions', put)
