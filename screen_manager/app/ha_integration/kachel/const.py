"""Constants for the Kachel integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "kachel"

DEFAULT_PORT: Final = 6053

CONF_NOISE_PSK: Final = "noise_psk"
CONF_DEVICE_NAME: Final = "device_name"
CONF_BOARD: Final = "board"

# The boards this integration takes: the Kachel base devices, Fire and Laufband ("Basis gleich", Philip
# 2026-11-19 20:51; Laufband added on his word, 2026-11-19 22:18). The Wohnzimmer (gta3xl) stays with Tessera/ESPHome.
# Keep in line with manifest.json "zeroconf".
SUPPORTED_BOARDS: Final = frozenset({"fire8", "a12s"})

CLIENT_INFO: Final = "Home Assistant Kachel"

MANUFACTURER: Final = "Kachel"

# May the device perform Home Assistant actions? The ESPHome integration's option name (the Kachel
# Manager reads it); default on for the Kachel devices (Philip, 2026-11-19), off at ESPHome.
CONF_ALLOW_SERVICE_CALLS: Final = "allow_service_calls"
DEFAULT_ALLOW_SERVICE_CALLS: Final = True
