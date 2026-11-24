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

# Shown as the manufacturer of every Kachel device (echod itself reports "TECHO5", its origin; Philip wants
# "Kachel" in HA, 2026-11-20).
MANUFACTURER: Final = "Kachel"

# May the device perform Home Assistant actions? The ESPHome integration's option name (the Kachel
# Manager reads it); default on for the Kachel devices (Philip, 2026-11-19), off at ESPHome.
CONF_ALLOW_SERVICE_CALLS: Final = "allow_service_calls"
DEFAULT_ALLOW_SERVICE_CALLS: Final = True

# A short random id given to each new adoption and kept in its config entry, part of every entity's
# unique id. After a factory reset and a new adoption the unique ids are new, so Home Assistant does not
# restore the old entity ids (it keeps deleted entities by unique id) and the ids follow the device's
# current name (Philip, 2026-11-20). Entries made before 0.3.1 have none and keep their unique ids.
CONF_ADOPTION_ID: Final = "adoption_id"

# Bluetooth proxy (bluetooth.py): the scanner's source, kept for removing it with the entry, and the
# scanning mode chosen in the options (as in Home Assistant's ESPHome integration: auto by default).
CONF_BLUETOOTH_MAC_ADDRESS = "bluetooth_mac_address"
CONF_BLUETOOTH_SCANNING_MODE = "bluetooth_scanning_mode"
DEFAULT_BLUETOOTH_SCANNING_MODE = "auto"
