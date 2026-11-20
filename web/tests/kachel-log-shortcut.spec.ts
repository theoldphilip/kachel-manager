// Kachel Manager: the way to a device's log from Settings (src/kachel/LogShortcut.vue): one button per device, which opens
// that screen's settings.
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import LogShortcut from "../src/kachel/LogShortcut.vue";
import { useInventoryStore } from "../src/stores/inventory";
import { useSessionStore } from "../src/stores/session";
import { useUiStore } from "../src/stores/ui";
import type { Screen } from "../src/types";

describe("the way to a device's log", () => {
  it("opens the screen's settings", async () => {
    const inv = useInventoryStore();
    inv.inventory.screens.push({ id: "text.fire_kachel_inbox", name: "Fire", online: true, layout: { title: "", tiles: [] } } as unknown as Screen);
    const session = useSessionStore();
    const select = vi.spyOn(session, "select").mockImplementation(async (id: string | null) => { (await import("../src/stores/screen")).useScreenStore().selected = id; });
    const wrapper = mount(LogShortcut);
    const button = wrapper.find('[data-screen="text.fire_kachel_inbox"]');
    expect(button.text()).toBe("Fire");
    await button.trigger("click");
    await flushPromises();
    expect(select).toHaveBeenCalledWith("text.fire_kachel_inbox");
    expect(useUiStore().tab).toBe("settings");
  });
});
