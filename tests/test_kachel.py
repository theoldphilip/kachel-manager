"""Kachel Manager: what this fork does differently from Tessera (screen_manager/app/kachel.py, CLAUDE.md)."""
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'screen_manager' / 'app'))

import core  # noqa: E402
import kachel  # noqa: E402


def registry_item(entity_id, name, device='dev1'):
    return {'entity_id': entity_id, 'original_name': name, 'platform': 'esphome', 'device_id': device}


class KachelScreens(unittest.TestCase):
    def test_only_a_kachel_inbox_is_a_screen(self):
        """A Kachel screen is found by its "Kachel inbox"; an ESP32 screen's "Tile settings" (Tessera's) is not ours."""
        registry = [registry_item('text.wohnzimmer_kachel_inbox', 'Kachel inbox', 'kachel'),
                    registry_item('text.flur_tile_settings', 'Tile settings', 'esp'),
                    registry_item('text.alt_tegelinstellingen', 'Tegelinstellingen', 'old')]
        states = {'text.wohnzimmer_kachel_inbox': {'state': 'Synced'}, 'text.flur_tile_settings': {'state': 'Synced'},
                  'text.alt_tegelinstellingen': {'state': 'Synced'}}
        devices = [{'id': 'kachel', 'name': 'Wohnzimmer'}, {'id': 'esp', 'name': 'Flur'}, {'id': 'old', 'name': 'Alt'}]
        screens = core.discover_screens(registry, states, devices, [])
        self.assertEqual([screen['id'] for screen in screens], ['text.wohnzimmer_kachel_inbox'])

    def test_the_inbox_id(self):
        self.assertEqual(core.inbox_prefix('text.laufband_display_kachel_inbox'), 'laufband_display')
        self.assertIsNone(core.inbox_prefix('text.flur_tile_settings'))

    def test_events_are_our_own(self):
        """An automation's event for this app never reaches Tessera, nor Tessera's this one."""
        names = [*core.TILE_EVENTS, core.TILE_RESULT_EVENT, *core.BROADCAST_EVENTS]
        self.assertTrue(names)
        for name in names:
            self.assertTrue(name.startswith('kachel_'), name)


class EspParts(unittest.TestCase):
    def test_esp_parts_are_off(self):
        self.assertFalse(kachel.ESP_SCREENS)

    def test_which_requests_are_refused(self):
        for path in ('/api/firmware', '/api/firmware/jobs', '/api/firmware/profiles/a.yaml/override', '/api/build-server',
                     '/api/build-server/pair', '/api/boards/known', '/api/updates', '/api/updates/run', '/api/video',
                     '/api/video/restart', '/api/screens/text.a_kachel_inbox/update', '/api/screens/text.a_kachel_inbox/icons/build'):
            self.assertTrue(kachel.esp_only(path), path)
        for path in ('/api/firmware-preview', '/api/firmware-preview/events', '/api/inventory', '/api/screens/text.a_kachel_inbox',
                     '/api/screens/text.a_kachel_inbox/icons', '/api/screens/text.a_kachel_inbox/settings', '/api/updates-x', None):
            self.assertFalse(kachel.esp_only(path), path)

    def test_the_app_is_the_kachel_manager(self):
        config = yaml.safe_load((ROOT / 'screen_manager' / 'config.yaml').read_text())
        self.assertEqual(config['slug'], 'kachel_manager')
        self.assertEqual(config['name'], 'Kachel Manager')
        self.assertNotIn('ports', config, "Tessera's port 8098 stays Tessera's")
        self.assertFalse(config.get('usb') or config.get('uart'))


class TesseraSite(unittest.TestCase):
    """Nothing goes to Tessera's website (Philip, 2026-11-19): no reports, feedback, plugin likes, ratings or counting."""
    def test_it_is_off(self):
        self.assertFalse(kachel.TESSERA_SITE)
        self.assertTrue(kachel.ISSUES.startswith('https://github.com/theoldphilip/kachel-manager/'))

    def test_which_requests_are_refused(self):
        for path in ('/api/reports/abc', '/api/reports/abc.zip', '/api/reports/abc/send', '/api/screens/text.a/report',
                     '/api/screens/text.a/feedback', '/api/plugins/weather/like', '/api/plugins/weather/rating',
                     '/api/plugins/weather/ask', '/api/plugins/counting'):
            self.assertTrue(kachel.site_only(path), path)
        for path in ('/api/plugins', '/api/plugins/weather/image', '/api/screens/text.a/layout', '/api/inventory'):
            self.assertFalse(kachel.site_only(path), path)

    def test_the_senders_never_reach_it(self):
        import asyncio
        import feedback
        import plugin_likes

        class Session:
            def request(self, *args, **kwargs):
                raise AssertionError('a request to the website')
            get = post = request

        self.assertEqual(asyncio.run(feedback.send(Session(), 'key', {'revision': 1})), {'state': 'retry'})
        self.assertIsNone(asyncio.run(feedback.fetch_boards(Session())))
        with tempfile.TemporaryDirectory() as folder:
            likes = plugin_likes.Likes(Path(folder) / 'plugin_likes.json')
            self.assertFalse(likes.usable)
            self.assertFalse(likes.view()['usable'])


