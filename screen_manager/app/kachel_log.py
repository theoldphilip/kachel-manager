"""Kachel Manager: a Kachel device's log, fetched through Home Assistant (no SSH on a device that is passed on).

The device offers the action `<domain>.<node>_log` (fire-app, plan of 2026-11-19), which answers: it takes `source`
(`echod` or `boot`), `offset` (bytes) and `max` (bytes, at most 64 KiB) and gives back `{"text", "next", "size"}`:
the piece of the log from `offset`, where the next piece starts (None at the end) and how long the whole log is. The
device blackens secrets (keys, passwords, tokens) itself. This module fetches in pieces: the end of a log for the
editor to show, and a whole log (at most MAX_DOWNLOAD, its end) for the user to download. Nothing goes to the
internet; the user sends the file on themselves, to a GitHub issue for instance.

Routes: GET /api/screens/{inbox}/kachel/log?source=echod (the end, or {"available": false} for a device without the
action) and GET /api/screens/{inbox}/kachel/log/download?source=echod|boot|all (a text file).
"""
import asyncio
import datetime
import re

from aiohttp import web

import kachel
from i18n import t

LOG_SUFFIX = '_log'
SOURCES = ('echod', 'boot')
CHUNK = 64 * 1024               # the most one answer carries
TAIL = CHUNK                    # what the editor shows: the end of a log
MAX_DOWNLOAD = 4 * 1024 * 1024  # the most of one log a download holds: its end
ANSWER_SECONDS = 15


def action_of(manager, screen):
    """(domain, service) of the screen's log action, or None when Home Assistant offers none for it."""
    node = (screen or {}).get('node')
    if not isinstance(node, str) or not node:
        return None
    domain = kachel.domain_of(node)
    service = node.replace('-', '_') + LOG_SUFFIX
    offered = (getattr(manager.ha, 'services', None) or {}).get(domain) or {}
    return (domain, service) if service in offered else None


def _piece(answer):
    """The answer of one call as (text, next, size), or None when it is not what the action promises."""
    if isinstance(answer, dict) and isinstance(answer.get('response'), dict):
        answer = answer['response']   # some Home Assistant versions wrap it once more
    if not isinstance(answer, dict):
        return None
    text, after, size = answer.get('text'), answer.get('next'), answer.get('size')
    if not isinstance(text, str) or not (after is None or (isinstance(after, int) and not isinstance(after, bool))):
        return None
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        return None
    return text, after, size


async def _call(manager, action, source, offset, most):
    domain, service = action
    try:
        answer = await asyncio.wait_for(manager.ha.call_answer(domain, service, {'source': source, 'offset': offset,
                                                                                 'max': most}), ANSWER_SECONDS)
    except (asyncio.TimeoutError, TimeoutError):
        raise ValueError(t('addon.errors.kachel_log.no_answer'))
    piece = _piece(answer)
    if piece is None:
        raise ValueError(t('addon.errors.kachel_log.no_answer'))
    return piece


async def read(manager, action, source, most):
    """The last `most` bytes of one log, as (text, size, cut): `cut` when the log is longer than what is given."""
    text, after, size = await _call(manager, action, source, 0, CHUNK)
    start = max(0, size - most)
    if after is None:
        return text, size, False
    parts, offset = ([text], after) if start == 0 else ([], start)
    taken = sum(len(part) for part in parts)
    while offset is not None and offset < size and taken < most + CHUNK:
        text, after, _ = await _call(manager, action, source, offset, CHUNK)
        if not text:
            break
        parts.append(text)
        taken += len(text)
        if after is not None and after <= offset:
            break   # a device that goes backwards would keep this loop going
        offset = after
    return ''.join(parts), size, start > 0


def _screen(manager, inbox):
    screen = manager.screen(inbox)
    if screen is None:
        raise ValueError(t('addon.errors.not_paired'))
    return screen


def _source(value, allow_all=False):
    if value in SOURCES or (allow_all and value == 'all'):
        return value
    raise ValueError(t('addon.errors.kachel_log.source'))


async def tail(manager, inbox, source):
    """The end of one log for the editor: {available, source, text, size, cut}."""
    source = _source(source)
    action = action_of(manager, _screen(manager, inbox))
    if action is None:
        return {'available': False, 'source': source}
    text, size, cut = await read(manager, action, source, TAIL)
    if cut:
        text = text.split('\n', 1)[1] if '\n' in text else text   # start on a whole line
    return {'available': True, 'source': source, 'text': text, 'size': size, 'cut': cut}


def file_name(screen, when):
    node = re.sub(r'[^a-z0-9_-]+', '-', str((screen or {}).get('node') or 'kachel').lower()).strip('-') or 'kachel'
    return f'kachel-log-{node}-{when:%Y-%m-%d-%H%M}.txt'


async def download(manager, inbox, source):
    """(file name, text) of one log or both, each under a header line."""
    source = _source(source, allow_all=True)
    screen = _screen(manager, inbox)
    action = action_of(manager, screen)
    if action is None:
        raise ValueError(t('addon.errors.kachel_log.none'))
    now = datetime.datetime.now()
    parts = [f"Kachel log of {screen.get('name') or screen.get('node')} ({screen.get('node')}), {now:%Y-%m-%d %H:%M}\n"]
    for one in (SOURCES if source == 'all' else (source,)):
        text, size, cut = await read(manager, action, one, MAX_DOWNLOAD)
        note = f', the last {len(text.encode("utf-8"))} of {size} bytes' if cut else ''
        parts.append(f'\n===== {one}{note} =====\n{text}')
    return file_name(screen, now), ''.join(parts)


def routes(app, manager):
    async def view(request):
        return web.json_response(await tail(manager, request.match_info['inbox'], request.query.get('source', 'echod')))

    async def save(request):
        name, text = await download(manager, request.match_info['inbox'], request.query.get('source', 'all'))
        return web.Response(text=text, content_type='text/plain', charset='utf-8',
                            headers={'Content-Disposition': f'attachment; filename="{name}"', 'Cache-Control': 'no-store'})

    app.router.add_get('/api/screens/{inbox}/kachel/log', view)
    app.router.add_get('/api/screens/{inbox}/kachel/log/download', save)
