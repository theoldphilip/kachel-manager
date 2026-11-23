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



import asyncio  # noqa: E402
import kachel_remove  # noqa: E402


class FakeHA:
    """The Laufband after a reset: its Kachel entry (no inbox, no pages), a Bluetooth entry of the same MAC from its ESPHome
    days, and someone else's device and Bluetooth entry that must stay."""
    def __init__(self):
        self.devices = [
            {'id': 'lb', 'connections': [['mac', '3c:19:5e:fa:cd:25']], 'config_entries': ['k1', 'bt1']},
            {'id': 'lb-play', 'via_device_id': 'lb', 'config_entries': ['k1']},
            {'id': 'other', 'connections': [['mac', '11:22:33:44:55:66']], 'config_entries': ['e2']},
        ]
        self.deleted = []

    async def esphome_entries(self):
        return {'k1': {'entry_id': 'k1', 'domain': 'kachel'}, 'e2': {'entry_id': 'e2', 'domain': 'esphome'}}

    async def request(self, kind, **data):
        if kind == 'config_entries/get' and data.get('domain') == 'bluetooth':
            return [{'entry_id': 'bt1', 'unique_id': '3C:19:5E:FA:CD:25'}, {'entry_id': 'bt2', 'unique_id': '11:22:33:44:55:66'}]
        return []

    async def delete_config_entry(self, entry):
        self.deleted.append(entry)


class FakeManager:
    def __init__(self):
        self.ha = FakeHA()

    def screens(self):
        return []


class LeavesByEvent(unittest.TestCase):
    """A Spezialanzeige without an inbox asks by the event screen_remove (kachel_remove), by its device or its MAC."""

    def test_by_device_id_its_kachel_and_bluetooth_entries_go(self):
        manager = FakeManager()
        self.assertTrue(asyncio.run(kachel_remove.remove_device(manager, 'lb-play')))
        self.assertEqual(sorted(manager.ha.deleted), ['bt1', 'k1'])

    def test_by_mac_alone(self):
        manager = FakeManager()
        self.assertTrue(asyncio.run(kachel_remove.remove_device(manager, None, '3C-19-5E-FA-CD-25')))
        self.assertEqual(sorted(manager.ha.deleted), ['bt1', 'k1'])

    def test_nothing_known(self):
        manager = FakeManager()
        self.assertFalse(asyncio.run(kachel_remove.remove_device(manager, None, 'aa:bb:cc:dd:ee:ff')))
        self.assertFalse(asyncio.run(kachel_remove.remove_device(manager, None, None)))
        self.assertEqual(manager.ha.deleted, [])

    def test_the_kachel_event_reads_as_its_esphome_twin(self):
        self.assertIn('kachel.screen_remove', kachel.KACHEL_SCREEN_EVENTS)
        self.assertEqual(kachel.as_esphome_event({'event_type': 'kachel.screen_remove', 'data': {}})['event_type'], kachel_remove.EVENT)


if __name__ == '__main__':
    unittest.main()
