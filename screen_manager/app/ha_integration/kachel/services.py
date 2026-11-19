"""What passes between a Kachel device and Home Assistant besides its entities.

- **Actions into the device:** each action echod offers (for example `screen_message`, `show_alert`) becomes
  `kachel.<node>_<action>`, answering where echod answers (`screen_message`: the Kachel Manager's protocol 2).
- **Events from the device:** echod sends `esphome.screen_*`; they go on the bus as `kachel.screen_*`, with the
  Home Assistant device id, data unchanged (agreed with kachel-manager-addon, 2026-11-19).
- **Actions from the device:** performed when the entry's option `allow_service_calls` is on (Philip: default
  on); when off, a repair issue `service_calls_not_enabled-<mac>` says so, as with ESPHome.
- **Home Assistant states into the device:** the entities echod asks for (weather, station list …).

Follows Home Assistant's ESPHome integration (homeassistant/components/esphome/manager.py, Apache-2.0,
see NOTICE), with the event domain and the option's default changed for the Kachel devices.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from aioesphomeapi import (
    APIConnectionError,
    HomeassistantServiceCall,
    SupportsResponseType,
    UserService,
    UserServiceArgType,
)
from homeassistant.components import tag
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    State,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound, ServiceValidationError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.util.json import json_loads_object
import probatio

from .const import CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .manager import KachelData

_LOGGER = logging.getLogger(__name__)

# The event domains echod may use: what it sends today (ESPHome's), and our own for later.
_DEVICE_EVENT_DOMAINS = ("esphome", DOMAIN)


class _ArgMeta(NamedTuple):
    validator: Any
    example: str
    selector: dict[str, Any]
    description: str | None = None


_ARG_TYPES: dict[UserServiceArgType, _ArgMeta] = {
    UserServiceArgType.BOOL: _ArgMeta(cv.boolean, "False", {"boolean": None}),
    UserServiceArgType.INT: _ArgMeta(probatio.Coerce(int), "42", {"number": {"mode": "box"}}),
    UserServiceArgType.FLOAT: _ArgMeta(
        probatio.Coerce(float), "12.3", {"number": {"mode": "box", "step": 1e-3}}
    ),
    UserServiceArgType.STRING: _ArgMeta(cv.string, "Example text", {"text": None}),
    UserServiceArgType.BOOL_ARRAY: _ArgMeta(
        [cv.boolean], "[True, False]", {"object": {}}, "A list of boolean values."
    ),
    UserServiceArgType.INT_ARRAY: _ArgMeta(
        [probatio.Coerce(int)], "[42, 34]", {"object": {}}, "A list of integer values."
    ),
    UserServiceArgType.FLOAT_ARRAY: _ArgMeta(
        [probatio.Coerce(float)], "[12.3, 34.5]", {"object": {}}, "A list of numbers."
    ),
    UserServiceArgType.STRING_ARRAY: _ArgMeta(
        [cv.string], "['Example text']", {"object": {}}, "A list of strings."
    ),
}

_RESPONSE_TYPES = {
    SupportsResponseType.NONE: SupportsResponse.NONE,
    SupportsResponseType.OPTIONAL: SupportsResponse.OPTIONAL,
    SupportsResponseType.ONLY: SupportsResponse.ONLY,
    # STATUS waits for success or failure, but gives Home Assistant no data.
    SupportsResponseType.STATUS: SupportsResponse.NONE,
}


def action_name(node: str, service: UserService) -> str:
    """`<node>_<action>`, dashes as underscores, as the ESPHome integration names them."""
    return f"{node.replace('-', '_')}_{service.name}"


def issue_id(mac: str) -> str:
    """The repair issue of a device whose actions are not allowed (the ESPHome integration's name)."""
    return f"service_calls_not_enabled-{mac}"


def _error(key: str, **placeholders: str) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders
    )


# --- actions into the device ---------------------------------------------------------------------


async def _execute(data: KachelData, service: UserService, call: ServiceCall) -> ServiceResponse:
    """Run one of the device's actions; wait for its answer where it gives one."""
    supports = service.supports_response or SupportsResponseType.NONE
    name = data.name
    if not data.available:
        raise _error("not_connected", device_name=name, call_name=service.name)
    if supports == SupportsResponseType.NONE:
        try:
            await data.client.execute_service(service, call.data)
        except APIConnectionError as err:
            raise _error(
                "action_call_failed", device_name=name, call_name=service.name, error=str(err)
            ) from err
        return None
    want_data = supports == SupportsResponseType.ONLY or (
        supports == SupportsResponseType.OPTIONAL and call.return_response
    )
    try:
        response = await data.client.execute_service(service, call.data, return_response=want_data)
    except APIConnectionError as err:
        raise _error(
            "action_call_failed", device_name=name, call_name=service.name, error=str(err)
        ) from err
    except TimeoutError as err:
        raise _error("action_call_timeout", device_name=name, call_name=service.name) from err
    if response is None or not response.success:
        raise _error(
            "action_call_failed",
            device_name=name,
            call_name=service.name,
            error=response.error_message if response else "no answer",
        )
    if want_data and response.response_data:
        try:
            return json_loads_object(response.response_data)
        except ValueError as err:
            raise _error(
                "action_call_failed",
                device_name=name,
                call_name=service.name,
                error=f"invalid JSON answer: {err}",
            ) from err
    return None


