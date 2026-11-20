// Kachel Manager: the Kachel look (src/kachel/kachel-theme.css) is loaded after Tessera's styles, and its accent is the
// turquoise of the Kachel mark; the add-on's own updates and screens waiting to be flashed are not shown (ESP32 is Tessera's).
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const main = readFileSync("src/main.ts", "utf8");
const theme = readFileSync("src/kachel/kachel-theme.css", "utf8");

describe("the Kachel look", () => {
  it("comes after Tessera's styles", () => {
    expect(main.indexOf("./kachel/kachel-theme.css")).toBeGreaterThan(main.indexOf("./styles/app.css"));
  });
  it("has the Kachel turquoise as its accent, light and dark", () => {
    expect(theme).toMatch(/--kachel-teal: #2bb3a3/);
    expect(theme.match(/--accent: #/g)).toHaveLength(2);
    expect(theme).toMatch(/prefers-color-scheme: dark[\s\S]*--accent: #2bb3a3/);
  });
});
