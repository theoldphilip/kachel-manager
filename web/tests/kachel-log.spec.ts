// Kachel Manager: the tablet's log under Screen settings (src/kachel/LogPanel.vue): nothing fetched until asked, the
// end of one log shown, both saved as one file, and a device without the action says so.
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import LogPanel from "../src/kachel/LogPanel.vue";
import { api, getJson } from "../src/api";
import { openScreen } from "./helpers/fixtures";
import type { Screen } from "../src/types";

vi.mock("../src/api", () => ({ api: vi.fn(), getJson: vi.fn(), send: vi.fn() }));

const SCREEN = { id: "text.fire_test_kachel_inbox", name: "Fire", online: true, layout: { title: "", tiles: [] } } as unknown as Screen;

async function panel() {
  openScreen(SCREEN);
  const wrapper = mount(LogPanel);
  await flushPromises();
  return wrapper;
}

afterEach(() => vi.mocked(getJson).mockReset());

describe("the tablet's log", () => {
  it("fetches nothing until asked", async () => {
    const wrapper = await panel();
    expect(wrapper.find("#settings-kachel-log").exists()).toBe(true);
    expect(getJson).not.toHaveBeenCalled();
    expect(wrapper.find("[data-log=text]").exists()).toBe(false);
  });

  it("shows the end of the log it is asked for", async () => {
    vi.mocked(getJson).mockResolvedValue({ available: true, source: "boot", text: "line 1\nline 2\n", size: 300000, cut: true });
    const wrapper = await panel();
    await wrapper.find("[data-source=boot]").trigger("click");
    await flushPromises();
    expect(getJson).toHaveBeenCalledWith("screens/text.fire_test_kachel_inbox/kachel/log?source=boot");
    expect(wrapper.find("[data-log=text]").text()).toBe("line 1\nline 2");
    expect(wrapper.find("[data-source=boot]").attributes("aria-pressed")).toBe("true");
    expect(wrapper.text()).toContain("293 KB");
  });

  it("says when the device can't send its log", async () => {
    vi.mocked(getJson).mockResolvedValue({ available: false, source: "echod" });
    const wrapper = await panel();
    await wrapper.find("[data-source=echod]").trigger("click");
    await flushPromises();
    expect(wrapper.find("[data-log=none]").exists()).toBe(true);
    expect(wrapper.find("[data-log=download]").exists()).toBe(false);
  });

  it("downloads both logs as one file", async () => {
    vi.mocked(api).mockResolvedValue(new Response("log", { headers: { "Content-Disposition": 'attachment; filename="kachel-log-fire-test.txt"' } }));
    const created = vi.fn(() => "blob:x");
    Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() });
    const clicked: string[] = [];
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { clicked.push(this.download); });
    const wrapper = await panel();
    await wrapper.find("[data-log=download]").trigger("click");
    await flushPromises();
    expect(api).toHaveBeenCalledWith("screens/text.fire_test_kachel_inbox/kachel/log/download?source=all");
    expect(clicked).toEqual(["kachel-log-fire-test.txt"]);
    click.mockRestore();
  });
});
