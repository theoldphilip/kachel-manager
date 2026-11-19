"""Kachel numbers."""

from __future__ import annotations

import math

from aioesphomeapi import NumberInfo, NumberMode as EspNumberMode, NumberState
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform, enum_or_none

_MODES = {
    EspNumberMode.AUTO: NumberMode.AUTO,
    EspNumberMode.BOX: NumberMode.BOX,
    EspNumberMode.SLIDER: NumberMode.SLIDER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers."""
    async_setup_platform(hass, entry, async_add_entities, "number", {NumberInfo: KachelNumber})


class KachelNumber(KachelEntity, NumberEntity):
    """A number of a Kachel device."""

    def _on_info(self, info: NumberInfo) -> None:
        self._attr_device_class = enum_or_none(NumberDeviceClass, info.device_class)
        self._attr_native_min_value = info.min_value
        self._attr_native_max_value = info.max_value
        self._attr_native_step = info.step
        self._attr_native_unit_of_measurement = info.unit_of_measurement or None
        self._attr_mode = _MODES.get(info.mode, NumberMode.AUTO)

    @property
    def native_value(self) -> float | None:
        """The value; unknown while the device has none."""
        if self._missing:
            return None
        assert isinstance(self._state, NumberState)
        if math.isnan(self._state.state):
            return None
        return self._state.state

    async def async_set_native_value(self, value: float) -> None:
        """Set on the device."""
        self._client.number_command(self._key, value, device_id=self._device_id)
