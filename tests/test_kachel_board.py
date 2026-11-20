"""Kachel Manager: a Kachel device's version and device name (screen_manager/app/kachel_board.py), shown in place of
Tessera's firmware number and ESP32 board."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel_board  # noqa: E402


def item(entity, name, device='fire', platform='kachel'):
    return {'entity_id': entity, 'original_name': name, 'device_id': device, 'platform': platform}


class HA:
    def __init__(self, registry, states):
        self.registry, self.states = registry, states
        self.devices = [{'id': 'fire'}, {'id': 'seiten', 'via_device_id': 'fire'}, {'id': 'other'}]


class Manager:
    def __init__(self, ha):
        self.ha = ha


SCREEN = {'id': 'text.philiponfire_seiten_kachel_inbox', 'device_id': 'seiten'}


class Info(unittest.TestCase):
    def test_the_fire(self):
        ha = HA([item('sensor.philiponfire_kachel_version', 'Kachel version'),
                 item('sensor.philiponfire_kachel_board', 'Kachel board'),
                 item('sensor.other_kachel_board', 'Kachel board', 'other')],
                {'sensor.philiponfire_kachel_version': {'state': '0.0.9-dev5'},
                 'sensor.philiponfire_kachel_board': {'state': 'fire8'},
                 'sensor.other_kachel_board': {'state': 'a12s'}})
        self.assertEqual(kachel_board.info(Manager(ha), SCREEN),
                         {'version': '0.0.9-dev5', 'board': 'fire8', 'device': 'Amazon Fire HD 8 Plus'})

    def test_the_update_entity_and_an_unknown_board(self):
        ha = HA([item('update.x_firmware', 'Firmware', platform='esphome'), item('sensor.x_kachel_board', 'Kachel board')],
                {'update.x_firmware': {'state': 'off', 'attributes': {'installed_version': '3.1.0'}},
                 'sensor.x_kachel_board': {'state': 'newboard'}})
        self.assertEqual(kachel_board.info(Manager(ha), SCREEN), {'version': '3.1.0', 'board': 'newboard', 'device': 'newboard'})

    def test_nothing_known(self):
        ha = HA([item('sensor.x_kachel_version', 'Kachel version')], {'sensor.x_kachel_version': {'state': 'unavailable'}})
        self.assertIsNone(kachel_board.info(Manager(ha), SCREEN))
        self.assertIsNone(kachel_board.info(Manager(ha), {'id': 'x'}))


if __name__ == '__main__':
    unittest.main()
