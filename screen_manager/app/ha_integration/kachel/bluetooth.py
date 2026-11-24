"""Bluetooth proxy: a Kachel device that hears BLE devices lends its radio to Home Assistant.

kacheld offers the ESPHome Bluetooth proxy (passive scan, raw advertisements, scanner state and mode;
with its "Bluetooth proxy connections" switch on also active connections). Here the device is
registered as a remote scanner with Home Assistant's Bluetooth integration, with the same library
Home Assistant's ESPHome integration uses (bleak-esphome). Follows
homeassistant/components/esphome/bluetooth.py (Apache-2.0, see NOTICE), without the migration from
the scanning mode configured on the device (Kachel devices never had one).

kacheld switches the proxy by changing what it advertises, which costs a reconnect: so each connect
decides anew whether there is a scanner (and the next connect without one removes it).
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from aioesphomeapi import BluetoothProxyFeature, DeviceInfo
from bleak_esphome import connect_scanner
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    async_register_scanner,
    async_remove_scanner,
)
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_BLUETOOTH_MAC_ADDRESS,
    CONF_BLUETOOTH_SCANNING_MODE,
    DEFAULT_BLUETOOTH_SCANNING_MODE,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .manager import KachelData

_LOGGER = logging.getLogger(__name__)
_VALID_MODES = {mode.value for mode in BluetoothScanningMode}


def proxy_features(data: KachelData) -> int:
    """The device's Bluetooth proxy features (0: no proxy, e.g. switched off on the device)."""
    if data.device_info is None:
        return 0
    api_version = data.client.api_version
    if api_version is None:
        return data.device_info.bluetooth_proxy_feature_flags
    return data.device_info.bluetooth_proxy_feature_flags_compat(api_version)


def scanner_source(device_info: DeviceInfo) -> str:
    """The scanner's address in Home Assistant (bleak-esphome's choice)."""
    return device_info.bluetooth_mac_address or device_info.mac_address


def scanning_mode(entry: ConfigEntry) -> BluetoothScanningMode:
    """The scanning mode from the options (auto when none or unknown)."""
    saved = entry.options.get(CONF_BLUETOOTH_SCANNING_MODE, DEFAULT_BLUETOOTH_SCANNING_MODE)
    if saved not in _VALID_MODES:
        _LOGGER.warning("Kachel %s: unknown scanning mode %r", entry.title, saved)
        saved = DEFAULT_BLUETOOTH_SCANNING_MODE
    return BluetoothScanningMode(saved)


@callback
def async_sync_scanner(
    hass: HomeAssistant, entry: ConfigEntry, data: KachelData
) -> Callable[[], None] | None:
    """At a connect: register the scanner if the device is a proxy, else remove an old one.

    Returns what undoes the registration at the disconnect (None when there is no scanner).
    """
    device_info = data.device_info
    if device_info is None:
        return None
    features = proxy_features(data)
    source = scanner_source(device_info)
    if not features:
        _async_remove(hass, source)
        return None
    if entry.data.get(CONF_BLUETOOTH_MAC_ADDRESS) != source:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_BLUETOOTH_MAC_ADDRESS: source}
        )
    client_data = connect_scanner(data.client, device_info, True)
    scanner = client_data.scanner
    if TYPE_CHECKING:
        assert scanner is not None
    if features & BluetoothProxyFeature.FEATURE_STATE_AND_MODE:
        # Before registering, so Home Assistant starts the scanner in this mode.
        scanner.async_set_scanning_mode(scanning_mode(entry))
    unregister = async_register_scanner(
        hass,
        scanner,
        source_domain=DOMAIN,
        source_model=device_info.model,
        source_config_entry_id=entry.entry_id,
        source_device_id=data.main_device_id,
    )
    stop_scanner = scanner.async_setup()
    _LOGGER.debug("Kachel %s: Bluetooth proxy %s (features %s)", entry.title, source, features)

    @callback
    def _undo() -> None:
        # As bleak-esphome asks: unavailable first (pending connection waits fail fast), then its
        # own disconnect callbacks, then the scanner goes.
        client_data.bluetooth_device.async_set_unavailable()
        for undo in list(client_data.disconnect_callbacks):
            undo()
        client_data.disconnect_callbacks.clear()
        stop_scanner()
        unregister()

    return _undo


@callback
def _async_remove(hass: HomeAssistant, source: str) -> None:
    """Remove the scanner of `source` (its advertisement history and its Bluetooth entry).

    Home Assistant finds the Bluetooth entry by the exact address the scanner was registered with.
    kacheld reports its MAC in lower case (ESPHome devices in upper case, hence ESPHome's .upper()):
    found in the Fire test 2026-11-24, the entry "kachel-223cb8cgggg (98:cc:f3:22:3c:b8)" stayed.
    So the address as registered, and its other spellings for entries from elsewhere.
    """
    for spelling in dict.fromkeys((source, source.lower(), source.upper())):
        async_remove_scanner(hass, spelling)


@callback
def async_remove_entry_scanner(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """The entry is deleted: its scanner (and the Bluetooth entry HA made for it) goes too."""
    if source := entry.data.get(CONF_BLUETOOTH_MAC_ADDRESS):
        _async_remove(hass, str(source))


def has_scanner(entry: ConfigEntry) -> bool:
    """Whether the options show the scanning mode: a proxy with modes, or a mode saved before."""
    if CONF_BLUETOOTH_SCANNING_MODE in entry.options:
        return True
    data: KachelData | None = getattr(entry, "runtime_data", None)
    return data is not None and bool(
        proxy_features(data) & BluetoothProxyFeature.FEATURE_STATE_AND_MODE
    )
