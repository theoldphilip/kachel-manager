"""Kachel update entity: echod's own update (it fetches its releases itself)."""

from __future__ import annotations

from typing import Any

from aioesphomeapi import UpdateCommand, UpdateInfo, UpdateState
from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform, enum_or_none


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up update entities."""
    async_setup_platform(hass, entry, async_add_entities, "update", {UpdateInfo: KachelUpdate})


class KachelUpdate(KachelEntity, UpdateEntity):
    """The firmware update of a Kachel device."""

    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    def _on_info(self, info: UpdateInfo) -> None:
        self._attr_device_class = enum_or_none(UpdateDeviceClass, info.device_class)

    @property
    def _update(self) -> UpdateState | None:
        return None if self._missing else self._state  # type: ignore[return-value]

    @property
    def installed_version(self) -> str | None:
        """The version running."""
        return None if (s := self._update) is None else s.current_version or None

    @property
    def latest_version(self) -> str | None:
        """The newest version offered."""
        return None if (s := self._update) is None else s.latest_version or None

    @property
    def title(self) -> str | None:
        """The release's title."""
        return None if (s := self._update) is None else s.title or None

    @property
    def release_summary(self) -> str | None:
        """What is new (Home Assistant shows at most 255 characters)."""
        return None if (s := self._update) is None else (s.release_summary[:255] or None)

    @property
    def release_url(self) -> str | None:
        """Where the release is described."""
        return None if (s := self._update) is None else s.release_url or None

    @property
    def in_progress(self) -> bool:
        """An install is running."""
        return False if (s := self._update) is None else s.in_progress

    @property
    def update_percentage(self) -> int | None:
        """How far the install is."""
        if (s := self._update) is None or not s.in_progress or not s.has_progress:
            return None
        return round(s.progress)

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install the offered version (echod fetches and installs it itself)."""
        self._client.update_command(self._key, UpdateCommand.INSTALL, device_id=self._device_id)

    async def async_update(self) -> None:
        """Home Assistant's "check for update": ask the device to look."""
        if self.available:
            self._client.update_command(self._key, UpdateCommand.CHECK, device_id=self._device_id)
