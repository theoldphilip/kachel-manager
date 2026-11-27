"""Kachel Manager: the install profile for the first install from the browser (screen_manager/app/kachel_installer.py,
format v1 of kachel-installer-tool, 2026-11-27): signed with the board's key from the code, checked against the lists in
the code, files handed out only when size and sha256 match."""
import base64
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import kachel_installer as ki  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

CACHE = b'KACHEL-ERST' + b'\0' * 4085 + b'payload'
BOOT = b'boot' * 100


def profile():
    return {
        'format': 'kachel-install-profile', 'format_version': 1, 'min_manager': '0.1.19',
        'board': 'gta3xl', 'name': {'de': 'Samsung Galaxy Tab A 10.1 (SM-T510)', 'en': 'Samsung Galaxy Tab A 10.1 (SM-T510)'},
        'version': '3.3.1', 'protocol': 'odin', 'usb': [{'vid': '04e8', 'pid': '685d'}],
        'match': {'odin': {'pit_entries': 38, 'block_size': 512,
                           'partitions': {'BOOT': 65536, 'RECOVERY': 92160, 'VBMETA': 1024, 'SYSTEM': 6242304, 'CACHE': 311296}}},
        'confirm': [{'id': 'unlocked', 'text': 'Der Bootloader ist entsperrt.'}, {'id': 'wipe', 'text': 'Alles wird gelöscht.'}],
        'mode_entry': [{'text': 'Ausschalten.', 'image': 'modus-1.png'}, {'text': 'Lauter und Leiser halten, Kabel einstecken.'}],
        'leave_mode': [{'text': 'Leiser und Ein/Aus 7 Sekunden halten.'}],
        'files': {'cache.img': {'url': '3.3.1/cache.img', 'sha256': hashlib.sha256(CACHE).hexdigest(), 'size': len(CACHE)},
                  'boot.img': {'url': '3.3.1/boot.img', 'sha256': hashlib.sha256(BOOT).hexdigest(), 'size': len(BOOT)},
                  'modus-1.png': {'url': '3.3.1/modus-1.png', 'sha256': hashlib.sha256(b'png').hexdigest(), 'size': 3}},
        'write': [{'partition': 'CACHE', 'file': 'cache.img', 'max_size': 159383552},
                  {'partition': 'BOOT', 'file': 'boot.img', 'max_size': 33554432}],
        'never': ['BOOTLOADER', 'PARAM', 'RECOVERY', 'SYSTEM', 'USERDATA'],
        'erst': {'header': 'KACHEL-ERST', 'header_version': 1, 'file': 'cache.img', 'max_payload': 159379456},
        'after': {'reboot': True, 'first_boot_minutes': 10, 'text': 'Das Tablet richtet sich ein.'},
    }


class Check(unittest.TestCase):
    def test_the_example_is_fine(self):
        self.assertEqual(ki.check(profile(), '0.1.19'), [])

    def test_the_lists_in_the_code_win(self):
        for partition in ('RECOVERY', 'BOOTLOADER', 'UP_PARAM', 'SEC_EFS', 'SYSTEM', 'boot'):
            bad = profile()
            bad['write'][1]['partition'] = partition
            self.assertTrue(ki.check(bad, '0.1.19'), partition)
        self.assertTrue(ki.never_hit('up_param') and ki.never_hit('RPMB') and not ki.never_hit('CACHE'))
        for name in ki.ALLOWED['gta3xl'] + ki.ALLOWED['fire8']:
            self.assertFalse(ki.never_hit(name), 'no allowed name hits the never list: ' + name)

    def test_what_else_is_refused(self):
        cases = {
            'size 0': lambda p: p['files']['boot.img'].update(size=0),
            'larger than max_size': lambda p: p['write'][1].update(max_size=10),
            'newer format': lambda p: p.update(format_version=2),
            'newer manager': lambda p: p.update(min_manager='9.0.0'),
            'fastboot not yet': lambda p: p.update(protocol='fastboot'),
            'unknown board': lambda p: p.update(board='other'),
            'image missing': lambda p: p['mode_entry'].append({'text': 'x', 'image': 'nope.png'}),
            'bad sha256': lambda p: p['files']['boot.img'].update(sha256='abc'),
        }
        for reason, change in cases.items():
            bad = profile()
            change(bad)
            self.assertTrue(ki.check(bad, '0.1.19'), reason)


class Mirror(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        key = Ed25519PrivateKey.generate()
        self.key = key
        raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.keys = dict(ki.KEYS)
        ki.KEYS['gta3xl'] = base64.b64encode(raw).decode()

    def tearDown(self):
        ki.KEYS.clear()
        ki.KEYS.update(self.keys)
        self.tmp.cleanup()

    def publish(self, data, channel='dev', key=None):
        place = self.folder.joinpath(*ki.CHANNELS[channel])
        (place / '3.3.1').mkdir(parents=True, exist_ok=True)
        raw = json.dumps(data).encode()
        (place / ki.PROFILE).write_bytes(raw)
        (place / (ki.PROFILE + '.sig')).write_text(base64.b64encode((key or self.key).sign(raw)).decode() + '\n')
        (place / '3.3.1' / 'cache.img').write_bytes(CACHE)
        (place / '3.3.1' / 'boot.img').write_bytes(BOOT)
        return place

    def test_signed_profile_loads(self):
        self.publish(profile())
        loaded = ki.load('dev', self.folder, '0.1.19')
        self.assertEqual((loaded['problems'], loaded['profile']['board']), ([], 'gta3xl'))
        self.assertFalse(ki.load('stable', self.folder)['present'])

    def test_a_foreign_signature_or_a_changed_byte_is_refused(self):
        self.publish(profile(), key=Ed25519PrivateKey.generate())
        self.assertEqual(ki.load('dev', self.folder)['profile'], None)
        place = self.publish(profile())
        (place / ki.PROFILE).write_bytes((place / ki.PROFILE).read_bytes().replace(b'3.3.1', b'3.3.2', 1))
        self.assertIn('signature', ki.load('dev', self.folder)['problems'][0])

    def test_files_stay_in_the_mirror_and_must_match(self):
        self.publish(profile())
        data = ki.load('dev', self.folder)['profile']
        path = ki.file_path('dev', data, 'boot.img', self.folder)
        files = ki.Files()
        self.assertTrue(files.checked(path, len(BOOT), hashlib.sha256(BOOT).hexdigest()))
        self.assertFalse(files.checked(path, len(BOOT), hashlib.sha256(b'other').hexdigest()))
        escaping = copy.deepcopy(data)
        escaping['files']['boot.img']['url'] = '../../../../etc/passwd'
        self.assertIsNone(ki.file_path('dev', escaping, 'boot.img', self.folder))
        escaping['files']['boot.img']['url'] = 'https://example.org/boot.img'
        self.assertIsNone(ki.file_path('dev', escaping, 'boot.img', self.folder))


if __name__ == '__main__':
    unittest.main()
