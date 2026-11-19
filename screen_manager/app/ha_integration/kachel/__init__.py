"""Kachel: the Kachel tablets (echod) in Home Assistant, under their own integration.

A Kachel device speaks the ESPHome native API. This integration is its client in place of Home
Assistant's ESPHome integration (decided 2026-11-19, "Weg E"): same protocol and key, own name,
own devices and entities. A device is in one of the two integrations, never in both.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .manager import KachelData, KachelManager, async_zeroconf, client_from_entry
from .services import async_remove_device_actions

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.UPDATE,
]

type KachelConfigEntry = ConfigEntry[KachelData]


async def async_setup_entry(hass: HomeAssistant, entry: KachelConfigEntry) -> bool:
    """Set up one Kachel device: platforms first, then the connection (in the background)."""
    zeroconf_instance = await async_zeroconf(hass)
    data = KachelData(client=client_from_entry(entry, zeroconf_instance))
    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    manager = KachelManager(hass, entry, data, zeroconf_instance)
    entry.async_on_unload(manager.async_stop)
    await manager.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KachelConfigEntry) -> bool:
    """Unload a Kachel device: its entities and its actions."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        async_remove_device_actions(hass, entry.runtime_data)
    return unloaded
