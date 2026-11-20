// Kachel Manager: a Kachel device names its Kachel version and what device it is (screen_manager/app/kachel_board.py), not
// Tessera's firmware number and ESP32 board: in the sidebar's details and on the overview.
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import Sidebar from "../src/components/Sidebar.vue";
import { screenFixture } from "./helpers/fixtures";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import type { Screen } from "../src/types";

describe("a Kachel device's details", () => {
  it("are its Kachel version and its device", async () => {
    const fire = screenFixture({ id: "text.fire_seiten_kachel_inbox", name: "Fire", online: true, firmware: "0.60.0", board: "unknown",
      kachel: { version: "0.0.9-dev5", board: "fire8", device: "Amazon Fire HD 8 Plus" }, layout: { title: "", tiles: [] } } as unknown as Screen);
    useInventoryStore().inventory.screens = [fire];
    useScreenStore().selected = null;
    const sidebar = mount(Sidebar);
    const item = sidebar.find("#screens .screen-item");
    await item.find(".nav-item").trigger("click");
    await item.find(".details-toggle").trigger("click");
    expect(item.findAll(".facts dt").map((dt) => dt.text())).toEqual(["Kachel version", "Device"]);
    expect(item.findAll(".facts dd").map((dd) => dd.text())).toEqual(["0.0.9-dev5", "Amazon Fire HD 8 Plus"]);
    expect(item.text()).not.toContain("0.60.0");
  });
});
