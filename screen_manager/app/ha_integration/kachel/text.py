"""Kachel texts."""

from __future__ import annotations

from aioesphomeapi import TextInfo, TextMode as EspTextMode, TextState
from homeassistant.components.text import TextEntity, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up texts."""
    async_setup_platform(hass, entry, async_add_entities, "text", {TextInfo: KachelText})


class KachelText(KachelEntity, TextEntity):
    """A text of a Kachel device (for example the Kachel Manager's inbox)."""

    def _on_info(self, info: TextInfo) -> None:
        self._attr_native_min = info.min_length
        self._attr_native_max = info.max_length
        self._attr_pattern = info.pattern or None
        self._attr_mode = TextMode.PASSWORD if info.mode == EspTextMode.PASSWORD else TextMode.TEXT

    @property
    def native_value(self) -> str | None:
        """The text; unknown while the device has none."""
        if self._missing:
            return None
        assert isinstance(self._state, TextState)
        return self._state.state

    async def async_set_value(self, value: str) -> None:
        """Set on the device."""
        self._client.text_command(self._key, value, device_id=self._device_id)
