// Kachel Manager: a tile that asks before it switches (Philip, 2026-11-20, test 0.0.9-dev7), chosen per tile in the tile's
// settings for a switchable entity: Tessera's lock option `guard: "confirm"` (a second tap) for every switchable kind.
// The same list as screen_manager/app/kachel.py CONFIRM_DOMAINS; a lock keeps Tessera's own choices.
import { TYPES } from "../model/catalogue";

export const CONFIRM_DOMAINS = ["cover", "switch", "light", "fan", "input_boolean", "valve", "humidifier", "siren"] as const;
export const asksBefore = (domain: string) => (CONFIRM_DOMAINS as readonly string[]).includes(domain);

// The catalogue's guards (page-validation.ts reads them): "confirm" for each of these kinds, as the add-on takes it.
for (const domain of CONFIRM_DOMAINS) {
  const type = TYPES[domain];
  if (type && !type.guards.includes("confirm")) type.guards = [...type.guards, "confirm"];
}
