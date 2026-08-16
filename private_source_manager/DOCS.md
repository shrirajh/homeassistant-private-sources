# Private Source Manager

HACS only installs from public GitHub repositories. This add-on covers the gap: it installs
and updates Home Assistant content from **private** git repositories, using a separate
credential per repository, kept in an encrypted vault.

## Installation

1. Settings → Add-ons → Add-on Store → ⋮ → Repositories.
2. Add `https://github.com/shrirajh/homeassistant-private-sources`.
3. Install **Private Source Manager**. The Supervisor builds the image on the device, which
   takes a few minutes on a Home Assistant Green.
4. Start the add-on and open **Private Sources** in the sidebar.

## What it can install

| Category | Taken from | Installed to |
|---|---|---|
| Integration | `custom_components/<domain>/` | `/config/custom_components/<domain>/` |
| Lovelace card | `dist/`, else the matching root `.js` | `/config/www/community/<repo>/`, resource registered automatically |
| Theme | `themes/*.yaml` | `/config/themes/` |
| Python script | `python_scripts/*.py` | `/config/python_scripts/` |
| AppDaemon app | `apps/<name>/` | `/config/appdaemon/apps/<name>/` |
| Home Assistant add-on | the whole repository | `/addons/<name>/`, store reloaded automatically |

The category is detected from the repository layout and can be overridden. `hacs.json` is
honoured for `name`, `content_in_root`, `filename`, `hide_default_branch`, `zip_release`,
`persistent_directory` and a minimum `homeassistant` version, so repositories written for
HACS work unchanged.

Integrations only load after a Home Assistant restart, offered as a button on the Settings
tab. Cards and themes take effect immediately.

## Credentials

Each repository gets its own credential, so one leak exposes one repository.

**SSH deploy key.** The add-on generates an Ed25519 key and shows you the public half to
paste into the repository's deploy keys on GitHub or GitLab. The private half never leaves
the vault, and during a git operation is written only to `/tmp`, which is a RAM filesystem.
You can also paste an existing unencrypted key.

**Access token.** A fine-grained personal access token or project token. Tokens are handed
to git through an askpass helper, so they never appear in a process listing or in
`.git/config`. A token additionally unlocks release metadata and `zip_release` downloads
from the GitHub and GitLab APIs; a deploy key gives git access only.

## Credential tiers

Every credential sits in one of two tiers. You choose per credential.

**Unattended.** Encrypted with a key file on `/data`. Survives reboots, so these
repositories keep checking and installing updates without you being present.

**Protected.** Encrypted with your passphrase. The passphrase is never written to disk, so
the vault locks on every add-on restart and you must re-enter it before these repositories
can be reached.

Public keys, repository URLs, categories and installed versions are stored in plaintext, so
the UI stays browsable and deploy keys stay copyable while the vault is locked. Only the use
of a credential is blocked.

## What the encryption does and does not protect

Worth being precise about, because "encrypted at rest" is often oversold.

**Unattended tier** stops credentials appearing in a `grep` of `/data`, in the SQLite file,
in logs, and in Home Assistant backups. The key file is excluded from backups, so a backup
archive on its own contains nothing usable. It does **not** protect against an attacker who
already has root on the device, because the key file is sitting right there next to the
ciphertext.

**Protected tier** additionally protects against device theft and against an attacker who
holds both the backup and the disk, as long as the passphrase is strong. The realistic
attack is offline brute force, so the key derivation cost matters more than the login
lockout. The vault uses scrypt, calibrated at setup to take roughly 750 ms on your hardware.
Failed unlock attempts back off exponentially up to five minutes, and the counter survives
restarts.

**Neither tier** protects against another Home Assistant admin. Ingress means Home Assistant
has already authenticated whoever reaches this UI, and there is no second factor beyond the
passphrase.

**Memory.** The passphrase-derived key is held in a mutable buffer and overwritten on lock,
but Python cannot guarantee that no copy survives elsewhere in the process.

## Host key verification

GitHub and GitLab host keys are bundled and pinned, cross checked against
`https://api.github.com/meta`. Any other ssh host must be confirmed once: Settings → Trust a
git host scans the server and shows you the fingerprints. Check them against what the server
operator publishes before accepting. Accepted keys are appended to `/data/known_hosts`.

`StrictHostKeyChecking` is always on, so an unknown or changed host key fails the operation
rather than silently trusting it.

## Updates

Every `update_check_interval_hours` the add-on refreshes each repository and raises one
persistent notification listing what is available. Repositories marked **auto update**
install the new version themselves.

While the vault is locked, protected repositories are skipped and you get one reminder per
lock session, not one per check. Unattended repositories carry on.

Tag selection prefers stable releases and orders numerically, so `v1.10.0` is newer than
`v1.2.0`. A repository can instead track a branch, or be pinned to an exact tag, branch or
commit.

## Uninstalling content

Every installed file is recorded with its sha256. Uninstall removes only files that still
match what was installed and reports anything you have edited locally rather than silently
overwriting it. Empty directories are pruned, but shared ones such as `themes/` are never
touched.

## Options

| Option | Default | Meaning |
|---|---|---|
| `log_level` | `info` | `trace`, `debug`, `info`, `warning`, `error` |
| `update_check_interval_hours` | `6` | How often to check for new refs. `0` disables checking. |
| `auto_lock_minutes` | `0` | Idle minutes before the vault locks itself. `0` never auto-locks. |
| `notify_on_update` | `true` | Raise a persistent notification when updates are available. |

## Restoring from a backup

Protected-tier credentials restore normally, because their key is your passphrase.
Unattended-tier credentials do not, because the key file is deliberately excluded from
backups. After restoring to new hardware you will need to re-enter those credentials.

## Permissions

The add-on requests `hassio_role: manager`, which lowers its rating in the Home Assistant
UI. It needs that role for exactly two things: restarting Core after installing an
integration, and reloading the add-on store after cloning a private add-on. It also maps the
Home Assistant configuration directory and `/addons` read-write, because that is where the
content it installs has to go.

An AppArmor profile ships with the add-on. It reads broadly but writes only to `/data`, the
Home Assistant configuration directory, `/addons`, `/tmp` and `/run`, and denies writes to
the container's own account and ssh configuration.

Because AppArmor matches the resolved path rather than the symlink, every entry point the
add-on executes is checked against the profile in CI, resolved through its symlinks. If the
add-on ever fails to start with `unable to exec ... Permission denied`, set
`apparmor: false` in the add-on configuration to confirm the profile is the cause and please
open an issue.
