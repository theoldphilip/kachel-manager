// What the editor remembers of itself in this browser (composables/usePreference.ts): under the names and values it always
// had, written as it changes and only then, never the default by itself, and nothing lost where the browser keeps nothing.
import { describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import { flagSerializer, usePreference } from "../../src/composables/usePreference";
import { inScope } from "../helpers/with-setup";

describe("a preference", () => {
  it("reads what the browser kept, in the values it always had, and the default when nothing is kept", () => {
    localStorage.setItem("kachel-manager.sidebar-folded", "1");
    const { result: folded } = inScope(() => usePreference("kachel-manager.sidebar-folded", false, { serializer: flagSerializer }));
    expect(folded.value).toBe(true);
    const { result: open } = inScope(() => usePreference("kachel-manager.full-editor", false, { serializer: flagSerializer }));
    expect(open.value).toBe(false);
    // The default is never written by itself.
    expect(localStorage.getItem("kachel-manager.full-editor")).toBeNull();
  });

  it("writes a change at once, and only a change", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const { result: width } = inScope(() => usePreference("kachel-manager.sidebar-width", 248, { serializer: { read: Number, write: String } }));
    width.value = 300;
    expect(localStorage.getItem("kachel-manager.sidebar-width")).toBe("300");
    width.value = 300;
    expect(setItem).toHaveBeenCalledTimes(1);
  });

  it("keeps JSON when it is given no serializer", () => {
    const { result } = inScope(() => usePreference<{ open: string[] }>("kachel-manager.test-json", { open: [] }));
    result.value = { open: ["kitchen"] };
    expect(JSON.parse(localStorage.getItem("kachel-manager.test-json")!)).toEqual({ open: ["kitchen"] });
  });

  it("follows a key that changes, such as the screen it belongs to, without writing one into the other", () => {
    localStorage.setItem("kachel-manager-mode:hall", "advanced");
    const screen = ref("hall");
    const { result: mode } = inScope(() => usePreference(() => `kachel-manager-mode:${screen.value}`, "simple"
      , { serializer: { read: (raw) => (raw === "advanced" ? "advanced" : "simple"), write: (value) => value } }));
    expect(mode.value).toBe("advanced");
    screen.value = "kitchen";
    expect(mode.value).toBe("simple");
    mode.value = "advanced";
    screen.value = "hall";
    expect(mode.value).toBe("advanced");
    expect([localStorage.getItem("kachel-manager-mode:hall"), localStorage.getItem("kachel-manager-mode:kitchen")]).toEqual(["advanced", "advanced"]);
  });

  it("goes on where the browser keeps nothing: the default, and no exception on a read or a write", () => {
    const blocked = () => { throw new DOMException("The operation is insecure.", "SecurityError"); };
    vi.stubGlobal("localStorage", { getItem: blocked, setItem: blocked, removeItem: blocked });
    const { result: height } = inScope(() => usePreference("kachel-manager.library-height", 300, { serializer: { read: Number, write: String } }));
    expect(height.value).toBe(300);
    height.value = 340;
    expect(height.value).toBe(340);
  });

  it("follows another tab only where it asks to", async () => {
    const quiet = inScope(() => usePreference("kachel-manager.test-tabs", "a"));
    const listening = inScope(() => usePreference("kachel-manager.test-tabs", "a", { listen: true }));
    localStorage.setItem("kachel-manager.test-tabs", JSON.stringify("b"));
    window.dispatchEvent(new StorageEvent("storage", { key: "kachel-manager.test-tabs", newValue: JSON.stringify("b"), storageArea: localStorage }));
    await nextTick();
    expect([quiet.result.value, listening.result.value]).toEqual(["a", "b"]);
    listening.stop();
  });
});
