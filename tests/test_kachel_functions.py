"""Kachel Manager: what is set up for a Kachel device (screen_manager/app/kachel_functions.py): checked as the tablet
takes it (fire-app, `functions` v2), kept per screen, sent in the screen's session once per hello and on every change,
and the presence after the hello, on a change and at least every minute."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel_functions as kf  # noqa: E402


class Clean(unittest.TestCase):
    def test_everything_as_the_tablet_takes_it(self):
        self.assertEqual(kf.clean({
            'presence': {'entities': ['binary_sensor.wohnzimmer_praesenz', 'binary_sensor.wohnzimmer_praesenz']},
            'page_turn': {'ways': ['remote', 'swipe']},
            'assist': {'ways': ['wake_word'], 'pipeline': ' Home Assistant '},
            'notices': {'doorbell': 'event.haustuer', 'waste': 'calendar.abfall', 'missed': True, 'weather': '', 'post': None}}),
            {'presence': {'entities': ['binary_sensor.wohnzimmer_praesenz']}, 'page_turn': {'ways': ['swipe', 'remote']},
             'assist': {'ways': ['wake_word'], 'pipeline': 'Home Assistant'},
             'notices': {'doorbell': 'event.haustuer', 'waste': 'calendar.abfall', 'missed': True}})

    def test_nothing_is_everything_off(self):
        self.assertEqual(kf.clean({}), {})
        self.assertEqual(kf.clean({'presence': None, 'notices': {'weather': ''}}), {})

    def test_what_is_refused(self):
        self.assertEqual(kf.clean({'presence': {'entities': ['person.philip', 'device_tracker.handy']}})['presence']['entities'],
                         ['person.philip', 'device_tracker.handy'])
        for bad in ({'presence': {'entities': ['light.x']}}, {'page_turn': {'ways': ['shake']}}, {'assist': {'ways': ['clap']}},
                    {'notices': {'doorbell': 'light.x'}}, {'notices': {'alarm': 'event.x'}}, [],
                    {'presence': {'entities': [f'binary_sensor.p{i}' for i in range(5)]}}):
            with self.assertRaises(ValueError, msg=bad):
                kf.clean(bad)


class Sender:
    def __init__(self, features=('functions',)):
        self.session, self.confirmed, self.features, self.name = 'a' * 16, 'rev1', set(features), 'Fire'
        self.sent = []

    async def auxiliary(self, message, *, session, revision):
        self.sent.append(message)
        return True


class HA:
    def __init__(self):
        self.states = {'binary_sensor.p': {'state': 'off'}}


class Manager:
    def __init__(self, folder, sender):
        self.kachel_functions = kf.Functions(folder)
        self.page_senders = {'text.fire': sender}
        self.ha = HA()


class Sync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_once_per_session_and_on_change_with_presence(self):
        sender = Sender()
        manager = Manager(self.tmp.name, sender)
        manager.kachel_functions.put('text.fire', kf.clean({'presence': {'entities': ['binary_sensor.p']}}))
        self.assertTrue(asyncio.run(kf.sync(manager, 'text.fire')))
        self.assertEqual(sender.sent, [{'op': 'functions', 'presence': {'entities': ['binary_sensor.p']}}, {'op': 'presence', 'present': False}])
        self.assertFalse(asyncio.run(kf.sync(manager, 'text.fire')), 'nothing new')
        manager.ha.states['binary_sensor.p'] = {'state': 'on'}
        asyncio.run(kf.sync(manager, 'text.fire'))
        self.assertEqual(sender.sent[-1], {'op': 'presence', 'present': True})
        sender.session = 'b' * 16   # a new hello: everything again
        asyncio.run(kf.sync(manager, 'text.fire'))
        self.assertEqual([m['op'] for m in sender.sent[-2:]], ['functions', 'presence'])
        # kept across a restart of the app
        self.assertEqual(json.loads((Path(self.tmp.name) / kf.FILE).read_text())['text.fire']['presence']['entities'], ['binary_sensor.p'])
        self.assertEqual(kf.Functions(self.tmp.name).get('text.fire'), {'presence': {'entities': ['binary_sensor.p']}})

    def test_a_screen_without_the_word_gets_nothing(self):
        sender = Sender(features=())
        manager = Manager(self.tmp.name, sender)
        manager.kachel_functions.put('text.fire', {'page_turn': {'ways': ['swipe']}})
        self.assertFalse(asyncio.run(kf.sync(manager, 'text.fire')))
        self.assertEqual(sender.sent, [])

    def test_an_empty_choice_still_goes_out_once(self):
        sender = Sender()
        manager = Manager(self.tmp.name, sender)
        asyncio.run(kf.sync(manager, 'text.fire'))
        self.assertEqual(sender.sent, [{'op': 'functions'}])
        self.assertEqual(manager.kachel_functions.watched(), set())

    def test_people_and_trackers_at_home(self):
        functions = {'presence': {'entities': ['person.philip', 'device_tracker.handy']}}
        self.assertTrue(kf.present(functions, {'person.philip': {'state': 'home'}, 'device_tracker.handy': {'state': 'not_home'}}))
        self.assertFalse(kf.present(functions, {'person.philip': {'state': 'Arbeit'}, 'device_tracker.handy': {'state': 'not_home'}}))

    def test_presence_unknown_is_not_sent(self):
        self.assertIsNone(kf.present({'presence': {'entities': ['binary_sensor.gone']}}, {}))
        self.assertTrue(kf.present({'presence': {'entities': ['binary_sensor.a', 'binary_sensor.b']}},
                                   {'binary_sensor.a': {'state': 'off'}, 'binary_sensor.b': {'state': 'on'}}))


if __name__ == '__main__':
    unittest.main()
