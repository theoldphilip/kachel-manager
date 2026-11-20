"""Kachel voice assistant: echod as an Assist satellite.

Adapted from Home Assistant's ESPHome assist satellite (homeassistant/components/esphome/assist_satellite.py,
Home Assistant Core 2026.11.2, Apache-2.0, see NOTICE), reduced to what echod speaks: audio both ways over
the API (no UDP), wake words detected on the device, timers, announcements and starting a conversation.
On the Fire the device offers a satellite only once Assist is set up in the Kachel Manager ("Funktionen");
the entity appears at the first connect that brings it and is unavailable while the device has none.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Callable
import contextlib
from functools import partial
import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aioesphomeapi import (
    APIConnectionError,
    MediaPlayerFormatPurpose,
    VoiceAssistantAnnounceFinished,
    VoiceAssistantAudioSettings,
    VoiceAssistantCommandFlag,
    VoiceAssistantEventType,
    VoiceAssistantExternalWakeWord,
    VoiceAssistantFeature,
    VoiceAssistantTimerEventType,
)
from homeassistant.components import assist_satellite, tts
from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType, PipelineStage
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.intent import TimerEventType, TimerInfo, async_register_timer_handler
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import get_url
from homeassistant.helpers.singleton import singleton
from homeassistant.util.hass_dict import HassKey
import probatio

from .const import DOMAIN
from .ffmpeg_proxy import async_create_proxy_url
from .manager import KachelData
from .wav_parser import stream_wav

if TYPE_CHECKING:
    from . import KachelConfigEntry

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# Custom wake words: the same folder as Home Assistant's ESPHome integration reads, served under our path.
WAKE_WORDS_DIR_NAME = "custom_wake_words"
WAKE_WORDS_API_PATH = f"/api/{DOMAIN}/wake_words"

_EVENT_TYPES: dict[PipelineEventType, VoiceAssistantEventType] = {
    PipelineEventType.ERROR: VoiceAssistantEventType.VOICE_ASSISTANT_ERROR,
    PipelineEventType.RUN_START: VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START,
    PipelineEventType.RUN_END: VoiceAssistantEventType.VOICE_ASSISTANT_RUN_END,
    PipelineEventType.STT_START: VoiceAssistantEventType.VOICE_ASSISTANT_STT_START,
    PipelineEventType.STT_END: VoiceAssistantEventType.VOICE_ASSISTANT_STT_END,
    PipelineEventType.INTENT_START: VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_START,
    PipelineEventType.INTENT_PROGRESS: VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_PROGRESS,
    PipelineEventType.INTENT_END: VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_END,
    PipelineEventType.TTS_START: VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START,
    PipelineEventType.TTS_END: VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END,
    PipelineEventType.WAKE_WORD_START: VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_START,
    PipelineEventType.WAKE_WORD_END: VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_END,
    PipelineEventType.STT_VAD_START: VoiceAssistantEventType.VOICE_ASSISTANT_STT_VAD_START,
    PipelineEventType.STT_VAD_END: VoiceAssistantEventType.VOICE_ASSISTANT_STT_VAD_END,
}

_TIMER_EVENT_TYPES: dict[TimerEventType, VoiceAssistantTimerEventType] = {
    TimerEventType.STARTED: VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_STARTED,
    TimerEventType.UPDATED: VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_UPDATED,
    TimerEventType.CANCELLED: VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_CANCELLED,
    TimerEventType.FINISHED: VoiceAssistantTimerEventType.VOICE_ASSISTANT_TIMER_FINISHED,
}

_ANNOUNCEMENT_TIMEOUT_SEC = 5 * 60
_CONFIG_TIMEOUT_SEC = 5
_WAKE_WORD_CONFIG_SCHEMA = probatio.Schema(
    {probatio.Required("type"): str, probatio.Required("wake_word"): str},
    extra=probatio.ALLOW_EXTRA,
)
_DATA_WAKE_WORDS: HassKey[dict[str, VoiceAssistantExternalWakeWord]] = HassKey(
    f"{DOMAIN}_wake_word_cache"
)


def unique_id_prefix(data: KachelData) -> str:
    """The prefix of the voice entities' unique ids (MAC and, for new adoptions, the adoption id)."""
    return f"{data.mac}-{data.adoption_id}" if data.adoption_id else data.mac


