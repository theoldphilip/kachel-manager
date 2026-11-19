"""Diagnostics download for a Kachel device (without the key)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import KachelConfigEntry
from .const import CONF_NOISE_PSK

TO_REDACT = {CONF_NOISE_PSK}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KachelConfigEntry
) -> dict[str, Any]:
    """What helps finding a fault: the entry (key redacted), the device and its entities."""
    data = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "available": data.available,
        "device_info": asdict(data.device_info) if data.device_info else None,
        "entities": {
            info_type.__name__: [{"object_id": i.object_id, "name": i.name} for i in infos]
            for info_type, infos in data.infos.items()
        },
    }
