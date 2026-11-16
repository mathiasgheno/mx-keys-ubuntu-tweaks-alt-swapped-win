import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('mx', Path(__file__).resolve().parents[1] / 'src/mx_keys_tweaks.py')
mx = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mx)
SERIAL = 'aa-bb-cc-dd'


def record(online='1', serial=SERIAL):
    return {'POWER_SUPPLY_MANUFACTURER': 'Logitech', 'POWER_SUPPLY_SERIAL_NUMBER': serial, 'POWER_SUPPLY_ONLINE': online}


class FakeSettings:
    def __init__(self, options, writable=True):
        self.options = options
        self.writes = []
        self.writable = writable

    def get_strv(self, _key):
        return self.options[:]

    def set_strv(self, _key, options):
        self.writes.append(options)
        if self.writable:
            self.options = options
        return self.writable


class PlatformTests(unittest.TestCase):
    def test_supported_releases(self):
        for version in ('24.04', '24.10', '26.04'):
            with self.subTest(version=version):
                self.assertTrue(mx.supported_ubuntu({'ID': 'ubuntu', 'VERSION_ID': version}))

    def test_old_ubuntu_and_other_distributions_rejected(self):
        for release in ({'ID': 'ubuntu', 'VERSION_ID': '22.04'},
                        {'ID': 'linuxmint', 'VERSION_ID': '26.04'},
                        {'ID': 'ubuntu', 'VERSION_ID': 'invalid'}, {}):
            with self.subTest(release=release):
                self.assertFalse(mx.supported_ubuntu(release))


class AvailabilityTests(unittest.TestCase):
    def test_connected(self):
        self.assertTrue(mx.available([record()], SERIAL))

    def test_off_with_receiver_present(self):
        self.assertFalse(mx.available([record('0')], SERIAL))

    def test_receiver_removed(self):
        self.assertFalse(mx.available([], SERIAL))

    def test_paired_but_never_online(self):
        self.assertFalse(mx.available([{'HID_UNIQ': SERIAL, 'HID_NAME': 'Logitech MX Keys'}], SERIAL))

    def test_other_keyboard_does_not_trigger(self):
        self.assertFalse(mx.available([record(serial='11-22-33-44')], SERIAL))

    def test_missing_state_is_not_online(self):
        value = record()
        del value['POWER_SUPPLY_ONLINE']
        self.assertFalse(mx.available([value], SERIAL))

    def test_serial_format_normalized(self):
        self.assertTrue(mx.available([record(serial='AA:BB:CC:DD')], SERIAL))

    def test_non_logitech_does_not_trigger(self):
        value = record()
        value['POWER_SUPPLY_MANUFACTURER'] = 'Other'
        self.assertFalse(mx.available([value], SERIAL))

    def test_new_battery_number_after_reconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / 'hidpp_battery_5'
            old.mkdir()
            (old / 'uevent').write_text('\n'.join(k + '=' + v for k, v in record('0').items()))
            self.assertFalse(mx.available(mx.scan_records(root), SERIAL))
            (old / 'uevent').unlink()
            old.rmdir()
            new = root / 'hidpp_battery_99'
            new.mkdir()
            (new / 'uevent').write_text('\n'.join(k + '=' + v for k, v in record().items()))
            self.assertTrue(mx.available(mx.scan_records(root), SERIAL))

    def test_vanished_sysfs_file_is_tolerated(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Path, 'glob', return_value=[Path(directory) / 'removed/uevent']):
                self.assertEqual(mx.scan_records(Path(directory)), [])


class SettingsTests(unittest.TestCase):
    def test_connect_disconnect_cycle_preserves_other_options(self):
        settings = FakeSettings(['compose:ralt'])
        self.assertTrue(mx.apply(settings, True, []))
        self.assertEqual(settings.options, ['compose:ralt', mx.OPTION])
        settings.options.insert(0, 'caps:escape')
        self.assertTrue(mx.apply(settings, False, []))
        self.assertEqual(settings.options, ['caps:escape', 'compose:ralt'])

    def test_duplicate_events_do_not_write_again(self):
        settings = FakeSettings([])
        mx.apply(settings, True, [])
        self.assertFalse(mx.apply(settings, True, []))
        self.assertEqual(len(settings.writes), 1)

    def test_conflicting_altwin_option_restored(self):
        settings = FakeSettings(['altwin:meta_alt', 'caps:escape'])
        baseline = ['altwin:meta_alt']
        mx.apply(settings, True, baseline)
        self.assertEqual(settings.options, ['caps:escape', mx.OPTION])
        mx.apply(settings, False, baseline)
        self.assertEqual(settings.options, ['caps:escape', 'altwin:meta_alt'])

    def test_rejected_write_is_an_error(self):
        with self.assertRaises(RuntimeError):
            mx.apply(FakeSettings([], writable=False), True, [])

    def test_invalid_config_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text('{"device_id":"aa", "baseline_altwin":["caps:escape"]}')
            with self.assertRaises(ValueError):
                mx.load_config(config)

    def test_systemd_paths_escape_spaces_and_specifiers(self):
        self.assertEqual(mx.unit_quote('/home/name %/app.py'), '"/home/name %%/app.py"')


if __name__ == '__main__':
    unittest.main()
