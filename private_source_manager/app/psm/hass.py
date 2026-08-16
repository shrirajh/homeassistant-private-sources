"""Home Assistant Supervisor and Core API client."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

SUPERVISOR = "http://supervisor"
WEBSOCKET = "ws://supervisor/core/websocket"
_TIMEOUT = aiohttp.ClientTimeout(total=60)


class HomeAssistantError(Exception):
    """A Supervisor or Core API call failed."""


class HomeAssistant:
    def __init__(self, token: str | None) -> None:
        self._token = token
        self._session: aiohttp.ClientSession | None = None
        self._command_id = 0

    @property
    def available(self) -> bool:
        return bool(self._token)

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def core_version(self) -> str | None:
        try:
            info = await self._request("GET", "/core/info")
        except HomeAssistantError as err:
            _LOGGER.debug("Could not read core info: %s", err)
            return None
        return (info.get("data") or {}).get("version")

    async def restart_core(self) -> None:
        await self._request("POST", "/core/restart")
        _LOGGER.info("Requested a Home Assistant Core restart")

    async def reload_store(self) -> None:
        await self._request("POST", "/store/reload")
        _LOGGER.info("Asked the Supervisor to rescan the add-on store")

    async def notify(self, title: str, message: str, notification_id: str) -> None:
        try:
            await self._request(
                "POST",
                "/core/api/services/persistent_notification/create",
                {"title": title, "message": message, "notification_id": notification_id},
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Could not raise notification: %s", err)

    async def dismiss(self, notification_id: str) -> None:
        try:
            await self._request(
                "POST",
                "/core/api/services/persistent_notification/dismiss",
                {"notification_id": notification_id},
            )
        except HomeAssistantError as err:
            _LOGGER.debug("Could not dismiss notification: %s", err)

    async def lovelace_resources(self) -> list[dict[str, Any]]:
        return await self._command({"type": "lovelace/resources"}) or []

    async def ensure_resource(self, url: str) -> str:
        """Make exactly one Lovelace resource point at this path, cache buster included."""
        base = url.split("?", 1)[0]
        for item in await self.lovelace_resources():
            if str(item.get("url", "")).split("?", 1)[0] != base:
                continue
            if item.get("url") == url:
                return "unchanged"
            await self._command(
                {"type": "lovelace/resources/update", "resource_id": item["id"], "url": url}
            )
            return "updated"

        await self._command({"type": "lovelace/resources/create", "res_type": "module", "url": url})
        return "created"

    async def remove_resource(self, url: str) -> bool:
        base = url.split("?", 1)[0]
        for item in await self.lovelace_resources():
            if str(item.get("url", "")).split("?", 1)[0] == base:
                await self._command(
                    {"type": "lovelace/resources/delete", "resource_id": item["id"]}
                )
                return True
        return False

    def _ensure_session(self) -> aiohttp.ClientSession:
        if not self.available:
            raise HomeAssistantError("no Supervisor token, this is not running as an add-on")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self._token}"}, timeout=_TIMEOUT
            )
        return self._session

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        session = self._ensure_session()
        try:
            async with session.request(method, f"{SUPERVISOR}{path}", json=payload) as response:
                body = await response.text()
                if response.status >= 400:
                    raise HomeAssistantError(f"{method} {path}: {response.status} {body[:200]}")
                if not body.strip():
                    return {}
                try:
                    return await response.json(content_type=None) or {}
                except ValueError:
                    return {}
        except aiohttp.ClientError as err:
            raise HomeAssistantError(f"{method} {path}: {err}") from err

    async def _command(self, message: dict[str, Any]) -> Any:
        session = self._ensure_session()
        try:
            async with session.ws_connect(WEBSOCKET, heartbeat=30) as socket:
                greeting = await socket.receive_json()
                if greeting.get("type") == "auth_required":
                    await socket.send_json({"type": "auth", "access_token": self._token})
                    outcome = await socket.receive_json()
                    if outcome.get("type") != "auth_ok":
                        raise HomeAssistantError("websocket authentication was rejected")

                self._command_id += 1
                await socket.send_json({"id": self._command_id, **message})
                while True:
                    reply = await socket.receive_json()
                    if reply.get("id") != self._command_id:
                        continue
                    if not reply.get("success", False):
                        detail = reply.get("error", {})
                        raise HomeAssistantError(
                            str(detail.get("message") or detail or "command failed")
                        )
                    return reply.get("result")
        except aiohttp.ClientError as err:
            raise HomeAssistantError(f"websocket: {err}") from err
        except TypeError as err:
            raise HomeAssistantError("unexpected websocket payload") from err
