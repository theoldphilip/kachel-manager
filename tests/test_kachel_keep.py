"""Kachel Manager: a Kachel device's pages outlast its leaving Home Assistant (screen_manager/app/kachel_keep.py): kept by
its MAC when it is removed, given back once when it comes back without pages, under ESPHome or the Kachel integration."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel_keep  # noqa: E402
from layout_store import FORMAT, LayoutStore, new_id, validate_document  # noqa: E402
from core import Grid  # noqa: E402

GRID = Grid(3, 2)


def record(title):
    page = new_id()
    document = validate_document({'title': title, 'homePageId': page, 'pages': [{
        'id': page, 'navigation': {'excludeFromPagination': False}, 'tiles': [],
        'topbar': {'leading': [{'id': new_id(), 'kind': 'home'}], 'title': {'source': 'screen'},
                   'trailing': [{'id': new_id(), 'type': 'clock'}]}}]}, GRID)
    return {'format': FORMAT, 'sourceGrid': {'columns': 3, 'rows': 2}, 'layout': document, 'revision': new_id()}


class HA:
    def __init__(self):
        # The Fire under ESPHome: its inbox on the "Seiten" sub-device; under Kachel: a new device with the same MAC.
        self.devices = [
            {'id': 'old-top', 'connections': [['mac', 'aa:bb:cc:22:3c:b8']]},
            {'id': 'old-sub', 'via_device_id': 'old-top'},
            {'id': 'new-top', 'connections': [['mac', 'AA:BB:CC:22:3C:B8']]},
            {'id': 'new-sub', 'via_device_id': 'new-top'},
            {'id': 'other', 'connections': [['mac', '11:22:33:44:55:66']]},
        ]


class Manager:
    def __init__(self, folder):
        self.path = Path(folder) / 'screens.json'
        self.ha = HA()
        self.store = LayoutStore(self.path, lambda inbox: GRID)

    def put(self, inbox, value):
        with self.store._locked():
            self.store._reload()
            self.store._replace({**self.store._records, inbox: value})


OLD = {'id': 'text.philiponfire_seiten_kachel_inbox', 'device_id': 'old-sub', 'name': 'philiponfire Seiten', 'node': 'philiponfire'}
NEW = {'id': 'text.test_philiponfire_seiten_kachel_inbox', 'device_id': 'new-sub', 'name': 'philiponfire Seiten', 'node': 'philiponfire'}


class Keep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.manager = Manager(self.tmp.name)
        self.pages = record('Zuhause')
        self.manager.put(OLD['id'], self.pages)

    def tearDown(self):
        self.tmp.cleanup()

    def test_removed_then_back_under_kachel_gets_its_pages_once(self):
        self.assertTrue(kachel_keep.keep(self.manager, OLD, OLD['id']))
        self.manager.store.forget(OLD['id'])
        self.assertTrue(kachel_keep.restore(self.manager, NEW))
        self.assertEqual(self.manager.store.get(NEW['id'])['layout']['title'], 'Zuhause')
        self.assertFalse(kachel_keep.restore(self.manager, NEW), 'once')
        kept = json.loads((Path(self.tmp.name) / kachel_keep.FILE).read_text())
        self.assertEqual(kept, {})

    def test_a_screen_with_pages_keeps_its_own(self):
        kachel_keep.keep(self.manager, OLD, OLD['id'])
        own = record('Eigene')
        self.manager.put(NEW['id'], own)
        self.assertFalse(kachel_keep.restore(self.manager, NEW))
        self.assertEqual(self.manager.store.get(NEW['id'])['layout']['title'], 'Eigene')

    def test_another_device_gets_nothing(self):
        kachel_keep.keep(self.manager, OLD, OLD['id'])
        other = {'id': 'text.other_kachel_inbox', 'device_id': 'other'}
        self.assertFalse(kachel_keep.restore(self.manager, other))
        self.assertIsNone(self.manager.store.get('text.other_kachel_inbox'))

    def test_nothing_kept_without_mac_or_pages(self):
        self.assertFalse(kachel_keep.keep(self.manager, {'device_id': 'unknown'}, OLD['id']))
        self.assertFalse(kachel_keep.keep(self.manager, NEW, NEW['id']))
        self.assertFalse((Path(self.tmp.name) / kachel_keep.FILE).exists())

    def test_at_most_keep_devices(self):
        for i in range(kachel_keep.KEEP + 3):
            mac = f'00:00:00:00:{i // 256:02x}:{i % 256:02x}'
            self.manager.ha.devices.append({'id': f'd{i}', 'connections': [['mac', mac]]})
            self.manager.put(f'text.d{i}', self.pages)
            kachel_keep.keep(self.manager, {'device_id': f'd{i}', 'name': f'd{i}'}, f'text.d{i}')
        kept = json.loads((Path(self.tmp.name) / kachel_keep.FILE).read_text())
        self.assertEqual(len(kept), kachel_keep.KEEP)

    def test_a_broken_file_is_no_harm(self):
        (Path(self.tmp.name) / kachel_keep.FILE).write_text('not json')
        self.assertFalse(kachel_keep.restore(self.manager, NEW))


if __name__ == '__main__':
    unittest.main()