@callback
def _register(hass: HomeAssistant, data: KachelData, node: str, service: UserService) -> bool:
    name = action_name(node, service)
    schema: dict[Any, Any] = {}
    fields: dict[str, Any] = {}
    for arg in service.args:
        if (meta := _ARG_TYPES.get(arg.type)) is None:
            _LOGGER.error(
                "Kachel: action %s not offered, %s has unknown type %s", name, arg.name, arg.type
            )
            return False
        schema[probatio.Required(arg.name)] = meta.validator
        fields[arg.name] = {
            "name": arg.name,
            "required": True,
            "description": arg.description or meta.description,
            "example": arg.example or meta.example,
            "selector": meta.selector,
        }
    supports = service.supports_response or SupportsResponseType.NONE
    hass.services.async_register(
        DOMAIN,
        name,
        partial(_execute, data, service),
        probatio.Schema(schema),
        supports_response=_RESPONSE_TYPES.get(supports, SupportsResponse.NONE),
    )
    async_set_service_schema(
        hass,
        DOMAIN,
        name,
        {
            "description": service.description
            or f"The action {service.name} of the Kachel device {node}",
            "fields": fields,
        },
    )
    return True


@callback
def async_setup_device_actions(
    hass: HomeAssistant, data: KachelData, services: list[UserService]
) -> None:
    """Offer the device's actions; drop the ones it no longer has, renew the changed ones."""
    assert data.device_info is not None
    node = data.device_info.name
    old = dict(data.services)
    keep: dict[str, UserService] = {}
    for service in services:
        name = action_name(node, service)
        if old.pop(name, None) == service and hass.services.has_service(DOMAIN, name):
            keep[name] = service
            continue
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)
        if _register(hass, data, node, service):
            keep[name] = service
    for name in old:
        hass.services.async_remove(DOMAIN, name)
    data.services = keep


@callback
def async_remove_device_actions(hass: HomeAssistant, data: KachelData) -> None:
    """The entry goes: its actions go with it."""
    for name in data.services:
        hass.services.async_remove(DOMAIN, name)
    data.services = {}


# --- events and actions from the device ----------------------------------------------------------


