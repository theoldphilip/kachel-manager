# Kachel Manager – Hinweise für Claude (Agent `kachel-manager-addon`)

Dieses Repo ist der **Kachel Manager**, ein Home-Assistant-Add-on und Fork von Tessera
(`MaxGramser/homeassistant_espscreen`, AGPL-3.0, Stand 0.4.98). Er verwaltet die **Kachel-Geräte** (Alpine Linux +
echod auf Tablets: Wohnzimmer-Tablet, Laufband-Display, später Fire). **Echte ESP32-Bildschirme bleiben beim
Tessera-Add-on**, das daneben in derselben Home-Assistant-Instanz läuft.

Ziel: Die Kachel-Firmware ideal und ohne Kompromisse an Home Assistant anbinden. Was heute über KI-Agents im Code
geändert wird, soll über die Oberfläche des Kachel Managers gehen.

`AGENTS.md` ist die Anleitung des Originals. Ihre Regeln zum Code (Katalog, Einstellungen, Editor, Kompatibilität)
gelten weiter. **Wo sie dieser Datei widerspricht, gilt diese Datei**: Branches, Releases, Versionen, Bench/Tests am
Gerät, GitHub-Signatur, Owner's machine.

## Zusammenarbeit (Kachel-Zentrale)

Der gemeinsame Stand aller Kachel-Projekte liegt in der Kachel-Zentrale (`~/kachel-zentrale`, Repo
`theoldphilip/kachel-zentrale`). Dort gelten `README.md` und `REGELN.md`.

- **Sitzungsbeginn:** `cd ~/kachel-zentrale && tools/gitk pull`, `LAGE.md` und `projekte/kachel-manager-addon.md`
  lesen, in `postfach/` nach Nachrichten an `kachel-manager-addon` sehen.
- **Nach jedem fertigen Schritt:** `projekte/kachel-manager-addon.md` aktualisieren, committen (Text beginnt mit
  `kachel-manager-addon:`) und mit `tools/gitk push` hochladen. Betrifft es andere: Nachricht ins Postfach (REGELN §5).
- **Uhrzeiten** immer mit `date '+%Y-%m-%d %H:%M'` ablesen, nie schätzen.
- Freigaben gibt nur Philip. Fehlt eine Berechtigung: Philip sagen, wo und warum, keine Umwege.

## Grenzen

- **echod** gehört `wohnzimmer-app` (`kachel`/`echod`) bzw. `laufband-app` (`kachel-a12`/`app`). Lesen nur über
  eine Wegwerf-Kopie im eigenen Scratchpad
  (`~/kachel-zentrale/tools/gitk clone --depth 1 --branch echod https://github.com/theoldphilip/kachel.git <scratchpad>/echod`).
  Wünsche an echod gehen über das Postfach.
- **Home Assistant:** nichts installieren oder ändern (REGELN §4). Das Add-on bindet Philip selbst ein.
- **Geräte:** kein Zugriff (SSH/adb).
- **Git:** `origin` = unser Fork, `upstream` = Original (nur lesen, Push gesperrt). Für GitHub immer
  `~/kachel-zentrale/tools/gitk` (z. B. `~/kachel-zentrale/tools/gitk -C ~/kachel-manager fetch upstream`).
  Das Token steht nie in diesem Ordner.

## Branches, Versionen, Prüfung

- Nur **`main`**. Jede Änderung auf einem eigenen Hilfsbranch (`kachel-manager-<thema>-<datum>`). GitHub lässt den
  Token in diesem Fork keine PRs anlegen, darum gilt (REGELN §2, Ausnahme Kachel Manager): Hilfsbranch pushen
  (`tools/gitk`), „Kachel check“ läuft bei jedem Push, Ergebnis mit
  `~/kachel-zentrale/tools/ghk checks kachel-manager <branch>`. Erst bei ganz grün per Fast-Forward auf `main` pushen,
  danach den Hilfsbranch löschen. Ist sie rot: nicht mergen.
