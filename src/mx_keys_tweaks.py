#!/usr/bin/python3
"""Event-driven GNOME Alt/Super switching for one Logitech MX Keys."""
import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

APP = 'mx-keys-ubuntu-tweaks-alt-swapped-win'
OPTION = 'altwin:swap_alt_win'
SCHEMA = 'org.gnome.desktop.input-sources'
KEY = 'xkb-options'
LOG = logging.getLogger(APP)


def paths():
    home = Path.home()
    config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    return config / APP / 'config.json', data / APP / 'mx_keys_tweaks.py', config / 'systemd/user' / (APP + '.service')


def normalize_id(value):
    return value.strip().lower().replace(':', '').replace('-', '')


def parse_properties(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def is_target(properties, device_id):
    return (normalize_id(properties.get('POWER_SUPPLY_SERIAL_NUMBER', '')) == normalize_id(device_id)
            and properties.get('POWER_SUPPLY_MANUFACTURER', '').lower() == 'logitech')


def available(records, device_id):
    return any(is_target(record, device_id) and record.get('POWER_SUPPLY_ONLINE') == '1' for record in records)


def scan_records(root=Path('/sys/class/power_supply')):
    records = []
    for entry in root.glob('*/uevent'):
        try:
            records.append(parse_properties(entry.read_text()))
        except OSError:
            # A removal can race with enumeration.
            continue
    return records


def desired_options(current, online, baseline):
    # Own only the altwin group, preserving unrelated changes made while running.
    other = [option for option in current if not option.startswith('altwin:')]
    target = [OPTION] if online else baseline
    return other + list(target)


def load_config(path):
    config = json.loads(path.read_text())
    if not normalize_id(config.get('device_id', '')):
        raise ValueError('Missing device_id in configuration')
    baseline = config.get('baseline_altwin', [])
    if not isinstance(baseline, list) or any(not isinstance(v, str) or not v.startswith('altwin:') for v in baseline):
        raise ValueError('Invalid baseline_altwin configuration')
    return config


def gi_modules():
    import gi
    gi.require_version('GUdev', '1.0')
    from gi.repository import Gio, GLib, GUdev
    return Gio, GLib, GUdev


def settings_object():
    Gio, _, _ = gi_modules()
    return Gio.Settings.new(SCHEMA)


def apply(settings, online, baseline):
    current = list(settings.get_strv(KEY))
    desired = desired_options(current, online, baseline)
    if current == desired:
        return False
    if not settings.set_strv(KEY, desired):
        raise RuntimeError('GNOME rejected the keyboard settings write')
    LOG.info('Keyboard %s; xkb-options=%s', 'available' if online else 'unavailable', desired)
    return True


def restore(config):
    Gio, _, _ = gi_modules()
    apply(settings_object(), False, config['baseline_altwin'])
    Gio.Settings.sync()


def supported_ubuntu(release):
    version = release.get('VERSION_ID', '').strip('"')
    try:
        supported = tuple(int(v) for v in version.split('.')) >= (24, 4)
    except ValueError:
        supported = False
    return release.get('ID', '').strip('"') == 'ubuntu' and supported


def validate():
    errors = []
    release = parse_properties(Path('/etc/os-release').read_text())
    if not supported_ubuntu(release):
        errors.append('Ubuntu 24.04 or newer is required (Ubuntu derivatives are not validated).')
    for package in ('gnome-tweaks', 'python3-gi', 'gir1.2-gudev-1.0', 'libglib2.0-bin', 'systemd', 'udev', 'dconf-gsettings-backend', 'gsettings-desktop-schemas'):
        result = subprocess.run(['dpkg-query', '-W', '-f=${Status}', package], capture_output=True, text=True)
        if result.returncode or result.stdout != 'install ok installed':
            errors.append('Missing package: ' + package)
    for command in ('systemctl', 'udevadm', 'gsettings'):
        if not shutil.which(command):
            errors.append('Missing command: ' + command)
    if os.geteuid() == 0:
        errors.append('Run as your desktop user, without sudo.')
    try:
        Gio, _, _ = gi_modules()
        Gio.bus_get_sync(Gio.BusType.SESSION, None)
        schema = Gio.SettingsSchemaSource.get_default().lookup(SCHEMA, True)
        if schema is None or not schema.has_key(KEY):
            errors.append('GNOME input-sources schema is unavailable.')
        elif not settings_object().is_writable(KEY):
            errors.append('GNOME keyboard settings are locked.')
    except Exception as exc:
        errors.append('Gio/GUdev/session bus unavailable: ' + str(exc))
    if shutil.which('systemctl'):
        result = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'graphical-session.target'])
        if result.returncode:
            errors.append('Run inside an active GNOME graphical session.')
    if 'gnome' not in os.environ.get('XDG_CURRENT_DESKTOP', '').lower():
        errors.append('A GNOME desktop session is required.')
    for error in errors:
        print('FAIL: ' + error, file=sys.stderr)
    if not errors:
        print('OK: Ubuntu >=24.04, GNOME, Tweaks, Gio, GUdev and user service prerequisites available.')
    return not errors