class DeviceCalls:
    """What the device asks of Home Assistant: events to fire, actions to perform."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: KachelData) -> None:
        """Bind to one device."""
        self.hass = hass
        self.entry = entry
        self.data = data

    @property
    def allowed(self) -> bool:
        """Whether the device may perform Home Assistant actions (option, default on)."""
        return bool(self.entry.options.get(CONF_ALLOW_SERVICE_CALLS, DEFAULT_ALLOW_SERVICE_CALLS))

    @callback
    def async_sync_issue(self) -> None:
        """Allowed again: the repair issue goes."""
        if self.allowed and self.entry.unique_id:
            async_delete_issue(self.hass, DOMAIN, issue_id(self.entry.unique_id))

    @callback
    def async_on_call(self, call: HomeassistantServiceCall) -> None:
        """An event or an action from the device."""
        if "." not in call.service:
            _LOGGER.warning("Kachel %s: unreadable request %r", self.data.name, call.service)
            return
        domain, name = call.service.split(".", 1)
        service_data: dict[str, Any] = dict(call.data)
        if call.data_template:
            try:
                tpl = {k: template.Template(v, self.hass) for k, v in call.data_template.items()}
                service_data.update(template.render_complex(tpl, call.variables))
            except template.TemplateError as err:
                _LOGGER.error(
                    "Kachel %s: template for %s failed: %s", self.data.name, call.service, err
                )
                return
        if call.is_event:
            self._event(domain, name, service_data)
        elif self.allowed:
            self._action(domain, name, service_data, call)
        else:
            self._refuse(domain, name)

    def _event(self, domain: str, name: str, service_data: dict[str, Any]) -> None:
        device_id = self.data.main_device_id
        if domain not in _DEVICE_EVENT_DOMAINS:
            _LOGGER.error(
                "Kachel %s: event %s.%s refused (only esphome.* or kachel.*)",
                self.data.name,
                domain,
                name,
            )
            return
        if name == "tag_scanned" and device_id is not None and "tag_id" in service_data:
            self.entry.async_create_task(
                self.hass, tag.async_scan_tag(self.hass, service_data["tag_id"], device_id)
            )
            return
        self.hass.bus.async_fire(f"{DOMAIN}.{name}", {ATTR_DEVICE_ID: device_id, **service_data})

    def _action(
        self, domain: str, name: str, service_data: dict[str, Any], call: HomeassistantServiceCall
    ) -> None:
        if call.call_id and call.wants_response:
            coro = self._action_with_response(domain, name, service_data, call)
        elif call.call_id:
            coro = self._action_with_status(domain, name, service_data, call.call_id)
        else:
            coro = self.hass.services.async_call(domain, name, service_data)
        self.entry.async_create_task(self.hass, coro)

    async def _action_with_response(
        self, domain: str, name: str, service_data: dict[str, Any], call: HomeassistantServiceCall
    ) -> None:
        try:
            result = await self.hass.services.async_call(
                domain, name, service_data, blocking=True, return_response=True
            )
            if call.response_template:
                try:
                    rendered = template.Template(call.response_template, self.hass).async_render(
                        variables={"response": result}, strict=True
                    )
                except template.TemplateError as err:
                    self._answer(call.call_id, False, f"Error rendering response template: {err}")
                    return
                body = {"response": rendered}
            else:
                body = {"response": result}
            payload = json_bytes(body)
        except (
            ServiceNotFound,
            ServiceValidationError,
            probatio.Invalid,
            HomeAssistantError,
        ) as err:
            self._answer(call.call_id, False, str(err))
            return
        self._answer(call.call_id, True, "", payload)

    async def _action_with_status(
        self, domain: str, name: str, service_data: dict[str, Any], call_id: int
    ) -> None:
        try:
            await self.hass.services.async_call(domain, name, service_data, blocking=True)
        except (
            ServiceNotFound,
            ServiceValidationError,
            probatio.Invalid,
            HomeAssistantError,
        ) as err:
            self._answer(call_id, False, str(err))
            return
        self._answer(call_id, True, "")

    def _answer(self, call_id: int, success: bool, error: str, payload: bytes = b"") -> None:
        try:
            self.data.client.send_homeassistant_action_response(call_id, success, error, payload)
        except APIConnectionError as err:
            _LOGGER.debug("Kachel %s: answer to call %s not sent: %s", self.data.name, call_id, err)

    def _refuse(self, domain: str, name: str) -> None:
        if self.entry.unique_id:
            async_create_issue(
                self.hass,
                DOMAIN,
                issue_id(self.entry.unique_id),
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="service_calls_not_allowed",
                translation_placeholders={"name": self.data.name},
            )
        _LOGGER.error(
            "Kachel %s: action %s.%s refused; allow it in the integration's options if you trust the device",
            self.data.name,
            domain,
            name,
        )


# --- Home Assistant states into the device ------------------------------------------------------


class StateForwarder:
    """Sends the device the states it follows, now and whenever they change."""

    def __init__(self, hass: HomeAssistant, data: KachelData) -> None:
        """Bind to one device."""
        self.hass = hass
        self.data = data

    @callback
    def _send(self, entity_id: str, attribute: str | None, state: State | None) -> None:
        if state is None or (attribute and attribute not in state.attributes):
            return
        value: Any = state.state
        if attribute:
            value = state.attributes[attribute]
            if isinstance(value, bool):  # the device takes "on"/"off" for true and false
                value = "on" if value else "off"
        try:
            self.data.client.send_home_assistant_state(entity_id, attribute, str(value))
        except APIConnectionError as err:
            _LOGGER.debug("Kachel %s: state of %s not sent: %s", self.data.name, entity_id, err)

    @callback
    def _changed(self, attribute: str | None, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None:
            return
        if old is not None and (
            (not attribute and old.state == new.state)
            or (attribute and old.attributes.get(attribute) == new.attributes.get(attribute))
        ):
            return
        self._send(event.data["entity_id"], attribute, new)

    @callback
    def async_on_subscribe(self, entity_id: str, attribute: str | None = None) -> None:
        """The device follows an entity: send it now and on every change (until the connection ends)."""
        unsub: Callable[[], None] = async_track_state_change_event(
            self.hass, [entity_id], partial(self._changed, attribute)
        )
        self.data.disconnect_callbacks.append(unsub)
        self._send(entity_id, attribute, self.hass.states.get(entity_id))

    @callback
    def async_on_request(self, entity_id: str, attribute: str | None = None) -> None:
        """The device asks for one state once."""
        self._send(entity_id, attribute, self.hass.states.get(entity_id))
