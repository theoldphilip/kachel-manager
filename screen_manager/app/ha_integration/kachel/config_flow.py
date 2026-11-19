"""Adding a Kachel device.

Found over zeroconf (echod announces itself as an ESPHome device; the manifest takes only the
boards in SUPPORTED_BOARDS) or added by address. The key works as with Home Assistant's ESPHome
integration (homeassistant/components/esphome/config_flow.py and manager.py, Apache-2.0, see NOTICE):
- a device that already has a key: the user enters it;
- a device in its adoption window (opened on the device's setup page, it then serves the all-zeros
  key): this integration generates a key and sets it over the encrypted zero-key connection.
A device the ESPHome integration still holds is refused: a device is in one integration, never both.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
import logging
import secrets
from typing import Any

from aioesphomeapi import (
    ZERO_NOISE_PSK,
    APIConnectionError,
    DeviceInfo,
    InvalidEncryptionKeyAPIError,
    RequiresEncryptionAPIError,
    ResolveAPIError,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .const import (
    CONF_ALLOW_SERVICE_CALLS,
    CONF_BOARD,
    CONF_DEVICE_NAME,
    CONF_NOISE_PSK,
    DEFAULT_ALLOW_SERVICE_CALLS,
    DEFAULT_PORT,
    DOMAIN,
    SUPPORTED_BOARDS,
)
from .keys import async_get_key_store
from .manager import async_zeroconf, create_client

_LOGGER = logging.getLogger(__name__)

ESPHOME_DOMAIN = "esphome"

ERROR_INVALID_KEY = "invalid_psk"
ERROR_CONNECT = "connection_error"
ERROR_RESOLVE = "resolve_error"
ERROR_SET_KEY = "set_key_failed"


class KeyResult:
    """What trying a key told."""

    def __init__(
        self, error: str | None = None, info: DeviceInfo | None = None, needs_key: bool = False
    ) -> None:
        """Hold the outcome."""
        self.error = error
        self.info = info
        self.needs_key = needs_key


class KachelFlowHandler(ConfigFlow, domain=DOMAIN):
    """Add a Kachel device."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> KachelOptionsFlow:
        """The device's options."""
        return KachelOptionsFlow()

    def __init__(self) -> None:
        """Start empty."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._name: str | None = None
        self._board: str | None = None
        self._noise_psk: str | None = None
        self._device_info: DeviceInfo | None = None
        self._mac: str | None = None

    # --- steps -------------------------------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a device by its address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            return await self._async_connect_first()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host or ""): str,
                    vol.Required(CONF_PORT, default=self._port): int,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """A Kachel device announced itself."""
        props = discovery_info.properties
        board = str(props.get("board", "")).lower()
        if board not in SUPPORTED_BOARDS:
            return self.async_abort(reason="not_kachel_board")
        mac = props.get("mac")
        if not mac:
            return self.async_abort(reason="no_mac")
        mac = format_mac(str(mac))
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        self._board = board
        self._name = str(
            props.get("friendly_name") or discovery_info.hostname.removesuffix(".local.")
        )
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host, CONF_PORT: self._port})
        if self._held_by_esphome(mac):
            return self.async_abort(reason="held_by_esphome")
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask before adding a device found on the network."""
        if user_input is not None:
            return await self._async_connect_first()
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name or ""}
        )

    async def async_step_encryption_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The device has a key: ask for it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._noise_psk = user_input[CONF_NOISE_PSK].strip()
            result = await self._async_try(self._noise_psk)
            if result.info is not None:
                return await self._async_finish(result.info)
            errors["base"] = result.error or ERROR_INVALID_KEY
        return self.async_show_form(
            step_id="encryption_key",
            data_schema=vol.Schema({vol.Required(CONF_NOISE_PSK): str}),
            errors=errors,
            description_placeholders={"name": self._name or self._host or ""},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The key is no longer accepted."""
        self._host = entry_data[CONF_HOST]
        self._port = entry_data[CONF_PORT]
        self._name = self._get_reauth_entry().title
        return await self._async_connect_first()

    # --- helpers -----------------------------------------------------------------------------

    def _held_by_esphome(self, mac: str) -> bool:
        """Whether the ESPHome integration still has this device."""
        return any(
            entry.unique_id == mac
            for entry in self.hass.config_entries.async_entries(ESPHOME_DOMAIN)
        )

    async def _async_connect_first(self) -> ConfigFlowResult:
        """First contact: in the adoption window we set a key, otherwise we ask for it."""
        result = await self._async_try(ZERO_NOISE_PSK)
        if result.info is not None:
            # The device took the zero key: it waits for a Home Assistant to give it one.
            return await self._async_provision(result.info)
        if result.needs_key:
            # A device added before keeps its key when its entry goes (keys.py): try the kept one.
            if (kept := await self._async_kept_key()) is not None:
                kept_result = await self._async_try(kept)
                if kept_result.info is not None:
                    self._noise_psk = kept
                    return await self._async_finish(kept_result.info)
            return await self.async_step_encryption_key()
        if self.source == SOURCE_REAUTH:
            return self.async_abort(reason=result.error or ERROR_CONNECT)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host or ""): str,
                    vol.Required(CONF_PORT, default=self._port): int,
                }
            ),
            errors={"base": result.error or ERROR_CONNECT},
        )

    async def _async_try(self, noise_psk: str) -> KeyResult:
        """Connect once with a key and read what the device is."""
        assert self._host is not None
        cli = create_client(self._host, self._port, noise_psk, await async_zeroconf(self.hass))
        try:
            await cli.connect()
            info = await cli.device_info()
        except (InvalidEncryptionKeyAPIError, RequiresEncryptionAPIError) as err:
            if name := getattr(err, "received_name", None):
                self._name = self._name or name
            if mac := getattr(err, "received_mac", None):
                self._mac = format_mac(mac)
            return KeyResult(error=ERROR_INVALID_KEY, needs_key=True)
        except ResolveAPIError:
            return KeyResult(error=ERROR_RESOLVE)
        except APIConnectionError as err:
            _LOGGER.debug("Kachel: connecting to %s failed: %s", self._host, err)
            return KeyResult(error=ERROR_CONNECT)
        finally:
            await cli.disconnect(force=True)
        return KeyResult(info=info)

    async def _async_provision(self, info: DeviceInfo) -> ConfigFlowResult:
        """Give a device in its adoption window a key of our own."""
        if (checked := await self._async_check_device(info)) is not None:
            return checked
        assert self._host is not None
        # A key kept from before is given again; otherwise a new one.
        kept = await async_get_key_store(self.hass).async_get(format_mac(info.mac_address))
        new_key = kept.encode() if kept else base64.b64encode(secrets.token_bytes(32))
        cli = create_client(self._host, self._port, ZERO_NOISE_PSK, await async_zeroconf(self.hass))
        try:
            await cli.connect()
            accepted = await cli.noise_encryption_set_key(new_key)
        except APIConnectionError as err:
            _LOGGER.warning("Kachel: setting the key on %s failed: %s", self._host, err)
            accepted = False
        finally:
            await cli.disconnect(force=True)
        if not accepted:
            return self.async_abort(reason=ERROR_SET_KEY)
        self._noise_psk = new_key.decode()
        return await self._async_finish(info)

    async def _async_kept_key(self) -> str | None:
        """The key kept for this device (by the MAC the device or its announcement gave)."""
        mac = self._mac or self.unique_id
        if self.source == SOURCE_REAUTH:
            mac = self._get_reauth_entry().unique_id
        if not mac:
            return None
        return await async_get_key_store(self.hass).async_get(mac)

    async def _async_check_device(self, info: DeviceInfo) -> ConfigFlowResult | None:
        """Refuse a device that is not ours to take (wrong board, or still in ESPHome)."""
        mac = format_mac(info.mac_address)
        if self.source == SOURCE_REAUTH:
            if mac != self._get_reauth_entry().unique_id:
                return self.async_abort(reason="wrong_device")
            return None
        await self.async_set_unique_id(mac, raise_on_progress=False)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host, CONF_PORT: self._port})
        if self._held_by_esphome(mac):
            return self.async_abort(reason="held_by_esphome")
        return None

    async def _async_finish(self, info: DeviceInfo) -> ConfigFlowResult:
        """Create (or, on reauth, update) the entry."""
        if (checked := await self._async_check_device(info)) is not None:
            return checked
        if self._noise_psk:
            await async_get_key_store(self.hass).async_set(
                format_mac(info.mac_address), self._noise_psk
            )
        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_NOISE_PSK: self._noise_psk or "",
            CONF_DEVICE_NAME: info.name,
            CONF_BOARD: self._board or "",
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        return self.async_create_entry(title=info.friendly_name or info.name, data=data)


class KachelOptionsFlow(OptionsFlowWithReload):
    """Options of a Kachel device; a change reloads it."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """May the device perform Home Assistant actions? (Philip: default on.)"""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_ALLOW_SERVICE_CALLS, default=current): bool}),
        )
