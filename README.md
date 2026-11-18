<p align="center">
  <img src="https://raw.githubusercontent.com/theoldphilip/kachel-manager/main/screen_manager/logo.png" width="360" alt="Kachel Manager">
</p>

<p align="center"><b>Aus einem alten Android-Tablet oder -Handy wird ein Wandpanel für Home Assistant.</b></p>

Kachel ersetzt Android auf dem Gerät durch ein kleines Linux (Alpine) mit einer eigenen Oberfläche. Das Gerät startet
direkt in deine Seiten aus Kacheln: Licht, Heizung, Musik, Kameras, Kalender, Energie. Keine App, kein
Browser, kein Google-Konto, keine Werbung. Der **Kachel Manager** ist das Add-on dazu: Hier legst du fest, was auf
welcher Seite steht, und stellst das Gerät selbst ein.

## Was der Kachel Manager kann

- 🧩 **Seiten aus Kacheln** zusammenstellen, per Ziehen und Ablegen, mit einer Vorschau, die zeigt, was Home Assistant
  gerade meldet.
- 🔋 **Das Gerät einstellen:** Updates, Akkuschutz, Helligkeit, Nachtmodus, Startseite. Alles, was das Gerät in
  Home Assistant anbietet, an einer Stelle.
- 🔔 **Hinweise auf alle Geräte schicken**, etwa wenn es klingelt, mit eigenen Ereignissen für Automationen.
- 🔒 **Bleibt bei dir:** keine Cloud, kein Konto. Was du einstellst, bleibt in Home Assistant.

## Welche Geräte gehen?

Kachel läuft auf Android-Geräten, deren **Bootloader sich entsperren lässt**. Das ist die eine harte Bedingung: Bleibt
der Bootloader gesperrt, startet das Gerät nur das System des Herstellers, und Kachel hat keine Chance.

**Läuft heute:**

| Gerät | Prozessor | Stand |
|---|---|---|
| Samsung Galaxy Tab A 10.1 (2019, SM-T510) | Exynos 7904 | ✅ läuft im Alltag |
| Samsung Galaxy A12 (SM-A127F) | Exynos 850 | ✅ läuft im Alltag |
| Amazon Fire HD 8 Plus (12. Generation) | MediaTek MT8169A | 🛠️ in Arbeit |

**Prognose für weitere Geräte** (noch nicht ausprobiert):

| Gerät | Warum | Aussicht |
|---|---|---|
| Andere Samsung-Geräte mit Exynos 7904/7885 (z. B. Tab A 10.1 LTE SM-T515, Galaxy A30, A40) | gleicher Prozessor wie das Tab A, Samsung veröffentlicht die Kernel-Quellen | 🟢 gut |
| Samsung-Geräte mit Exynos 850 (z. B. Galaxy A13 SM-A135F, A21s, M13) | gleicher Prozessor wie das A12 | 🟢 gut |
| Andere Samsung-Geräte aus Europa (Exynos oder MediaTek) | Bootloader lässt sich in den Entwickler-Optionen entsperren, Kernel-Quellen sind öffentlich | 🟡 machbar, braucht Anpassung |
| Google Pixel und Pixel Tablet, Lenovo- und Xiaomi-Tablets | Bootloader meist offiziell entsperrbar, anderer Prozessor | 🟡 machbar, mehr Arbeit |
| Amazon Fire (andere Modelle) | Bootloader gesperrt, bei einigen MediaTek-Modellen über eine bekannte Lücke entsperrbar | 🟠 nur einzelne Modelle |
| Samsung aus den USA (Snapdragon), Huawei, Geräte vom Mobilfunkanbieter | Bootloader lässt sich nicht entsperren | 🔴 keine Chance |

## Ehrlich gesagt: noch viel Handarbeit

Kachel ist jung. Ein neues Gerät einzurichten heißt heute vor allem: Bootloader entsperren, einen passenden Kernel
bauen und das System von Hand aufspielen. Das ist nichts für einen Nachmittag ohne Vorkenntnisse, aber es wird mit
jedem Gerät leichter.

**Du hast ein Gerät, das noch nicht in der Liste steht?** Ich prüfe neue Geräte gern. Schreib mir auf
[GitHub](https://github.com/theoldphilip/kachel-manager/issues/new) das genaue Modell (zum Beispiel SM-T510), den
Prozessor und ob sich der Bootloader entsperren lässt.

## Und ESP32-Bildschirme?

Kleine ESP32-Touch-Bildschirme (CYD, Guition, Waveshare …) versorgt das Add-on
[Tessera](https://github.com/MaxGramser/homeassistant_espscreen). Beide laufen problemlos nebeneinander.

---

Der Kachel Manager ist kostenlos. Wenn er dir nützt, freue ich mich über eine
[Spende per PayPal](https://www.paypal.com/donate/?hosted_button_id=SLNW2MCC268SG).

Fork von [Tessera](https://github.com/MaxGramser/homeassistant_espscreen) von Max Gramser (AGPL-3.0) ·
Quelle: [theoldphilip/kachel-manager](https://github.com/theoldphilip/kachel-manager)

## Für Entwickler

`CLAUDE.md` beschreibt, was dieser Fork anders macht als Tessera und wie Neues vom Original übernommen wird.
`AGENTS.md` und `README_EXTENDED.md` sind die Anleitungen von Tessera. Icon und Logo schneidet `tools/kachel_logo.py`
aus dem Startbild der Geräte (echod).
