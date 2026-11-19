<script setup lang="ts">
// Kachel Manager: the tablet's log under Screen settings (screen_manager/app/kachel_log.py), fetched through Home
// Assistant from the device's <node>_log action, since a device that is passed on has no SSH. Nothing is fetched until
// asked: "Show the end" draws the last piece of one log, "Download log" saves both as one text file for the user to
// add to a GitHub issue themselves. A device without the action says so.
import { computed, ref, watch } from "vue";
import { api, getJson } from "../api";
import { editorNumber, t } from "../i18n";
import { glyph } from "../model/topbar";
import { useUiStore } from "../stores/ui";
import { useScreenStore } from "../stores/screen";

type Tail = { available: boolean; source: string; text?: string; size?: number; cut?: boolean };
type Source = "echod" | "boot";

const ui = useUiStore();
const scr = useScreenStore();
const source = ref<Source>("echod");
const tail = ref<Tail | null>(null);
const busy = ref(false);
const missing = ref(false);

const screen = computed(() => scr.currentScreen);
const route = (id: string) => `screens/${encodeURIComponent(id)}/kachel/log`;
watch(() => screen.value?.id, () => { tail.value = null; missing.value = false; });

function bytes(size: number) {
  return size < 1024 * 1024 ? `${editorNumber(Math.max(1, Math.round(size / 1024)))} KB` : `${editorNumber(Math.round(size / 104857.6) / 10)} MB`;
}

async function show(which: Source = source.value) {
  const current = screen.value;
  if (!current || busy.value) return;
  source.value = which;
  busy.value = true;
  try {
    const data = await getJson<Tail>(`${route(current.id)}?source=${which}`);
    if (screen.value?.id !== current.id) return;
    missing.value = !data.available;
    tail.value = data.available ? data : null;
  } catch (error: any) {
    ui.toast(error.message);
  } finally {
    busy.value = false;
  }
}

async function download() {
  const current = screen.value;
  if (!current || busy.value) return;
  busy.value = true;
  try {
    const response = await api(`${route(current.id)}/download?source=all`);
    const name = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "")?.[1] || "kachel-log.txt";
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url; link.download = name;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error: any) {
    ui.toast(error.message);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section v-if="screen && !screen.virtual" class="set-card" id="settings-kachel-log">
    <h4><span class="mdi">{{ glyph("F0219") }}</span>{{ t("editor.screen_settings.kachel_log.title") }}</h4>
    <p class="hint">{{ t("editor.screen_settings.kachel_log.note") }}</p>
    <p v-if="missing" class="hint warn" data-log="none">{{ t("editor.screen_settings.kachel_log.none") }}</p>
    <div v-else class="kachel-log-bar">
      <div class="seg" role="group" :aria-label="t('editor.screen_settings.kachel_log.title')">
        <button v-for="one in (['echod', 'boot'] as Source[])" :key="one" type="button" :data-source="one"
          :aria-pressed="tail && source === one ? 'true' : 'false'" :disabled="busy" @click="show(one)">{{ t(`editor.screen_settings.kachel_log.${one}`) }}</button>
      </div>
      <button v-if="tail" type="button" class="btn quiet mini" data-log="refresh" :disabled="busy" @click="show()">{{ t("editor.screen_settings.kachel_log.refresh") }}</button>
      <button type="button" class="btn quiet mini" data-log="download" :disabled="busy" @click="download">{{ t("editor.screen_settings.kachel_log.download") }}</button>
    </div>
    <p v-if="busy" class="hint" aria-live="polite">{{ t("editor.screen_settings.kachel_log.loading") }}</p>
    <template v-else-if="tail">
      <p v-if="tail.cut && tail.size" class="hint">{{ t("editor.screen_settings.kachel_log.cut", { size: bytes(tail.size) }) }}</p>
      <pre v-if="tail.text" class="kachel-log" data-log="text">{{ tail.text }}</pre>
      <p v-else class="hint" data-log="empty">{{ t("editor.screen_settings.kachel_log.empty") }}</p>
    </template>
  </section>
</template>

<style scoped>
.kachel-log-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.kachel-log {
  max-height: 360px; overflow: auto; margin: 10px 0 0; padding: 10px; border-radius: 8px;
  background: var(--surface-2, rgba(127, 127, 127, 0.1)); font-size: 12px; line-height: 1.4;
  white-space: pre-wrap; overflow-wrap: anywhere;
}
</style>
