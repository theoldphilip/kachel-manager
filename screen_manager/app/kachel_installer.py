"""Kachel Manager: the first install of Kachel OS from the browser (Spur K, plan of kachel-installer-tool, Philip 2026-11-27).

The device hangs by USB at the person's PC, the editor talks to it over WebUSB (Odin for Samsung, through
@lineageos-infra/libmjolnir), and this module gives it what it may use: the device's install profile and its files,
checked first. Format v1 (~/kachel-installer/STAND.md, "Formate v1 – FESTGELEGT"):

- `install-profile.json` with `install-profile.json.sig` (Base64 of the raw 64-byte Ed25519 signature over the file, byte
  for byte, then a newline), signed with the board's release key. The public keys are KEYS, here in the code, never from
  a download.
- The profile lies in the Home Assistant mirror (`/homeassistant/www/kachel/` in this app = HA `/config/www/kachel/`), in
  the channel folders like the manifest: CHANNELS. A file's `url` is relative to the profile's folder (an absolute URL is
  for public releases, later, the Fire).
- A double lock: what may be written is ALLOWED per board and never what NEVER names (any case, any part of a name), both
  here in the code; the profile can only make it smaller. No PIT is ever written and no lock command sent (the editor has
  neither in its code).

This step (Spur K, first stage) is the read-only trial: the editor reads the device's PIT and compares it with `match`.
The files are checked and served already, so the next stage needs no other format; nothing here writes to a device.

Routes: GET /api/kachel/installer (both channels: the profile as checked, or what is wrong), GET
/api/kachel/installer/{channel}/file/{name} (a file of the profile, after its size and sha256 matched).
"""
import base64
import hashlib
import json
import logging
import os
import re
from pathlib import Path

from aiohttp import web

import core

LOG = logging.getLogger('screen_manager')

FORMAT = 'kachel-install-profile'
FORMAT_VERSION = 1
PROFILE = 'install-profile.json'
# The channel folders in the mirror, as the manifest's (STAND.md B).
CHANNELS = {'stable': ('latest', 'download'), 'dev': ('download', 'dev')}
# The release keys per board: Base64 of the 32 raw bytes of the Ed25519 public key (STAND.md A.3).
KEYS = {
    'gta3xl': 'cRXQxPrwY4uSwH8FcEKUz2ZKFfXGqmdNxVyeB5XbVpY=',   # Wohnzimmer release key (wohnzimmer-firmware, 2026-11-27)
}
# What may ever be written, per board (STAND.md E). The profile's `write` must stay inside.
ALLOWED = {'gta3xl': ('BOOT', 'VBMETA', 'CACHE'), 'fire8': ('boot', 'cache'), 'a12s': ('boot', 'cache')}
# Never on any device, as any part of a partition's name, any case (STAND.md E).
NEVER = ('bootloader', 'param', 'efs', 'persistent', 'steady', 'rpmb', 'preloader', 'lk', 'tee', 'nvcfg', 'boot_para',
         'kb', 'dkb', 'metadata', 'misc', 'recovery')
# What the editor's Odin speaks so far: the read-only trial (protocol odin). fastboot comes with the Fire.
PROTOCOLS = ('odin',)
_SHA = re.compile(r'^[0-9a-f]{64}$')
_HEX4 = re.compile(r'^[0-9a-fA-F]{4}$')
_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')


def mirror(config=None):
    """The Home Assistant mirror of the releases: <HA configuration>/www/kachel."""
    return Path(config or os.environ.get('HA_CONFIG', '/homeassistant')) / 'www' / 'kachel'


def never_hit(partition):
    """Whether a partition's name holds a word of NEVER (any case)."""
    name = str(partition or '').lower()
    return any(word in name for word in NEVER)


