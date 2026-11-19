"""The encryption keys of the Kachel devices, kept in Home Assistant beyond their entries.

A device keeps its key when its entry is deleted: echod refuses an empty or all-zeros key, so the key
cannot be taken back over the API. So that the device can be added again at once (without typing the
key, without a factory reset) and is never left open, the key stays here by MAC address and is offered
when the device is added again (Philip, 2026-11-19: option a). Like Home Assistant's ESPHome
integration (homeassistant/components/esphome/encryption_key_storage.py, Apache-2.0, see NOTICE).
Stored in .storage/kachel.encryption_keys, which only Home Assistant reads.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_STORAGE_KEY = f"{DOMAIN}.encryption_keys"
_STORAGE_VERSION = 1
_DATA: HassKey[KeyStore] = HassKey(f"{DOMAIN}_encryption_keys")


class KeyStore:
    """Keys by MAC address (lowercase, with colons, as format_mac gives it)."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Bind the store; loaded on first use."""
        self._store: Store[dict[str, str]] = Store(
            hass, _STORAGE_VERSION, _STORAGE_KEY, private=True
        )
        self._keys: dict[str, str] | None = None

    async def _load(self) -> dict[str, str]:
        if self._keys is None:
            self._keys = dict(await self._store.async_load() or {})
        return self._keys

    async def async_get(self, mac: str) -> str | None:
        """The key kept for a device, if any."""
        return (await self._load()).get(mac)

    async def async_set(self, mac: str, key: str) -> None:
        """Keep a device's key (written at once: a key lost is a device to reset)."""
        keys = await self._load()
        if not key or keys.get(mac) == key:
            return
        keys[mac] = key
        await self._store.async_save(keys)


def async_get_key_store(hass: HomeAssistant) -> KeyStore:
    """The one key store."""
    if (store := hass.data.get(_DATA)) is None:
        store = hass.data[_DATA] = KeyStore(hass)
    return store
