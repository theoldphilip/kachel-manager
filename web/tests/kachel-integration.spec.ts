// Kachel Manager: the Home Assistant integration `kachel` under Settings (src/kachel/IntegrationCard.vue): installed
// only when asked, and a restart only said, never done.
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import IntegrationCard from "../src/kachel/IntegrationCard.vue";
import { getJson, send } from "../src/api";

vi.mock("../src/api", () => ({ api: vi.fn(), getJson: vi.fn(), send: vi.fn() }));

const MISSING = { installed: false, current: false, version: "0.2.0", there: null, loaded: null, restart: false, path: "/homeassistant/custom_components/kachel" };

afterEach(() => { vi.mocked(getJson).mockReset(); vi.mocked(send).mockReset(); });

describe("the Kachel integration", () => {
  it("installs on request and then asks for a restart", async () => {
    vi.mocked(getJson).mockResolvedValue(MISSING);
    vi.mocked(send).mockResolvedValue({ ...MISSING, installed: true, current: true, there: "0.2.0", restart: true });
    const wrapper = mount(IntegrationCard);
    await flushPromises();
    expect(wrapper.find("#kachel-integration-status").text()).toBe("Not installed");
    await wrapper.find("#kachel-integration-install").trigger("click");
    await flushPromises();
    expect(send).toHaveBeenCalledWith("kachel/integration", "POST");
    expect(wrapper.find("#kachel-integration-install").exists()).toBe(false);
    expect(wrapper.find("#kachel-integration-status").text()).toContain("Restart Home Assistant");
    expect(wrapper.text()).not.toContain("Restart Home Assistant now");
  });

  it("offers the update over an older version, and says when it runs", async () => {
    vi.mocked(getJson).mockResolvedValue({ ...MISSING, installed: true, there: "0.1.0", loaded: "0.1.0" });
    const wrapper = mount(IntegrationCard);
    await flushPromises();
    expect(wrapper.find("#kachel-integration-install").text()).toBe("Update to 0.2.0");
    vi.mocked(getJson).mockResolvedValue({ ...MISSING, installed: true, current: true, there: "0.2.0", loaded: "0.2.0" });
    const again = mount(IntegrationCard);
    await flushPromises();
    expect(again.find("#kachel-integration-status").text()).toBe("Version 0.2.0 running");
  });
});