async def async_setup(hass: HomeAssistant) -> None:
    """Once: serve the custom wake word models the devices may download."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url_path=WAKE_WORDS_API_PATH, path=hass.config.path(WAKE_WORDS_DIR_NAME))]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KachelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the satellite at the first connect that brings voice features."""
    data = entry.runtime_data
    added = False

    @callback
    def on_connect() -> None:
        nonlocal added
        if added or not data.voice_features:
            return
        added = True
        async_add_entities([KachelAssistSatellite(entry)])

    entry.async_on_unload(data.async_add_connect_listener(on_connect))


class KachelAssistSatellite(assist_satellite.AssistSatelliteEntity):
    """The voice assistant of a Kachel device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(self, entry: KachelConfigEntry) -> None:
        """Bind to the device."""
        self.config_entry = entry
        self._data: KachelData = entry.runtime_data
        self._attr_unique_id = f"{unique_id_prefix(self._data)}-assist_satellite"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._data.mac)})
        self._attr_supported_features = assist_satellite.AssistSatelliteEntityFeature(0)
        self._is_running = True
        self._pipeline_task: asyncio.Task | None = None
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._tts_streaming_task: asyncio.Task | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._satellite_config = assist_satellite.AssistSatelliteConfiguration(
            available_wake_words=[], active_wake_words=[], max_active_wake_words=1
        )

    # --- what the entity is -------------------------------------------------------------------

    @property
    def _cli(self) -> Any:
        return self._data.client

    @property
    def _features(self) -> int:
        return self._data.voice_features

    @property
    def available(self) -> bool:
        """Available while connected and the device offers a voice assistant."""
        return self._data.available and bool(self._features)

    def _select_entity_id(self, key: str) -> str | None:
        return er.async_get(self.hass).async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{unique_id_prefix(self._data)}-{key}"
        )

    @property
    def pipeline_entity_id(self) -> str | None:
        """The pipeline select (select.py)."""
        return self._select_entity_id("pipeline")

    @property
    def vad_sensitivity_entity_id(self) -> str | None:
        """The "finished speaking" select (select.py)."""
        return self._select_entity_id("vad_sensitivity")

    @callback
    def async_get_configuration(self) -> assist_satellite.AssistSatelliteConfiguration:
        """Wake words the device has and uses."""
        return self._satellite_config

    async def async_set_configuration(
        self, config: assist_satellite.AssistSatelliteConfiguration
    ) -> None:
        """Choose the device's wake words."""
        await self._cli.set_voice_assistant_configuration(
            active_wake_words=config.active_wake_words
        )
        await self._update_satellite_config()

    async def _update_satellite_config(self) -> None:
        wake_words = await async_get_custom_wake_words(self.hass)
        try:
            config = await self._cli.get_voice_assistant_configuration(
                _CONFIG_TIMEOUT_SEC, external_wake_words=list(wake_words.values())
            )
        except TimeoutError, APIConnectionError:
            return
        self._satellite_config.available_wake_words = [
            assist_satellite.AssistSatelliteWakeWord(
                id=model.id,
                wake_word=model.wake_word,
                trained_languages=list(model.trained_languages),
            )
            for model in config.available_wake_words
        ]
        self._satellite_config.active_wake_words = list(config.active_wake_words)
        self._satellite_config.max_active_wake_words = config.max_active_wake_words

    # --- life cycle -----------------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Follow the connection: subscribe to the device's voice on every connect."""
        await super().async_added_to_hass()
        assert self.device_entry is not None
        self.async_on_remove(
            async_register_timer_handler(self.hass, self.device_entry.id, self.handle_timer_event)
        )
        self._data.availability_listeners.append(self.async_write_ha_state)
        self.async_on_remove(
            lambda: self._data.availability_listeners.remove(self.async_write_ha_state)
        )
        self.async_on_remove(self._data.async_add_connect_listener(self._on_connect))
        self.async_on_remove(self._unsubscribe_voice)

    @callback
    def _unsubscribe_voice(self) -> None:
        if self._unsubscribe is not None:
            with contextlib.suppress(APIConnectionError, RuntimeError):
                self._unsubscribe()
            self._unsubscribe = None

    @callback
    def _on_connect(self) -> None:
        """A (new) connection: subscribe again, read the wake words, set the features."""
        self._unsubscribe_voice()
        features = self._features
        if not features:
            self.async_write_ha_state()
            return
        self._unsubscribe = self._cli.subscribe_voice_assistant(
            handle_start=self.handle_pipeline_start,
            handle_stop=self.handle_pipeline_stop,
            handle_audio=self.handle_audio,
            handle_announcement_finished=self.handle_announcement_finished,
        )
        supported = assist_satellite.AssistSatelliteEntityFeature(0)
        if features & VoiceAssistantFeature.ANNOUNCE:
            supported |= assist_satellite.AssistSatelliteEntityFeature.ANNOUNCE
        if features & VoiceAssistantFeature.START_CONVERSATION:
            supported |= assist_satellite.AssistSatelliteEntityFeature.START_CONVERSATION
        self._attr_supported_features = supported
        if features & VoiceAssistantFeature.ANNOUNCE:
            self.config_entry.async_create_background_task(
                self.hass, self._update_satellite_config(), "kachel_satellite_config"
            )
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Stop what runs."""
        await super().async_will_remove_from_hass()
        self._is_running = False
        self._stop_pipeline()

    # --- pipeline events to the device ---------------------------------------------------------

    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Tell the device how the pipeline goes (and stream the answer)."""
        if (event_type := _EVENT_TYPES.get(event.type)) is None:
            return
        data: dict[str, Any] = {}
        if event_type == VoiceAssistantEventType.VOICE_ASSISTANT_STT_END:
            assert event.data is not None
            data = {"text": event.data["stt_output"]["text"]}
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_PROGRESS:
            if not event.data or not event.data.get("tts_start_streaming"):
                return
            data = {"tts_start_streaming": "1"}
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_INTENT_END:
            assert event.data is not None
            out = event.data["intent_output"]
            data = {
                "conversation_id": out["conversation_id"],
                "continue_conversation": str(int(out["continue_conversation"])),
                "speech": out["response"]["speech"].get("plain", {}).get("speech", ""),
            }
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_START:
            assert event.data is not None
            data = {"text": event.data["tts_input"]}
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END:
            assert event.data is not None
            if tts_output := event.data["tts_output"]:
                data = {"url": async_process_play_media_url(self.hass, tts_output["url"])}
                if self._features & VoiceAssistantFeature.SPEAKER and (
                    stream := tts.async_get_stream(self.hass, tts_output["token"])
                ):
                    self._tts_streaming_task = self.config_entry.async_create_background_task(
                        self.hass, self._stream_tts_audio(stream), "kachel_satellite_tts"
                    )
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_WAKE_WORD_END:
            assert event.data is not None
            if not event.data["wake_word_output"]:
                event_type = VoiceAssistantEventType.VOICE_ASSISTANT_ERROR
                data = {"code": "no_wake_word", "message": "No wake word detected"}
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_ERROR:
            assert event.data is not None
            data = {"code": event.data["code"], "message": event.data["message"]}
        elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_RUN_START:
            assert event.data is not None
            if tts_output := event.data.get("tts_output"):
                data = {"url": async_process_play_media_url(self.hass, tts_output["url"])}
        self._cli.send_voice_assistant_event(event_type, data)

    # --- announcements and conversations from Home Assistant ----------------------------------

    async def async_announce(
        self, announcement: assist_satellite.AssistSatelliteAnnouncement
    ) -> None:
        """Say something on the device; returns when it has been said."""
        await self._do_announce(announcement, run_pipeline_after=False)

    async def async_start_conversation(
        self, start_announcement: assist_satellite.AssistSatelliteAnnouncement
    ) -> None:
        """Say something, then listen for the answer."""
        await self._do_announce(start_announcement, run_pipeline_after=True)

    async def _do_announce(
        self, announcement: assist_satellite.AssistSatelliteAnnouncement, run_pipeline_after: bool
    ) -> None:
        media_id = announcement.media_id
        is_tts = announcement.media_id_source == "tts"
        preannounce = announcement.preannounce_media_id
        fmt = next(
            (
                f
                for f in self._data.media_formats
                if f.purpose == MediaPlayerFormatPurpose.ANNOUNCEMENT
            ),
            None,
        )
        if fmt is not None and self.device_entry is not None and ((not is_tts) or preannounce):
            make = partial(
                async_create_proxy_url,
                hass=self.hass,
                device_id=self.device_entry.id,
                media_format=fmt.format,
                rate=fmt.sample_rate or None,
                channels=fmt.num_channels or None,
                width=fmt.sample_bytes or None,
            )
            if not is_tts:
                media_id = async_process_play_media_url(self.hass, make(media_url=media_id))
            if preannounce:
                preannounce = async_process_play_media_url(self.hass, make(media_url=preannounce))
        try:
            await self._cli.send_voice_assistant_announcement_await_response(
                media_id,
                _ANNOUNCEMENT_TIMEOUT_SEC,
                announcement.message,
                start_conversation=run_pipeline_after,
                preannounce_media_id=preannounce or "",
            )
        except APIConnectionError as err:
            raise HomeAssistantError(f"Announcement on {self.name} failed: {err}") from err

    # --- what the device asks ------------------------------------------------------------------

    async def handle_pipeline_start(
        self,
        conversation_id: str,
        flags: int,
        audio_settings: VoiceAssistantAudioSettings,
        wake_word_phrase: str | None,
    ) -> int | None:
        """The device heard its wake word (or was tapped): run the pipeline with its audio."""
        while not self._audio_queue.empty():
            await self._audio_queue.get()
        if self._tts_streaming_task is not None:
            self._tts_streaming_task.cancel()
            self._tts_streaming_task = None
        start_stage = (
            PipelineStage.WAKE_WORD
            if flags & VoiceAssistantCommandFlag.USE_WAKE_WORD
            else PipelineStage.STT
        )
        if self._features & VoiceAssistantFeature.SPEAKER:
            # The answer is streamed as 16 kHz mono 16-bit PCM over the API.
            self._attr_tts_options = {
                tts.ATTR_PREFERRED_FORMAT: "wav",
                tts.ATTR_PREFERRED_SAMPLE_RATE: 16000,
                tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 1,
                tts.ATTR_PREFERRED_SAMPLE_BYTES: 2,
            }
        self._pipeline_task = self.config_entry.async_create_background_task(
            self.hass,
            self.async_accept_pipeline_from_satellite(
                audio_stream=self._wrap_audio_stream(),
                start_stage=start_stage,
                end_stage=PipelineStage.TTS,
                wake_word_phrase=wake_word_phrase,
            ),
            "kachel_satellite_pipeline",
        )
        return 0  # audio comes over the API, no UDP port

    async def handle_audio(self, data: bytes, data2: bytes | None = None) -> None:
        """A chunk of the device's microphone."""
        self._audio_queue.put_nowait(data)

    async def handle_pipeline_stop(self, abort: bool) -> None:
        """The device stopped sending audio (or aborts)."""
        self._audio_queue.put_nowait(None)
        if abort and self._pipeline_task is not None:
            self._pipeline_task.cancel()

    async def handle_announcement_finished(self, finished: VoiceAssistantAnnounceFinished) -> None:
        """The device has finished saying something."""
        self.tts_response_finished()

    def handle_timer_event(self, event_type: TimerEventType, timer_info: TimerInfo) -> None:
        """A timer of this device started, changed, was cancelled or finished."""
        if (native := _TIMER_EVENT_TYPES.get(event_type)) is None:
            return
        self._cli.send_voice_assistant_timer_event(
            native,
            timer_info.id,
            timer_info.name,
            timer_info.created_seconds,
            timer_info.seconds_left,
            timer_info.is_active,
        )

    # --- streaming --------------------------------------------------------------------------

    async def _stream_tts_audio(
        self,
        tts_result: tts.ResultStream,
        sample_rate: int = 16000,
        sample_width: int = 2,
        sample_channels: int = 1,
        samples_per_chunk: int = 512,
    ) -> None:
        """Stream the spoken answer to the device, keeping its 512 ms buffer about 75 % full."""
        self._cli.send_voice_assistant_event(
            VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_START, {}
        )
        try:
            if not self._is_running:
                return
            if tts_result.extension != "wav":
                _LOGGER.error("Kachel: only WAV can be streamed, got %s", tts_result.extension)
                return
            seconds_in_chunk = samples_per_chunk / sample_rate
            start_time: float | None = None
            sent = 0.0
            async for chunk, is_last in stream_wav(
                tts_result.async_stream_result(),
                expected_format="pcm",
                expected_channels=sample_channels,
                expected_width=sample_width,
                expected_sample_rate=sample_rate,
                samples_per_chunk=samples_per_chunk,
            ):
                if not self._is_running:
                    break
                if start_time is None:
                    start_time = asyncio.get_running_loop().time()
                self._cli.send_voice_assistant_audio(chunk)
                sent += seconds_in_chunk
                if is_last:
                    break
                elapsed = asyncio.get_running_loop().time() - start_time
                if (wait := (sent - 0.384) - elapsed) > 0:
                    await asyncio.sleep(wait)
        except ValueError as err:
            _LOGGER.error("Kachel: error streaming WAV: %s", err)
        except asyncio.CancelledError:
            return
        finally:
            self._cli.send_voice_assistant_event(
                VoiceAssistantEventType.VOICE_ASSISTANT_TTS_STREAM_END, {}
            )
        self.tts_response_finished()

    async def _wrap_audio_stream(self) -> AsyncIterable[bytes]:
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                break
            if chunk:
                yield chunk

    def _stop_pipeline(self) -> None:
        self._audio_queue.put_nowait(None)


