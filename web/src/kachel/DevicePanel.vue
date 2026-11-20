<script setup lang="ts">
// Kachel Manager: the tablet's own device under Screen settings (screen_manager/app/kachel_device.py): its updates, its
// battery and its screen, the tablet's own entities in Home Assistant, changed through Home Assistant at once. A row the
// tablet does not have is not there, and a card without rows is not drawn. Switches, choices and buttons look as the
// board's extras do (PluginSettings.vue); an update asks before it installs, since the tablet restarts. In the Kachel
// Manager it stands in for Tessera's own setting groups (SettingsTab.vue), whose entities only an ESP32 screen has.
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
  kind: "update" | "select" | "button" | "switch" | "light" | "flag" | "reading" | "outcome" | null;
  value?: boolean | string | null; options?: string[]; unit?: string;
  latest?: string | null; at?: string | null; pending?: boolean; installing?: boolean; progress?: number | null; brightness?: number | null;
};
type Section = { section: "updates" | "battery" | "screen" | "pages"; rows: Row[] };

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
  pages: t("editor.screen_settings.kachel_device.pages"),
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
// The last update's outcome and when it came, in the editor's language: "Installed · 19.11., 21:05".
function outcome(row: Row) {
  if (typeof row.value !== "string") return "–";
  const word = t(`editor.screen_settings.kachel_device.outcome.${row.value}`);
  const at = row.at ? new Date(row.at) : null;
  return at && !isNaN(at.getTime())
    ? `${word} · ${at.toLocaleString(editorLanguage(), { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}` : word;
}
// The menu (the redesign, 2026-11-20): one card per section as the tablet's own settings show them (kachel-zentrale
// design/einstellungen.png), a symbol in a circle, what is in it and how it stands now; a tap opens its rows.
const open = ref<Section["section"] | null>(null);
watch(() => scr.currentScreen?.id, () => { open.value = null; });
const opened = computed(() => sections.value.find((s) => s.section === open.value) || null);
const MENU: Record<Section["section"], { icon: string; tint: string }> = {
  screen: { icon: "F00DF", tint: "amber" }, pages: { icon: "F056E", tint: "blue" },
  updates: { icon: "F06B0", tint: "teal" }, battery: { icon: "F0084", tint: "green" },
};
const about = computed<Record<Section["section"], string>>(() => ({
  screen: t("editor.screen_settings.kachel_device.menu.about.screen"), pages: t("editor.screen_settings.kachel_device.menu.about.pages"),
  updates: t("editor.screen_settings.kachel_device.menu.about.updates"), battery: t("editor.screen_settings.kachel_device.menu.about.battery"),
}));
const ORDER: Section["section"][] = ["screen", "pages", "updates", "battery"];
const menu = computed(() => ORDER.map((key) => sections.value.find((s) => s.section === key)).filter((s): s is Section => Boolean(s)));
const rowOf = (section: Section, key: string) => section.rows.find((row) => row.key === key);
function standing(section: Section) {
  if (section.section === "screen") {
    const light = rowOf(section, "screen");
    return light && light.brightness !== null && light.brightness !== undefined && light.value ? t("editor.screen_settings.kachel_device.menu.brightness", { value: editorNumber(light.brightness) })
      : light && light.value === false ? t("editor.screen_settings.kachel_device.menu.off") : "";
  }
  if (section.section === "pages") { const start = rowOf(section, "start_page"); return start?.value ? t("editor.screen_settings.kachel_device.menu.start", { page: String(start.value) }) : ""; }
  if (section.section === "updates") {
    const fw = rowOf(section, "firmware");
    return fw?.pending && fw.latest ? t("editor.screen_settings.kachel_device.menu.offered", { version: fw.latest }) : fw?.value ? t("editor.screen_settings.kachel_device.menu.version", { version: String(fw.value) }) : "";
  }
  const level = rowOf(section, "battery_level"), charging = rowOf(section, "battery_charging");
  return level?.value ? `${reading(level)}${charging?.value ? ` · ${t("editor.screen_settings.kachel_device.menu.charging")}` : ""}` : "";
}
const reading = (row: Row) => row.value === null || row.value === undefined ? "–"
  : `${/^-?\d+(\.\d+)?$/.test(String(row.value)) ? editorNumber(Number(row.value)) : row.value}${row.unit ? ` ${row.unit}` : ""}`;
</script>

<template>
  <section v-if="sections.length" class="set-card" id="settings-kachel-device">
    <h4><span class="mdi">{{ glyph("F0493") }}</span>{{ t("editor.screen_settings.kachel_device.title") }}</h4>
    <p class="hint">{{ t("editor.screen_settings.kachel_device.note") }}</p>
    <div v-if="!opened" class="kachel-menu">
      <button v-for="section in menu" :key="section.section" type="button" class="kachel-menu-card" :data-menu="section.section" @click="open = section.section">
        <span class="kachel-circle" :class="MENU[section.section].tint"><span class="mdi">{{ glyph(MENU[section.section].icon) }}</span></span>
        <span class="kachel-menu-text">
          <b>{{ titles[section.section] }}</b>
          <small>{{ about[section.section] }}</small>
          <em v-if="standing(section)" :class="MENU[section.section].tint">{{ standing(section) }}</em>
        </span>
        <span class="mdi kachel-menu-go">{{ glyph("F0142") }}</span>
      </button>
    </div>
    <div v-for="section in opened ? [opened] : []" :key="section.section" class="plugin-settings kachel-device" :data-section="section.section">
      <h5 class="kachel-back-row"><button type="button" class="kachel-back" :aria-label="t('editor.screen_settings.kachel_device.menu.back')" @click="open = null"><span class="mdi">{{ glyph("F004D") }}</span></button>{{ titles[section.section] }}</h5>
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
          <span v-else-if="row.kind === 'outcome'" class="s-status">{{ outcome(row) }}</span>
          <span v-else-if="row.kind === 'flag' || row.kind === 'switch'" class="s-status">{{ flag(row.value) }}</span>
          <span v-else class="s-status">{{ reading(row) }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* The version and its word beside it ("0.0.9 · Aktuell") need room between them, as the buttons beside a choice do. */
.kachel-device .s-status + .s-status, .kachel-device .s-status + .btn { margin-left: 8px; }
</style>

<style scoped>
.kachel-menu { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; padding: 6px 0 4px; }
.kachel-menu-card { display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-radius: 16px; background: var(--surface-2);
  border: 1px solid var(--line); text-align: left; color: var(--ink); }
.kachel-menu-card:hover { border-color: var(--line-strong); }
.kachel-circle { width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; font-size: 22px; flex: none; }
.kachel-menu-text { display: grid; min-width: 0; flex: 1; }
.kachel-menu-text b { font-size: 15px; }
.kachel-menu-text small { color: var(--muted); font-size: 12px; }
.kachel-menu-text em { font-style: normal; font-size: 12.5px; }
.kachel-menu-go { color: var(--muted); font-size: 20px; }
.amber { color: #d8941c; } .kachel-circle.amber { background: rgba(224, 160, 58, 0.16); }
.blue { color: #4f86f0; } .kachel-circle.blue { background: rgba(80, 140, 255, 0.16); }
.teal { color: var(--accent); } .kachel-circle.teal { background: var(--accent-soft); }
.green { color: #2fa86c; } .kachel-circle.green { background: rgba(63, 191, 127, 0.16); }
.kachel-back-row { display: flex; align-items: center; gap: 10px; }
.kachel-back { width: 32px; height: 32px; border-radius: 50%; background: var(--surface-2); display: grid; place-items: center; font-size: 18px; color: var(--ink); }
</style>
