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
- **Schlanke Prüfung** (zentrale, 20.11.): Ein neuer Push bricht den alten Lauf desselben Branches ab (`concurrency`).
  Ändert ein Push nur `CLAUDE.md`, `screen_manager/DOCS.md`, `screen_manager/README.md` oder Icon/Logo des Stores, läuft
  keine Prüfung (`paths-ignore`); so ein Branch darf nach grünen lokalen Tests auf `main`. **Vor jedem Push von Code die
  Tests lokal laufen lassen** (REGELN §5), rot wird nicht gepusht.
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
- **Kachel, nicht Tessera** (Philip, 18.11.): Wo die App von sich spricht, sagt sie „Kachel Manager“. Die Texte stehen
  in `tools/kachel_texts.json` (Englisch, Deutsch; `keep` = wo Tessera gemeint ist: ESP32-Teile, Tesseras Website).
  `tools/kachel_names.py` schreibt sie in die Übersetzungen; ein neuer Text mit „Tessera“ in keiner Liste lässt
  `--check` scheitern, dann entscheiden. Automationen heißen „Kachel: …“ (IDs `kachel_…`). Seitenleiste: Kachel-Zeichen
  (`web/src/kachel/KachelMark.vue`), Handbuch und Spende (PayPal) in `web/src/kachel/links.ts`, Tesseras
  Finanzierungs-Karte aus. Store-Icon/-Logo schneidet `tools/kachel_logo.py` aus echods Startbild.
- **Nichts an Tesseras Website** (Philip, 19.11.): `kachel.TESSERA_SITE = False` – keine Berichte, kein Feedback,
  keine Plugin-Likes/-Bewertungen/-Zählung. Der Server lehnt die Routen ab (`kachel.site_only`), die Sender
  (`feedback.py`, `reports.py`, `plugin_likes.py`) rufen `kachel.site_closed()` vor jeder Verbindung. Probleme meldet
  man auf GitHub (`kachel.ISSUES`, `web/src/kachel/IssueCard.vue`). Tesseras Tests dazu laufen mit
  `site_on_module()` aus `tests/kachel_esp.py`.
- **Knotenname** (19.11.): Alle Aktionen eines Geräts heißen `esphome.<node>_…`, `<node>` aus dem Sensor „Device
  name“. Kennt Home Assistant für diesen Namen keine `…_screen_message`, nimmt `kachel.message_node` die eine Aktion,
  die auf die letzten 6 Stellen der MAC des Geräts endet (Sicherheitsnetz, Haken in `server.py`: `screens`, `screen`,
  `inventory`).
- **Aus HA entfernen** (19.11., mit `fire-app`): Schreibt ein Gerät bei den Werkseinstellungen `remove` (oder
  `{"status":"remove"}`) in seine Inbox, ruft die Sync-Schleife einmal `Manager.remove_screen` (ESPHome-Eintrag samt
  Gerät weg). `kachel.wants_removal`, Test `tests/test_kachel_remove.py`. Das Gerät wartet bis 20 s auf den Abbruch.
- **Unter ESPHome oder der Kachel-Integration** (19.11., mit `kachel-verbindung-plugin`): `kachel.PLATFORMS =
  ('esphome', 'kachel')`. Registry-Abfragen über `kachel.ours(item)` (die Regel `PLATFORM_RULES` in
  `tools/kachel_names.py` setzt sie nach jedem Merge wieder ein), Ereignisse `kachel.screen_*` liest `server.py` als
  `esphome.screen_*` (`kachel.as_esphome_event`, Abos aus `KACHEL_SCREEN_EVENTS`), Aktionen gehen an die Plattform der
  Inbox (`kachel.NODE_DOMAINS`, `core.alert_service`), Config-Entries und Repair-Issues beider Plattformen. Nur noch
  `kachel`: `esphome` aus `PLATFORMS` streichen (Philips Wort).
- **Protokoll holen** (19.11., mit `fire-app`): Kein SSH auf weitergegebenen Geräten. Das Gerät bietet die Aktion
  `<domain>.<node>_log` mit Antwort (Eingabe `source` `echod`|`boot`, `offset`, `max` ≤ 64 KB; Antwort `{text, next,
  size}`, Geheimnisse schwärzt das Gerät). `screen_manager/app/kachel_log.py` holt in Stücken, Karte „Protokoll“
  (`web/src/kachel/LogPanel.vue`): Ende anzeigen, beide als eine Datei herunterladen. Nichts geht ins Internet.
  Tests `tests/test_kachel_log.py`, `web/tests/kachel-log.spec.ts`.
