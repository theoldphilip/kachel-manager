// Kachel Manager: the tablet's own device under Screen settings (src/kachel/DevicePanel.vue): the rows the add-on streams
// (screen_manager/app/kachel_device.py), changed through it, an update only after the question.
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import DevicePanel from "../src/kachel/DevicePanel.vue";
import { send } from "../src/api";
import { openScreen } from "./helpers/fixtures";
import { lastStream } from "./helpers/fake-event-source";
import { answerDialogs } from "./helpers/dialogs";
import type { Screen } from "../src/types";

vi.mock("../src/api", () => ({ api: vi.fn(), getJson: vi.fn(), send: vi.fn(async () => ({ ok: true })) }));

const SCREEN = { id: "text.wohnzimmer_kachel_inbox", name: "Wohnzimmer", online: true, layout: { title: "", tiles: [] } } as unknown as Screen;
const SECTIONS = [
  { section: "updates", rows: [
    { key: "firmware", entity: "update.w_firmware", kind: "update", label: { en: "Kachel version" }, available: true, writable: true,
      value: "2.5.0-b9", latest: "2.5.0-b10", pending: true, installing: false, progress: null },
    { key: "update_outcome", entity: "event.w_update_outcome", kind: "outcome", label: { en: "Last update" }, available: true,
      writable: false, value: "rolled_back", at: "2026-11-19T20:05:00Z" },
    { key: "update_channel", entity: "select.w_update_channel", kind: "select", label: { en: "Update channel" }, available: true,
      writable: true, value: "dev", options: ["stable", "dev"] },
  ] },
  { section: "battery", rows: [
    { key: "battery_level", entity: "sensor.w_battery_level", kind: "reading", label: { en: "Battery level" }, available: true,
      writable: false, value: "71", unit: "%" },
    { key: "battery_care", entity: "binary_sensor.w_battery_care", kind: "flag", label: { en: "Battery care" }, available: true,
      writable: true, value: true },
  ] },
  { section: "screen", rows: [
    { key: "screen", entity: "light.w_screen", kind: "light", label: { en: "Screen" }, available: true, writable: true, value: true, brightness: 50 },
    { key: "settings_lock", entity: "switch.w_settings_lock", kind: "switch", label: { en: "Settings lock" }, available: true,
      writable: true, value: false },
  ] },
];

async function show(wrapper: Awaited<ReturnType<typeof panel>>, section: string) {
  if (wrapper.find(".kachel-back").exists()) await wrapper.find(".kachel-back").trigger("click");
  await wrapper.find(`[data-menu=${section}]`).trigger("click");
}

async function panel() {
  openScreen(SCREEN);
  const wrapper = mount(DevicePanel);
  await flushPromises();
  const stream = lastStream()!;
  expect(stream.url).toBe("api/screens/text.wohnzimmer_kachel_inbox/kachel/device/events?language=en");
  stream.send(SECTIONS);
  await flushPromises();
  return wrapper;
}

describe("the tablet's device", () => {
  it("draws nothing before the add-on says what the tablet has", async () => {
    openScreen(SCREEN);
    const wrapper = mount(DevicePanel);
    await flushPromises();
    expect(wrapper.find("#settings-kachel-device").exists()).toBe(false);
  });

  it("shows a menu of its sections, as the tablet does, and each section's rows behind its card", async () => {
    const wrapper = await panel();
    expect(wrapper.findAll("[data-menu]").map((s) => s.attributes("data-menu"))).toEqual(["screen", "updates", "battery"]);
    expect(wrapper.find("[data-menu=screen]").text()).toContain("Brightness 50 %");
    expect(wrapper.find("[data-menu=updates]").text()).toContain("New: 2.5.0-b10 ready");
    expect(wrapper.find("[data-menu=battery]").text()).toContain("71 %");
    expect(wrapper.find("[data-section]").exists()).toBe(false);
    await show(wrapper, "battery");
    expect(wrapper.findAll("[data-section]").map((s) => s.attributes("data-section"))).toEqual(["battery"]);
    expect(wrapper.find("[data-setting=battery_level]").text()).toContain("71 %");
    expect(wrapper.find("[data-setting=battery_care]").text()).toContain("Yes");
    expect(wrapper.find("[data-setting=battery_care] button").exists()).toBe(false);
    await show(wrapper, "screen");
    expect(wrapper.find("[data-setting=screen] output").text()).toBe("50 %");
    await show(wrapper, "updates");
    expect(wrapper.find("[data-setting=update_outcome]").text()).toContain("Rolled back · ");
  });

  it("installs an update only after the question, and changes a switch, a choice and the brightness at once", async () => {
    const wrapper = await panel();
    const replies = [false, true];
    const asked = answerDialogs(() => replies.shift() ?? false);
    await show(wrapper, "updates");
    await wrapper.find("[data-setting=firmware] button").trigger("click");
    await flushPromises();
    expect(asked).toHaveLength(1);
    expect(asked[0].message).toContain("2.5.0-b10");
    expect(send).not.toHaveBeenCalled();
    await wrapper.find("[data-setting=firmware] button").trigger("click");
    await flushPromises();
    expect(asked).toHaveLength(2);
    expect(send).toHaveBeenLastCalledWith("screens/text.wohnzimmer_kachel_inbox/kachel/device", "POST", { entity: "update.w_firmware", value: "install" });
    await show(wrapper, "screen");
    await wrapper.find("[data-setting=settings_lock] button.switch").trigger("click");
    expect(send).toHaveBeenLastCalledWith("screens/text.wohnzimmer_kachel_inbox/kachel/device", "POST", { entity: "switch.w_settings_lock", value: true });
    await show(wrapper, "updates");
    await wrapper.findAll("[data-setting=update_channel] .seg button")[0].trigger("click");
    expect(send).toHaveBeenLastCalledWith("screens/text.wohnzimmer_kachel_inbox/kachel/device", "POST", { entity: "select.w_update_channel", value: "stable" });
    await show(wrapper, "screen");
    await wrapper.findAll("[data-setting=screen] .step button")[1].trigger("click");
    expect(send).toHaveBeenLastCalledWith("screens/text.wohnzimmer_kachel_inbox/kachel/device", "POST", { entity: "light.w_screen", value: 60 });
  });
});
