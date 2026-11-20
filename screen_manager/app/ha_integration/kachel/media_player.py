"""Kachel media player: echod's speaker.

Follows Home Assistant's ESPHome media player (homeassistant/components/esphome/media_player.py, Home
Assistant Core 2026.11.2, Apache-2.0, see NOTICE). What the device is sent to play goes through the
ffmpeg proxy (ffmpeg_proxy.py) in the format the device asks for: echod plays plain WAV.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from aioesphomeapi import (
    MediaPlayerCommand,
    MediaPlayerEntityFeature as EspFeature,
    MediaPlayerEntityState,
    MediaPlayerFormatPurpose,
    MediaPlayerInfo,
    MediaPlayerState as EspState,
    MediaPlayerSupportedFormat,
)
from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KachelConfigEntry
from .const import DOMAIN
from .entity import KachelEntity, async_setup_platform
from .ffmpeg_proxy import async_create_proxy_url

PARALLEL_UPDATES = 0

ATTR_BYPASS_PROXY = "bypass_proxy"

_STATES = {
    EspState.IDLE: MediaPlayerState.IDLE,
    EspState.PLAYING: MediaPlayerState.PLAYING,
    EspState.ANNOUNCING: MediaPlayerState.PLAYING,
    EspState.PAUSED: MediaPlayerState.PAUSED,
    EspState.OFF: MediaPlayerState.OFF,
    EspState.ON: MediaPlayerState.ON,
}

_FEATURES = {
    EspFeature.PAUSE: MediaPlayerEntityFeature.PAUSE,
    EspFeature.VOLUME_SET: MediaPlayerEntityFeature.VOLUME_SET,
    EspFeature.VOLUME_MUTE: MediaPlayerEntityFeature.VOLUME_MUTE,
    EspFeature.TURN_ON: MediaPlayerEntityFeature.TURN_ON,
    EspFeature.TURN_OFF: MediaPlayerEntityFeature.TURN_OFF,
    EspFeature.PLAY_MEDIA: MediaPlayerEntityFeature.PLAY_MEDIA,
    EspFeature.VOLUME_STEP: MediaPlayerEntityFeature.VOLUME_STEP,
    EspFeature.STOP: MediaPlayerEntityFeature.STOP,
    EspFeature.CLEAR_PLAYLIST: MediaPlayerEntityFeature.CLEAR_PLAYLIST,
    EspFeature.PLAY: MediaPlayerEntityFeature.PLAY,
    EspFeature.BROWSE_MEDIA: MediaPlayerEntityFeature.BROWSE_MEDIA,
    EspFeature.REPEAT_SET: MediaPlayerEntityFeature.REPEAT_SET,
    EspFeature.MEDIA_ANNOUNCE: MediaPlayerEntityFeature.MEDIA_ANNOUNCE,
    EspFeature.MEDIA_ENQUEUE: MediaPlayerEntityFeature.MEDIA_ENQUEUE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media players."""
    async_setup_platform(
        hass, entry, async_add_entities, "media_player", {MediaPlayerInfo: KachelMediaPlayer}
    )


def _is_url(url: str) -> bool:
    result = urlparse(url)
    return bool(result.scheme and result.netloc)