- **Kachel-Integration installieren** (19.11., Wunsch `kachel-verbindung-plugin`, Philips Weg): Kopie von
  `custom_components/kachel` aus `kachel-verbindung` in `screen_manager/app/ha_integration/kachel` (Stand
  `kachel_integration.SOURCE_COMMIT`; neue Version mit `tools/kachel_integration_copy.sh <commit>`). Einstellungen →
  Kachel-Integration schreibt den Ordner auf Knopfdruck ganz neu nach `/homeassistant/custom_components/kachel`, nur wenn
  er anders ist; Neustart nur anzeigen, nie selbst; kein Config-Entry. Tests `tests/test_kachel_integration.py`,
  `web/tests/kachel-integration.spec.ts`.
- **Seiten bleiben** (20.11., Fire-Test): `Manager.remove_screen` hebt vor `forget_inbox` die Seiten eines Kachel-Geräts
  nach MAC auf (`kachel_keep.keep`, Datei `/data/kachel_kept_pages.json`, höchstens 20); die Sync-Schleife gibt sie einem
  Bildschirm ohne Seiten mit derselben MAC einmal zurück (`kachel_keep.restore`). Test `tests/test_kachel_keep.py`.
- **Kachel-Version und Gerät** (20.11., Philip): Statt Tesseras Firmware-Nummer und ESP32-Board zeigt der Editor
  (Seitenleiste, Übersicht) `screen['kachel']` = Kachel-Version und Gerät aus echods Sensoren „Kachel version“/„Kachel
  board“ (`kachel_board.py`, `DEVICES`: fire8, a12s, gta3xl). Tests `tests/test_kachel_board.py`,
  `web/tests/kachel-board.spec.ts`.
- **Redesign** (20.11., Philip „perfekt!“ zum Entwurf): Kachel-Aussehen nach `design/` der Zentrale in
  `web/src/kachel/kachel-theme.css` (nach `app.css` geladen, nur Farben/Ecken/Abstände; Türkis `#2BB3A3`, runde Tasten,
  Karten). Tesseras Dateien bleiben möglichst unverändert. Ohne `ESP_SCREENS` kein ESPHome-Update und keine wartenden
  Profile im Inventar (`server.py`). Weitere Schritte: Übersicht, Reiter je Gerät, Gerät als Kartenmenü, Suche über alles.
- **Funktionen** (20.11., mit `fire-app`, Protokoll `functions` v2): Reiter „Funktionen“ (`web/src/kachel/FunctionsPanel.vue`),
  gespeichert je Inbox in `/data/kachel_functions.json` (`kachel_functions.py`, `clean` prüft wie das Tablet). Die
  Sync-Schleife schickt `{"op":"functions",…}` in der Sitzung einmal je Hello und bei Änderung, nur bei Hello-Wort
  `functions`; `{"op":"presence","present"}` nach dem Hello, bei Änderung und spätestens alle 60 s. Präsenz-Sensoren
  wecken die Schleife (`watched_entities`). Tests `tests/test_kachel_functions.py`, `web/tests/kachel-functions.spec.ts`.
- **Vor dem Schalten nachfragen** (20.11., Philip): je Kachel Tesseras `guard: "confirm"` (sonst nur Schloss) für
  `kachel.CONFIRM_DOMAINS` (Server `core.validate_layout`, Editor `web/src/kachel/confirm.ts`, Zeile im Kachel-Dialog).
- **Redesign Runde 2** (20.11.): Seiten einzeln mit Reitern, Bibliothek rechts (`.kachel-work`), dunkle Vorschau nach „Theme
  mode“ des Tablets (`kachel_board.info` → `theme`), Kachel-Zeichen statt Tessera-Logo (`TesseraMark.vue`), „Geräte“ statt
  „Bildschirme“ (`tools/kachel_texts.json`; doppelte Texte setzt `kachel_names.py` per Pfad).
- **Entfernen über Ereignis** (23.11., Laufband-Befund): `kachel_remove.py` – ein Gerät fragt per Inbox `remove` **oder** per
  Ereignis `esphome.screen_remove`/`kachel.screen_remove` (Daten: `device_id` von HA, `mac` vom Gerät); entfernt werden alle
  Einträge seiner MAC (ESPHome, Kachel, Bluetooth-Rest), Seiten vorher aufgehoben. `kachel_removing` vergisst die Inbox, sobald
  sie nicht mehr `remove` sagt. Test `tests/test_kachel_remove.py`.
- **Quellen der Spezialanzeige** (24.11., mit `fire-app`/`laufband-app`, SCHRITTE A1): `kachel_sources.py`. Das hello sagt
  `kind` (`special`/`tiles`), Wort `sources`, Liste `sources` [{key, name{de,en}, domains, device_class, required}]
  (`page_delivery.Sender.kachel`). Wahl je Inbox und nach MAC in `/data/kachel_sources.json`; die Sync-Schleife schickt
  `{"op":"sources","sources","names","room"}` (`room` immer, leer `""`, sonst Bereich des Geräts) und
  `{"op":"source_state","key","state","unit"}` (nach hello, bei Änderung, ≤60 s). Knöpfe: Ereignis `screen_source`
  {key, action} → `ACTIONS` je Domain. Editor: Reiter „Quellen“ (`web/src/kachel/SourcesPanel.vue`) statt Seiten/Plugins bei
  `screen.kachel_kind == 'special'`. `presence` trägt `battery_low` (Akku am Gerät des Präsenz-Sensors,
  `kachel_functions.battery_low`). Tests `tests/test_kachel_sources.py`, `web/tests/kachel-sources.spec.ts`.
  Alles in der Sitzung braucht eine bestätigte Seiten-Revision (`Sender.confirmed`): eine Spezialanzeige ohne Seiten bekommt darum
  einmal ein leeres Seiten-Dokument (`kachel_sources.give_pages`, 0.1.16, Laufband-Test 25.11.).
