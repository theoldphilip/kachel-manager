"""Kachel Manager: a Kachel tablet's own device under Screen settings, Device (screen_manager/app/kachel_device.py): its
updates, battery and screen, found as the tablet's ESPHome entities and changed only through Home Assistant."""
import asyncio
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel_device  # noqa: E402

ENGLISH = json.loads((ROOT / 'screen_manager/translations/en.json').read_text())


def item(entity, name, device='tablet'):
    return {'entity_id': entity, 'platform': 'esphome', 'original_name': name, 'device_id': device}


class HA:
    """The living room tablet as echod 2.5.0-b9 has it: the inbox on a sub-device, everything else on the tablet."""
    def __init__(self):
        self.registry = [
            item('text.wohnzimmer_kachel_inbox', 'Kachel inbox', 'sub'),
            item('update.wohnzimmer_firmware', 'Firmware'),
            item('select.wohnzimmer_update_channel', 'Update channel'),
            item('button.wohnzimmer_check_for_updates', 'Check for updates'),
            item('sensor.wohnzimmer_update_status', 'Update status'),
            item('switch.wohnzimmer_install_updates_automatically', 'Install updates automatically'),
            item('sensor.wohnzimmer_battery_level', 'Battery level'),
            item('binary_sensor.wohnzimmer_charger_connected', 'Charger connected'),
            item('binary_sensor.wohnzimmer_battery_charging', 'Battery charging'),
            item('binary_sensor.wohnzimmer_battery_care', 'Battery care'),
            item('light.wohnzimmer_screen', 'Screen'),
            item('switch.wohnzimmer_screen_power', 'Screen power'),
            item('switch.wohnzimmer_settings_lock', 'Settings lock'),
            # Not ours: another device's switch of the same name, and a tablet entity of another integration.
            item('switch.flur_settings_lock', 'Settings lock', 'flur'),
            {'entity_id': 'sensor.wohnzimmer_battery_level_2', 'platform': 'template', 'original_name': 'Battery level',
             'device_id': 'tablet'},
        ]
        self.devices = [{'id': 'tablet', 'name': 'Wohnzimmer'}, {'id': 'sub', 'name': 'Wohnzimmer tessera', 'via_device_id': 'tablet'},
                        {'id': 'flur', 'name': 'Flur'}]
        self.states = {
            'update.wohnzimmer_firmware': {'state': 'on', 'attributes': {'installed_version': '2.5.0-b9', 'latest_version': '2.5.0-b10',
                                                                         'in_progress': False, 'title': 'Kachel'}},
            'select.wohnzimmer_update_channel': {'state': 'dev', 'attributes': {'options': ['stable', 'dev']}},
            'button.wohnzimmer_check_for_updates': {'state': 'unknown'},
            'sensor.wohnzimmer_update_status': {'state': 'Up to date'},
            'switch.wohnzimmer_install_updates_automatically': {'state': 'off'},
            'sensor.wohnzimmer_battery_level': {'state': '71', 'attributes': {'unit_of_measurement': '%'}},
            'binary_sensor.wohnzimmer_charger_connected': {'state': 'on'},
            'binary_sensor.wohnzimmer_battery_charging': {'state': 'on'},
            'binary_sensor.wohnzimmer_battery_care': {'state': 'on'},
            'light.wohnzimmer_screen': {'state': 'on', 'attributes': {'brightness': 128}},
            'switch.wohnzimmer_screen_power': {'state': 'on'},
            'switch.wohnzimmer_settings_lock': {'state': 'off'},
        }
        self.calls = []

    async def call_service(self, domain, service, data):
        self.calls.append((domain, service, data))


class Manager:
    def __init__(self, ha=None):
        self.ha = ha or HA()

    def screen(self, inbox):
        if inbox == 'text.wohnzimmer_kachel_inbox':
            return {'id': inbox, 'device_id': 'sub', 'online': True}
        return None


