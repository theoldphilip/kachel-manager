// Kachel Manager: the sources of a Spezialanzeige, its tab "Sources" (src/kachel/SourcesPanel.vue): what the device asks
// for, an entity picked for each from what fits, the room's name, saved in one go.
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import SourcesPanel from "../src/kachel/SourcesPanel.vue";
import UiSelect from "../src/components/ui/UiSelect.vue";
import { getJson, send } from "../src/api";
import { openScreen } from "./helpers/fixtures";
import type { Screen } from "../src/types";

vi.mock("../src/api", () => ({ api: vi.fn(), getJson: vi.fn(), send: vi.fn() }));

const SCREEN = { id: "text.laufband_kachel_inbox", name: "Laufband", online: true, kachel_kind: "special", layout: { title: "", tiles: [] } } as unknown as Screen;
const VIEW = {
  kind: "special", supported: true, delivered: true, area: "Hobbyraum", room: null,
  sources: { temperature: "sensor.hobby_temp" },
  offered: [
    { key: "temperature", name: { de: "Raumtemperatur", en: "Room temperature" }, domains: ["sensor"], device_class: ["temperature"], required: false },
    { key: "light", name: { de: "Licht", en: "Light" }, domains: ["switch", "light"], device_class: [], required: false },
    { key: "power", name: { en: "Power meter" }, domains: ["sensor"], device_class: ["power"], required: true },
  ],
  choices: { temperature: [["sensor.hobby_temp", "Hobby Temperatur"]], light: [["switch.hobby_deckenlicht", "Hobby Deckenlicht"]], power: [] },
};

afterEach(() => { vi.mocked(getJson).mockReset(); vi.mocked(send).mockReset(); });

async function panel(view: object) {
  vi.mocked(getJson).mockResolvedValue(view);
  openScreen(SCREEN);
  const wrapper = mount(SourcesPanel);
  await flushPromises();
  return wrapper;
}

describe("a Spezialanzeige's sources", () => {
  it("lists what the device asks for, with the names it gives and what fits", async () => {
    const wrapper = await panel(VIEW);
    expect(getJson).toHaveBeenCalledWith("screens/text.laufband_kachel_inbox/kachel/sources");
    expect(wrapper.find("[data-source=temperature] .s-label").text()).toContain("Room temperature");
    expect(wrapper.find("[data-source=power] .req").classes()).toContain("missing");
    expect(wrapper.find("[data-source=power]").text()).toContain("Nothing in Home Assistant fits");
    expect((wrapper.find("#kachel-room").element as HTMLInputElement).placeholder).toBe("Hobbyraum");
    expect(wrapper.find("[data-sources=state]").text()).toBe("The device has it");
  });

  it("are changed here and saved in one go, an empty one off", async () => {
    const wrapper = await panel(VIEW);
    const selects = wrapper.findAllComponents(UiSelect);
    selects[0].vm.$emit("update:modelValue", "");
    selects[1].vm.$emit("update:modelValue", "switch.hobby_deckenlicht");
    await wrapper.find("#kachel-room").setValue(" Keller ");
    expect(wrapper.find("[data-sources=state]").text()).toBe("Not saved yet");
    vi.mocked(send).mockResolvedValue({ ...VIEW, sources: { light: "switch.hobby_deckenlicht" }, room: "Keller", delivered: false });
    await wrapper.find("#kachel-sources-save").trigger("click");
    await flushPromises();
    expect(send).toHaveBeenCalledWith("screens/text.laufband_kachel_inbox/kachel/sources", "PUT",
      { sources: { light: "switch.hobby_deckenlicht" }, room: "Keller" });
  });

  it("says when the device has not offered any yet, or can't take them", async () => {
    const wrapper = await panel({ ...VIEW, offered: [], choices: {}, sources: {}, supported: false });
    expect(wrapper.find("[data-sources=none]").exists()).toBe(true);
    expect(wrapper.find("[data-sources=unsupported]").exists()).toBe(true);
  });

  it("of a device without its inbox wait for it, and say so", async () => {
    vi.mocked(getJson).mockResolvedValue({ ...VIEW, offered: [], choices: {}, sources: {}, supported: false });
    openScreen({ ...SCREEN, id: "kachel:laufband", kachel_bare: true } as unknown as Screen);
    const wrapper = mount(SourcesPanel);
    await flushPromises();
    expect(getJson).toHaveBeenCalledWith("screens/kachel%3Alaufband/kachel/sources");
    expect(wrapper.find("[data-sources=bare]").exists()).toBe(true);
    expect(wrapper.find("[data-sources=unsupported]").exists()).toBe(false);
  });
});
