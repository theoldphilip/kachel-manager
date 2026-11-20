// Kachel Manager: what is set up for a Kachel device, its tab "Functions" (src/kachel/FunctionsPanel.vue): read from the
// add-on, changed here, saved in one go; a tablet that can't take functions yet says so.
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import FunctionsPanel from "../src/kachel/FunctionsPanel.vue";
import { getJson, send } from "../src/api";
import { openScreen } from "./helpers/fixtures";
import { useInventoryStore } from "../src/stores/inventory";
import type { Screen } from "../src/types";

vi.mock("../src/api", () => ({ api: vi.fn(), getJson: vi.fn(), send: vi.fn() }));

const SCREEN = { id: "text.fire_kachel_inbox", name: "Fire", online: true, layout: { title: "", tiles: [] } } as unknown as Screen;

afterEach(() => { vi.mocked(getJson).mockReset(); vi.mocked(send).mockReset(); });

async function panel(view: object) {
  vi.mocked(getJson).mockResolvedValue(view);
  openScreen(SCREEN);
  const wrapper = mount(FunctionsPanel);
  await flushPromises();
  return wrapper;
}

describe("a tablet's functions", () => {
  it("are changed here and saved in one go", async () => {
    const wrapper = await panel({ functions: { page_turn: { ways: ["swipe"] } }, supported: true, delivered: true });
    expect(getJson).toHaveBeenCalledWith("screens/text.fire_kachel_inbox/kachel/functions");
    expect(wrapper.find("[data-functions=state]").text()).toBe("The tablet has it");
    expect(wrapper.find("#kachel-functions-save").attributes("disabled")).toBeDefined();
    await wrapper.find("[data-function=page_turn] [data-way=buttons]").trigger("click");
    await wrapper.find("[data-function=assist] .kachel-switch").trigger("click");
    await wrapper.find("[data-function=assist] [data-way=wake_word]").trigger("click");
    await wrapper.find("[data-notice=missed] .switch").trigger("click");
    expect(wrapper.find("[data-functions=state]").text()).toBe("Not saved yet");
    vi.mocked(send).mockResolvedValue({ functions: {}, supported: true, delivered: false });
    await wrapper.find("#kachel-functions-save").trigger("click");
    await flushPromises();
    expect(send).toHaveBeenCalledWith("screens/text.fire_kachel_inbox/kachel/functions", "PUT", {
      page_turn: { ways: ["swipe", "buttons"] }, assist: { ways: ["tap_clock", "wake_word"] }, notices: { missed: true } });
  });

  it("turns a function off with its last way, and says when the tablet can't take them yet", async () => {
    const wrapper = await panel({ functions: { page_turn: { ways: ["swipe"] } }, supported: false, delivered: false });
    expect(wrapper.find("[data-functions=unsupported]").exists()).toBe(true);
    await wrapper.find("[data-function=page_turn] [data-way=swipe]").trigger("click");
    vi.mocked(send).mockResolvedValue({ functions: {}, supported: false, delivered: false });
    await wrapper.find("#kachel-functions-save").trigger("click");
    await flushPromises();
    expect(send).toHaveBeenCalledWith("screens/text.fire_kachel_inbox/kachel/functions", "PUT", {});
  });
});

describe("what the Functions tab offers", () => {
  it("only fitting sensors, and per notice a question that offers only what fits", async () => {
    const inv = useInventoryStore();
    inv.inventory.entities.push(
      { id: "binary_sensor.flur_bewegung", name: "Flur Bewegung", area: "Flur", state: "off", words: "motion Bewegung" } as any,
      { id: "binary_sensor.fenster", name: "Fenster", area: "Flur", state: "off", words: "window Fenster" } as any,
      { id: "person.philip", name: "Philip", area: "", state: "home" } as any,
      { id: "event.haustuer_klingel", name: "Haustür Klingel", area: "", state: "unknown", words: "doorbell" } as any,
      { id: "event.taster", name: "Taster", area: "", state: "unknown", words: "button" } as any);
    const wrapper = await panel({ functions: {}, supported: true, delivered: false });
    const vm = wrapper.vm as any;
    const presenceIds = (vm.sensors as [string, string][]).map(([id]) => id);
    expect(presenceIds).toContain("binary_sensor.flur_bewegung");
    expect(presenceIds).toContain("person.philip");
    expect(presenceIds).not.toContain("binary_sensor.fenster");
    expect(wrapper.find("[data-notice=doorbell] .kachel-notice-pick").exists()).toBe(false);
    await wrapper.findAll("[data-notice=doorbell] .seg button")[1].trigger("click");
    expect(wrapper.find("[data-notice=doorbell] .kachel-notice-pick").exists()).toBe(true);
    expect((vm.lists.notices.doorbell as [string, string][]).map(([id]) => id)).toEqual(["event.haustuer_klingel"]);
  });
});
