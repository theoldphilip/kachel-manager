// Kachel Manager: the sidebar shows the Kachel mark and name (src/kachel/KachelMark.vue), not Tessera's.
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Sidebar from "../src/components/Sidebar.vue";
import { useInventoryStore } from "../src/stores/inventory";

beforeEach(() => { vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline")))); });

describe("the Kachel Manager's sidebar", () => {
  it("has the Kachel mark and name", async () => {
    useInventoryStore().inventory = { connected: true, entities: [], screens: [], editor_features: { esp_screens: false } } as any;
    const sidebar = mount(Sidebar);
    await flushPromises();
    expect(sidebar.find(".brand .kachel-mark").exists()).toBe(true);
    expect(sidebar.find(".brand .tessera-mark").exists()).toBe(false);
    expect(sidebar.find(".brand .txt").text()).toBe("Kachel");
    sidebar.unmount();
  });
});