- **Eigene Versionsreihe** ab 0.1.0 in `screen_manager/config.yaml`. Eine neue Nummer nur nach Philips Okay. Unsere
  Abschnitte stehen oben im CHANGELOG als `## Kachel Manager x.y.z (...)` (ohne Firmware-Nummer, damit Tesseras
  Werkzeuge sie nicht als ihre lesen). Die Release-Werkzeuge (`tools/release.py` usw.) sind noch die von Tessera.
- **Prüfen:** Python-Tests (`python -m unittest discover -s tests`) und der Editor (`cd web && npm test && npm run
  build`, dann `screen_manager/app/static` mit committen). Die Firmware-Teile (`components/`, `packages/`, C++-Tests,
  Firmware-Builds) gehören zu Tessera und werden hier nicht gebaut.

## Kachel Manager und Tessera

Was dieser Fork anders macht, steht an einer Stelle: `screen_manager/app/kachel.py` (Test: `tests/test_kachel.py`).

- **Erkennung:** Ein Kachel-Gerät meldet sein Postfach als ESPHome-Text **„Kachel inbox“** (in echod: Auswahl
  „Managed by: Kachel Manager“). Der Kachel Manager sucht nur diesen Namen, Tessera nur „Tile settings“. So nimmt
  keiner das Gerät des anderen.
- **Eigene Namen:** Ereignisse für Automationen heißen `kachel_*` (z. B. `kachel_show_alert`), die Layout-Sensoren
  `sensor.kachel_<node>`. Der Schlüssel `esp_screens_layout` der Export-Datei bleibt, damit ein Export aus Tessera
  hier importiert werden kann. Der Editor speichert im Browser unter `kachel-manager.*` statt `esp-screens.*`, weil
  beide Editoren unter derselben Home-Assistant-Adresse laufen.
- **Ausgeschaltet (ESP32 bleibt bei Tessera):** Firmware bauen und flashen, „Neuer Bildschirm“, Kopplung neuer
  Bildschirme mit Home Assistant, Firmware-Updates, Build-Server, `tessera_video`, das Nachziehen der YAML-Profile im
  ESPHome-Ordner. Der Server lehnt diese Anfragen ab (`kachel.refuse_esp`), der Editor blendet sie aus
  (`editor_features.esp_screens`). Kein Port 8098, kein USB/UART.
- **Gerät** (Schritt 2a): Unter Bildschirm-Einstellungen zeigt der Kachel Manager Updates, Akku und Bildschirm des
  Tablets aus dessen eigenen Entitäten und ändert sie über Home Assistant (`screen_manager/app/kachel_device.py`,
  `web/src/kachel/DevicePanel.vue`, Tests `tests/test_kachel_device.py`, `web/tests/kachel-device.spec.ts`). Nur was
  `SECTIONS` als änderbar nennt, und nur auf den Geräten des Tablets. Gefunden wird jede Zeile über den **Namen** der
  Entität in echod (`original_name`, z. B. „Night hours“ zu ObjectID `screen_night_hours`) und ihre Domain. Neue
  Entitäten erscheinen, sobald ihr Name in `SECTIONS` steht; was ein Gerät nicht hat, fehlt (Fire: kein Auto-Update).
  Tesseras eigene Bildschirm-Einstellungen blendet der Editor aus (`SettingsTab.vue`, nur mit `esp_screens`).
- Eigene Änderungen möglichst in eigenen Dateien (`kachel*.py`, später `web/src/kachel/`) und kleinen, mit
  „Kachel Manager:“ kommentierten Haken in Tessera-Dateien, damit Merges vom Original leicht bleiben.

## Neues vom Original übernehmen

1. `~/kachel-zentrale/tools/gitk -C ~/kachel-manager fetch upstream --tags`
2. Eigener Branch von `main`, `git merge <Tessera-Tag oder upstream/main>`, Konflikte lösen.
3. `python3 tools/kachel_names.py` schreibt unsere Namen über die neuen von Tessera und entfernt Tesseras Workflows
   wieder (`--check` zeigt nur, was fehlt). Geprüft wird nur mit `.github/workflows/kachel-check.yml`.
4. Prüfen (siehe oben), Editor neu bauen, Hilfsbranch pushen, nach grün Fast-Forward auf `main`.
