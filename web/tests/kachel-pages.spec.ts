// Kachel Manager: pages as the redesign draws them (src/components/LayoutView.vue, src/kachel/kachel-theme.css): one page at
// a time with its pages as tabs above it, as large as fits, no row of pages and no map; Tessera keeps its row.
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import LayoutView from "../src/components/LayoutView.vue";
import { useInventoryStore } from "../src/stores/inventory";
import { useDocumentStore } from "../src/stores/document";
import { loadLayout } from "./helpers/fixtures";

describe("the pages of a Kachel device", () => {
  it("stand one at a time, with their pages as tabs", () => {
    const inv = useInventoryStore();
    inv.inventory.editor_features = { ...(inv.inventory.editor_features || {}), esp_screens: false } as any;
    loadLayout({ title: "Wohnzimmer", pages: 2, tiles: [] });
    const view = mount(LayoutView);
    const doc = useDocumentStore();
    expect(view.find(".page-pills").exists()).toBe(true);
    expect(view.findAll(".page-pills button[aria-pressed]").length).toBe(doc.document!.pages.length);
    expect(view.find(".page-pill-add").exists()).toBe(true);
    expect(view.findAll("#layout-preview .page:not(.ghost)").length).toBe(1);
    expect(view.find("#layout-preview .page.ghost").exists()).toBe(false);
    expect(view.find(".seg.views").exists()).toBe(false);
  });
  it("keep Tessera's row while the ESP32 parts are on", () => {
    const inv = useInventoryStore();
    inv.inventory.editor_features = { ...(inv.inventory.editor_features || {}), esp_screens: true } as any;
    loadLayout({ title: "Wohnzimmer", pages: 2, tiles: [] });
    const view = mount(LayoutView);
    expect(view.find(".page-pills").exists()).toBe(false);
    expect(view.find(".seg.views").exists()).toBe(true);
  });
});
