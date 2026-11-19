"""Kachel buttons."""

from __future__ import annotations

from aioesphomeapi import ButtonInfo
from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform, enum_or_none


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    async_setup_platform(hass, entry, async_add_entities, "button", {ButtonInfo: KachelButton})


class KachelButton(KachelEntity, ButtonEntity):
    """A button of a Kachel device."""

    def _on_info(self, info: ButtonInfo) -> None:
        self._attr_device_class = enum_or_none(ButtonDeviceClass, info.device_class)

    async def async_press(self) -> None:
        """Press it on the device."""
        self._client.button_command(self._key, device_id=self._device_id)