class TheDevice(unittest.TestCase):
    def test_the_rows_come_from_the_tablet_and_its_sub_devices_only(self):
        found = kachel_device.entities(Manager(), Manager().screen('text.wohnzimmer_kachel_inbox'))
        self.assertEqual(found['settings_lock'], 'switch.wohnzimmer_settings_lock')
        self.assertEqual(found['battery_level'], 'sensor.wohnzimmer_battery_level')
        self.assertNotIn('screen_off_when_nobody_is_near', found, 'a row the tablet does not have is left out')

    def test_sections_and_rows_as_the_editor_draws_them(self):
        sections = kachel_device.device_for(Manager(), 'text.wohnzimmer_kachel_inbox')
        self.assertEqual([s['section'] for s in sections], ['updates', 'battery', 'screen'])
        rows = {row['key']: row for s in sections for row in s['rows']}
        self.assertEqual(rows['firmware'] | {'label': None},
                         {'key': 'firmware', 'entity': 'update.wohnzimmer_firmware', 'label': None, 'available': True,
                          'writable': True, 'kind': 'update', 'value': '2.5.0-b9', 'latest': '2.5.0-b10', 'pending': True,
                          'installing': False, 'progress': None, 'title': 'Kachel'})
        self.assertEqual(rows['firmware']['label']['en'], 'Kachel version')
        self.assertEqual((rows['update_channel']['kind'], rows['update_channel']['value'], rows['update_channel']['options']),
                         ('select', 'dev', ['stable', 'dev']))
        self.assertEqual(rows['check_for_updates']['kind'], 'button')
        self.assertEqual((rows['battery_level']['kind'], rows['battery_level']['value'], rows['battery_level']['unit']), ('reading', '71', '%'))
        self.assertEqual((rows['battery_care']['kind'], rows['battery_care']['value'], rows['battery_care']['writable']), ('flag', True, False))
        self.assertEqual((rows['screen']['kind'], rows['screen']['value'], rows['screen']['brightness']), ('light', True, 50))
        self.assertFalse(rows['update_status']['writable'])

    def test_every_row_has_its_words(self):
        labels = ENGLISH['addon']['labels']['kachel_device']
        self.assertEqual(set(labels), set(kachel_device.WANTED))
        self.assertIn('request', ENGLISH['addon']['errors']['kachel_device'])

    def test_the_tablet_s_own_names_and_the_battery_switch_in_place_of_its_reading(self):
        """echod 2.6.1: entities found by their names, not their object ids (\"Night hours\" is screen_night_hours), and
        with the switch Battery protection the reading Battery care is left out."""
        ha = HA()
        for entity, name, state, attributes in (
                ('switch.wohnzimmer_battery_protection', 'Battery protection', 'on', {}),
                ('select.wohnzimmer_screen_night_hours', 'Night hours', 'Fixed', {'options': ['Off', 'Fixed']}),
                ('select.wohnzimmer_screen_night_start', 'Night starts', '22:00',
                 {'options': [f'{h:02}:{m:02}' for h in range(24) for m in (0, 15, 30, 45)]}),
                ('select.wohnzimmer_start_page', 'Start page', 'As in Tessera', {'options': ['As in Tessera', '1', '2']}),
                ('switch.wohnzimmer_screen_night_mode', 'Night mode', 'off', {})):
            ha.registry.append(item(entity, name))
            ha.states[entity] = {'state': state, 'attributes': attributes}
        sections = {s['section']: {row['key']: row for row in s['rows']} for s in kachel_device.device_for(Manager(ha), 'text.wohnzimmer_kachel_inbox')}
        self.assertEqual(list(sections), ['updates', 'battery', 'screen', 'pages'])
        self.assertNotIn('battery_care', sections['battery'])
        self.assertEqual((sections['battery']['battery_protection']['kind'], sections['battery']['battery_protection']['value']), ('switch', True))
        self.assertEqual(len(sections['screen']['night_starts']['options']), 96, 'every quarter of an hour')
        self.assertEqual(sections['screen']['night_hours']['value'], 'Fixed')
        self.assertEqual(sections['pages']['start_page']['options'], ['As in Tessera', '1', '2'])
        asyncio.run(kachel_device.change(Manager(ha), 'text.wohnzimmer_kachel_inbox', 'select.wohnzimmer_screen_night_start', '22:15'))
        self.assertEqual(ha.calls, [('select', 'select_option', {'entity_id': 'select.wohnzimmer_screen_night_start', 'option': '22:15'})])

    def test_a_name_in_the_wrong_domain_is_not_a_row(self):
        ha = HA()
        ha.registry.append(item('sensor.wohnzimmer_start_page', 'Start page'))
        found = kachel_device.entities(Manager(ha), Manager(ha).screen('text.wohnzimmer_kachel_inbox'))
        self.assertNotIn('start_page', found)

    def test_an_unknown_screen_is_refused(self):
        with self.assertRaises(ValueError):
            kachel_device.device_for(Manager(), 'text.flur_unknown')


