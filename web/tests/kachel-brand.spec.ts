// Kachel Manager: the sidebar shows the Kachel mark and name (src/kachel/KachelMark.vue), not Tessera's, the manual is
// ours, and the support card asks for Philip's donation page (src/kachel/links.ts).
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Sidebar from "../src/components/Sidebar.vue";
import DonateCard from "../src/components/DonateCard.vue";
import { DONATE, MANUAL } from "../src/kachel/links";
import { useInventoryStore } from "../src/stores/inventory";

beforeEach(() => { vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline")))); });

describe("the Kachel Manager's sidebar", () => {
  it("has the Kachel mark and name", async () => {
    useInventoryStore().inventory = { connected: true, entities: [], screens: [], editor_features: { esp_screens: false } } as any;
    const sidebar = mount(Sidebar);
    await flushPromises();
    expect(sidebar.find(".brand .kachel-mark").exists()).toBe(true);
    expect(sidebar.find(".brand .tessera-mark").exists()).toBe(false);
    expect(sidebar.find(".brand .txt").text()).toBe("Kachel Manager");
    expect(sidebar.find("#open-manual").attributes("href")).toBe(MANUAL);
    sidebar.unmount();
  });

  it("asks for a donation through Philip's page, with one link", () => {
    localStorage.setItem("kachel-manager.donate", "0");
    const card = mount(DonateCard);
    expect(card.findAll(".donate-actions a").map((a) => a.attributes("href"))).toEqual([DONATE]);
    card.unmount();
  });
});
