"""Kachel Manager: a Kachel device's log through its <node>_log action (screen_manager/app/kachel_log.py), fetched in
pieces: the end for the editor, the whole log (its end at most) as a file."""
import asyncio
import datetime
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel  # noqa: E402
import kachel_log  # noqa: E402


class Device:
    """The action as fire-app's plan has it: {text, next, size} from `offset`, at most `max` bytes."""
    def __init__(self, logs, services=None):
        self.logs = {name: text.encode('utf-8') for name, text in logs.items()}
        self.services = services if services is not None else {'esphome': {'fire_test_log': {}, 'fire_test_screen_message': {}}}
        self.calls = []

    async def call_answer(self, domain, service, data):
        self.calls.append((domain, service, data))
        log = self.logs[data['source']]
        piece = log[data['offset']:data['offset'] + min(data['max'], kachel_log.CHUNK)]
        end = data['offset'] + len(piece)
        return {'text': piece.decode('utf-8', 'replace'), 'next': end if end < len(log) else None, 'size': len(log)}


class Manager:
    def __init__(self, ha, screen=None):
        self.ha = ha
        self._screen = screen if screen is not None else {'id': 'text.fire_test_kachel_inbox', 'node': 'fire-test', 'name': 'Fire'}

    def screen(self, inbox):
        return self._screen if inbox == self._screen.get('id') else None


def run(coro):
    return asyncio.run(coro)


class Action(unittest.TestCase):
    def test_found_by_node(self):
        manager = Manager(Device({}))
        self.assertEqual(kachel_log.action_of(manager, manager._screen), ('esphome', 'fire_test_log'))

    def test_under_the_kachel_integration(self):
        manager = Manager(Device({}, {'kachel': {'fire_test_log': {}}}))
        kachel.NODE_DOMAINS['fire_test'] = 'kachel'
        try:
            self.assertEqual(kachel_log.action_of(manager, manager._screen), ('kachel', 'fire_test_log'))
        finally:
            kachel.NODE_DOMAINS.pop('fire_test', None)

    def test_none_without_the_action(self):
        manager = Manager(Device({'kacheld': 'x'}, {'esphome': {'fire_test_screen_message': {}}}))
        self.assertIsNone(kachel_log.action_of(manager, manager._screen))
        self.assertEqual(run(kachel_log.tail(manager, 'text.fire_test_kachel_inbox', 'kacheld')),
                         {'available': False, 'source': 'kacheld'})
        with self.assertRaises(ValueError):
            run(kachel_log.download(manager, 'text.fire_test_kachel_inbox', 'all'))


class Tail(unittest.TestCase):
    def test_short_log_in_one_call(self):
        device = Device({'kacheld': 'one\ntwo\n'})
        out = run(kachel_log.tail(Manager(device), 'text.fire_test_kachel_inbox', 'kacheld'))
        self.assertEqual(out, {'available': True, 'source': 'kacheld', 'text': 'one\ntwo\n', 'size': 8, 'cut': False})
        self.assertEqual(device.calls, [('esphome', 'fire_test_log', {'source': 'kacheld', 'offset': 0, 'max': kachel_log.CHUNK})])

    def test_long_log_gives_its_end_on_a_whole_line(self):
        lines = ''.join(f'line {i:06d}\n' for i in range(20000))   # 240 000 bytes
        device = Device({'kacheld': lines})
        out = run(kachel_log.tail(Manager(device), 'text.fire_test_kachel_inbox', 'kacheld'))
        self.assertTrue(out['cut'])
        self.assertEqual(out['size'], len(lines))
        self.assertTrue(out['text'].startswith('line '))
        self.assertTrue(out['text'].endswith('line 019999\n'))
        self.assertTrue(lines.endswith(out['text']))
        self.assertLessEqual(len(out['text']), kachel_log.TAIL)

    def test_unknown_source_and_screen(self):
        manager = Manager(Device({}))
        with self.assertRaises(ValueError):
            run(kachel_log.tail(manager, 'text.fire_test_kachel_inbox', '/etc/passwd'))
        with self.assertRaises(ValueError):
            run(kachel_log.tail(manager, 'text.other', 'kacheld'))

    def test_bad_answer(self):
        class Odd(Device):
            async def call_answer(self, domain, service, data):
                return {'text': 5}
        with self.assertRaises(ValueError):
            run(kachel_log.tail(Manager(Odd({})), 'text.fire_test_kachel_inbox', 'kacheld'))

    def test_wrapped_answer(self):
        class Wrapped(Device):
            async def call_answer(self, domain, service, data):
                return {'response': await super().call_answer(domain, service, data)}
        out = run(kachel_log.tail(Manager(Wrapped({'boot': 'ok\n'})), 'text.fire_test_kachel_inbox', 'boot'))
        self.assertEqual(out['text'], 'ok\n')

    def test_device_that_goes_backwards_stops(self):
        class Stuck(Device):
            async def call_answer(self, domain, service, data):
                return {'text': 'x' * 10, 'next': 5, 'size': 10 ** 9}
        out = run(kachel_log.tail(Manager(Stuck({})), 'text.fire_test_kachel_inbox', 'kacheld'))
        self.assertEqual(out['text'], 'x' * 10)