class Changes(unittest.TestCase):
    def change(self, entity, value, manager=None):
        manager = manager or Manager()
        asyncio.run(kachel_device.change(manager, 'text.wohnzimmer_kachel_inbox', entity, value))
        return manager.ha.calls

    def test_each_kind_changes_the_way_home_assistant_takes_it(self):
        self.assertEqual(self.change('update.wohnzimmer_firmware', 'install'), [('update', 'install', {'entity_id': 'update.wohnzimmer_firmware'})])
        self.assertEqual(self.change('select.wohnzimmer_update_channel', 'stable'),
                         [('select', 'select_option', {'entity_id': 'select.wohnzimmer_update_channel', 'option': 'stable'})])
        self.assertEqual(self.change('button.wohnzimmer_check_for_updates', True),
                         [('button', 'press', {'entity_id': 'button.wohnzimmer_check_for_updates'})])
        self.assertEqual(self.change('switch.wohnzimmer_settings_lock', True),
                         [('switch', 'turn_on', {'entity_id': 'switch.wohnzimmer_settings_lock'})])
        self.assertEqual(self.change('light.wohnzimmer_screen', False), [('light', 'turn_off', {'entity_id': 'light.wohnzimmer_screen'})])
        self.assertEqual(self.change('light.wohnzimmer_screen', 40),
                         [('light', 'turn_on', {'entity_id': 'light.wohnzimmer_screen', 'brightness_pct': 40})])

    def test_nothing_else_changes(self):
        for entity, value in (('switch.flur_settings_lock', True),            # another device
                              ('sensor.wohnzimmer_battery_level', 50),         # a reading
                              ('binary_sensor.wohnzimmer_battery_care', True),  # a reading
                              ('update.wohnzimmer_firmware', True),            # an update only installs
                              ('light.wohnzimmer_screen', 0),                  # out of range
                              ('light.wohnzimmer_screen', 'on'),
                              ('select.wohnzimmer_update_channel', 7),
                              (None, True)):
            manager = Manager()
            with self.subTest(entity=entity, value=value), self.assertRaises(ValueError):
                asyncio.run(kachel_device.change(manager, 'text.wohnzimmer_kachel_inbox', entity, value))
            self.assertEqual(manager.ha.calls, [])


class TheRoutes(unittest.IsolatedAsyncioTestCase):
    async def test_the_editor_reads_and_changes_through_the_app(self):
        import tempfile
        from aiohttp.test_utils import TestClient, TestServer
        from server import Manager as App, create_app
        from test_screen_owned_settings import fake_ha
        ha = fake_ha()
        ha.registry.append(item('switch.office_settings_lock', 'Settings lock', 'd1'))
        ha.states['switch.office_settings_lock'] = {'state': 'off'}
        ha.service_calls = []

        async def call_service(domain, service, data):
            ha.service_calls.append((domain, service, data))
        ha.call_service = call_service
        with tempfile.TemporaryDirectory() as folder:
            client = TestClient(TestServer(create_app(App(ha, Path(folder) / 'screens.json'), development=True)))
            await client.start_server()
            try:
                response = await client.get('/api/screens/text.screen/kachel/device')
                self.assertEqual(response.status, 200)
                rows = [row for section in await response.json() for row in section['rows']]
                self.assertEqual([(row['key'], row['value']) for row in rows], [('night_mode', True), ('settings_lock', False)])
                csrf = (await (await client.get('/api/inventory')).json())['csrf']
                headers = {'X-Screen-CSRF': csrf}
                response = await client.post('/api/screens/text.screen/kachel/device', headers=headers,
                                             json={'entity': 'switch.office_settings_lock', 'value': True})
                self.assertEqual(response.status, 200)
                self.assertEqual(ha.service_calls, [('switch', 'turn_on', {'entity_id': 'switch.office_settings_lock'})])
                response = await client.post('/api/screens/text.screen/kachel/device', headers=headers,
                                             json={'entity': 'light.a', 'value': True})
                self.assertEqual(response.status, 400)
                self.assertEqual(len(ha.service_calls), 1)
            finally:
                await client.close()


if __name__ == '__main__':
    unittest.main()
