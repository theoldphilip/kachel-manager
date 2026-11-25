// Kachel Manager: a Kachel device without its inbox (screen_manager/app/kachel_bare.py) opens with its tabs. The entry is
// the one the add-on sends (kachel-bare-entry.json, checked against kachel_bare.inventory_entries by test_kachel_bare.py):
// with 0.1.14 it came without a grid, the editor built no layout and showed the empty page instead of the tabs.
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ScreenView from "../src/components/ScreenView.vue";
import { useDocumentStore } from "../src/stores/document";
import { useInventoryStore } from "../src/stores/inventory";
import { useUiStore } from "../src/stores/ui";
import { openScreen } from "./helpers/fixtures";
import type { Screen } from "../src/types";
import entry from "./kachel-bare-entry.json";

vi.mock("../src/api", () => ({ api: vi.fn(), getJson: vi.fn(() => new Promise(() => {})), send: vi.fn() }));

describe("a Kachel device without its inbox", () => {
  it("opens with Sources, Device, Functions and Log, and no pages", async () => {
    // The Kachel Manager always says it has no ESP32 screens (kachel.ESP_SCREENS).
    useInventoryStore().inventory.editor_features = { ...(useInventoryStore().inventory.editor_features || {}), esp_screens: false } as any;
    openScreen(entry as unknown as Screen);
    await flushPromises();
    expect(useDocumentStore().layout).not.toBeNull();
    const wrapper = mount(ScreenView);
    await flushPromises();
    for (const tab of ["sources", "settings", "functions", "log"]) expect(wrapper.find(`#tab-${tab}`).exists(), tab).toBe(true);
    expect(wrapper.find("#tab-layout").exists()).toBe(false);
    expect(useUiStore().tab).toBe("sources");
  });
});
