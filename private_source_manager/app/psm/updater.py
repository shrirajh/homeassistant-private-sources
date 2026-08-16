"""Periodic update checks, auto updates and notifications."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from .config import Settings
from .credentials import CredentialStore, UnknownCredential
from .hass import HomeAssistant
from .repos import Repo, RepositoryStore
from .vault import Vault

_LOGGER = logging.getLogger(__name__)

STARTUP_DELAY_SECONDS = 45
UPDATES_NOTIFICATION = "psm_updates_available"
LOCKED_NOTIFICATION = "psm_vault_locked"


@dataclass
class UpdateSummary:
    checked: int = 0
    skipped_locked: int = 0
    updates: list[str] = field(default_factory=list)
    upgraded: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "checked": self.checked,
            "skipped_locked": self.skipped_locked,
            "updates": self.updates,
            "upgraded": self.upgraded,
            "failed": self.failed,
        }


class Updater:
    def __init__(
        self,
        repos: RepositoryStore,
        credentials: CredentialStore,
        vault: Vault,
        hass: HomeAssistant,
        settings: Settings,
    ) -> None:
        self._repos = repos
        self._credentials = credentials
        self._vault = vault
        self._hass = hass
        self._settings = settings
        self._locked_notice_sent = False

    async def run_once(self) -> UpdateSummary:
        summary = UpdateSummary()

        for repo in self._repos.list():
            if not self._reachable(repo):
                summary.skipped_locked += 1
                continue

            try:
                refreshed = await self._repos.refresh(repo.id)
            except Exception as err:  # noqa: BLE001 - one bad repo must not stop the sweep
                _LOGGER.warning("Could not check %s: %s", repo.slug, err)
                summary.failed[repo.slug] = str(err)
                continue

            summary.checked += 1
            if not refreshed.update_available:
                continue

            summary.updates.append(f"{refreshed.slug} {refreshed.available_version}")
            if refreshed.auto_update:
                await self._auto_update(refreshed, summary)

        await self._announce(summary)
        return summary

    async def loop(self) -> None:
        interval = self._settings.update_interval_hours
        if interval <= 0:
            _LOGGER.info("Update checking is disabled")
            return

        await asyncio.sleep(STARTUP_DELAY_SECONDS)
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Update check failed")
            await asyncio.sleep(interval * 3600)

    def _reachable(self, repo: Repo) -> bool:
        """Protected tier repositories cannot be checked while the vault is locked."""
        if not repo.credential_id:
            return True
        try:
            credential = self._credentials.get(repo.credential_id)
        except UnknownCredential:
            return True
        return self._vault.available(credential.tier)

    async def _auto_update(self, repo: Repo, summary: UpdateSummary) -> None:
        try:
            await self._repos.install(repo.id)
        except Exception as err:  # noqa: BLE001 - a failed upgrade must not stop the sweep
            _LOGGER.warning("Auto update of %s failed: %s", repo.slug, err)
            summary.failed[repo.slug] = str(err)
            return
        summary.upgraded.append(repo.slug)
        summary.updates.remove(f"{repo.slug} {repo.available_version}")

    async def _announce(self, summary: UpdateSummary) -> None:
        if not self._hass.available:
            return

        if self._settings.notify_on_update:
            if summary.updates:
                lines = "\n".join(f"- {entry}" for entry in summary.updates)
                await self._hass.notify(
                    "Private source updates",
                    f"Updates are available for:\n{lines}",
                    UPDATES_NOTIFICATION,
                )
            else:
                await self._hass.dismiss(UPDATES_NOTIFICATION)

        if summary.upgraded:
            lines = "\n".join(f"- {slug}" for slug in summary.upgraded)
            await self._hass.notify(
                "Private sources updated",
                f"Installed updates for:\n{lines}\n\nRestart Home Assistant to load them.",
                "psm_auto_updated",
            )

        await self._announce_lock(summary)

    async def _announce_lock(self, summary: UpdateSummary) -> None:
        if not summary.skipped_locked:
            self._locked_notice_sent = False
            await self._hass.dismiss(LOCKED_NOTIFICATION)
            return

        # One reminder per lock session, not one per check.
        if self._locked_notice_sent:
            return
        self._locked_notice_sent = True
        await self._hass.notify(
            "Private source vault is locked",
            f"{summary.skipped_locked} protected repositories were not checked. "
            "Unlock the vault in the Private Sources panel to resume.",
            LOCKED_NOTIFICATION,
        )
