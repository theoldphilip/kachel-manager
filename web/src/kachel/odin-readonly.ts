// Kachel Manager: the read-only trial of the first install (Spur K, format v1 of kachel-installer-tool). The one place
// that touches the Odin library (@lineageos-infra/libmjolnir, MIT): connect, begin a session, read the partition table
// (PIT), end the session without a reboot, close. Nothing here writes to the device, and no write call of the library
// is named in this file (tests/kachel-installer.spec.ts reads it to make sure). Writing comes in a later stage, only
// after this trial worked on a real device, and only through the lists in the code (installer.ts).
import { OdinDevice } from "@lineageos-infra/libmjolnir";

// `start`: the PIT's blockSizeOrOffset, on eMMC the first block of the partition (not a size); the block size comes from
// the profile (512 on Samsung).
export type PitRow = { name: string; identifier: number; blocks: number; start: number };
export type PitRead = { entries: number; rows: PitRow[] };

/** The device's partition table, read and nothing else. `usb` comes from the browser's own device chooser. */
export async function readPit(usb: USBDevice, log: (line: string) => void = () => {}): Promise<PitRead> {
  const device = new OdinDevice(usb, { timeout: 15000, logging: false, logger: (_level, ...data) => log(data.map(String).join(" ")) });
  try {
    await device.initialize();
    await device.beginSession();
    const pit = await device.getPitData();
    await device.endSession(false);
    const rows = pit.entries.map((entry) => ({ name: entry.partitionName, identifier: entry.identifier,
      blocks: entry.blockCount, start: entry.blockSizeOrOffset }));
    return { entries: pit.entryCount, rows };
  } finally {
    await device.close().catch(() => undefined);
  }
}
