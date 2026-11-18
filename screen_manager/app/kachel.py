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
