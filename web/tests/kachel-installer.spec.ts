// Kachel Manager: the installer page's read-only trial (src/kachel/InstallerView.vue, installer.ts, odin-readonly.ts):
// the read partition table against the profile, the lists of the code winning over the profile, and no write call of the
// Odin library anywhere in this stage.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { comparePit, neverHit, say, type InstallProfile } from "../src/kachel/installer";
import type { PitRead } from "../src/kachel/odin-readonly";

vi.mock("../src/api", () => ({ api: vi.fn(), getJson: vi.fn(), send: vi.fn() }));
vi.mock("../src/kachel/odin-readonly", () => ({ readPit: vi.fn() }));
import { getJson } from "../src/api";
import { readPit } from "../src/kachel/odin-readonly";
import InstallerView from "../src/kachel/InstallerView.vue";

const PROFILE: InstallProfile = {
  format: "kachel-install-profile", format_version: 1, board: "gta3xl", name: { de: "Galaxy Tab A 10.1", en: "Galaxy Tab A 10.1" },
  version: "3.3.1", protocol: "odin", usb: [{ vid: "04e8", pid: "685d" }],
  match: { odin: { pit_entries: 3, block_size: 512, partitions: { BOOT: 65536, CACHE: 311296 } } },
  confirm: [{ id: "wipe", text: "Alles wird gelöscht." }],
  mode_entry: [{ text: "Lauter und Leiser halten." }], leave_mode: [{ text: "Leiser und Ein/Aus 7 s halten." }],
  files: { "cache.img": { url: "3.3.1/cache.img", sha256: "a".repeat(64), size: 1000 }, "boot.img": { url: "3.3.1/boot.img", sha256: "b".repeat(64), size: 1000 } },
  write: [{ partition: "CACHE", file: "cache.img", max_size: 159383552 }, { partition: "BOOT", file: "boot.img", max_size: 33554432 }],
  never: ["RECOVERY"], after: { reboot: true, text: "Fertig." },
};
const PIT: PitRead = { entries: 3, rows: [
  { name: "BOOT", identifier: 5, blocks: 65536, start: 0 }, { name: "CACHE", identifier: 9, blocks: 311296, start: 0 },
  { name: "RECOVERY", identifier: 6, blocks: 92160, start: 0 }] };

afterEach(() => { vi.mocked(getJson).mockReset(); vi.mocked(readPit).mockReset(); });

describe("the read-only trial", () => {
  it("passes when the partition table is the one the profile means", () => {
    expect(comparePit(PROFILE, PIT).ok).toBe(true);
  });

  it("fails on another table, a missing partition, or a file too large", () => {
    expect(comparePit(PROFILE, { ...PIT, entries: 4 }).ok).toBe(false);
    expect(comparePit(PROFILE, { ...PIT, rows: PIT.rows.filter((r) => r.name !== "CACHE") }).ok).toBe(false);
    const big = structuredClone(PROFILE);
    big.files["boot.img"].size = 65536 * 512 + 1;
    expect(comparePit(big, PIT).ok).toBe(false);
  });

  it("never lets the profile name a partition the code does not allow", () => {
    for (const partition of ["RECOVERY", "BOOTLOADER", "UP_PARAM", "SYSTEM"]) {
      const bad = structuredClone(PROFILE);
      bad.write[1].partition = partition;
      bad.match.odin!.partitions[partition] = 92160;
      const rows = [...PIT.rows, { name: partition, identifier: 20, blocks: 92160, start: 0 }];
      expect(comparePit(bad, { entries: 3, rows }).ok, partition).toBe(false);
    }
    expect(neverHit("sec_efs") && neverHit("UP_PARAM") && !neverHit("CACHE")).toBe(true);
  });

  it("reads texts in the editor's language", () => {
    expect(say("nur deutsch", "en")).toBe("nur deutsch");
    expect(say({ de: "Hallo", en: "Hello" }, "en")).toBe("Hello");
    expect(say({ de: "Hallo", en: "Hello" }, "de-DE")).toBe("Hallo");
  });

  it("has no write call of the Odin library in this stage", () => {
    const source = readFileSync(resolve(process.cwd(), "src/kachel/odin-readonly.ts"), "utf8").replace(/\/\/.*$/gm, "");
    for (const call of ["flashPartition", "flashPit", "sendFile", "sendLz4File", "eraseUserdata", "reboot(", "endSession(true"]) {
      expect(source.includes(call), call).toBe(false);
    }
    const view = readFileSync(resolve(process.cwd(), "src/kachel/InstallerView.vue"), "utf8");
    expect(view.includes("libmjolnir")).toBe(false);
  });
});

describe("the installer page", () => {
  it("shows the device, runs the trial and says that it fits", async () => {
    vi.mocked(getJson).mockResolvedValue({ manager: "0.1.19", channels: [
      { channel: "stable", present: false, profile: null, problems: [] }, { channel: "dev", present: true, profile: PROFILE, problems: [] }] });
    vi.mocked(readPit).mockResolvedValue(PIT);
    Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });
    Object.defineProperty(navigator, "usb", { value: { requestDevice: vi.fn().mockResolvedValue({}) }, configurable: true });
    const wrapper = mount(InstallerView);
    await flushPromises();
    expect(wrapper.find("[data-browser=ok]").exists()).toBe(true);
    expect(wrapper.find("[data-profile=ok]").text()).toContain("3.3.1");
    await wrapper.find("#kachel-install-trial").trigger("click");
    await flushPromises();
    expect((navigator as any).usb.requestDevice).toHaveBeenCalledWith({ filters: [{ vendorId: 0x04e8, productId: 0x685d }] });
    expect(wrapper.find("[data-trial=match]").exists()).toBe(true);
    expect(wrapper.find("[data-row=BOOT]").exists()).toBe(true);
  });

  it("says when the page is not on HTTPS", async () => {
    vi.mocked(getJson).mockResolvedValue({ manager: "0.1.19", channels: [] });
    Object.defineProperty(window, "isSecureContext", { value: false, configurable: true });
    const wrapper = mount(InstallerView);
    await flushPromises();
    expect(wrapper.find("[data-browser=insecure]").exists()).toBe(true);
    expect(wrapper.find("[data-profile=none]").exists()).toBe(true);
  });
});
