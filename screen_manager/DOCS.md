# Kachel Manager

## Installieren

1. Repository `https://github.com/theoldphilip/kachel-manager` unter **Einstellungen → Add-ons → Add-on Store → ⋮ →
   Repositories** hinzufügen.
2. **Kachel Manager** installieren und starten. Auf der Info-Seite **Watchdog** einschalten: Home Assistant startet
   das Add-on dann neu, falls es einmal stehen bleibt.
3. **Kachel** in der Seitenleiste öffnen. Das Add-on läuft über Home Assistant Ingress und braucht kein eigenes
   Login und kein Token.

## Kachel-Integration

Die Kachel-Geräte verbinden sich künftig über die eigene Integration **Kachel** mit Home Assistant statt über ESPHome.
Der Kachel Manager bringt sie mit. Unter **Einstellungen → Kachel-Integration** tippst du auf **Installieren**, dann
schreibt er sie nach `/homeassistant/custom_components/kachel`. Vorher schreibt er nichts dorthin. Danach Home Assistant
neu starten (das macht der Kachel Manager nicht selbst) und das Gerät unter **Einstellungen → Geräte & Dienste**
aufnehmen. Bringt eine neue Version des Kachel Managers eine neuere Integration mit, steht dort **Aktualisieren**.

## Ein Tablet verbinden

Ein Kachel-Gerät hat in Home Assistant die Auswahl **Managed by**. Steht sie auf **Kachel Manager**, meldet das Tablet
sein Postfach als Text „Kachel inbox“, und der Kachel Manager zeigt es in der Seitenleiste. Steht sie auf
**Tessera**, gehört es dem Tessera-Add-on. So nimmt keiner das Gerät des anderen.

Beim Umstellen bleibt das bisherige Layout auf dem Tablet stehen, bis der Kachel Manager ein neues schickt.

Setzt du ein Kachel-Gerät auf Werkseinstellungen zurück (mit „Auch aus Home Assistant entfernen“), nimmt der Kachel Manager es
ganz aus Home Assistant: unter ESPHome, unter Kachel und einen alten Bluetooth-Eintrag desselben Geräts – auch eine
Spezialanzeige wie das Laufband.

Entfernst du ein Kachel-Gerät (im Editor oder bei den Werkseinstellungen des Tablets), hebt der Kachel Manager seine
Seiten auf. Kommt dasselbe Gerät wieder (erkannt an seiner MAC-Adresse), unter ESPHome oder unter der Kachel-Integration,
bekommt es seine Seiten zurück, sofern es noch keine eigenen hat.

Das **Protokoll** eines Geräts steht unter **Bildschirmeinstellungen → Protokoll**; unter **Einstellungen → Protokoll
eines Geräts** führt je ein Knopf dorthin.

## Layout

Im Tab **Layout** stehen die Seiten des Tablets mit ihren Kacheln. Eine Entität aus Home Assistant wird zur Kachel,
ein Tipp auf eine Kachel öffnet rechts ihre Einstellungen. Die Leiste oben auf jeder Seite ist die Kopfzeile: links
der Name, rechts Uhrzeit, Datum oder Entitäten.

## Gerät

Unter **Bildschirmeinstellungen → Gerät** stehen die Einstellungen, die das Tablet selbst in Home Assistant meldet:

- **Updates:** installierte Version, Update-Kanal, Suche nach Updates, automatische Updates, die Version im anderen
  Slot und wie das letzte Update ausging (installiert, zurückgesetzt, fehlgeschlagen). Ein Update fragt vor dem Installieren, weil das Tablet danach neu startet. Den Slot wechselt der Kachel
  Manager nicht, er zeigt ihn nur.
- **Akku:** Ladestand, Ladegerät, Akkuschutz, volle Leistung.
- **Bildschirm:** Helligkeit, Dimmen bei Ruhe, Nachtmodus und Nachtstunden (auch am Wochenende), aus bei leerem
  Raum, Textgröße, Uhrzeit-Format, Design (hell/dunkel), Sprache, Einstellungssperre.
- **Seiten:** Startseite, zurück zur Startseite, blättern mit.

Dieselben Einstellungen stehen in Home Assistant beim Gerät des Tablets. Eine Änderung hier oder dort erscheint
sofort auf beiden Seiten. Was ein Gerät nicht hat (der Fire etwa kein automatisches Update), fehlt.

## Funktionen

Im Reiter **Funktionen** eines Geräts richtest du ein, was das Tablet können soll: **Präsenz** (Sensoren, die melden,
dass jemand da ist), **Blättern** (Wischen, Lautstärketasten, Fernbedienung), **Sprachassistent** und **Meldungen**
(Klingel, Post, Pakete, Müllabfuhr, Wetterwarnungen, verpasste Meldungen). Das Tablet zeigt eine Einstellung nur, wenn
ihre Funktion hier eingerichtet ist. Was nicht eingerichtet ist, ist aus.

## Vor dem Schalten nachfragen

Bei Kacheln für Rollläden, Schalter, Licht, Lüfter oder Ventile kannst du in den Einstellungen der Kachel **Vor dem Schalten
nachfragen** einschalten: Ein Tippen fragt zuerst, ein zweites schaltet.

## Automationen

Die Ereignisse des Kachel Managers beginnen mit `kachel_` (etwa `kachel_show_alert`), damit sie sich nicht mit
Tesseras mischen. Ob ein Tablet ein Ereignis schon anzeigt, hängt von seiner echod-Version ab. Das Layout jedes Tablets steht im Sensor `sensor.kachel_<gerät>`. Tesseras Ereignisse
(`esp_screens_*`) bleiben bei Tessera.

## Was nicht dabei ist

Alles für ESP32-Bildschirme bleibt beim Tessera-Add-on: Firmware bauen und flashen, neue Bildschirme über USB,
Firmware-Updates, Build-Server und Video. Der Kachel Manager öffnet keinen Port im Netz und braucht kein USB.

## Herkunft

Fork von [Tessera](https://github.com/MaxGramser/homeassistant_espscreen) von Max Gramser, Lizenz AGPL-3.0. Quelle
und Änderungen: [theoldphilip/kachel-manager](https://github.com/theoldphilip/kachel-manager), Änderungen im
CHANGELOG unter „Kachel Manager“.

## Unterstützen

Der Kachel Manager ist kostenlos. Wenn er dir nützt, freue ich mich über eine
[Spende per PayPal](https://www.paypal.com/donate/?hosted_button_id=SLNW2MCC268SG).
