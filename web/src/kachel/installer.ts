// Kachel Manager: what the installer page decides, without a device (Spur K, format v1 of kachel-installer-tool,
// ~/kachel-installer/STAND.md "Formate v1 – FESTGELEGT"). The lists here are the same as the add-on's
// (screen_manager/app/kachel_installer.py) and win over the profile: the profile can only make them smaller.
import type { PitRead } from "./odin-readonly";

export type Text = string | { de?: string; en?: string };
export type Step = { text: Text; image?: string };
export type InstallProfile = {
  format: string; format_version: number; board: string; name: Text; version: string; protocol: string;
  usb: { vid: string; pid: string }[];
  match: { odin?: { pit_entries: number; block_size: number; partitions: Record<string, number> } };
  confirm: { id: string; text: Text }[]; mode_entry: Step[]; leave_mode?: Step[];
  files: Record<string, { url: string; sha256: string; size: number }>;
  write: { partition: string; file: string; max_size: number }[]; never: string[];
  after: { reboot: boolean; first_boot_minutes?: number; text: Text };
};
export type Channel = { channel: string; present: boolean; profile: InstallProfile | null; problems: string[] };

export const ALLOWED: Record<string, readonly string[]> = { gta3xl: ["BOOT", "VBMETA", "CACHE"], fire8: ["boot", "cache"], a12s: ["boot", "cache"] };
export const NEVER = ["bootloader", "param", "efs", "persistent", "steady", "rpmb", "preloader", "lk", "tee", "nvcfg", "boot_para",
  "kb", "dkb", "metadata", "misc", "recovery"] as const;
export const neverHit = (name: string) => NEVER.some((word) => name.toLowerCase().includes(word));

/** A text of the profile in the editor's language: a plain string is German, else {de, en}. */
export function say(text: Text | undefined, language: string): string {
  if (!text) return "";
  if (typeof text === "string") return text;
  return (language.startsWith("de") ? text.de || text.en : text.en || text.de) || "";
}

/** Whether this browser can do it at all: WebUSB needs a secure page (HTTPS) and Chrome or Edge. */
export function browserCheck(win: { isSecureContext: boolean; navigator: Navigator }) {
  return { secure: Boolean(win.isSecureContext), usb: Boolean(win.isSecureContext && "usb" in win.navigator) };
}

export type CheckRow = { what: "entries" | "partition" | "write"; name: string; want: string; got: string; ok: boolean };

/** The read PIT against the profile: the number of entries, every partition of `match` with exactly its blocks, and every
 * partition the install would write there, allowed, never hit and large enough for its file. All rows ok: the device is
 * the one the profile means. Nothing is written by this, ever. */
export function comparePit(profile: InstallProfile, pit: PitRead): { ok: boolean; rows: CheckRow[] } {
  const odin = profile.match.odin;
  const rows: CheckRow[] = [];
  if (!odin) return { ok: false, rows };
  const byName = new Map(pit.rows.map((row) => [row.name, row]));
  rows.push({ what: "entries", name: "PIT", want: String(odin.pit_entries), got: String(pit.entries), ok: pit.entries === odin.pit_entries });
  for (const [name, blocks] of Object.entries(odin.partitions)) {
    const found = byName.get(name);
    rows.push({ what: "partition", name, want: String(blocks), got: found ? String(found.blocks) : "–", ok: Boolean(found && found.blocks === blocks) });
  }
  const allowed = ALLOWED[profile.board] || [];
  for (const item of profile.write) {
    const found = byName.get(item.partition);
    const size = profile.files[item.file]?.size ?? 0;
    const room = found ? found.blocks * odin.block_size : 0;
    const fits = Boolean(found) && size > 0 && size <= item.max_size && size <= room;
    const legal = allowed.includes(item.partition) && !neverHit(item.partition) && !profile.never.includes(item.partition);
    rows.push({ what: "write", name: item.partition, want: `${item.file} ${size}`, got: found ? String(room) : "–", ok: fits && legal });
  }
  return { ok: rows.every((row) => row.ok), rows };
}
