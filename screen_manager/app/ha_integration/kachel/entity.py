"""Common base of the Kachel entities.

Follows Home Assistant's ESPHome integration (homeassistant/components/esphome/entity.py, Apache-2.0,
see NOTICE): one entity per entity the device lists, its state pushed by the device.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

from aioesphomeapi import EntityCategory as EspEntityCategory, EntityInfo, EntityState
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .manager import KachelData, entity_key

if TYPE_CHECKING:
    from . import KachelConfigEntry

_LOGGER = logging.getLogger(__name__)

_CATEGORIES = {
    EspEntityCategory.CONFIG: EntityCategory.CONFIG,
    EspEntityCategory.DIAGNOSTIC: EntityCategory.DIAGNOSTIC,
}


def unique_id_for(mac: str, platform: str, info: EntityInfo, adoption_id: str = "") -> str:
    """The entity's unique id: the device's MAC, the adoption, the sub-device, the platform and the object id.

    Its own scheme (not ESPHome's), so an entity of this integration is never taken for one of
    the ESPHome integration's. The adoption id (const.CONF_ADOPTION_ID) is new with every adoption.
    """
    base = f"{mac}-{adoption_id}" if adoption_id else mac
    if info.device_id:
        return f"{base}-{info.device_id}-{platform}-{info.object_id}"
    return f"{base}-{platform}-{info.object_id}"


def enum_or_none[T](enum_type: Callable[[str], T], value: str) -> T | None:
    """A device class the device names, if Home Assistant knows it."""
    if not value:
        return None
    try:
        return enum_type(value)
    except ValueError:
        _LOGGER.debug("Kachel: unknown device class %s", value)
        return None


class KachelEntity(Entity):
    """One entity of a Kachel device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _info: EntityInfo
    _state: EntityState | None = None

    def __init__(self, data: KachelData, platform: str, info: EntityInfo) -> None:
        """Set up from the device's description of the entity."""
        self._data = data
        mac = data.mac
        self._attr_unique_id = unique_id_for(mac, platform, info, data.adoption_id)
        identifier = f"{mac}_{info.device_id}" if info.device_id else mac
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, identifier)})
        self._attr_name = info.name or None
        self._attr_icon = info.icon or None
        self._attr_entity_category = _CATEGORIES.get(info.entity_category)
        self._attr_entity_registry_enabled_default = not info.disabled_by_default
        self.async_set_info(info)

    @callback
    def async_set_info(self, info: EntityInfo) -> None:
        """The device described the entity (again, after a reconnect); keys may have changed."""
        self._info = info
        self._data.entities[entity_key(info)] = self
        self._state = self._data.states.get(entity_key(info))
        self._on_info(info)

    def _on_info(self, info: EntityInfo) -> None:
        """Read the platform's own fields from the description."""

    @callback
    def async_on_state(self, state: EntityState) -> None:
        """A new state from the device."""
        self._state = state
        if self.hass is not None and self.entity_id is not None:
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Available while the device is connected."""
        return self._data.available

    @property
    def _missing(self) -> bool:
        """The device has no value for this entity (yet)."""
        return self._state is None or bool(getattr(self._state, "missing_state", False))

    async def async_added_to_hass(self) -> None:
        """Follow the connection's coming and going."""
        self._data.availability_listeners.append(self._on_availability)
        self.async_on_remove(
            lambda: self._data.availability_listeners.remove(self._on_availability)
        )

    @callback
    def _on_availability(self) -> None:
        self.async_write_ha_state()

    @property
    def _client(self) -> Any:
        return self._data.client

    @property
    def _key(self) -> int:
        return self._info.key

    @property
    def _device_id(self) -> int:
        return self._info.device_id


@callback
def async_setup_platform(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    platform: str,
    entity_types: dict[type[EntityInfo], type[KachelEntity]],
) -> None:
    """Add a platform's entities now and after every reconnect that lists new ones."""
    data = entry.runtime_data
    known: dict[str, KachelEntity] = {}

    @callback
    def add_infos(infos: list[EntityInfo]) -> None:
        new: list[KachelEntity] = []
        for info in infos:
            uid = unique_id_for(data.mac, platform, info, data.adoption_id)
            if (entity := known.get(uid)) is not None:
                entity.async_set_info(info)
                if entity.hass is not None and entity.entity_id is not None:
                    entity.async_write_ha_state()
                continue
            entity = entity_types[type(info)](data, platform, info)
            known[uid] = entity
            new.append(entity)
        if new:
            async_add_entities(new)

    data.async_register_platform(tuple(entity_types), add_infos)
