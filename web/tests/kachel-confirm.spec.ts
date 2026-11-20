// Kachel Manager: a switchable tile may ask before it switches (src/kachel/confirm.ts): Tessera's lock option
// guard "confirm", here for blinds, switches, lights and the like; the page check takes it there and nowhere else new.
import { describe, expect, it } from "vitest";
import { asksBefore, CONFIRM_DOMAINS } from "../src/kachel/confirm";
import { ofType } from "../src/model/catalogue";

describe("asking before switching", () => {
  it("is offered for switchable kinds", () => {
    expect(asksBefore("cover")).toBe(true);
    expect(asksBefore("light")).toBe(true);
    expect(asksBefore("sensor")).toBe(false);
    for (const domain of CONFIRM_DOMAINS) if (ofType(domain)) expect(ofType(domain)!.guards).toContain("confirm");
    expect(ofType("lock")!.guards).toEqual(["confirm", "lock_only"]);
  });
});