def verify(data, signature_text, key_b64):
    """Whether `signature_text` (Base64 of a raw Ed25519 signature, with whitespace around it) signs `data` with the key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        signature = base64.b64decode(str(signature_text).strip(), validate=True)
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(key_b64, validate=True))
        key.verify(signature, data)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _version(text):
    parts = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', str(text or ''))
    return tuple(int(part) for part in parts.groups()) if parts else None


def _text(value):
    return isinstance(value, str) and value.strip() or (isinstance(value, dict) and any(
        isinstance(value.get(lang), str) and value[lang].strip() for lang in ('de', 'en')))


def _steps(value, need_text=True):
    return isinstance(value, list) and all(isinstance(step, dict) and (_text(step.get('text')) or not need_text)
                                           and (step.get('image') is None or isinstance(step.get('image'), str)) for step in value)


def check(profile, mine=None):
    """What is wrong with a profile, as a list of short English reasons (empty: it may be used). `mine`: this app's
    version for `min_manager`. Checked here as well as in the editor: the lists in the code win over the profile."""
    wrong = []
    if not isinstance(profile, dict):
        return ['not a JSON object']
    if profile.get('format') != FORMAT:
        wrong.append('format is not kachel-install-profile')
    if profile.get('format_version') != FORMAT_VERSION:
        wrong.append('update the Kachel Manager: format_version %r' % profile.get('format_version'))
    need = profile.get('min_manager')
    if need is not None and (_version(need) is None or (_version(mine) or (0, 0, 0)) < _version(need)):
        wrong.append('update the Kachel Manager: needs %s' % need)
    board = profile.get('board')
    if board not in KEYS or board not in ALLOWED:
        wrong.append('unknown board %r' % board)
    if profile.get('protocol') not in PROTOCOLS:
        wrong.append('protocol %r not supported yet' % profile.get('protocol'))
    if not _text(profile.get('name')) or not isinstance(profile.get('version'), str):
        wrong.append('name or version missing')
    usb = profile.get('usb')
    if not isinstance(usb, list) or not usb or not all(isinstance(u, dict) and _HEX4.match(str(u.get('vid', '')))
                                                       and _HEX4.match(str(u.get('pid', ''))) for u in usb):
        wrong.append('usb filter invalid')
    odin = (profile.get('match') or {}).get('odin') if isinstance(profile.get('match'), dict) else None
    if profile.get('protocol') == 'odin':
        if not (isinstance(odin, dict) and isinstance(odin.get('pit_entries'), int) and isinstance(odin.get('block_size'), int)
                and odin['block_size'] > 0 and isinstance(odin.get('partitions'), dict) and odin['partitions']
                and all(isinstance(k, str) and isinstance(v, int) and v > 0 for k, v in odin['partitions'].items())):
            wrong.append('match.odin invalid')
    if not isinstance(profile.get('confirm'), list) or not all(isinstance(c, dict) and isinstance(c.get('id'), str)
                                                              and _text(c.get('text')) for c in profile['confirm']):
        wrong.append('confirm invalid')
    if not _steps(profile.get('mode_entry')) or not profile.get('mode_entry'):
        wrong.append('mode_entry invalid')
    if profile.get('leave_mode') is not None and not _steps(profile.get('leave_mode')):
        wrong.append('leave_mode invalid')
    files = profile.get('files')
    if not isinstance(files, dict) or not files:
        wrong.append('files missing')
        files = {}
    for name, entry in files.items():
        if not _NAME.match(str(name)) or not isinstance(entry, dict) or not relative_url(entry.get('url')) \
                or not _SHA.match(str(entry.get('sha256', ''))) or not isinstance(entry.get('size'), int) \
                or isinstance(entry.get('size'), bool) or entry['size'] <= 0:
            wrong.append('file %s invalid (url, sha256 and a real size)' % name)
    for step in (profile.get('mode_entry') or []) + (profile.get('leave_mode') or []):
        if isinstance(step, dict) and step.get('image') and step['image'] not in files:
            wrong.append('image %s not in files' % step['image'])
    write = profile.get('write')
    if not isinstance(write, list) or not write:
        wrong.append('write missing')
        write = []
    allowed = ALLOWED.get(board, ())
    for item in write:
        if not isinstance(item, dict):
            wrong.append('write entry invalid')
            continue
        part, file, most = item.get('partition'), item.get('file'), item.get('max_size')
        if part not in allowed:
            wrong.append('partition %r not allowed for %s' % (part, board))
        if never_hit(part) or part in (profile.get('never') or []):
            wrong.append('partition %r is never written' % part)
        if file not in files:
            wrong.append('file %r of %r not in files' % (file, part))
        elif not isinstance(most, int) or most <= 0 or (isinstance(files[file].get('size'), int) and files[file]['size'] > most):
            wrong.append('%s larger than max_size of %s' % (file, part))
    if not isinstance(profile.get('never'), list):
        wrong.append('never missing')
    erst = profile.get('erst')
    if not (isinstance(erst, dict) and erst.get('header') == 'KACHEL-ERST' and erst.get('header_version') == 1
            and erst.get('file') in files and isinstance(erst.get('max_payload'), int)):
        wrong.append('erst invalid')
    after = profile.get('after')
    if not (isinstance(after, dict) and isinstance(after.get('reboot'), bool) and _text(after.get('text'))):
        wrong.append('after invalid')
    return wrong


def load(channel, folder=None, mine=None):
    """{channel, profile, problems, present}: the channel's profile from the mirror, its signature checked with the key of
    the board it names, then `check`. A profile with problems is shown with them and never used."""
    folder = folder or mirror()
    place = folder.joinpath(*CHANNELS[channel])
    path = place / PROFILE
    out = {'channel': channel, 'present': path.is_file(), 'profile': None, 'problems': []}
    if not out['present']:
        return out
    try:
        data = path.read_bytes()
        signature = (place / (PROFILE + '.sig')).read_text(encoding='ascii')
        profile = json.loads(data.decode('utf8'))
    except (OSError, ValueError) as error:
        out['problems'] = ['profile or signature unreadable (%s)' % type(error).__name__]
        return out
    board = profile.get('board') if isinstance(profile, dict) else None
    if board not in KEYS:
        out['problems'] = ['unknown board %r' % board]
        return out
    if not verify(data, signature, KEYS[board]):
        out['problems'] = ['signature does not match the %s key' % board]
        return out
    out['profile'] = profile
    out['problems'] = check(profile, mine)
    return out


def relative_url(url):
    """Whether `url` is a clean relative link (format v1, clarification 27.11.): `..` is allowed, but no leading `/`, no
    `\\`, NUL or `%` (never decoded), no empty or `.` parts and no scheme. Absolute https URLs come later, with the Fire."""
    if not isinstance(url, str) or not url or url.startswith('/') or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', url):
        return False
    if any(bad in url for bad in ('\\', '\0', '%')):
        return False
    return all(part not in ('', '.') for part in url.split('/'))


def file_path(channel, profile, name, folder=None):
    """Where a profile's file lies in the mirror: its `url` resolved like a relative link against the profile's folder
    (`..` allowed), symlinks followed, never outside the mirror. None for anything `relative_url` refuses or a path that
    leaves the mirror."""
    folder = (folder or mirror()).resolve()
    entry = (profile.get('files') or {}).get(name)
    url = entry.get('url') if isinstance(entry, dict) else None
    if not relative_url(url):
        return None
    path = (folder.joinpath(*CHANNELS[channel]) / url).resolve()
    return path if folder in path.parents else None


class Files:
    """A file is handed out only once its size and sha256 match the profile; the result is kept per (path, size, mtime)."""

    def __init__(self):
        self.good = {}

    def checked(self, path, size, sha256):
        try:
            stat = path.stat()
        except OSError:
            return False
        key = (str(path), stat.st_size, stat.st_mtime_ns, sha256)
        if key in self.good:
            return True
        if stat.st_size != size:
            return False
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b''):
                digest.update(chunk)
        if digest.hexdigest() != sha256:
            return False
        self.good[key] = True
        return True


def view(folder=None):
    """Both channels, for the editor's page; the rules from the code beside them, so it shows the same lists."""
    mine = core.APP_VERSION
    return {'channels': [load(channel, folder, mine) for channel in CHANNELS], 'manager': mine,
            'allowed': {board: list(names) for board, names in ALLOWED.items()}, 'never': list(NEVER)}


def routes(app, folder=None):
    files = Files()

    async def show(request):
        return web.json_response(view(folder))

    async def serve(request):
        channel, name = request.match_info['channel'], request.match_info['name']
        if channel not in CHANNELS:
            raise web.HTTPNotFound()
        loaded = load(channel, folder, core.APP_VERSION)
        profile = loaded['profile']
        if profile is None or loaded['problems']:
            raise web.HTTPConflict(text='profile not usable')
        entry = (profile.get('files') or {}).get(name)
        path = file_path(channel, profile, name, folder)
        if not entry or path is None or not files.checked(path, entry['size'], entry['sha256']):
            LOG.warning('Installer: %s of the %s profile does not match its size or sha256', name, channel)
            raise web.HTTPConflict(text='file does not match the profile')
        return web.FileResponse(path, headers={'Cache-Control': 'no-store'})

    app.router.add_get('/api/kachel/installer', show)
    app.router.add_get('/api/kachel/installer/{channel}/file/{name}', serve)
