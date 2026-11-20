// Kachel Manager: the overview names each tablet with its device and Kachel version (kachel_board.py), and its last card
// says how a tablet joins Home Assistant (the manual) instead of Tessera's New screen, which flashes an ESP32.
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import HomeView from "../src/components/HomeView.vue";
import { JOIN } from "../src/kachel/links";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import { loadLayout, screenFixture } from "./helpers/fixtures";

describe("the overview", () => {
  it("names the device and its Kachel version, and says how a tablet joins", () => {
    const inv = useInventoryStore();
    inv.inventory.editor_features = { ...(inv.inventory.editor_features || {}), esp_screens: false } as any;
    inv.inventory.screens = [screenFixture({ id: "text.fire_kachel_inbox", name: "Fire", online: true, area: "Test",
      kachel: { version: "0.0.9-dev5", board: "fire8", device: "Amazon Fire HD 8 Plus" },
      shape: { width: 1280, height: 800, columns: 4, rows: 3 }, layout: { title: "Fire", tiles: [] } } as any)];
    useScreenStore().selected = null;
    loadLayout(null);
    const home = mount(HomeView);
    expect(home.find(".home-name small").text()).toBe("Test · Amazon Fire HD 8 Plus · Kachel 0.0.9-dev5");
    expect(home.find(".kachel-join").attributes("href")).toBe(JOIN);
    expect(home.text()).toContain("How a tablet joins Home Assistant");
  });
});