class Download(unittest.TestCase):
    def test_both_logs_in_one_file(self):
        device = Device({'kacheld': 'app line\n', 'boot': 'boot line\n'})
        name, text = run(kachel_log.download(Manager(device), 'text.fire_test_kachel_inbox', 'all'))
        self.assertRegex(name, r'^kachel-log-fire-test-\d{4}-\d\d-\d\d-\d{4}\.txt$')
        self.assertIn('===== kacheld =====\napp line\n', text)
        self.assertIn('===== boot =====\nboot line\n', text)
        self.assertTrue(text.startswith('Kachel log of Fire (fire-test)'))

    def test_whole_log_across_pieces(self):
        lines = ''.join(f'{i}\n' for i in range(60000))
        _, text = run(kachel_log.download(Manager(Device({'kacheld': lines})), 'text.fire_test_kachel_inbox', 'kacheld'))
        self.assertTrue(text.endswith('===== kacheld =====\n' + lines))

    def test_file_name_is_safe(self):
        when = datetime.datetime(2026, 11, 19, 19, 5)
        self.assertEqual(kachel_log.file_name({'node': '../Evil Node'}, when), 'kachel-log-evil-node-2026-11-19-1905.txt')


class Texts(unittest.TestCase):
    def test_english_and_german(self):
        for lang in ('en', 'de'):
            data = json.loads((ROOT / f'screen_manager/translations/{lang}.json').read_text())
            self.assertEqual(set(data['addon']['errors']['kachel_log']), {'none', 'no_answer', 'source'})
            self.assertIn('download', data['editor']['screen_settings']['kachel_log'])


class OldName(unittest.TestCase):
    def setUp(self):
        kachel_log._old_only.clear()

    def tearDown(self):
        kachel_log._old_only.clear()

    def test_a_device_that_knows_only_echod_is_asked_by_it(self):
        class Old(Device):
            async def call_answer(self, domain, service, data):
                if data['source'] == 'kacheld':
                    self.calls.append((domain, service, data))
                    raise RuntimeError('unknown source')
                return await super().call_answer(domain, service, data)
        device = Old({'echod': 'old app\n'})
        out = run(kachel_log.tail(Manager(device), 'text.fire_test_kachel_inbox', 'kacheld'))
        self.assertEqual(out['text'], 'old app\n')
        run(kachel_log.tail(Manager(device), 'text.fire_test_kachel_inbox', 'echod'))
        self.assertEqual([call[2]['source'] for call in device.calls].count('kacheld'), 1, 'asked by the old name from then on')


if __name__ == '__main__':
    unittest.main()
