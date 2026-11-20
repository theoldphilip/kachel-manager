"""Music for the Kachel music page: what plays, where else it can play, and moving it there.

Asked for by fire-app (2026-11-20, Philip: "bau das alles ein"), sent with the device action
`kachel_message` (echod @d33a853: one JSON argument, no session, ops "media" and "players"):
- **media:** before the speaker plays something, the device is told the station, song and picture
  (media_player.py works them out; the device itself only gets the converted stream).
- **players:** the Music Assistant speakers other than the device itself, at every connect and whenever
  Music Assistant's players change. An empty list hides the "Play on …" button.
- **Play on …:** the device fires `esphome.kachel_play_on` {"target": entity} (here `kachel.kachel_play_on`).
  A Music Assistant queue playing on the device moves with `music_assistant.transfer_queue`; otherwise what
  this integration played (radio from Home Assistant) plays on the target, and the device stops.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import TYPE_CHECKING, Any

from aioesphomeapi import APIConnectionError, MediaPlayerCommand, MediaPlayerInfo
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .manager import KachelData
    from .media_player import NowPlaying

_LOGGER = logging.getLogger(__name__)

MESSAGE_ACTION = "kachel_message"
PLAY_ON_EVENT = f"{DOMAIN}.kachel_play_on"
MUSIC_ASSISTANT = "music_assistant"
_MESSAGE_TIMEOUT = 5.0
_PLAYERS_DELAY = 2.0
_PLAYING = ("playing", "paused", "buffering")


class MediaFlow:
    """The music page's side of one Kachel device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: KachelData) -> None:
        """Bind to one device."""
        self.hass = hass
        self.entry = entry
        self.data = data
        self._sent_players: list[dict[str, str]] | None = None
        self._pending: Callable[[], None] | None = None

    @callback
    def async_start(self) -> None:
        """Follow connects, Music Assistant's players and the device's "Play on …"."""
        self.entry.async_on_unload(self.data.async_add_connect_listener(self._on_connect))
        self.entry.async_on_unload(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_registry_change)
        )
        self.entry.async_on_unload(self.hass.bus.async_listen(PLAY_ON_EVENT, self._on_play_on))
        self.entry.async_on_unload(self._cancel_pending)

    # --- sending -------------------------------------------------------------------------------

    def _message_service(self) -> Any:
        return next((s for s in self.data.services.values() if s.name == MESSAGE_ACTION), None)

    async def async_send(self, message: dict[str, Any]) -> bool:
        """Hand the device one message; False when it cannot take it (older echod, not connected)."""
        service = self._message_service()
        if service is None or not self.data.available:
            return False
        try:
            response = await self.data.client.execute_service(
                service,
                {"message": json.dumps(message, ensure_ascii=False)},
                return_response=True,
                timeout=_MESSAGE_TIMEOUT,
            )
        except (APIConnectionError, TimeoutError) as err:
            _LOGGER.debug("Kachel %s: %s not taken: %s", self.data.name, message.get("op"), err)
            return False
        if response is None or not response.success:
            _LOGGER.debug("Kachel %s: %s refused: %s", self.data.name, message.get("op"), response)
            return False
        return True

    async def async_send_media(self, now: NowPlaying) -> None:
        """Tell the device what it is about to play (only what is known)."""
        fields = {
            "station": now.station,
            "title": now.title,
            "artist": now.artist,
            "album": now.album,
            "picture": now.picture,
        }
        await self.async_send({"op": "media", **{k: v for k, v in fields.items() if v}})

    # --- players -------------------------------------------------------------------------------

    def own_music_assistant_player(self) -> str | None:
        """The Music Assistant player that is this device (its Sendspin player), if there is one."""
        if self.data.device_info is None:
            return None
        mac = self.data.mac
        tail = mac.replace(":", "")[-6:]
        ent_reg, dev_reg = er.async_get(self.hass), dr.async_get(self.hass)
        for entry in ent_reg.entities.values():
            if entry.platform != MUSIC_ASSISTANT or entry.domain != "media_player":
                continue
            if tail in entry.entity_id or tail in (entry.unique_id or "").lower().replace(":", ""):
                return entry.entity_id
            device = dev_reg.async_get(entry.device_id) if entry.device_id else None
            if device is not None and any(c[1].lower() == mac for c in device.connections):
                return entry.entity_id
        return None

    def players(self) -> list[dict[str, str]]:
        """Music Assistant's speakers other than this device, with their names, sorted by name."""
        own = self.own_music_assistant_player()
        out: list[dict[str, str]] = []
        for entry in er.async_get(self.hass).entities.values():
            if entry.platform != MUSIC_ASSISTANT or entry.domain != "media_player":
                continue
            if entry.entity_id == own or entry.disabled_by is not None:
                continue
            state = self.hass.states.get(entry.entity_id)
            name = (
                (state.attributes.get("friendly_name") if state else None)
                or entry.name
                or entry.original_name
                or entry.entity_id
            )
            out.append({"entity": entry.entity_id, "name": str(name)})
        return sorted(out, key=lambda p: p["name"].lower())

    async def async_send_players(self, force: bool = False) -> None:
        """Send the list when it changed (or at a connect)."""
        players = self.players()
        if not force and players == self._sent_players:
            return
        if await self.async_send({"op": "players", "players": players}):
            self._sent_players = players

    @callback
    def _on_connect(self) -> None:
        self._sent_players = None
        self._schedule_players()

    @callback
    def _on_registry_change(self, event: Event) -> None:
        entity_id = str(event.data.get("entity_id", ""))
        if entity_id.startswith("media_player."):
            self._schedule_players()

    @callback
    def _schedule_players(self) -> None:
        """A short pause first, so a burst of changes (Music Assistant starting) sends one list."""
        self._cancel_pending()

        @callback
        def run(_now: Any) -> None:
            self._pending = None
            self.entry.async_create_background_task(
                self.hass, self.async_send_players(), "kachel_players"
            )

        self._pending = async_call_later(self.hass, _PLAYERS_DELAY, run)

    @callback
    def _cancel_pending(self) -> None:
        if self._pending is not None:
            self._pending()
            self._pending = None

    # --- play on … --------------------------------------------------------------------------

    async def _on_play_on(self, event: Event) -> None:
        if event.data.get(ATTR_DEVICE_ID) != self.data.main_device_id:
            return
        target = event.data.get("target")
        if not isinstance(target, str) or target not in {p["entity"] for p in self.players()}:
            _LOGGER.warning(
                "Kachel %s: play on %r refused (not a Music Assistant speaker)",
                self.data.name,
                target,
            )
            return
        await self.async_play_on(target)

    async def async_play_on(self, target: str) -> None:
        """Move what the device plays to `target`."""
        own = self.own_music_assistant_player()
        own_state = self.hass.states.get(own) if own else None
        if own and own_state is not None and own_state.state in _PLAYING:
            await self.hass.services.async_call(
                MUSIC_ASSISTANT,
                "transfer_queue",
                {"entity_id": target, "source_player": own, "auto_play": True},
                blocking=True,
            )
            return
        if self.data.last_media is not None and self._speaker_playing():
            media_id, media_type = self.data.last_media
            await self.hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": target,
                    "media_content_id": media_id,
                    "media_content_type": media_type,
                },
                blocking=True,
            )
            self._stop_speaker()
            return
        _LOGGER.info("Kachel %s: nothing playing to move to %s", self.data.name, target)

    def _speaker(self) -> MediaPlayerInfo | None:
        infos = self.data.infos.get(MediaPlayerInfo) or []
        return infos[0] if infos else None

    def _speaker_playing(self) -> bool:
        if (info := self._speaker()) is None:
            return False
        state = self.data.states.get((info.device_id, info.key))
        return state is not None and getattr(state, "state", None) in (2, 3)  # PLAYING, PAUSED

    def _stop_speaker(self) -> None:
        if (info := self._speaker()) is not None:
            self.data.client.media_player_command(
                info.key, command=MediaPlayerCommand.STOP, device_id=info.device_id
            )
