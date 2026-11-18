<script setup lang="ts">
// Kachel Manager: the tablet's own device under Screen settings (screen_manager/app/kachel_device.py): its updates, its
// battery and its screen, the tablet's own entities in Home Assistant, changed through Home Assistant at once. A row the
// tablet does not have is not there, and a card without rows is not drawn. Switches, choices and buttons look as the
// board's extras do (PluginSettings.vue); an update asks before it installs, since the tablet restarts.
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useDocumentVisibility } from "@vueuse/core";
import { getJson, send } from "../api";
import { editorLanguage, editorNumber, t } from "../i18n";
import { text, type Texts } from "../model/plugins";
import { glyph } from "../model/topbar";
import UiSelect from "../components/ui/UiSelect.vue";
import { useConfirm } from "../composables/useConfirm";
import { useUiStore } from "../stores/ui";
import { useScreenStore } from "../stores/screen";

type Row = {
  key: string; entity: string; label: Texts; available: boolean; writable: boolean;
  kind: "update" | "select" | "button" | "switch" | "light" | "flag" | "reading" | null;
  value?: boolean | string | null; options?: string[]; unit?: string;
  latest?: string | null; pending?: boolean; installing?: boolean; progress?: number | null; brightness?: number | null;
};
type Section = { section: "updates" | "battery" | "screen"; rows: Row[] };

const ui = useUiStore();
const scr = useScreenStore();
const { confirm } = useConfirm();
const visible = useDocumentVisibility();
const sections = ref<Section[]>([]);
let events: EventSource | null = null;

const route = (screenId: string) => `screens/${encodeURIComponent(screenId)}/kachel/device`;
const titles = computed<Record<Section["section"], string>>(() => ({
  updates: t("editor.screen_settings.kachel_device.updates"),
  battery: t("editor.screen_settings.kachel_device.battery"),
  screen: t("editor.screen_settings.kachel_device.screen"),
}));

function listen() {
  events?.close(); events = null;
  sections.value = [];
  const screen = scr.currentScreen;
  if (!screen || screen.virtual || visible.value !== "visible" || typeof EventSource === "undefined") return;
  const stream = new EventSource(`api/${route(screen.id)}/events?language=${encodeURIComponent(editorLanguage())}`);
  events = stream;
  stream.onmessage = (event) => { if (events === stream) sections.value = JSON.parse(event.data); };
  stream.onerror = () => {
    if (events === stream) sections.value = sections.value.map((s) => ({ ...s, rows: s.rows.map((row) => ({ ...row, available: false })) }));
  };
}
// Home Assistant pushes every change of the tablet's entities through this stream; a hidden view has none.
watch(() => [scr.currentScreen?.id, visible.value, editorLanguage()], listen, { immediate: true });
onBeforeUnmount(() => { events?.close(); events = null; });

async function set(row: Row, value: boolean | number | string) {
  const screen = scr.currentScreen;
  if (!screen) return;
  const stream = events;
  if (row.kind === "switch" || (row.kind === "light" && typeof value === "boolean")) row.value = value as boolean;
  else if (row.kind === "select") row.value = value as string;
  else if (row.kind === "light") row.brightness = value as number;
  try {
    await send(route(screen.id), "POST", { entity: row.entity, value });
  } catch (error: any) {
    ui.toast(error.message);
    // A refused change may bring no state event: read once to undo what was shown.
    try { const data = await getJson<Section[]>(route(screen.id)); if (events === stream) sections.value = data; }
    catch { /* The stream brings the values back when the connection returns. */ }
  }
}
async function install(row: Row) {
  const name = scr.currentScreen?.name || "";
  const version = row.latest || "";
  if (!await confirm(t("editor.screen_settings.kachel_device.confirm_install", { version, name }),
    { confirm: t("editor.screen_settings.kachel_device.install") })) return;
  await set(row, "install");
}
function brighter(row: Row, by: number) {
  const next = Math.min(100, Math.max(10, Math.round(((row.brightness ?? 50) + by) / 10) * 10));
  if (next !== row.brightness) set(row, next);
}
const choices = (row: Row) => (row.options || []).map((option) => [option, option] as [string, string]);
const flag = (value: Row["value"]) => value === null || value === undefined ? "–"
  : value ? t("editor.screen_settings.kachel_device.yes") : t("editor.screen_settings.kachel_device.no");