def daemon(config):
    Gio, GLib, GUdev = gi_modules()
    settings = settings_object()
    loop = GLib.MainLoop()
    pending = None
    previous = None

    def reconcile():
        nonlocal pending, previous
        pending = None
        online = available(scan_records(), config['device_id'])
        if online != previous:
            LOG.info('MX Keys availability: %s', online)
            previous = online
        apply(settings, online, config['baseline_altwin'])
        Gio.Settings.sync()
        return GLib.SOURCE_REMOVE

    def schedule(*_args):
        nonlocal pending
        if pending is None:
            pending = GLib.timeout_add(250, reconcile)

    # Subscribe before taking the initial snapshot to avoid missing startup events.
    client = GUdev.Client.new(['power_supply', 'hid'])
    client.connect('uevent', schedule)
    settings.connect('changed::' + KEY, schedule)
    # Sleep/resume reconciliation is a one-shot action, never a polling timer.
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    def on_sleep(_connection, _sender, _path, _interface, _signal, params, _data):
        if not params.unpack()[0]:
            schedule()
    subscription = bus.signal_subscribe('org.freedesktop.login1', 'org.freedesktop.login1.Manager',
                                       'PrepareForSleep', '/org/freedesktop/login1', None,
                                       Gio.DBusSignalFlags.NONE, on_sleep, None)
    for number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, number, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
    try:
        reconcile()
        loop.run()
    finally:
        bus.signal_unsubscribe(subscription)
        restore(config)


def run_systemctl(*args):
    subprocess.run(['systemctl', '--user', *args], check=True)


def unit_quote(path):
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def install(device_id):
    if not validate():
        return 1
    config_path, program_path, unit_path = paths()
    if config_path.exists():
        config = load_config(config_path)
        if device_id and normalize_id(device_id) != normalize_id(config['device_id']):
            raise ValueError('Uninstall the existing device configuration before selecting another keyboard.')
    else:
        if not device_id:
            ids = {p.get('POWER_SUPPLY_SERIAL_NUMBER') for p in scan_records()
                   if p.get('POWER_SUPPLY_MANUFACTURER') == 'Logitech' and 'MX Keys' in p.get('POWER_SUPPLY_MODEL_NAME', '')}
            ids.discard(None)
            if len(ids) != 1:
                raise ValueError('Connect and turn on one MX Keys, or supply --device-id SERIAL.')
            device_id = ids.pop()
        current = list(settings_object().get_strv(KEY))
        config = {'device_id': device_id, 'baseline_altwin': [v for v in current if v.startswith('altwin:') and v != OPTION]}
    for directory in (config_path.parent, program_path.parent, unit_path.parent):
        directory.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        config_path.chmod(0o600)
    source = Path(__file__).resolve()
    if source != program_path.resolve():
        shutil.copy2(source, program_path)
    unit_path.write_text(f'''[Unit]
Description=Automatic Alt/Super swap for Logitech MX Keys
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {unit_quote(program_path)} daemon
ExecStopPost=/usr/bin/python3 {unit_quote(program_path)} restore
Restart=on-failure
RestartSec=3
UMask=0077

[Install]
WantedBy=graphical-session.target
''')
    run_systemctl('daemon-reload')
    run_systemctl('enable', APP + '.service')
    run_systemctl('restart', APP + '.service')
    print('Installed for device ' + config['device_id'])
    return 0


def uninstall():
    config_path, program_path, unit_path = paths()
    if unit_path.exists():
        run_systemctl('disable', '--now', APP + '.service')
    if config_path.exists():
        restore(load_config(config_path))
    for path in (unit_path, program_path, config_path):
        path.unlink(missing_ok=True)
    run_systemctl('daemon-reload')
    print('Uninstalled; baseline Alt/Win settings restored. Repository preserved.')
    return 0


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'install', 'uninstall', 'status', 'daemon', 'restore'])
    parser.add_argument('--device-id', help='Individual keyboard serial (not receiver USB product ID)')
    args = parser.parse_args()
    try:
        if args.command == 'validate':
            return 0 if validate() else 1
        if args.command == 'install':
            return install(args.device_id)
        if args.command == 'uninstall':
            return uninstall()
        config = load_config(paths()[0])
        if args.command == 'daemon':
            daemon(config)
        elif args.command == 'restore':
            restore(config)
        else:
            print('Device:', config['device_id'])
            print('Available:', available(scan_records(), config['device_id']))
            print('xkb-options:', list(settings_object().get_strv(KEY)))
            return subprocess.run(['systemctl', '--user', 'status', '--no-pager', APP + '.service']).returncode
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        LOG.error('%s', exc)
        return 1


if __name__ == '__main__':
    sys.exit(main())
