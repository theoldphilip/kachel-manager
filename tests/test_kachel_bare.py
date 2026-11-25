"""Kachel Manager: a Kachel device without a "Kachel inbox" is shown all the same (screen_manager/app/kachel_bare.py,
Philip 2026-11-25): listed as a Spezialanzeige without pages, found by its id for its tabs, never an ESP32 screen, and
what was saved for it moves to its inbox once it reports one."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel_bare  # noqa: E402
import kachel_functions  # noqa: E402
import kachel_sources  # noqa: E402


class HA:
    def __init__(self):
        self.devices = [
            {'id': 'laufband', 'name': 'Laufband Display', 'area_id': 'test', 'connections': [['mac', '3c:19:5e:fa:cd:25']]},
            {'id': 'fire', 'name': 'Kachel-guru'}, {'id': 'fire-seiten', 'name': 'Kachel-guru Seiten', 'via_device_id': 'fire'},
            {'id': 'esp32', 'name': 'Küche CYD'},
        ]
        self.registry = [
            {'entity_id': 'light.test_laufband_display_screen', 'device_id': 'laufband', 'platform': 'kachel', 'original_name': 'Screen'},
            {'entity_id': 'sensor.test_laufband_display_kachel_board', 'device_id': 'laufband', 'platform': 'kachel', 'original_name': 'Kachel board'},
            {'entity_id': 'text.test_kachel_guru_seiten_kachel_inbox', 'device_id': 'fire-seiten', 'platform': 'kachel', 'original_name': 'Kachel inbox'},
            {'entity_id': 'light.fire_screen', 'device_id': 'fire', 'platform': 'kachel', 'original_name': 'Screen'},
            {'entity_id': 'light.kueche_backlight', 'device_id': 'esp32', 'platform': 'esphome', 'original_name': 'Backlight'},
        ]
        self.states = {'light.test_laufband_display_screen': {'state': 'on'},
                       'sensor.test_laufband_display_kachel_board': {'state': 'a12s'}}
        self.areas = [{'area_id': 'test', 'name': 'Test'}]
        self.services = {'kachel': {'laufband_display_screen_message': {}, 'laufband_display_log': {},
                                    'kachel_guru_screen_message': {}}, 'esphome': {'kueche_cyd_screen_message': {}}}


class Manager:
    def __init__(self, folder=None):
        self.ha = HA()
        self.fire = {'id': 'text.test_kachel_guru_seiten_kachel_inbox', 'device_id': 'fire-seiten', 'name': 'Kachel-guru'}
        if folder:
            self.kachel_functions = kachel_functions.Functions(folder)
            self.kachel_sources = kachel_sources.Sources(folder)

    def screens(self):
        return [self.fire]


class Bare(unittest.TestCase):
    def test_the_laufband_without_inbox_is_listed(self):
        found = kachel_bare.bare(Manager())
        self.assertEqual([entry['id'] for entry in found], ['kachel:laufband'], 'not the Fire (it has an inbox), not the ESP32')
        laufband = found[0]
        self.assertEqual((laufband['name'], laufband['node'], laufband['area']), ('Laufband Display', 'laufband_display', 'Test'))
        self.assertTrue(laufband['online'] and laufband['kachel_bare'])
        self.assertEqual(laufband['kachel_kind'], 'special')
        self.assertEqual(laufband['kachel']['board'], 'a12s')

    def test_found_by_its_id_for_its_tabs(self):
        manager = Manager()
        self.assertEqual(kachel_bare.screen(manager, 'kachel:laufband')['device_id'], 'laufband')
        self.assertIsNone(kachel_bare.screen(manager, 'kachel:fire'))
        self.assertIsNone(kachel_bare.screen(manager, 'text.anything'))

    def test_inventory_entries_have_no_pages(self):
        entry = kachel_bare.inventory_entries(Manager(), None)[0]
        self.assertEqual(entry['layout'], {'title': 'Laufband Display', 'tiles': []})
        self.assertIsNone(entry['page_document'])
        # A grid all the same: without one the editor showed no tabs (Laufband with 0.1.14).
        self.assertEqual(entry['source_grid'], {'columns': 4, 'rows': 2})

    def test_the_editor_test_opens_what_the_app_sends(self):
        # web/tests/kachel-bare.spec.ts opens this very entry: the two tests stay one.
        sent = json.loads(json.dumps(kachel_bare.inventory_entries(Manager(), None)[0]))
        shared = json.loads((ROOT / 'web/tests/kachel-bare-entry.json').read_text(encoding='utf8'))
        self.assertEqual(sent, shared)

    def test_a_node_by_its_mac_when_the_name_differs(self):
        ha = HA()
        ha.devices[0]['name'] = 'Hobby Laufband'
        ha.services = {'kachel': {'kachel_facd25_log': {}}}
        self.assertEqual(kachel_bare.node_of(ha, ha.devices[0]), ('kachel_facd25', 'kachel'))

    def test_what_was_saved_moves_to_the_inbox(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = Manager(folder)
            manager.kachel_functions.put('kachel:fire', {'presence': {'entities': ['binary_sensor.p']}})
            manager.kachel_sources.put('kachel:fire', {'sources': {'light': 'switch.l'}, 'room': None})
            self.assertTrue(kachel_bare.adopt(manager, manager.fire))
            self.assertEqual(manager.kachel_functions.get(manager.fire['id']), {'presence': {'entities': ['binary_sensor.p']}})
            self.assertEqual(manager.kachel_sources.get(manager.fire['id'])['sources'], {'light': 'switch.l'})
            self.assertFalse(kachel_bare.adopt(manager, manager.fire), 'once')


if __name__ == '__main__':
    unittest.main()
