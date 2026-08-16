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

## Options

| Option | Default | Meaning |
|---|---|---|
| `log_level` | `info` | `trace`, `debug`, `info`, `warning`, `error` |
| `update_check_interval_hours` | `6` | How often to check for new refs. `0` disables checking. |
| `auto_lock_minutes` | `0` | Idle minutes before the vault locks itself. `0` never auto-locks. |
| `notify_on_update` | `true` | Raise a persistent notification when updates are available. |

## Credential tiers

Every repository credential sits in one of two tiers. You choose per repository.

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

## Restoring from a backup

Protected-tier credentials restore normally, because their key is your passphrase.
Unattended-tier credentials do not, because the key file is deliberately excluded from
backups. After restoring to new hardware you will need to re-enter those credentials.