const reading = (row: Row) => row.value === null || row.value === undefined ? "–"
  : `${/^-?\d+(\.\d+)?$/.test(String(row.value)) ? editorNumber(Number(row.value)) : row.value}${row.unit ? ` ${row.unit}` : ""}`;
</script>

<template>
  <section v-if="sections.length" class="set-card" id="settings-kachel-device">
    <h4><span class="mdi">{{ glyph("F0493") }}</span>{{ t("editor.screen_settings.kachel_device.title") }}</h4>
    <p class="hint">{{ t("editor.screen_settings.kachel_device.note") }}</p>
    <div v-for="section in sections" :key="section.section" class="plugin-settings kachel-device" :data-section="section.section">
      <h5>{{ titles[section.section] }}</h5>
      <div v-for="row in section.rows" :key="row.key" class="srow" :class="{ inactive: !row.available }" :data-setting="row.key"
        :title="row.available ? '' : t('editor.screen_settings.unavailable')">
        <span class="s-label">{{ text(row.label) }}</span>
        <div class="s-control">
          <template v-if="row.kind === 'update'">
            <span class="s-status">{{ row.value || "–" }}</span>
            <span v-if="row.installing" class="s-status" aria-live="polite">{{ t("editor.screen_settings.kachel_device.installing") }}{{ row.progress !== null && row.progress !== undefined ? ` ${editorNumber(row.progress)} %` : "" }}</span>
            <template v-else-if="row.pending && row.latest">
              <span class="s-status">{{ t("editor.screen_settings.kachel_device.offered", { version: row.latest }) }}</span>
              <button type="button" class="btn primary mini" :disabled="!row.available" @click="install(row)">{{ t("editor.screen_settings.kachel_device.install") }}</button>
            </template>
            <span v-else class="s-status">{{ t("editor.screen_settings.kachel_device.up_to_date") }}</span>
          </template>
          <button v-else-if="row.kind === 'switch' && row.writable" type="button" class="switch" role="switch" :aria-checked="row.value ? 'true' : 'false'"
            :disabled="!row.available" :aria-label="text(row.label)" @click="set(row, !row.value)"></button>
          <template v-else-if="row.kind === 'select'">
            <div v-if="(row.options || []).length <= 5" class="seg" role="group" :aria-label="text(row.label)">
              <button v-for="option in row.options" :key="option" type="button" :aria-pressed="row.value === option ? 'true' : 'false'" :disabled="!row.available" @click="set(row, option)">{{ option }}</button>
            </div>
            <UiSelect v-else :id="`kachel-device-${row.key}`" :model-value="String(row.value ?? '')" :options="choices(row)" :disabled="!row.available"
              @update:model-value="(value: string) => set(row, value)" />
          </template>
          <button v-else-if="row.kind === 'button'" type="button" class="btn quiet mini" :disabled="!row.available" @click="set(row, true)">{{ text(row.label) }}</button>
          <template v-else-if="row.kind === 'light'">
            <div class="step">
              <button type="button" :aria-label="t('editor.screen_settings.lower', { name: t('editor.screen_settings.kachel_device.brightness') })"
                :disabled="!row.available || !row.value || (row.brightness ?? 0) <= 10" @click="brighter(row, -10)"><span class="mdi">{{ glyph("F0374") }}</span></button>
              <output>{{ row.brightness === null || row.brightness === undefined ? "–" : `${editorNumber(row.brightness)} %` }}</output>
              <button type="button" :aria-label="t('editor.screen_settings.higher', { name: t('editor.screen_settings.kachel_device.brightness') })"
                :disabled="!row.available || !row.value || (row.brightness ?? 100) >= 100" @click="brighter(row, 10)"><span class="mdi">{{ glyph("F0415") }}</span></button>
            </div>
            <button type="button" class="switch" role="switch" :aria-checked="row.value ? 'true' : 'false'" :disabled="!row.available"
              :aria-label="text(row.label)" @click="set(row, !row.value)"></button>
          </template>
          <span v-else-if="row.kind === 'flag' || row.kind === 'switch'" class="s-status">{{ flag(row.value) }}</span>
          <span v-else class="s-status">{{ reading(row) }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
