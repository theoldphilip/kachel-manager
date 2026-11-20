"""Kachel Manager: the Home Assistant integration `kachel` (kachel-verbindung-plugin), which this add-on ships and
writes into Home Assistant's configuration folder only when a person presses Install (Philip, 2026-11-19).

The integration connects the Kachel devices to Home Assistant in place of the ESPHome integration (kachel.PLATFORMS).
Its repository is private, so neither HACS nor Home Assistant can fetch it: the add-on carries a copy of its folder
`custom_components/kachel` in ha_integration/kachel, at the commit SOURCE_COMMIT names. A new version comes from
kachel-verbindung-plugin through the hub's mailbox and is copied in by hand (tools/kachel_integration_copy.sh).

Install writes the whole folder, so no file of an older version is left behind, and does nothing when the copy there is
already this one. Home Assistant loads a new or changed custom integration only at its next start: the add-on says a
restart is needed and leaves the restart to the person. It adds no config entry and changes no ESPHome entry: taking a
device in is done in Home Assistant ("Kachel device found", or by address).
"""
import json
import logging
import os
import shutil
from pathlib import Path

from aiohttp import web

from i18n import t

LOG = logging.getLogger('screen_manager')

DOMAIN = 'kachel'
SOURCE = Path(__file__).parent / 'ha_integration' / DOMAIN
# The commit of theoldphilip/kachel-verbindung the copy in SOURCE was taken from.
SOURCE_COMMIT = 'ac7fb28'


def target(config=None):
    """Where the integration goes: <Home Assistant configuration>/custom_components/kachel."""
    return Path(config or os.environ.get('HA_CONFIG', '/homeassistant')) / 'custom_components' / DOMAIN


def _tree(folder):
    return {str(path.relative_to(folder)): path for path in sorted(folder.rglob('*'))
            if path.is_file() and '__pycache__' not in path.parts}


def files():
    """{relative path: bytes} of the integration as this add-on ships it."""
    return {name: path.read_bytes() for name, path in _tree(SOURCE).items()}


def version(folder=SOURCE):
    try:
        found = json.loads((folder / 'manifest.json').read_text(encoding='utf8')).get('version')
    except (OSError, ValueError, AttributeError):
        return None
    return found if isinstance(found, str) else None


def status(directory, loaded=None):
    """{installed, current, version, there, loaded, restart, path}: whether the folder is there, whether it is exactly
    this add-on's copy (no file more, none less, none different), the version this add-on ships and the one there, the
    one Home Assistant runs (`loaded`, None before it does), and whether Home Assistant needs a restart to run this one."""
    there = version(directory) if (directory / 'manifest.json').is_file() else None
    current = False
    if there is not None:
        try:
            ours, theirs = files(), _tree(directory)
            current = set(ours) == set(theirs) and all(theirs[name].read_bytes() == data for name, data in ours.items())
        except OSError:
            current = False
    return {'installed': there is not None, 'current': current, 'version': version(), 'there': there,
            'loaded': loaded, 'restart': current and loaded != version(), 'path': str(directory),
            'commit': SOURCE_COMMIT}


def install(directory):
    """Write the integration as a whole: into a new folder beside it first, then put in place of the old one, which is
    removed. Nothing is written when the copy there is this one already."""
    if status(directory)['current']:
        return False
    parent = directory.parent
    fresh, old = parent / f'.{DOMAIN}.new', parent / f'.{DOMAIN}.old'
    try:
        parent.mkdir(parents=True, exist_ok=True)
        for leftover in (fresh, old):
            if leftover.exists():
                shutil.rmtree(leftover)
        for name, data in files().items():
            path = fresh / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o644)
        if directory.exists():
            directory.rename(old)
        fresh.rename(directory)
        if old.exists():
            shutil.rmtree(old)
    except OSError as error:
        raise ValueError(t('addon.errors.kachel_integration.not_written', folder=directory,
                           reason=error.strerror or type(error).__name__)) from error
    LOG.info('Kachel integration %s written to %s; Home Assistant loads it at its next start', version(), directory)
    return True


async def loaded_version(ha):
    """The version of `kachel` Home Assistant runs, or None when it runs none.

    Whether it runs one says Home Assistant's list of loaded components (get_config); manifest/get alone is no proof,
    since it reads a custom integration's folder even before Home Assistant ever loaded it, so a fresh install looked as
    if it ran already and the editor never asked for the restart (Fire test, 2026-11-20). Once loaded, Home Assistant
    keeps the manifest it loaded, so after an update on disk this still gives the running version until the restart."""
    try:
        config = await ha.request('get_config')
        if not isinstance(config, dict) or DOMAIN not in (config.get('components') or ()):
            return None
        manifest = await ha.request('manifest/get', integration=DOMAIN)
    except Exception:  # noqa: BLE001 - Home Assistant away: nothing is known to run
        return None
    return manifest.get('version') if isinstance(manifest, dict) else None


def routes(app, manager, directory=None):
    """GET /api/kachel/integration (the status), POST /api/kachel/integration (install or update)."""
    folder = directory or target()

    async def view(request):
        return web.json_response(status(folder, await loaded_version(manager.ha)))

    async def put(request):
        written = install(folder)
        return web.json_response({**status(folder, await loaded_version(manager.ha)), 'written': written})

    app.router.add_get('/api/kachel/integration', view)
    app.router.add_post('/api/kachel/integration', put)
