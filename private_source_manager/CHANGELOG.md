# Changelog

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
