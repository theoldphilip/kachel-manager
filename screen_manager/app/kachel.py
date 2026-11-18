"""Kachel Manager: what this fork of Tessera does differently, in one place (CLAUDE.md, "Kachel Manager and Tessera").

The Kachel Manager looks after the Kachel screens (Alpine Linux and echod on tablets) and nothing else. Real ESP32 screens
stay with the Tessera add-on, which may run beside this one in the same Home Assistant. So that the two never take the
same screen, a Kachel screen names its inbox "Kachel inbox" (echod, "Managed by: Kachel Manager") instead of Tessera's
"Tile settings", and this app looks for that name only (core.NAME_TILE_SETTINGS). The events an automation fires for this
app start with kachel_ instead of esp_screens_ (tools/kachel_names.py keeps every source in line after a merge from
Tessera), and what only an ESP32 screen needs is off: building and flashing firmware, adding a new screen to Home
Assistant, firmware updates, the build server and the tessera_video integration.

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

def esp_only(path):
    """Whether a request to `path` is for what only an ESP32 screen needs."""
    if not isinstance(path, str):
        return False
    if any(path == prefix or path.startswith(prefix.rstrip('/') + '/') for prefix in ESP_PATHS):
        return True
    return path.startswith('/api/screens/') and path.endswith(ESP_SCREEN_PATHS)

def refuse_esp():
    """The server's middleware that answers a request for an ESP32 screen's part with 404 while ESP_SCREENS is off,
    before its handler runs. Made on request, since core.py reads this module without aiohttp (tools/)."""
    from aiohttp import web

    @web.middleware
    async def refuse(request, handler):
        if not ESP_SCREENS and esp_only(request.path):
            return web.json_response({'error': 'Not part of the Kachel Manager: ESP32 screens stay with Tessera.'}, status=404)
        return await handler(request)
    return refuse
