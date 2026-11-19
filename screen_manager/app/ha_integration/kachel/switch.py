"""Kachel switches."""

from __future__ import annotations

from typing import Any

from aioesphomeapi import SwitchInfo, SwitchState
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform, enum_or_none


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    async_setup_platform(hass, entry, async_add_entities, "switch", {SwitchInfo: KachelSwitch})


class KachelSwitch(KachelEntity, SwitchEntity):
    """A switch of a Kachel device."""

    def _on_info(self, info: SwitchInfo) -> None:
        self._attr_device_class = enum_or_none(SwitchDeviceClass, info.device_class)
        self._attr_assumed_state = info.assumed_state

    @property
    def is_on(self) -> bool | None:
        """On or off; unknown while the device has no value."""
        if self._missing:
            return None
        assert isinstance(self._state, SwitchState)
        return self._state.state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn it on on the device."""
        self._client.switch_command(self._key, True, device_id=self._device_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn it off on the device."""
        self._client.switch_command(self._key, False, device_id=self._device_id)
