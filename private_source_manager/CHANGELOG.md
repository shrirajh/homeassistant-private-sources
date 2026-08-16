# Changelog

## 0.2.0

- Show the panel in the sidebar. `ingress_panel` was missing, so the panel existed but
  could only be reached through the add-on page.
- Follow the active Home Assistant theme. Ingress serves the panel in its own document, so
  nothing cascades in from the frontend; the theme is now fetched and applied to the root
  element, where custom properties inherit through shadow DOM. The built in palette also
  matches Home Assistant's own default light and dark values rather than approximating them.
- Remove the white border around the panel, caused by the iframe document keeping its
  default body margin with no background.
- Rolling releases actually roll. A repository tracking a branch reported its installed
  version as the available one, so `update_available` was permanently false and a moving
  branch never registered. The branch head is now the available version, and the channel
  can be switched between newest tag and a chosen branch after adding, with a branch picker.
- Clearing a repository's credential stores NULL rather than an empty string, which would
  have violated the foreign key onto credentials.

## 0.1.3

- Grant `k` on every writable path in the AppArmor profile. SQLite takes an fcntl advisory
  lock on any database it opens and an exclusive one to enter WAL mode, so without it the
  add-on died at startup with a misleading `database is locked`. Also grants `l`, for the
  hard links git makes when cloning a local repository.
- `tools/check_apparmor.py` now fails any rule that grants write without `k`, so a writable
  path that cannot be locked is rejected before it ships.

## 0.1.2

- Grant `m` as well as `r` in the AppArmor profile. Loading a shared library is an
  executable mmap, so read alone left the dynamic linker unable to map `libpython`,
  and the add-on exited with code 127.
- `tools/check_apparmor.py` now verifies mmap coverage for the loader, every `ldd`
  dependency and every compiled Python extension module, alongside the existing execute
  coverage. It also re-checks each path with `x86_64` swapped for `aarch64`, so a rule
  that hard codes one architecture fails the build instead of only failing on the device.

## 0.1.1

- Grant execute on `/usr/lib/bashio/**` in the AppArmor profile. `/usr/bin/bashio` is a
  symlink and AppArmor matches the resolved path, so the add-on could not start.
- Grant execute on `/opt/psm/psm/bin/**`, without which git could not run the askpass
  helper and token authentication would have failed.
- `tools/check_apparmor.py` resolves every entry point in a built image and fails if the
  profile does not cover it, so this class of gap cannot ship again.

## 0.1.0

First release.

- Install integrations, Lovelace cards, themes, python scripts, AppDaemon apps and Home
  Assistant add-ons from private git repositories.
- Per repository credentials: generated Ed25519 deploy keys, imported keys, or access
  tokens. Secrets are encrypted at rest and never reach a process listing or `.git/config`.
- Two credential tiers. Unattended credentials are wrapped by a key file and keep background
  updates running after a reboot. Protected credentials are wrapped by a passphrase that is
  never written to disk, so the vault locks on every restart.
- HACS compatible layout detection, including `hacs.json` handling for `content_in_root`,
  `filename`, `persistent_directory`, `zip_release` and a minimum Home Assistant version.
- Transactional installs with a sha256 file manifest. Uninstall refuses to delete files you
  have edited locally.
- Pinned host keys for GitHub and GitLab, with a scan and confirm flow for anything else.
- Periodic update checks with persistent notifications, skipping protected repositories
  while the vault is locked.
