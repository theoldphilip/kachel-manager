"""Connection to one Kachel device (echod) over the ESPHome native API.

Kachel devices speak the ESPHome native API (port 6053, Noise encryption). This integration is the
client instead of Home Assistant's ESPHome integration, so the devices show up under "Kachel".
The connection handling follows Home Assistant's own ESPHome integration (homeassistant/components/
esphome/manager.py, Apache-2.0, see NOTICE), reduced to what a Kachel device needs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    DeviceInfo,
    EntityInfo,
    EntityState,
    InvalidEncryptionKeyAPIError,
    MediaPlayerInfo,
    MediaPlayerSupportedFormat,
    ReconnectLogic,
    RequiresEncryptionAPIError,
    UserService,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac

from .const import CLIENT_INFO, CONF_DEVICE_NAME, CONF_NOISE_PSK, DOMAIN, MANUFACTURER
from .services import DeviceCalls, StateForwarder, async_setup_device_actions

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .entity import KachelEntity

_LOGGER = logging.getLogger(__name__)

# What each platform is offered: the platform's own callback adds entities for infos it has not seen.
type AddInfos = Callable[[list[EntityInfo]], None]


async def async_zeroconf(hass: HomeAssistant) -> Any:
    """Home Assistant's shared zeroconf instance (a function, so tests can replace it)."""
    from homeassistant.components import zeroconf

    return await zeroconf.async_get_instance(hass)


def create_client(host: str, port: int, noise_psk: str | None, zeroconf_instance: Any) -> APIClient:
    """A client for one device (a function, so tests can replace it)."""
    return APIClient(
        host,
        port,
        "",
        client_info=CLIENT_INFO,
        zeroconf_instance=zeroconf_instance,
        noise_psk=noise_psk,
    )


def entity_key(info: EntityInfo | EntityState) -> tuple[int, int]:
    """The key a state is routed by: the sub-device and the entity's key on the device."""
    return (info.device_id, info.key)


@dataclass
class KachelData:
    """What the integration keeps for one connected device."""

    client: APIClient
    # This adoption's id (const.CONF_ADOPTION_ID); empty for entries made before 0.3.1.
    adoption_id: str = ""
    available: bool = False
    device_info: DeviceInfo | None = None
    infos: dict[type[EntityInfo], list[EntityInfo]] = field(default_factory=dict)
    states: dict[tuple[int, int], EntityState] = field(default_factory=dict)
    entities: dict[tuple[int, int], KachelEntity] = field(default_factory=dict)
    platform_adders: dict[type[EntityInfo], AddInfos] = field(default_factory=dict)
    availability_listeners: list[Callable[[], None]] = field(default_factory=list)
    # The device's actions, by name in Home Assistant (services.py).
    services: dict[str, UserService] = field(default_factory=dict)
    # The device in Home Assistant's device registry (for events: device_id).
    main_device_id: str | None = None
    # Undone when the connection ends (state forwarding).
    disconnect_callbacks: list[Callable[[], None]] = field(default_factory=list)
    # Called after every connect, once the device is registered and its states are followed: what
    # needs the connection itself (the voice assistant subscribes to the device's audio here).
    connect_listeners: list[Callable[[], None]] = field(default_factory=list)

    @property
    def voice_features(self) -> int:
        """The device's voice assistant features (0: none; on the Fire only once Assist is set up)."""
        if self.device_info is None:
            return 0
        api_version = self.client.api_version
        if api_version is None:
            return self.device_info.voice_assistant_feature_flags
        return self.device_info.voice_assistant_feature_flags_compat(api_version)

    @property
    def media_formats(self) -> list[MediaPlayerSupportedFormat]:
        """The formats the device's speaker asks for (for announcements of the voice assistant)."""
        return [f for info in self.infos.get(MediaPlayerInfo, []) for f in info.supported_formats]

    @callback
    def async_add_connect_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call `listener` after every connect (and now, if connected); returns the remover."""
        self.connect_listeners.append(listener)
        if self.available:
            listener()
        return lambda: self.connect_listeners.remove(listener)

    @property
    def name(self) -> str:
        """The device's name for messages."""
        if self.device_info is None:
            return "Kachel device"
        return self.device_info.friendly_name or self.device_info.name

    @property
    def mac(self) -> str:
        """The device's MAC address, formatted as Home Assistant does."""
        assert self.device_info is not None
        return format_mac(self.device_info.mac_address)

    @callback
    def async_register_platform(
        self, info_types: tuple[type[EntityInfo], ...], add_infos: AddInfos
    ) -> None:
        """A platform says which entity kinds it takes; it is offered the ones already known."""
        for info_type in info_types:
            self.platform_adders[info_type] = add_infos
            if known := self.infos.get(info_type):
                add_infos(known)

    @callback
    def async_set_infos(self, entity_infos: list[EntityInfo]) -> None:
        """A (re)connect brought the device's entity list: hand each kind to its platform."""
        by_type: dict[type[EntityInfo], list[EntityInfo]] = {}
        for info in entity_infos:
            by_type.setdefault(type(info), []).append(info)
        self.infos = by_type
        # Keys can change between connections: entities are routed afresh by unique id (entity.py).
        self.entities = {}
        for info_type, infos in by_type.items():
            if add_infos := self.platform_adders.get(info_type):
                add_infos(infos)
            else:
                _LOGGER.debug("Kachel: no platform yet for %s", info_type.__name__)

    @callback
    def async_on_state(self, state: EntityState) -> None:
        """A state arrived from the device."""
        key = entity_key(state)
        self.states[key] = state
        if (entity := self.entities.get(key)) is not None:
            entity.async_on_state(state)

    @callback
    def async_set_available(self, available: bool) -> None:
        """The connection came or went."""
        self.available = available
        for listener in list(self.availability_listeners):
            listener()