class KachelMediaPlayer(KachelEntity, MediaPlayerEntity):
    """The speaker of a Kachel device."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _formats: list[MediaPlayerSupportedFormat]

    def _on_info(self, info: MediaPlayerInfo) -> None:
        api_version = self._data.client.api_version
        flags = info.feature_flags_compat(api_version) if api_version else info.feature_flags
        features = MediaPlayerEntityFeature(0)
        for esp_flag, ha_flag in _FEATURES.items():
            if flags & esp_flag:
                features |= ha_flag
        self._attr_supported_features = features
        self._formats = list(info.supported_formats)

    @property
    def _player(self) -> MediaPlayerEntityState | None:
        return None if self._missing else self._state  # type: ignore[return-value]

    @property
    def state(self) -> MediaPlayerState | None:
        """Idle, playing, paused …"""
        if (s := self._player) is None or s.state is None:
            return None
        return _STATES.get(s.state)

    @property
    def is_volume_muted(self) -> bool | None:
        """Muted."""
        return None if (s := self._player) is None else s.muted

    @property
    def volume_level(self) -> float | None:
        """Volume 0..1."""
        return None if (s := self._player) is None else s.volume

    def _command(self, **kwargs: Any) -> None:
        self._client.media_player_command(self._key, device_id=self._device_id, **kwargs)

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a URL or a media source item; announcements interrupt and resume."""
        enqueue = kwargs.get(ATTR_MEDIA_ENQUEUE)
        if enqueue in (MediaPlayerEnqueue.NEXT, MediaPlayerEnqueue.PLAY):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="enqueue_mode_not_supported",
                translation_placeholders={"enqueue": str(enqueue)},
            )
        if media_source.is_media_source_id(media_id):
            media_id = (
                await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            ).url
        media_id = async_process_play_media_url(self.hass, media_id)
        announcement = kwargs.get(ATTR_MEDIA_ANNOUNCE)
        bypass = (kwargs.get(ATTR_MEDIA_EXTRA) or {}).get(ATTR_BYPASS_PROXY)
        if (
            not bypass
            and self._formats
            and _is_url(media_id)
            and (proxy_url := self._proxy_url(media_id, announcement is True))
        ):
            media_id = proxy_url
        self._command(
            command=MediaPlayerCommand.ENQUEUE if enqueue == MediaPlayerEnqueue.ADD else None,
            media_url=media_id,
            announcement=announcement,
        )

    def _proxy_url(self, url: str, announcement: bool) -> str | None:
        """A one-time URL on Home Assistant that converts `url` to the device's format."""
        chosen: MediaPlayerSupportedFormat | None = None
        for fmt in self._formats:
            if chosen is None and fmt.purpose == MediaPlayerFormatPurpose.DEFAULT:
                chosen = fmt
            elif announcement and fmt.purpose == MediaPlayerFormatPurpose.ANNOUNCEMENT:
                chosen = fmt
                break
        if chosen is None or self.device_entry is None:
            return None
        proxy_url = async_create_proxy_url(
            self.hass,
            self.device_entry.id,
            url,
            media_format=chosen.format,
            rate=chosen.sample_rate or None,
            channels=chosen.num_channels or None,
            width=chosen.sample_bytes or None,
        )
        return async_process_play_media_url(self.hass, proxy_url)

    async def async_browse_media(
        self, media_content_type: MediaType | str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Browse Home Assistant's media sources (audio only)."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume, 0..1."""
        self._command(volume=volume)

    async def async_volume_up(self) -> None:
        """One step louder."""
        self._command(command=MediaPlayerCommand.VOLUME_UP)

    async def async_volume_down(self) -> None:
        """One step quieter."""
        self._command(command=MediaPlayerCommand.VOLUME_DOWN)

    async def async_media_pause(self) -> None:
        """Pause."""
        self._command(command=MediaPlayerCommand.PAUSE)

    async def async_media_play(self) -> None:
        """Play."""
        self._command(command=MediaPlayerCommand.PLAY)

    async def async_media_stop(self) -> None:
        """Stop."""
        self._command(command=MediaPlayerCommand.STOP)

    async def async_clear_playlist(self) -> None:
        """Clear what is queued."""
        self._command(command=MediaPlayerCommand.CLEAR_PLAYLIST)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Repeat one or off (the device has no "all")."""
        if repeat == RepeatMode.ALL:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="repeat_mode_not_supported",
                translation_placeholders={"repeat_mode": str(repeat)},
            )
        self._command(
            command=MediaPlayerCommand.REPEAT_ONE
            if repeat == RepeatMode.ONE
            else MediaPlayerCommand.REPEAT_OFF
        )
        self._attr_repeat = repeat  # the device does not report it
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute."""
        self._command(command=MediaPlayerCommand.MUTE if mute else MediaPlayerCommand.UNMUTE)

    async def async_turn_on(self) -> None:
        """Turn on."""
        self._command(command=MediaPlayerCommand.TURN_ON)

    async def async_turn_off(self) -> None:
        """Turn off."""
        self._command(command=MediaPlayerCommand.TURN_OFF)
