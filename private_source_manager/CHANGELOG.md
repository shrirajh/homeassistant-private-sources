# Changelog

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
