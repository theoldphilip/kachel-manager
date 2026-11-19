"""Kachel selects."""

from __future__ import annotations

from aioesphomeapi import SelectInfo, SelectState
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects."""
    async_setup_platform(hass, entry, async_add_entities, "select", {SelectInfo: KachelSelect})


class KachelSelect(KachelEntity, SelectEntity):
    """A choice of a Kachel device."""

    def _on_info(self, info: SelectInfo) -> None:
        self._attr_options = list(info.options)

    @property
    def current_option(self) -> str | None:
        """The option chosen; unknown while the device has no value."""
        if self._missing:
            return None
        assert isinstance(self._state, SelectState)
        return self._state.state or None

    async def async_select_option(self, option: str) -> None:
        """Choose on the device."""
        self._client.select_command(self._key, option, device_id=self._device_id)
