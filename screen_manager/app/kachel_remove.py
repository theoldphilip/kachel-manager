"""Kachel Manager: a Kachel device leaves Home Assistant when it is reset to its factory settings (fire-app, laufband test
2026-11-21).

A device asks in one of two ways: its inbox says `remove` (kachel.wants_removal, a device with pages), or it fires the
event `screen_remove` (EVENT under ESPHome, `kachel.screen_remove` under the Kachel integration, read as the ESPHome
twin by kachel.as_esphome_event), which every Kachel device can send, a Spezialanzeige without an inbox too (the
Laufband: its inbox-less request never reached the add-on, and its entry stayed). The event's data carry the `device_id`
Home Assistant adds and, from the device, its `mac`.

Removing a device takes everything Home Assistant keeps for it by its MAC address: its entry under ESPHome and under the
Kachel integration (a device moved from one to the other can have both) and a Bluetooth proxy's entry of the same MAC
from its ESPHome days. The pages of a screen on it are kept first (kachel_keep), and what the add-on kept for the screen
is forgotten. Home Assistant goes first: what it refuses stays, and the log says so.
"""
import asyncio
import contextlib
import logging
import re

import kachel
import kachel_keep

LOG = logging.getLogger('screen_manager')

EVENT = 'esphome.screen_remove'
LEFTOVER_DOMAINS = ('bluetooth',)
_MAC = re.compile(r'^[0-9a-f]{12}$')


def plain_mac(value):
    """12 lower-case hex digits of a MAC address in any common spelling, or None."""
    text = re.sub(r'[^0-9a-fA-F]', '', value).lower() if isinstance(value, str) else ''
    return text if _MAC.match(text) else None


def devices_of_mac(devices, mac):
    """The ids of the devices whose MAC address (their own or the one they hang under) is `mac`."""
    devices = [d for d in devices or () if isinstance(d, dict)]
    return {d.get('id') for d in devices if kachel._mac_of(d, devices) == mac}


async def entries_to_remove(ha, ids, mac):
    """The config entries that go with the device: ESPHome and Kachel entries of its devices, and leftovers of the same MAC
    (a Bluetooth proxy's entry, whose unique id is the MAC)."""
    platform = await ha.esphome_entries()   # ESPHome and Kachel (kachel.PLATFORMS)
    found = {entry for device in getattr(ha, 'devices', None) or [] if isinstance(device, dict) and device.get('id') in ids
             for entry in device.get('config_entries') or [] if entry in platform}
    for domain in LEFTOVER_DOMAINS:
        with contextlib.suppress(Exception):
            for entry in await ha.request('config_entries/get', domain=domain) or []:
                if isinstance(entry, dict) and plain_mac(entry.get('unique_id')) == mac and entry.get('entry_id'):
                    found.add(entry['entry_id'])
    return sorted(found)


async def forget_screens(manager, ids):
    """Keep the pages of every screen on these devices and forget what the add-on kept for it (Manager.remove_screen's
    second half): its layout sensors, its inbox's records, its plugins, icons, label and hang."""
    for screen in [s for s in manager.screens() if s.get('device_id') in ids]:
        inbox = screen['id']
        kachel_keep.keep(manager, screen, inbox)
        for sensor in manager.layout_sensors(screen):
            with contextlib.suppress(Exception):
                await manager.ha.remove_state(sensor)
        manager.forget_inbox(inbox)
        for keeper, name in ((getattr(manager, 'plugins', None), 'forget_screen'), (getattr(manager, 'icons', None), 'forget_screen')):
            if keeper is not None and hasattr(keeper, name):
                getattr(keeper, name)(inbox)
        for keeper in (getattr(manager, 'labels', None), getattr(manager, 'hangs', None)):
            if keeper is not None and hasattr(keeper, 'forget'):
                keeper.forget(screen.get('device_id'))


async def remove_device(manager, device_id=None, mac=None):
    """Remove a Kachel device from Home Assistant by its MAC (from the request, else from its device): True when every
    entry went, False when there was nothing to remove or Home Assistant refused one."""
    ha = manager.ha
    devices = getattr(ha, 'devices', None) or []
    mac = plain_mac(mac)
    if not mac and device_id:
        device = next((d for d in devices if isinstance(d, dict) and d.get('id') == device_id), None)
        mac = kachel._mac_of(device, devices)
    if not mac:
        LOG.warning('A device asked to leave Home Assistant, but its MAC address is not known (device %s)', device_id)
        return False
    ids = devices_of_mac(devices, mac) | ({device_id} if device_id else set())
    entries = await entries_to_remove(ha, ids, mac)
    if not entries:
        LOG.info('A device (%s) asked to leave Home Assistant; nothing of it is there', mac)
        return False
    await forget_screens(manager, ids)
    done = True
    for entry in entries:
        try:
            await ha.delete_config_entry(entry)
        except Exception as error:  # noqa: BLE001 - the others still go; the log says which stayed
            LOG.warning('The entry %s of device %s could not be removed (%s)', entry, mac, error)
            done = False
    LOG.info('Device %s left Home Assistant at its factory reset: %d entr%s removed', mac, len(entries), 'y' if len(entries) == 1 else 'ies')
    return done


async def loop(manager):
    """The devices' requests to leave (HA client's kachel_removals): one at a time."""
    queue = manager.ha.kachel_removals
    while True:
        body = await queue.get()
        if not isinstance(body, dict):
            continue
        try:
            await remove_device(manager, body.get('device_id'), body.get('mac'))
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - a failed removal must not stop the next one
            LOG.warning('A device could not leave Home Assistant (%s)', error)
