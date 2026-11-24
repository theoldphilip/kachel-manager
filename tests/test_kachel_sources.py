"""Kachel Manager: the sources of a Spezialanzeige (screen_manager/app/kachel_sources.py), as agreed with fire-app and
laufband-app on 2026-11-24: read from the hello, checked, kept per inbox and by MAC, sent with the values in the
device's session, and a button of the device performs the action of its source."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel  # noqa: E402
import kachel_functions as kf  # noqa: E402
import kachel_sources as ks  # noqa: E402

LAUFBAND = {'features': ['functions', 'sources'], 'kind': 'special', 'sources': [
    {'key': 'temperature', 'name': {'de': 'Raumtemperatur', 'en': 'Room temperature'}, 'domains': ['sensor'], 'device_class': ['temperature']},
    {'key': 'light', 'name': {'de': 'Licht', 'en': 'Light'}, 'domains': ['switch', 'light']},
    {'key': 'emergency', 'name': {'de': 'Notfall', 'en': 'Emergency'}, 'domains': ['switch', 'script', 'button']},
    {'key': 'power', 'name': {'de': 'Leistungsmesser', 'en': 'Power meter'}, 'domains': ['sensor'], 'device_class': ['power']}]}

STATES = {
    'sensor.hobby_temp': {'state': '21.5', 'attributes': {'device_class': 'temperature', 'unit_of_measurement': '°C', 'friendly_name': 'Hobby Temperatur'}},
    'sensor.steckdose_power': {'state': '120', 'attributes': {'device_class': 'power', 'unit_of_measurement': 'W', 'friendly_name': 'Laufband Leistung'}},
    'sensor.feuchte': {'state': '40', 'attributes': {'device_class': 'humidity'}},
    'switch.hobby_deckenlicht': {'state': 'off', 'attributes': {'friendly_name': 'Hobby Deckenlicht'}},
}


class Hello(unittest.TestCase):
    def test_a_spezialanzeige_and_its_sources(self):
        said = ks.hello(LAUFBAND)
        self.assertEqual(said['kind'], 'special')
        self.assertEqual([s['key'] for s in said['sources']], ['temperature', 'light', 'emergency', 'power'])
        self.assertEqual(said['sources'][0], {'key': 'temperature', 'name': {'de': 'Raumtemperatur', 'en': 'Room temperature'},
                                              'domains': ['sensor'], 'device_class': ['temperature'], 'required': False})

    def test_a_tablet_and_what_is_left_out(self):
        self.assertEqual(ks.hello({'features': ['functions']}), {'kind': 'tiles', 'sources': []})
        said = ks.hello({'kind': 'special', 'sources': [{'key': 'Bad Key', 'domains': ['sensor']}, {'key': 'x', 'domains': []},
                                                        {'key': 'ok', 'domains': ['sensor']}, {'key': 'ok', 'domains': ['light']}, 'junk']})
        self.assertEqual([s['key'] for s in said['sources']], ['ok'])
        many = ks.hello({'sources': [{'key': f's{i}', 'domains': ['sensor']} for i in range(30)]})
        self.assertEqual(len(many['sources']), ks.MAX_SOURCES)


class Clean(unittest.TestCase):
    def test_what_fits(self):
        offered = ks.hello(LAUFBAND)['sources']
        self.assertEqual(ks.clean({'sources': {'temperature': 'sensor.hobby_temp', 'light': 'switch.hobby_deckenlicht', 'power': ''},
                                   'room': ' Hobbyraum '}, offered, STATES),
                         {'sources': {'temperature': 'sensor.hobby_temp', 'light': 'switch.hobby_deckenlicht'}, 'room': 'Hobbyraum'})
        self.assertEqual(ks.clean({}, offered, STATES), {'sources': {}, 'room': None})

    def test_what_is_refused(self):
        offered = ks.hello(LAUFBAND)['sources']
        for bad in ({'sources': {'temperature': 'sensor.feuchte'}}, {'sources': {'light': 'sensor.hobby_temp'}},
                    {'sources': {'treadmill': 'switch.hobby_deckenlicht'}}, {'room': 5}, []):
            with self.assertRaises(ValueError, msg=bad):
                ks.clean(bad, offered, STATES)

    def test_choices_by_device_class(self):
        offered = ks.hello(LAUFBAND)['sources']
        found = ks.choices(offered, STATES)
        self.assertEqual(found['temperature'], [['sensor.hobby_temp', 'Hobby Temperatur']])
        self.assertEqual(found['power'], [['sensor.steckdose_power', 'Laufband Leistung']])
        self.assertEqual(found['emergency'], [['switch.hobby_deckenlicht', 'Hobby Deckenlicht']])


class Sender:
    def __init__(self, hello=LAUFBAND):
        self.session, self.confirmed, self.name = 'a' * 16, 'rev1', 'Laufband'
        self.features = set(hello.get('features', ()))
        self.kachel = ks.hello(hello)
        self.sent = []

    async def auxiliary(self, message, *, session, revision):
        self.sent.append(message)
        return True


class HA:
    def __init__(self):
        self.states = json.loads(json.dumps(STATES))
        self.devices = [{'id': 'tablet', 'area_id': 'hobby', 'connections': [['mac', '3c:19:5e:fa:cd:25']]},
                        {'id': 'inbox-dev', 'via_device_id': 'tablet', 'area_id': None}]
        self.areas = [{'area_id': 'hobby', 'name': 'Hobbyraum'}]
        self.registry = []
        self.calls = []

    async def call_service(self, domain, service, data):
        self.calls.append((domain, service, data))


class Manager:
    def __init__(self, folder, sender):
        self.path = Path(folder) / 'screens.json'
        self.kachel_sources = ks.Sources(folder)
        self.page_senders = {'text.laufband': sender}
        self.ha = HA()

    def screens(self):
        return [{'id': 'text.laufband', 'device_id': 'inbox-dev', 'name': 'Laufband'}]

    def screen(self, inbox):
        return next((s for s in self.screens() if s['id'] == inbox), None)


class Sync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sender = Sender()
        self.manager = Manager(self.tmp.name, self.sender)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sources_and_values_once_then_on_change(self):
        m = self.manager
        m.kachel_sources.heard('text.laufband', self.sender.kachel)
        m.kachel_sources.put('text.laufband', ks.clean({'sources': {'temperature': 'sensor.hobby_temp', 'light': 'switch.hobby_deckenlicht'}},
                                                       self.sender.kachel['sources'], STATES))
        self.assertTrue(asyncio.run(ks.sync(m, 'text.laufband')))
        self.assertEqual(self.sender.sent[0], {'op': 'sources', 'sources': {'light': 'switch.hobby_deckenlicht', 'temperature': 'sensor.hobby_temp'},
                                               'names': {'light': 'Hobby Deckenlicht', 'temperature': 'Hobby Temperatur'}, 'room': 'Hobbyraum'})
        self.assertIn({'op': 'source_state', 'key': 'temperature', 'state': '21.5', 'unit': '°C'}, self.sender.sent)
        self.assertIn({'op': 'source_state', 'key': 'light', 'state': 'off', 'unit': ''}, self.sender.sent)
        self.assertEqual(len(self.sender.sent), 3)
        self.assertFalse(asyncio.run(ks.sync(m, 'text.laufband')), 'nothing new')
        m.ha.states['sensor.hobby_temp']['state'] = '22.0'
        asyncio.run(ks.sync(m, 'text.laufband'))
        self.assertEqual(self.sender.sent[-1], {'op': 'source_state', 'key': 'temperature', 'state': '22.0', 'unit': '°C'})
        self.assertEqual(len(self.sender.sent), 4)

    def test_room_is_always_there_and_typed_wins(self):
        m = self.manager
        m.kachel_sources.heard('text.laufband', self.sender.kachel)
        m.ha.areas = []
        asyncio.run(ks.sync(m, 'text.laufband'))
        self.assertEqual(self.sender.sent[-1], {'op': 'sources', 'sources': {}, 'names': {}, 'room': ''})
        m.kachel_sources.put('text.laufband', {'sources': {}, 'room': 'Keller'})
        asyncio.run(ks.sync(m, 'text.laufband'))
        self.assertEqual(self.sender.sent[-1]['room'], 'Keller')

    def test_a_tablet_without_the_word_gets_nothing(self):
        sender = Sender({'features': ['functions']})
        manager = Manager(self.tmp.name, sender)
        self.assertFalse(asyncio.run(ks.sync(manager, 'text.laufband')))
        self.assertEqual(sender.sent, [])
        self.assertEqual(manager.kachel_sources.kind('text.laufband'), 'tiles')

    def test_offered_and_chosen_outlast_a_restart_and_a_new_inbox(self):
        m = self.manager
        asyncio.run(ks.sync(m, 'text.laufband'))
        m.kachel_sources.put('text.laufband', {'sources': {'light': 'switch.hobby_deckenlicht'}, 'room': None}, 'aabbccddeeff')
        again = ks.Sources(self.tmp.name)
        self.assertEqual(again.kind('text.laufband'), 'special')
        self.assertEqual(again.get('text.laufband')['sources'], {'light': 'switch.hobby_deckenlicht'})
        self.assertTrue(again.restore('text.neu', 'aabbccddeeff'))
        self.assertEqual(again.get('text.neu')['sources'], {'light': 'switch.hobby_deckenlicht'})
        self.assertFalse(again.restore('text.neu', 'aabbccddeeff'), 'once')

    def test_a_button_performs_its_source(self):
        m = self.manager
        m.kachel_sources.put('text.laufband', {'sources': {'light': 'switch.hobby_deckenlicht', 'emergency': 'script.notaus'}, 'room': None})
        self.assertTrue(asyncio.run(ks.press(m, {'device_id': 'tablet', 'key': 'light', 'action': 'toggle'})))
        self.assertTrue(asyncio.run(ks.press(m, {'device_id': 'inbox-dev', 'key': 'emergency', 'action': 'press'})))
        self.assertEqual(m.ha.calls, [('switch', 'toggle', {'entity_id': 'switch.hobby_deckenlicht'}),
                                      ('script', 'turn_on', {'entity_id': 'script.notaus'})])
        for body in ({'device_id': 'tablet', 'key': 'power', 'action': 'toggle'}, {'device_id': 'other', 'key': 'light', 'action': 'toggle'},
                     {'device_id': 'tablet', 'key': 'light', 'action': 'explode'}, None):
            self.assertFalse(asyncio.run(ks.press(m, body)), body)
        self.assertEqual(len(m.ha.calls), 2)


class Events(unittest.TestCase):
    def test_the_button_event_under_both_platforms(self):
        self.assertIn('kachel.screen_source', kachel.KACHEL_SCREEN_EVENTS)
        self.assertEqual(kachel.as_esphome_event({'event_type': 'kachel.screen_source'})['event_type'], ks.EVENT)


class BatteryLow(unittest.TestCase):
    def test_the_presence_sensors_battery(self):
        functions = {'presence': {'entities': ['binary_sensor.hobby_presence']}}
        registry = [{'entity_id': 'binary_sensor.hobby_presence', 'device_id': 'melder'},
                    {'entity_id': 'sensor.hobby_battery', 'device_id': 'melder'},
                    {'entity_id': 'binary_sensor.hobby_battery_low', 'device_id': 'melder'},
                    {'entity_id': 'sensor.other_battery', 'device_id': 'other'}]
        states = {'sensor.hobby_battery': {'state': '80', 'attributes': {'device_class': 'battery'}},
                  'binary_sensor.hobby_battery_low': {'state': 'off', 'attributes': {'device_class': 'battery'}},
                  'sensor.other_battery': {'state': '3', 'attributes': {'device_class': 'battery'}}}
        self.assertIs(kf.battery_low(functions, registry, states), False)
        states['sensor.hobby_battery']['state'] = '10'
        self.assertIs(kf.battery_low(functions, registry, states), True)
        self.assertIsNone(kf.battery_low(functions, registry[:1], states), 'no battery: nothing said')


if __name__ == '__main__':
    unittest.main()
