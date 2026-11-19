"""Kachel Manager: a Kachel device reset to its factory settings asks to leave Home Assistant (fire-app, 2026-11-19).

It writes "remove" into its inbox (kachel.REMOVE_STATUS); the app removes it as the editor's Remove does, with the ESP32
parts off as the Kachel Manager ships them: its ESPHome entry with the device, and what this app kept for it.
"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kachel  # noqa: E402

HAS_AIOHTTP = importlib.util.find_spec('aiohttp') is not None
if HAS_AIOHTTP:
    from manager_fixtures import with_screen_grid
    from server import Manager
    from firmware import Firmware
    from test_remove_screen import INBOX, LAYOUT, with_entries
    from test_screen_owned_settings import fake_ha


class AsksToLeave(unittest.TestCase):
    def test_what_the_inbox_says(self):
        for status in ('remove', ' remove ', '{"status": "remove"}'):
            self.assertTrue(kachel.wants_removal({'status': status}), status)
        for status in ('Synced', 'Ready for tile configuration', '{"status": "Synced"}', '{nope', None, 'Remove me'):
            self.assertFalse(kachel.wants_removal({'status': status}), status)
        self.assertFalse(kachel.wants_removal(None))


@unittest.skipUnless(HAS_AIOHTTP, 'needs aiohttp')
class Removed(unittest.IsolatedAsyncioTestCase):
    async def test_the_sync_loop_removes_it_once_with_the_esp32_parts_off(self):
        self.assertFalse(kachel.ESP_SCREENS)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'screens.json').write_text(json.dumps({'version': 1, 'screens': {INBOX: LAYOUT}}))
            ha = with_screen_grid(with_entries(fake_ha()))
            manager = Manager(ha, Path(tmp) / 'screens.json')
            manager.firmware = Firmware(Path(tmp) / 'esphome', Path(tmp) / 'data')
            screen = manager.screens()[0]
            ha.states[INBOX] = {**ha.states.get(INBOX, {}), 'state': 'remove'}
            manager._screens_key = None
            self.assertTrue(kachel.wants_removal(manager.screens()[0]))
            # What the loop does for such a screen (Manager.sync_loop, "Kachel Manager: ... factory settings").
            answer = await manager.remove_screen(screen['id'])
            self.assertTrue(answer['removed'])
            self.assertEqual(ha.deleted, ['e1'])
            self.assertEqual(manager.screens(), [])
            self.assertEqual(manager.layouts, {})


if __name__ == '__main__':
    unittest.main()
