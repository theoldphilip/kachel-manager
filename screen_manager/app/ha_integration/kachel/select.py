"""Kachel selects."""

from __future__ import annotations

from aioesphomeapi import SelectInfo, SelectState
from homeassistant.components.assist_pipeline.select import (
    AssistPipelineSelect,
    VadSensitivitySelect,
)
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .const import DOMAIN
from .entity import KachelEntity, async_setup_platform
from .manager import KachelData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects: the device's own, and, once it offers a voice assistant, the pipeline and
    "finished speaking" choices Home Assistant keeps for it (as for an ESPHome satellite)."""
    async_setup_platform(hass, entry, async_add_entities, "select", {SelectInfo: KachelSelect})
    data = entry.runtime_data
    added = False

    @callback
    def on_connect() -> None:
        nonlocal added
        if added or not data.voice_features:
            return
        added = True
        async_add_entities(
            [KachelPipelineSelect(hass, data), KachelVadSensitivitySelect(hass, data)]
        )

    entry.async_on_unload(data.async_add_connect_listener(on_connect))


def _voice_prefix(data: KachelData) -> str:
    return f"{data.mac}-{data.adoption_id}" if data.adoption_id else data.mac


class _VoiceSelectMixin:
    """Belongs to the device; available while it is connected and offers a voice assistant."""

    _attr_has_entity_name = True
    _data: KachelData

    @property
    def available(self) -> bool:
        return self._data.available and bool(self._data.voice_features)


class KachelPipelineSelect(_VoiceSelectMixin, AssistPipelineSelect):
    """Which Assist pipeline the device's voice assistant uses."""

    def __init__(self, hass: HomeAssistant, data: KachelData) -> None:
        """Bind to the device."""
        self._data = data
        AssistPipelineSelect.__init__(self, hass, DOMAIN, _voice_prefix(data))
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, data.mac)})


class KachelVadSensitivitySelect(_VoiceSelectMixin, VadSensitivitySelect):
    """How quickly the assistant decides the speaker has finished."""

    def __init__(self, hass: HomeAssistant, data: KachelData) -> None:
        """Bind to the device."""
        self._data = data
        VadSensitivitySelect.__init__(self, hass, _voice_prefix(data))
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, data.mac)})


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
