"""The icon set `kachel:` in Home Assistant's frontend (`kachel:mark`, `kachel:duo`, `kachel:tablet`).

Asked for by kachel-manager-addon (2026-11-28, Philip chose design A "mark" and this way): the Kachel Manager's
sidebar panel shows `kachel:mark`. Home Assistant draws an icon set only when a frontend module registers it as
`window.customIcons[prefix]`; this integration serves that module (frontend/kachel-icons.js, made by the Kachel
Manager's tools/kachel_sidebar_icon.py) and adds it to every frontend page.

Set up once in async_setup, not per device: the icon is there without a connected device. Home Assistant sets
up the integration at start whenever it has an entry; with no Kachel device added at all it is not loaded.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

ICONS_URL = "/kachel_static/kachel-icons.js"
ICONS_FILE = Path(__file__).parent / "frontend" / "kachel-icons.js"


async def async_setup(hass: HomeAssistant) -> None:
    """Serve the icon module and load it in the frontend (versioned, so a new release is not cached)."""
    version = (await async_get_integration(hass, DOMAIN)).version or "0"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(ICONS_URL, str(ICONS_FILE), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{ICONS_URL}?v={version}")
