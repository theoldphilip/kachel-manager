// Kachel Manager: Tessera's own setting groups (brightness, night, ...) need an ESP32 screen's entities, so the Kachel
// Manager (editor_features.esp_screens false) leaves them out of Screen settings; a Kachel tablet's are under Device.
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsTab from "../src/components/SettingsTab.vue";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import type { Screen } from "../src/types";
import { screenFixture } from "./helpers/fixtures";

const living = () => screenFixture({ id: "living", name: "Living room", online: true, firmware: "0.53.0",
  layout: { title: "Living room", tiles: [] },
  settings: { owner: "screen", keys: ["brightness", "dark_mode"], values: { brightness: 80, dark_mode: true }, unavailable: [] } } as unknown as Screen);

async function settings(espScreens?: boolean) {
  useInventoryStore().inventory = { connected: true, entities: [], screens: [living()],
    ...(espScreens === undefined ? {} : { editor_features: { esp_screens: espScreens } }) } as any;
  useScreenStore().selected = "living";
  const page = mount(SettingsTab, { attachTo: document.body });
  await flushPromises();
  return page;
}

beforeEach(() => { vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline")))); });

describe("Screen settings in the Kachel Manager", () => {
  it("leaves out Tessera's own groups", async () => {
    const page = await settings(false);
    expect(page.find('[data-setting="brightness"]').exists()).toBe(false);
    page.unmount();
  });

  it("keeps them where the app has ESP32 screens, as Tessera does", async () => {
    const page = await settings();
    expect(page.find('[data-setting="brightness"]').exists()).toBe(true);
    page.unmount();
  });
});