class MessageNode(unittest.TestCase):
    """The safety net for a device whose "Device name" is not its ESPHome node (the Fire, 2026-11-19)."""
    PARENT = {'id': 'p', 'connections': [['mac', '98:cc:f3:22:3c:b8']], 'via_device_id': None}
    INBOX = {'id': 'd', 'connections': [], 'identifiers': [], 'via_device_id': 'p'}
    SERVICES = {'wohnzimmer_screen_message': {}, 'kachel_223cb8_screen_message': {}, 'techo5_panel_6591d3_screen_message': {}}

    def node(self, node, devices=None, services=None):
        return kachel.message_node({'node': node, 'device_id': 'd'}, devices if devices is not None else [self.PARENT, self.INBOX],
                                   self.SERVICES if services is None else services)

    def test_the_named_node_stands_when_home_assistant_has_it(self):
        self.assertEqual(self.node('techo5-panel-6591d3'), 'techo5-panel-6591d3')

    def test_a_name_without_an_action_takes_the_node_of_the_devices_mac(self):
        self.assertEqual(self.node('fire-test'), 'kachel_223cb8')
        self.assertEqual(core.message_action(self.node('fire-test')), 'esphome.kachel_223cb8_screen_message')
        # Its MAC in the inbox device's identifier works as well as the parent's connection.
        inbox = {'id': 'd', 'identifiers': [['esphome', '98:cc:f3:22:3c:b8_64']]}
        self.assertEqual(self.node('fire-test', devices=[inbox]), 'kachel_223cb8')

    def test_without_a_sure_answer_the_screens_word_stands(self):
        self.assertEqual(self.node('fire-test', services={}), 'fire-test')
        self.assertEqual(self.node('fire-test', devices=[]), 'fire-test')
        two = {**self.SERVICES, 'other_223cb8_screen_message': {}}
        self.assertEqual(self.node('fire-test', services=two), 'fire-test')
        self.assertEqual(self.node('fire-test', services={'wohnzimmer_screen_message': {}}), 'fire-test')

    def test_the_manager_gets_corrected_copies(self):
        class Ha:
            services = {'esphome': self.SERVICES}
            devices = [self.PARENT, self.INBOX]
        screens = kachel.with_message_nodes([{'node': 'fire-test', 'device_id': 'd'}, {'node': None, 'device_id': 'x'}], Ha())
        self.assertEqual([screen['node'] for screen in screens], ['kachel_223cb8', None])


class KachelIntegration(unittest.TestCase):
    """A device under the Kachel integration (kachel-verbindung, 2026-11-19) as under ESPHome: platform kachel, actions
    kachel.<node>_<action>, events kachel.screen_*."""
    def tearDown(self):
        kachel.NODE_DOMAINS.clear()

    def test_both_platforms_are_ours(self):
        self.assertEqual(kachel.PLATFORMS, ('esphome', 'kachel'))
        self.assertTrue(kachel.ours({'platform': 'kachel'}))
        self.assertTrue(kachel.ours({'platform': 'esphome'}))
        self.assertFalse(kachel.ours({'platform': 'mqtt'}))
        self.assertFalse(kachel.ours(None))

    def test_its_events_read_as_esphomes(self):
        self.assertEqual(kachel.as_esphome_event({'event_type': 'kachel.screen_setting', 'data': {'a': 1}}),
                         {'event_type': 'esphome.screen_setting', 'data': {'a': 1}})
        event = {'event_type': 'kachel_show_alert'}
        self.assertIs(kachel.as_esphome_event(event), event)
        self.assertIn('kachel.screen_doorbell', kachel.KACHEL_SCREEN_EVENTS)

    def test_a_screen_finds_its_screen_under_the_kachel_integration(self):
        registry = [registry_item('text.fire_kachel_inbox', 'Kachel inbox', 'd'), registry_item('sensor.fire_device_name', 'Device name', 'd'),
                    registry_item('sensor.fire_screen_firmware', 'Screen firmware', 'd')]
        for item in registry:
            item['platform'] = 'kachel'
        states = {'text.fire_kachel_inbox': {'state': 'Synced'}, 'sensor.fire_device_name': {'state': 'kachel-fire'},
                  'sensor.fire_screen_firmware': {'state': '0.60.0'}}
        screens = core.discover_screens(registry, states, [{'id': 'd', 'name': 'Fire'}], [])
        self.assertEqual([(screen['id'], screen['node']) for screen in screens], [('text.fire_kachel_inbox', 'kachel-fire')])

        class Ha:
            services = {'kachel': {'kachel_fire_screen_message': {'response': {'optional': True}}}}
            devices = [{'id': 'd', 'connections': [['mac', 'aa:bb:cc:dd:ee:ff']]}]
        Ha.registry = registry
        kachel.with_message_nodes(screens, Ha())
        self.assertEqual(core.message_action('kachel-fire'), 'kachel.kachel_fire_screen_message')
        self.assertEqual(core.alert_service('kachel-fire'), 'kachel.kachel_fire_show_alert')
        # A node nobody placed stays with ESPHome, as before.
        self.assertEqual(core.alert_service('office-1'), 'esphome.office_1_show_alert')


class Names(unittest.TestCase):
    def test_no_tessera_names_left(self):
        """After a merge from Tessera, tools/kachel_names.py writes our names; this says when it was not run."""
        result = subprocess.run([sys.executable, str(ROOT / 'tools' / 'kachel_names.py'), '--check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, 'run tools/kachel_names.py:\n' + result.stdout)


if __name__ == '__main__':
    unittest.main()


class Confirm(unittest.TestCase):
    """Kachel Manager: a switchable tile may ask before it switches (kachel.guard_allowed, core.validate_layout)."""

    def test_switchable_kinds_take_the_confirm_guard(self):
        self.assertTrue(kachel.guard_allowed('cover', 'confirm'))
        self.assertTrue(kachel.guard_allowed('switch', 'confirm'))
        self.assertFalse(kachel.guard_allowed('sensor', 'confirm'))
        self.assertFalse(kachel.guard_allowed('cover', 'lock_only'))
