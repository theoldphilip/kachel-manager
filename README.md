# Kachel Manager

<p align="center"><img src="screen_manager/logo.png" width="320" alt="Kachel Manager"></p>

**Seiten aus Kacheln für die Kachel-Bildschirme: das Wohnzimmer-Tablet, das Laufband-Display und den Fire.**

Der Kachel Manager verwaltet die Kachel-Geräte (Alpine Linux mit echod) in Home Assistant: welche Kacheln auf welcher
Seite stehen, die Kopfzeile, und unter **Bildschirmeinstellungen → Gerät** Updates, Akku und Bildschirm des Tablets.
Was ein Gerät nicht hat, zeigt er nicht.

Öffne nach der Installation **Kachel** in der Seitenleiste. Ein Tablet erscheint dort, sobald an ihm
„Managed by“ auf **Kachel Manager** steht. Mehr unter **Dokumentation**.

ESP32-Bildschirme (CYD, Guition, Waveshare …) gehören nicht hierher, sie bleiben beim Tessera-Add-on. Beide können
nebeneinander in derselben Home-Assistant-Instanz laufen.

Der Kachel Manager ist ein Fork von [Tessera](https://github.com/MaxGramser/homeassistant_espscreen) von Max Gramser
(AGPL-3.0). Quelle: [theoldphilip/kachel-manager](https://github.com/theoldphilip/kachel-manager).

## Für Entwickler

`CLAUDE.md` beschreibt, was dieser Fork anders macht als Tessera und wie Neues vom Original übernommen wird.
`AGENTS.md` und `README_EXTENDED.md` sind die Anleitungen von Tessera. Icon und Logo zeichnet `tools/kachel_logo.py`.
