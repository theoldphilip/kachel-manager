"""Kachel Manager: Tessera's tests of what only an ESP32 screen needs (building firmware, New screen, updates, the build
server, tessera_video) run with those parts on, as Tessera ships them. The Kachel Manager ships them off
(screen_manager/app/kachel.py), which tests/test_kachel.py proves; the code stays, so a merge from Tessera keeps it
working, and these tests say so.

    @esp_on
    class FirmwareRoutes(unittest.IsolatedAsyncioTestCase): ...
"""
from pathlib import Path
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'screen_manager' / 'app'))

import kachel  # noqa: E402


def esp_on(target):
    """A test class or test with the ESP32 parts on for every test it runs."""
    return mock.patch.object(kachel, 'ESP_SCREENS', True)(target)


def site_on_module():
    """Kachel Manager: Tessera's tests of what goes to its website (reports, feedback, plugin likes, ratings, counting)
    run with it on, as Tessera ships it; the Kachel Manager ships it off (kachel.TESSERA_SITE, tests/test_kachel.py).

        setUpModule, tearDownModule = site_on_module()
    """
    patcher = mock.patch.object(kachel, 'TESSERA_SITE', True)
    return patcher.start, patcher.stop
