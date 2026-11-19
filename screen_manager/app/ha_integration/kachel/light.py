"""Kachel lights (for example the screen as a dimmable light).

The color mode handling is a reduced form of Home Assistant's ESPHome light platform
(homeassistant/components/esphome/light.py, Apache-2.0, see NOTICE): on/off, brightness and RGB,
which is what echod offers.
"""

from __future__ import annotations

from typing import Any

from aioesphomeapi import LightColorCapability, LightInfo, LightState
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .entity import KachelEntity, async_setup_platform


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights."""
    async_setup_platform(hass, entry, async_add_entities, "light", {LightInfo: KachelLight})


def _ha_mode(capabilities: int) -> ColorMode:
    if capabilities & LightColorCapability.RGB:
        return ColorMode.RGB
    if capabilities & LightColorCapability.BRIGHTNESS:
        return ColorMode.BRIGHTNESS
    return ColorMode.ONOFF


class KachelLight(KachelEntity, LightEntity):
    """A light of a Kachel device."""

    _modes: dict[ColorMode, int]

    def _on_info(self, info: LightInfo) -> None:
        self._modes = {}
        for mode in info.supported_color_modes:
            self._modes.setdefault(_ha_mode(int(mode)), int(mode))
        if not self._modes:
            self._modes = {ColorMode.ONOFF: 1}
        supported = set(self._modes)
        # Home Assistant: ONOFF and BRIGHTNESS only stand alone.
        if ColorMode.RGB in supported:
            supported -= {ColorMode.ONOFF, ColorMode.BRIGHTNESS}
        elif ColorMode.BRIGHTNESS in supported:
            supported.discard(ColorMode.ONOFF)
        self._attr_supported_color_modes = supported
        features = LightEntityFeature.TRANSITION
        if info.effects:
            features |= LightEntityFeature.EFFECT
            self._attr_effect_list = [e for e in info.effects if e != "None"]
        self._attr_supported_features = features

    @property
    def _light(self) -> LightState | None:
        return None if self._missing else self._state  # type: ignore[return-value]

    @property
    def is_on(self) -> bool | None:
        """On or off."""
        return None if (state := self._light) is None else state.state

    @property
    def brightness(self) -> int | None:
        """Brightness 0..255."""
        if (state := self._light) is None:
            return None
        return round(state.brightness * 255)

    @property
    def color_mode(self) -> ColorMode:
        """The mode in force."""
        supported = self._attr_supported_color_modes or {ColorMode.ONOFF}
        if (state := self._light) is not None and state.color_mode:
            mode = _ha_mode(int(state.color_mode))
            if mode in supported:
                return mode
        return next(iter(supported))

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """The color, if the light has one."""
        if (state := self._light) is None:
            return None
        return (round(state.red * 255), round(state.green * 255), round(state.blue * 255))

    @property
    def effect(self) -> str | None:
        """The effect running, if any."""
        if (state := self._light) is None or not state.effect or state.effect == "None":
            return None
        return state.effect

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, with brightness, color and effect if given."""
        args: dict[str, Any] = {"state": True}
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            args["brightness"] = brightness / 255
        if (rgb := kwargs.get(ATTR_RGB_COLOR)) is not None and ColorMode.RGB in self._modes:
            args["rgb"] = tuple(c / 255 for c in rgb)
            args["color_mode"] = self._modes[ColorMode.RGB]
            args["color_brightness"] = 1.0
        if (transition := kwargs.get(ATTR_TRANSITION)) is not None:
            args["transition_length"] = transition
        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            args["effect"] = effect
        self._client.light_command(self._key, device_id=self._device_id, **args)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        args: dict[str, Any] = {"state": False}
        if (transition := kwargs.get(ATTR_TRANSITION)) is not None:
            args["transition_length"] = transition
        self._client.light_command(self._key, device_id=self._device_id, **args)