async def async_get_custom_wake_words(
    hass: HomeAssistant,
) -> dict[str, VoiceAssistantExternalWakeWord]:
    """The custom wake word models in <config>/custom_wake_words (offered to the device)."""
    return await hass.async_add_executor_job(_get_custom_wake_words, hass)


@singleton(_DATA_WAKE_WORDS)
def _get_custom_wake_words(hass: HomeAssistant) -> dict[str, VoiceAssistantExternalWakeWord]:
    wake_words_dir = Path(hass.config.path(WAKE_WORDS_DIR_NAME))
    wake_words: dict[str, VoiceAssistantExternalWakeWord] = {}
    for config_path in wake_words_dir.glob("*.json"):
        model_path = config_path.with_suffix(".tflite")
        if not model_path.exists():
            continue
        with open(config_path, encoding="utf-8") as config_file:
            config_dict = json.load(config_file)
        try:
            config = _WAKE_WORD_CONFIG_SCHEMA(config_dict)
        except probatio.Invalid:
            continue
        model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
        base_url = get_url(hass, prefer_external=False, allow_cloud=False)
        wake_words[config_path.stem] = VoiceAssistantExternalWakeWord.from_dict(
            {
                "id": config_path.stem,
                "wake_word": config["wake_word"],
                "trained_languages": config_dict.get("trained_languages", []),
                "model_type": config["type"],
                "model_size": model_path.stat().st_size,
                "model_hash": model_hash,
                # The model's JSON config; the device reads the model file's name from it (as with ESPHome).
                "url": f"{base_url}{WAKE_WORDS_API_PATH}/{config_path.name}",
            }
        )
    return wake_words
