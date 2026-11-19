"""Kachel Manager: what this fork of Tessera does differently, in one place (CLAUDE.md, "Kachel Manager and Tessera").

The Kachel Manager looks after the Kachel screens (Alpine Linux and echod on tablets) and nothing else. Real ESP32 screens
stay with the Tessera add-on, which may run beside this one in the same Home Assistant. So that the two never take the
same screen, a Kachel screen names its inbox "Kachel inbox" (echod, "Managed by: Kachel Manager") instead of Tessera's
"Tile settings", and this app looks for that name only (core.NAME_TILE_SETTINGS). The events an automation fires for this
app start with kachel_ instead of esp_screens_ (tools/kachel_names.py keeps every source in line after a merge from
Tessera), and what only an ESP32 screen needs is off: building and flashing firmware, adding a new screen to Home
Assistant, firmware updates, the build server and the tessera_video integration. Nothing goes to Tessera's website
either (TESSERA_SITE): no troubleshooting reports, no feedback on a board, no plugin likes, ratings or counting; a problem
is reported as an issue on GitHub (ISSUES).

Tested by tests/test_kachel.py.
"""
import re

# The name of a Kachel screen's inbox entity (a text entity of its ESPHome device), as echod gives it.
INBOX_NAME = 'Kachel inbox'

# Whether this app does what only an ESP32 screen needs. Off: those screens stay with Tessera.
ESP_SCREENS = False

# What the editor asks the app for only for an ESP32 screen: a request for it is refused while ESP_SCREENS is off.
# /api/firmware-preview is the editor's own preview of a page and stays.
ESP_PATHS = ('/api/firmware', '/api/build-server', '/api/boards/', '/api/updates', '/api/video')
ESP_SCREEN_PATHS = ('/update', '/icons/build')

# Whether this app sends anything to Tessera's website (feedback.API): reports, feedback, plugin likes, ratings and
# counting. Off (Philip, 2026-11-19): people report a problem on GitHub instead.
TESSERA_SITE = False
ISSUES = 'https://github.com/theoldphilip/kachel-manager/issues'
SITE_PATHS = ('/api/reports', '/api/plugins/counting')
SITE_SCREEN_PATHS = ('/report', '/feedback')
SITE_PLUGIN_PATHS = ('/like', '/rating', '/ask')
SITE_REFUSED = "Not part of the Kachel Manager: nothing goes to Tessera's website. Report a problem on GitHub: " + ISSUES

def site_only(path):
    """Whether a request to `path` is for what goes to Tessera's website."""
    if not isinstance(path, str):
        return False
    if any(path == prefix or path.startswith(prefix + '/') or path.startswith(prefix + '.') for prefix in SITE_PATHS):
        return True
    if path.startswith('/api/screens/') and path.endswith(SITE_SCREEN_PATHS):
        return True
    return path.startswith('/api/plugins/') and path.endswith(SITE_PLUGIN_PATHS)

def site_closed():
    """Raised by the senders (feedback.py, reports.py, plugin_likes.py) while TESSERA_SITE is off: what they send never
    leaves the house, even from a loop or an answer saved before."""
    if not TESSERA_SITE:
        from aiohttp import ClientError
        raise ClientError(SITE_REFUSED)

# Where a Kachel device hangs in Home Assistant: under ESPHome, or under the Kachel integration (kachel-verbindung,
# 2026-11-19), which speaks the same protocol with its own names. Both are searched while devices move over; the inbox's
# name keeps Tessera's screens apart either way. Entities carry the integration as `platform`, actions are
# <platform>.<node>_<action>, and the device's events kachel.screen_* (esphome.screen_* under ESPHome).
PLATFORMS = ('esphome', 'kachel')
# The device's events the app listens to, under the Kachel integration's names; they are read as their ESPHome twins.
KACHEL_SCREEN_EVENTS = tuple(f'kachel.screen_{name}' for name in (
    'alert', 'browse', 'calendar', 'call', 'camera', 'doorbell', 'history', 'options', 'play', 'plugin', 'setting',
    'speaker', 'todo'))
# Which platform the actions of a node go to (with_message_nodes keeps it): esphome unless its device is under kachel.
NODE_DOMAINS = {}

def ours(item):
    """Whether an entity-registry item is an entity of a device this app can talk to (ESPHome or Kachel)."""
    return isinstance(item, dict) and item.get('platform') in PLATFORMS

def as_esphome_event(event):
    """A Home Assistant event with a Kachel device's kachel.screen_* type read as its esphome.screen_* twin, so the app
    handles both alike; every other event as it is."""
    kind = event.get('event_type') if isinstance(event, dict) else None
    if isinstance(kind, str) and kind.startswith('kachel.screen_'):
        return {**event, 'event_type': 'esphome.' + kind[len('kachel.'):]}
    return event

def domain_of(node):
    """The platform whose actions this node has (NODE_DOMAINS), esphome by default."""
    slug = node.replace('-', '_') if isinstance(node, str) else ''
    return NODE_DOMAINS.get(slug, 'esphome')

