<script setup lang="ts">
// Kachel Manager: the way to a device's log from Settings (Fire test, 2026-11-20: the card "Log" was not found under
// each screen's own settings). One button per Kachel device opens that screen's settings at its card "Log"
// (src/kachel/LogPanel.vue); nothing is fetched here.
import { computed, nextTick } from "vue";
import { t } from "../i18n";
import { useInventoryStore } from "../stores/inventory";
import { useScreenStore } from "../stores/screen";
import { useSessionStore } from "../stores/session";
import { useUiStore } from "../stores/ui";
import type { Screen } from "../types";

const inv = useInventoryStore();
const ui = useUiStore();
const scr = useScreenStore();
const session = useSessionStore();
const screens = computed(() => inv.inventory.screens.filter((screen) => !screen.virtual));

async function open(screen: Screen) {
  // As the command palette opens a screen's setting: the screen first, then its settings.
  if (scr.selected !== screen.id) await session.select(screen.id);
  if (scr.selected !== screen.id) return;
  await ui.go("");
  ui.tab = "settings";
  await nextTick();
  setTimeout(() => document.getElementById("settings-kachel-log")?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
}
</script>

<template>
  <section v-if="screens.length" class="card" id="kachel-log-shortcut">
    <h2>{{ t("editor.settings.kachel_log.title") }}</h2>
    <p>{{ t("editor.settings.kachel_log.text") }}</p>
    <div class="actions">
      <button v-for="screen in screens" :key="screen.id" type="button" class="btn quiet" :data-screen="screen.id" @click="open(screen)">
        {{ screen.name || screen.id }}
      </button>
    </div>
  </section>
</template>
