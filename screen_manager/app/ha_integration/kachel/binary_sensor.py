"""Kachel binary sensors."""

from __future__ import annotations

from aioesphomeapi import BinarySensorInfo, BinarySensorState
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform, enum_or_none


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    async_setup_platform(
        hass, entry, async_add_entities, "binary_sensor", {BinarySensorInfo: KachelBinarySensor}
    )


class KachelBinarySensor(KachelEntity, BinarySensorEntity):
    """A binary sensor of a Kachel device."""

    def _on_info(self, info: BinarySensorInfo) -> None:
        self._attr_device_class = enum_or_none(BinarySensorDeviceClass, info.device_class)

    @property
    def is_on(self) -> bool | None:
        """On or off; unknown while the device has no value."""
        if self._missing:
            return None
        assert isinstance(self._state, BinarySensorState)
        return self._state.state
