# Kachel Manager

## Installieren

1. Repository `https://github.com/theoldphilip/kachel-manager` unter **Einstellungen → Add-ons → Add-on Store → ⋮ →
   Repositories** hinzufügen.
2. **Kachel Manager** installieren und starten. Auf der Info-Seite **Watchdog** einschalten: Home Assistant startet
   das Add-on dann neu, falls es einmal stehen bleibt.
3. **Kachel** in der Seitenleiste öffnen. Das Add-on läuft über Home Assistant Ingress und braucht kein eigenes
   Login und kein Token.

## Ein Tablet verbinden

Ein Kachel-Gerät hat in Home Assistant die Auswahl **Managed by**. Steht sie auf **Kachel Manager**, meldet das Tablet
sein Postfach als Text „Kachel inbox“, und der Kachel Manager zeigt es in der Seitenleiste. Steht sie auf
**Tessera**, gehört es dem Tessera-Add-on. So nimmt keiner das Gerät des anderen.

Beim Umstellen bleibt das bisherige Layout auf dem Tablet stehen, bis der Kachel Manager ein neues schickt.

## Layout

Im Tab **Layout** stehen die Seiten des Tablets mit ihren Kacheln. Eine Entität aus Home Assistant wird zur Kachel,
ein Tipp auf eine Kachel öffnet rechts ihre Einstellungen. Die Leiste oben auf jeder Seite ist die Kopfzeile: links
der Name, rechts Uhrzeit, Datum oder Entitäten.

## Gerät

Unter **Bildschirmeinstellungen → Gerät** stehen die Einstellungen, die das Tablet selbst in Home Assistant meldet:

- **Updates:** installierte Version, Update-Kanal, Suche nach Updates, automatische Updates, die Version im anderen
  Slot. Ein Update fragt vor dem Installieren, weil das Tablet danach neu startet. Den Slot wechselt der Kachel
  Manager nicht, er zeigt ihn nur.
- **Akku:** Ladestand, Ladegerät, Akkuschutz, volle Leistung.
- **Bildschirm:** Helligkeit, Dimmen bei Ruhe, Nachtmodus und Nachtstunden (auch am Wochenende), aus bei leerem
  Raum, Textgröße, Uhrzeit-Format, Einstellungssperre.
- **Seiten:** Startseite, zurück zur Startseite, blättern mit.

Dieselben Einstellungen stehen in Home Assistant beim Gerät des Tablets. Eine Änderung hier oder dort erscheint
sofort auf beiden Seiten. Was ein Gerät nicht hat (der Fire etwa kein automatisches Update), fehlt.

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
