"""Kachel Manager: the Home Assistant integration `kachel` (screen_manager/app/kachel_integration.py), shipped in
ha_integration/kachel and written into Home Assistant's folder only on request, as a whole."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel_integration as ki  # noqa: E402


class HA:
    def __init__(self, loaded=None):
        self.loaded = loaded

    async def request(self, kind, **data):
        if kind == 'get_config':
            return {'components': ['esphome'] + (['kachel'] if self.loaded else [])}
        # manifest/get reads the folder whether or not Home Assistant loaded it.
        return {'domain': 'kachel', 'version': self.loaded or '0.2.2'}


class Shipped(unittest.TestCase):
    def test_the_copy_is_the_integration(self):
        manifest = json.loads((ki.SOURCE / 'manifest.json').read_text())
        self.assertEqual(manifest['domain'], 'kachel')
        self.assertEqual(ki.version(), manifest['version'])
        names = set(ki.files())
        self.assertTrue({'__init__.py', 'config_flow.py', 'manifest.json', 'services.yaml', 'translations/de.json'} <= names)
        self.assertFalse(any('__pycache__' in name for name in names))
        self.assertRegex(ki.SOURCE_COMMIT, r'^[0-9a-f]{7,40}$')

    def test_the_target_is_in_custom_components(self):
        self.assertEqual(ki.target('/config'), Path('/config/custom_components/kachel'))


class Install(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / 'custom_components' / 'kachel'

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_then_written_then_restart_then_running(self):
        self.assertEqual(ki.status(self.folder) | {'path': None},
                         {'installed': False, 'current': False, 'version': ki.version(), 'there': None, 'loaded': None,
                          'restart': False, 'path': None, 'commit': ki.SOURCE_COMMIT})
        self.assertTrue(ki.install(self.folder))
        state = ki.status(self.folder)
        self.assertTrue(state['installed'] and state['current'] and state['restart'])
        self.assertEqual({p.name for p in self.folder.parent.iterdir()}, {'kachel'}, 'nothing left beside it')
        self.assertFalse(ki.install(self.folder), 'the same copy is not written again')
        self.assertFalse(ki.status(self.folder, loaded=ki.version())['restart'])

    def test_an_older_version_is_replaced_whole(self):
        self.folder.mkdir(parents=True)
        (self.folder / 'manifest.json').write_text('{"domain": "kachel", "version": "0.1.0"}')
        (self.folder / 'old_platform.py').write_text('# gone in the new version\n')
        state = ki.status(self.folder, loaded='0.1.0')
        self.assertEqual((state['installed'], state['current'], state['there'], state['restart']), (True, False, '0.1.0', False))
        self.assertTrue(ki.install(self.folder))
        self.assertFalse((self.folder / 'old_platform.py').exists())
        self.assertTrue(ki.status(self.folder, loaded='0.1.0')['restart'])

    def test_an_extra_file_is_not_current(self):
        ki.install(self.folder)
        (self.folder / 'extra.py').write_text('')
        self.assertFalse(ki.status(self.folder)['current'])

    def test_a_folder_that_can_not_be_written(self):
        blocker = Path(self.tmp.name) / 'file'
        blocker.write_text('')
        with self.assertRaises(ValueError):
            ki.install(blocker / 'custom_components' / 'kachel')

    def test_loaded_version(self):
        self.assertIsNone(asyncio.run(ki.loaded_version(HA())))
        self.assertEqual(asyncio.run(ki.loaded_version(HA('0.2.0'))), '0.2.0')


class Texts(unittest.TestCase):
    def test_english_and_german(self):
        for lang in ('en', 'de'):
            data = json.loads((ROOT / f'screen_manager/translations/{lang}.json').read_text())
            self.assertIn('not_written', data['addon']['errors']['kachel_integration'])
            self.assertIn('restart', data['editor']['settings']['kachel_integration'])


if __name__ == '__main__':
    unittest.main()