# The ESPHome action a screen takes a whole message through (core.message_action): esphome.<node>_screen_message.
MESSAGE_SUFFIX = '_screen_message'

def _mac_of(device, devices):
    """The MAC address Home Assistant knows for a screen's device or the device it hangs under, as 12 hex digits."""
    by_id = {d.get('id'): d for d in devices or () if isinstance(d, dict)}
    seen = set()
    while isinstance(device, dict) and device.get('id') not in seen:
        seen.add(device.get('id'))
        for kind, value in device.get('connections') or ():
            if kind == 'mac' and isinstance(value, str):
                return value.replace(':', '').lower()
        for domain, value in device.get('identifiers') or ():
            if domain in PLATFORMS and isinstance(value, str) and re.match(r'^([0-9a-f]{2}:){5}[0-9a-f]{2}', value.lower()):
                return value[:17].replace(':', '').lower()
        device = by_id.get(device.get('via_device_id'))
    return None

def message_node(screen, devices, esphome_services):
    """The node whose esphome.<node>_screen_message Home Assistant really offers for this screen.

    A screen names its node in the sensor "Device name", and every action this app calls is built from it. A Kachel
    device that shows a name of its own there (the Fire after its first setup: "fire-test") while ESPHome still knows it
    by its node ("kachel-223cb8") would be sent everything under an action Home Assistant does not have, and refuse it.
    A safety net: when Home Assistant has no action for the named node, the one that ends with the last six digits of the
    device's MAC address (ESPHome's own suffix for a node) is taken, if exactly one does. Otherwise, or before Home
    Assistant's actions are known, the screen's own word stands."""
    node = screen.get('node')
    known = {name[:-len(MESSAGE_SUFFIX)] for name in esphome_services or () if isinstance(name, str) and name.endswith(MESSAGE_SUFFIX)}
    if not known or (isinstance(node, str) and node.replace('-', '_') in known):
        return node
    device = next((d for d in devices or () if isinstance(d, dict) and d.get('id') == screen.get('device_id')), None)
    mac = _mac_of(device, devices)
    if not mac:
        return node
    suffix = mac[-6:]
    hits = [name for name in known if name == suffix or name.endswith('_' + suffix)]
    return hits[0] if len(hits) == 1 else node

def with_message_nodes(screens, ha):
    """`screens` (discovered, copies) with each node corrected by message_node from what `ha` knows, and the platform
    its actions go to remembered (NODE_DOMAINS): that of its inbox entity."""
    all_services = getattr(ha, 'services', None) or {}
    devices = getattr(ha, 'devices', None) or []
    platforms = {item.get('entity_id'): item.get('platform') for item in getattr(ha, 'registry', None) or ()
                 if isinstance(item, dict) and item.get('platform') in PLATFORMS}
    for screen in screens:
        if isinstance(screen, dict):
            platform = platforms.get(screen.get('id'), 'esphome')
            screen['node'] = message_node(screen, devices, all_services.get(platform) or {})
            if isinstance(screen['node'], str) and screen['node']:
                NODE_DOMAINS[screen['node'].replace('-', '_')] = platform
    return screens

# What a Kachel device writes into its inbox when it is reset to its factory settings and was asked "Also remove from
# Home Assistant?" (fire-app, 2026-11-19): the app removes it as the editor's Remove does (Manager.remove_screen: its
# ESPHome entry with the device and its entities). The device waits up to 20 s for its connection to drop.
REMOVE_STATUS = 'remove'

def wants_removal(screen):
    """Whether this discovered screen asks to be removed from Home Assistant: its inbox says REMOVE_STATUS, also as
    {"status": "remove"}."""
    status = screen.get('status') if isinstance(screen, dict) else None
    if not isinstance(status, str):
        return False
    text = status.strip()
    if text.startswith('{'):
        try:
            import json
            text = str((json.loads(text) or {}).get('status', '')).strip()
        except (ValueError, AttributeError):
            return False
    return text == REMOVE_STATUS

def esp_only(path):
    """Whether a request to `path` is for what only an ESP32 screen needs."""
    if not isinstance(path, str):
        return False
    if any(path == prefix or path.startswith(prefix.rstrip('/') + '/') for prefix in ESP_PATHS):
        return True
    return path.startswith('/api/screens/') and path.endswith(ESP_SCREEN_PATHS)

def refuse_esp():
    """The server's middleware that answers a request for an ESP32 screen's part with 404 while ESP_SCREENS is off, and
    one for Tessera's website while TESSERA_SITE is off, before its handler runs. Made on request, since core.py reads this module without aiohttp (tools/)."""
    from aiohttp import web

    @web.middleware
    async def refuse(request, handler):
        if not ESP_SCREENS and esp_only(request.path):
            return web.json_response({'error': 'Not part of the Kachel Manager: ESP32 screens stay with Tessera.'}, status=404)
        if not TESSERA_SITE and site_only(request.path):
            return web.json_response({'error': SITE_REFUSED}, status=404)
        return await handler(request)
    return refuse
