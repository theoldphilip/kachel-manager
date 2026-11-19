"""Kachel sensors (numeric sensors and text sensors)."""

from __future__ import annotations

from datetime import datetime
import math

from aioesphomeapi import (
    SensorInfo,
    SensorState,
    SensorStateClass as EspStateClass,
    TextSensorInfo,
    TextSensorState,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform, enum_or_none

_STATE_CLASSES = {
    EspStateClass.MEASUREMENT: SensorStateClass.MEASUREMENT,
    EspStateClass.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
    EspStateClass.TOTAL: SensorStateClass.TOTAL,
    EspStateClass.MEASUREMENT_ANGLE: SensorStateClass.MEASUREMENT_ANGLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    async_setup_platform(
        hass,
        entry,
        async_add_entities,
        "sensor",
        {SensorInfo: KachelSensor, TextSensorInfo: KachelTextSensor},
    )


class KachelSensor(KachelEntity, SensorEntity):
    """A numeric sensor of a Kachel device."""

    def _on_info(self, info: SensorInfo) -> None:
        self._attr_device_class = enum_or_none(SensorDeviceClass, info.device_class)
        self._attr_native_unit_of_measurement = info.unit_of_measurement or None
        self._attr_suggested_display_precision = info.accuracy_decimals
        self._attr_force_update = info.force_update
        self._attr_state_class = _STATE_CLASSES.get(info.state_class)

    @property
    def native_value(self) -> float | datetime | None:
        """The value; unknown while the device has none."""
        if self._missing:
            return None
        assert isinstance(self._state, SensorState)
        value = self._state.state
        if math.isnan(value) or math.isinf(value):
            return None
        if self.device_class is SensorDeviceClass.TIMESTAMP:
            return dt_util.utc_from_timestamp(value)
        return value


class KachelTextSensor(KachelEntity, SensorEntity):
    """A text sensor of a Kachel device."""

    def _on_info(self, info: TextSensorInfo) -> None:
        self._attr_device_class = enum_or_none(SensorDeviceClass, info.device_class)

    @property
    def native_value(self) -> str | datetime | None:
        """The text; unknown while the device has none."""
        if self._missing:
            return None
        assert isinstance(self._state, TextSensorState)
        value = self._state.state
        if self.device_class is SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(value)
        return value[:255]