class KachelManager:
    """Keeps one device connected: connects, reconnects, registers the device, routes states."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, data: KachelData, zeroconf_instance: Any
    ) -> None:
        """Set up the manager for one config entry."""
        self.hass = hass
        self.entry = entry
        self.data = data
        self.calls = DeviceCalls(hass, entry, data)
        self.states = StateForwarder(hass, data)
        self.reconnect_logic = ReconnectLogic(
            client=data.client,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
            zeroconf_instance=zeroconf_instance,
            name=entry.data.get(CONF_DEVICE_NAME),
            on_connect_error=self._on_connect_error,
        )

    async def async_start(self) -> None:
        """Start connecting (in the background; the device may be away)."""
        await self.reconnect_logic.start()

    async def async_stop(self) -> None:
        """Stop reconnecting and drop the connection."""
        await self.reconnect_logic.stop()
        self._async_run_disconnect_callbacks()
        await self.data.client.disconnect()

    @callback
    def _async_run_disconnect_callbacks(self) -> None:
        while self.data.disconnect_callbacks:
            self.data.disconnect_callbacks.pop()()

    async def _on_connect(self) -> None:
        """Connected: read what the device is and has, then follow its states."""
        cli = self.data.client
        try:
            device_info, entity_infos, services = await cli.device_info_and_list_entities()
        except APIConnectionError as err:
            _LOGGER.warning("Kachel %s: reading the device failed: %s", self.entry.title, err)
            await cli.disconnect()
            return
        self.data.device_info = device_info
        self._async_register_device(device_info)
        self.data.async_set_infos(entity_infos)
        async_setup_device_actions(self.hass, self.data, services)
        self.calls.async_sync_issue()
        # States, the device's requests and the states it follows, in one request (as ESPHome does).
        cli.subscribe_home_assistant_states_and_services(
            on_state=self.data.async_on_state,
            on_service_call=self.calls.async_on_call,
            on_state_sub=self.states.async_on_subscribe,
            on_state_request=self.states.async_on_request,
        )
        self.data.async_set_available(True)
        for listener in list(self.data.connect_listeners):
            listener()
        _LOGGER.info(
            "Kachel %s connected (%s, %s entities)",
            self.entry.title,
            device_info.model,
            len(entity_infos),
        )

    async def _on_disconnect(self, expected_disconnect: bool) -> None:
        """Disconnected: everything is unavailable until the next connect."""
        self._async_run_disconnect_callbacks()
        self.data.async_set_available(False)
        if not expected_disconnect:
            _LOGGER.info("Kachel %s disconnected, reconnecting", self.entry.title)

    async def _on_connect_error(self, err: Exception) -> None:
        """A connect failed. A wrong or missing key needs the user (reauth)."""
        if isinstance(err, (InvalidEncryptionKeyAPIError, RequiresEncryptionAPIError)):
            _LOGGER.warning("Kachel %s: the encryption key is not accepted", self.entry.title)
            self.entry.async_start_reauth(self.hass)

    @callback
    def _async_register_device(self, device_info: DeviceInfo) -> None:
        """The device (and its sub-devices) in Home Assistant's device registry."""
        registry = dr.async_get(self.hass)
        mac = format_mac(device_info.mac_address)
        main = registry.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, mac)},
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            manufacturer=MANUFACTURER,
            model=device_info.model or None,
            name=device_info.friendly_name or device_info.name,
            sw_version=device_info.project_version or device_info.esphome_version or None,
        )
        for sub in device_info.devices:
            registry.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                identifiers={(DOMAIN, f"{mac}_{sub.device_id}")},
                manufacturer=MANUFACTURER,
                name=sub.name or None,
                via_device_id=main.id,
            )
        self.data.main_device_id = main.id
        _LOGGER.debug("Kachel device registered: %s", main.id)


def client_from_entry(entry: ConfigEntry, zeroconf_instance: Any) -> APIClient:
    """The client for a config entry."""
    return create_client(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_NOISE_PSK) or None,
        zeroconf_instance,
    )
