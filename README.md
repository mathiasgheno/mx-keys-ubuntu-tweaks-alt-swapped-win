# mx-keys-ubuntu-tweaks-alt-swapped-win

Automatically enable GNOME Tweaks **“Alt is swapped with Win”** while one specific
Logitech MX Keys is available. Restore the baseline when the keyboard turns off
or its Unifying receiver is unplugged.

[Documentação em português](README.pt-BR.md) · [MIT license](LICENSE)

## Requirements

- Ubuntu **24.04 or newer**, GNOME desktop, active graphical user session.
- Logitech MX Keys with a kernel driver exposing HID++ battery `ONLINE` events.
  Tested locally on Ubuntu 24.04 with a Unifying receiver. Other Ubuntu releases,
  kernels, keyboards, Bolt and direct Bluetooth are not hardware-validated.
- GNOME Tweaks installed, although it does not need to remain open.
- Distribution packages: `python3`, `python3-gi`, `gir1.2-gudev-1.0`,
  `libglib2.0-bin`, `systemd`, `udev`, `dconf-gsettings-backend`,
  `gsettings-desktop-schemas`, `gnome-tweaks`. Git is needed to clone the repository.

Python uses its standard library plus distribution-provided PyGObject (Gio,
GLib and GUdev). No pip, npm, Solaar, root daemon, cron or polling loop is used.
These packages were already present on the development machine; other Ubuntu
installations may require packages. The validator reports missing prerequisites
and does not install anything automatically.

## Install

Run from a terminal in your GNOME session, **without sudo**:

```sh
git clone https://github.com/mathiasgheno/mx-keys-ubuntu-tweaks-alt-swapped-win.git
cd mx-keys-ubuntu-tweaks-alt-swapped-win
./scripts/validate.sh
# Connect the receiver and turn the keyboard on for automatic discovery:
./scripts/install.sh
```

To select an individual keyboard explicitly, including when it is disconnected:

```sh
./scripts/install.sh --device-id YOUR-KEYBOARD-SERIAL
```

The serial is `POWER_SUPPLY_SERIAL_NUMBER` in `/sys/class/power_supply/hidpp_battery_*/uevent`
when available, or `HID_UNIQ` in the keyboard HID device's `uevent` file. It is not
the receiver's USB product ID. Personal identifiers are kept in your local config,
not committed to this repository.

The installer validates Ubuntu and dependencies, copies the program outside the
checkout, saves the individual keyboard ID and baseline, and enables a user
systemd service immediately. Re-run it after pulling an update. Existing device
selection and baseline are preserved on reinstall. Uninstall before changing the
selected keyboard.

## Behavior

| State | Alt ↔ Win |
| --- | --- |
| Target keyboard reports `ONLINE=1` | Enabled |
| Target keyboard reports `ONLINE=0` | Baseline restored |
| Receiver removed or target battery device absent | Baseline restored |
| Login / service start / resume | Reconcile current availability once |
| Service stopped / uninstalled | Baseline restored |

GUdev delivers kernel/udev events to one GLib main loop. A 250 ms one-shot timer
coalesces event bursts; there is no recurring device query. Discovery occurs at
startup, on events and after resume. The process remains resident and uses some
memory, while remaining idle between events. It does not read keystrokes or use
the network.

The preference is `org.gnome.desktop.input-sources xkb-options`, with the option
`altwin:swap_alt_win`. This is **session-wide**: the integrated keyboard is also
swapped while the MX Keys is available. Both left and right Alt/Super are swapped;
check AltGr behavior if you depend on it. The service owns the `altwin:` option
group while running and preserves unrelated options, including later changes.
Other `altwin:` preferences present at first install are restored on disconnect.
If swap is already enabled at first install, it is excluded from the baseline so
absence of the keyboard disables the swap as intended.

The service starts after graphical login, not at the login screen. Detection
latency depends on the hardware and kernel, and it cannot guarantee remapping
before the first keypress on wake. Sleep, radio loss, low battery and resume must
be tested on your hardware: a receiver that does not publish state changes cannot
be monitored reliably this way. No battery entry at startup is treated as offline.
We do not equate the receiver's presence, HID pairing, UPower `present`, or lack of
keypresses with a working keyboard connection.

## Manage

```sh
python3 src/mx_keys_tweaks.py status
journalctl --user -u mx-keys-ubuntu-tweaks-alt-swapped-win.service -n 50 --no-pager
systemctl --user stop mx-keys-ubuntu-tweaks-alt-swapped-win.service
systemctl --user start mx-keys-ubuntu-tweaks-alt-swapped-win.service
./scripts/uninstall.sh
```

The source checkout may be moved after installation. Installed files:

- `${XDG_DATA_HOME:-~/.local/share}/mx-keys-ubuntu-tweaks-alt-swapped-win/mx_keys_tweaks.py`
- `${XDG_CONFIG_HOME:-~/.config}/mx-keys-ubuntu-tweaks-alt-swapped-win/config.json`
- `${XDG_CONFIG_HOME:-~/.config}/systemd/user/mx-keys-ubuntu-tweaks-alt-swapped-win.service`

Uninstall removes these files and restores baseline settings, preserving this
repository. A forced process termination is handled by systemd's `ExecStopPost`
when possible. A power failure can leave the last saved setting until next login,
when the service reconciles it. If installation fails after writing its files,
fix the reported issue and rerun the installer or use the uninstaller.

## Tests and contributions

```sh
python3 -m unittest discover -s tests -v
```

Unit tests run without hardware or GI and cover individual identity, online/offline
states, missing devices, changing sysfs paths, removal races, duplicate events,
option preservation and rejected settings writes. CI runs these on Ubuntu 24.04.
They do not replace hardware integration tests.

Manual acceptance: test login with keyboard on/off, receiver removal while on/off,
receiver insertion while on/off, keyboard power off/on with receiver attached,
idle sleep/wake, suspend/resume, unrelated keyboard options, service restart,
reinstall and uninstall. Watch the journal and `gsettings get
org.gnome.desktop.input-sources xkb-options` after each transition. Never use
`sudo` to change your user's GSettings.

Contributions are welcome via issues and pull requests. Include Ubuntu/kernel,
receiver type, sanitized event samples and reproduction steps. Use focused commits
for each requested feature and run the tests and validator before submission.

## Technical references

- [Linux Logitech HID++ driver](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-hidpp.c)
- [GUdev Client API](https://gudev.github.io/gudev/GUdevClient.html)
- [Gio.Settings](https://docs.gtk.org/gio/class.Settings.html)

## Optional Portuguese cedilla composition

To make acute/apostrophe followed by C produce `ç` (and uppercase `Ç`), run:

```sh
python3 scripts/install-cedilla.py
```

This adds two personal `~/.XCompose` rules, independently of keyboard connection.
Existing content is preserved and backed up to `~/.XCompose.before-cedilla` on
first modification. A new file includes the locale's default rules (`%L`).
Reopening applications or logging out/in may be necessary. Application input
methods differ; check the applications you use. No system Compose files change.
To undo, remove the marked block, or restore the backup if you have made no
subsequent edits. The service uninstaller does not remove these optional rules.
