// Kachel Manager: a search in the library looks through everything, whatever room or kind is chosen (src/components/
// Library.vue): a calendar without a room is found while a room stays chosen.
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import Library from "../src/components/Library.vue";
import { useInventoryStore } from "../src/stores/inventory";
import { useUiStore } from "../src/stores/ui";

describe("the library's search", () => {
  it("finds a calendar without a room while a room and a kind are chosen", async () => {
    const ui = useUiStore();
    ui.libraryOpen = true;
    const inv = useInventoryStore();
    inv.inventory.editor_features = { ...(inv.inventory.editor_features || {}), esp_screens: false } as any;
    inv.inventory.entities.push({ id: "calendar.abfallnavi", name: "AbfallNavi", device: "", area: "", state: "off" } as any);
    ui.room = "Kitchen";
    ui.filter = "light";
    ui.search = "abfall";
    const library = mount(Library);
    await flushPromises();
    expect(library.findAll(".ent .tx b").map((b) => b.text())).toEqual(["AbfallNavi"]);
  });
});