- **Begriffe** (Zentrale, 24.11.): **Kachel OS** = Firmware + **kacheld** (früher echod). Neue Texte nutzen sie; alte nebenbei.
  Protokoll-Quelle heißt `kacheld` (`kachel_log.SOURCES`); ein Gerät vor fire-app @16c8a61 wird mit `echod` gefragt (`OLD_NAMES`).
- **Feinschliff Redesign** (24.11., 0.1.13): Kachelform wie kacheld (Symbol oben links, Name/Zustand unten links, an = Schimmer),
  Kachel-Dialog unten in der rechten Spalte (`.body:has(> .work.kachel-work) > .drawer`), alles in `kachel-theme.css`. Weitere
  „Gerät“-Texte in `tools/kachel_texts.json`; Englisch bleibt, wo Tesseras Tests den Wortlaut prüfen.
- **Geräte ohne Inbox** (25.11., Laufband-Test, Philip): `kachel_bare.py` – jedes Kachel-Gerät (Plattform `kachel`, oder
  `esphome` mit Sensor „Kachel board“; nie ein ESP32) ohne Bildschirm dieser App erscheint als `kachel:<device_id>`
  (`kachel_kind` special, `kachel_bare`) im Inventar; `Manager.screen` findet es für Gerät/Protokoll/Funktionen/Quellen, die
  Sync-Schleife nie. Meldet es die Inbox, übernimmt `kachel_bare.adopt` Funktionen und Quellen. Test `tests/test_kachel_bare.py`.
  Der Eintrag braucht ein `source_grid` (ohne zeigt der Editor keine Reiter, 0.1.14); `web/tests/kachel-bare.spec.ts` öffnet genau
  den Eintrag aus `web/tests/kachel-bare-entry.json`, den `test_kachel_bare` gegen den Server prüft.
- **Kopplung:** `ha_pairing` (nur `handler == 'esphome'`) läuft nur mit `ESP_SCREENS`; Kachel-Geräte nimmt HA selbst auf,
  darum braucht `_kachel._tcp` hier nichts. „Aktionen erlauben“ geht unter beiden Plattformen (gleiches Feld, gleiche Repair-ID).
- Eigene Änderungen möglichst in eigenen Dateien (`kachel*.py`, später `web/src/kachel/`) und kleinen, mit
  „Kachel Manager:“ kommentierten Haken in Tessera-Dateien, damit Merges vom Original leicht bleiben.

## Aufteilung und Basisdesign (Philip, 19.11.)

- **Entwickelt wird mit dem Fire** (`kachel-fire`/`app`, Board `fire8`): Es ist die Werkbank und Quelle der Basis.
  Das **Wohnzimmer** bleibt bei Tessera und arbeitet für sich; später ist es der **Prüfstein**: Ziel sind alle
  Funktionen des Wohnzimmers über den Kachel Manager (Liste `wohnzimmer-funktionen.md` von `wohnzimmer-app`). Das
  **Laufband** nutzt Kachel Manager und Verbindung, zeigt aber seine eigene Anzeige (keine frei belegbaren Seiten).
- **Erinnerungspflicht (REGELN §2):** Wünscht Philip hier eine Änderung am **Basisdesign** (Einstellungsmenü,
  Ersteinrichtung, Werkseinstellungen, Tastatur, Design des Geräts), erst fragen: „Das Basisdesign macht `fire-app` am
  Fire – soll ich es als Wunsch an `fire-app` geben?“ und nicht selbst bauen. Sagt Philip ausdrücklich, ich soll es
  selbst machen, gilt sein Wort. Ausgenommen: Wohnzimmer und Laufband-Anzeige.

## Neues vom Original übernehmen

1. `~/kachel-zentrale/tools/gitk -C ~/kachel-manager fetch upstream --tags`
2. Eigener Branch von `main`, `git merge <Tessera-Tag oder upstream/main>`, Konflikte lösen.
3. `python3 tools/kachel_names.py` schreibt unsere Namen über die neuen von Tessera und entfernt Tesseras Workflows
   wieder (`--check` zeigt nur, was fehlt). Geprüft wird nur mit `.github/workflows/kachel-check.yml`.
4. Prüfen (siehe oben), Editor neu bauen, Hilfsbranch pushen, nach grün Fast-Forward auf `main`.
