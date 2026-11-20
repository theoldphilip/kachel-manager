<script setup lang="ts">
// Kachel Manager: what is set up for a Kachel device, its tab "Functions" (screen_manager/app/kachel_functions.py). The
// tablet shows a setting only when its function is set up here: the presence sensor that turns the screen off, the ways
// to turn pages, the voice assistant, the kinds of notices. Saved, the add-on hands it to the tablet in its session.
import { computed, ref, watch } from "vue";
import { getJson, send } from "../api";
import { t } from "../i18n";
import { glyph } from "../model/topbar";
import UiSelect from "../components/ui/UiSelect.vue";
import { useInventoryStore } from "../stores/inventory";
import { useScreenStore } from "../stores/screen";
import { useUiStore } from "../stores/ui";

type Functions = {
  presence?: { entities: string[] };
  page_turn?: { ways: string[] };
  assist?: { ways: string[]; pipeline?: string };
  notices?: Record<string, string | boolean>;
};
type View = { functions: Functions; supported: boolean; delivered: boolean };

const inv = useInventoryStore();
const scr = useScreenStore();
const ui = useUiStore();
const view = ref<View | null>(null);
const draft = ref<Functions>({});
const busy = ref(false);
const PAGE_WAYS = ["swipe", "buttons", "remote"] as const;
const ASSIST_WAYS = ["tap_clock", "wake_word"] as const;
const NOTICES = { doorbell: ["event", "binary_sensor"], post: ["sensor", "binary_sensor", "calendar"], parcels: ["sensor", "calendar"],
  waste: ["calendar", "sensor"], weather: ["weather"] } as const;
type Notice = keyof typeof NOTICES;

const route = () => `screens/${encodeURIComponent(scr.currentScreen!.id)}/kachel/functions`;
async function load() {
  view.value = null;
  if (!scr.currentScreen || scr.currentScreen.virtual) return;
  try {
    view.value = await getJson<View>(route());
    draft.value = JSON.parse(JSON.stringify(view.value.functions || {}));
  } catch (error: any) { ui.toast(error.message); }
}
watch(() => scr.currentScreen?.id, load, { immediate: true });

const changed = computed(() => JSON.stringify(draft.value) !== JSON.stringify(view.value?.functions || {}));
const entitiesOf = (domains: readonly string[]) => inv.inventory.entities
  .filter((e) => domains.includes(e.id.split(".")[0]))
  .map((e) => [e.id, `${e.name}${e.area ? ` · ${e.area}` : ""}`] as [string, string]);

// Presence: the sensors whose "on" means someone is near.
const presence = computed(() => draft.value.presence?.entities || []);
const sensors = computed(() => entitiesOf(["binary_sensor"]).filter(([id]) => !presence.value.includes(id)));
function addSensor(id: string) { draft.value.presence = { entities: [...presence.value, id].slice(0, 4) }; }
function dropSensor(id: string) {
  const left = presence.value.filter((e) => e !== id);
  if (left.length) draft.value.presence = { entities: left }; else delete draft.value.presence;
}
const nameOf = (id: string) => inv.inventory.entities.find((e) => e.id === id)?.name || id;

// Ways: a way is on while it is in the list; the last one off turns the function off.
function toggleWay(key: "page_turn" | "assist", way: string) {
  const current = draft.value[key]?.ways || [];
  const ways = current.includes(way) ? current.filter((w) => w !== way) : [...current, way];
  if (key === "page_turn") { if (ways.length) draft.value.page_turn = { ways }; else delete draft.value.page_turn; }
  else draft.value.assist = { ...(draft.value.assist || {}), ways };
}
const assistOn = computed(() => Boolean(draft.value.assist));
function setAssist(on: boolean) { if (on) draft.value.assist = { ways: ["tap_clock"] }; else delete draft.value.assist; }

function notice(kind: Notice) { return String(draft.value.notices?.[kind] || ""); }
function setNotice(kind: Notice | "missed", value: string | boolean) {
  const notices = { ...(draft.value.notices || {}) };
  if (value === "" || value === false) delete notices[kind]; else notices[kind] = value;
  if (Object.keys(notices).length) draft.value.notices = notices; else delete draft.value.notices;
}
const noticeLabels = computed<Record<Notice, string>>(() => ({
  doorbell: t("editor.kachel_functions.notices.doorbell"), post: t("editor.kachel_functions.notices.post"),
  parcels: t("editor.kachel_functions.notices.parcels"), waste: t("editor.kachel_functions.notices.waste"),
  weather: t("editor.kachel_functions.notices.weather"),
}));
const wayLabels = computed<Record<string, string>>(() => ({
  swipe: t("editor.kachel_functions.ways.swipe"), buttons: t("editor.kachel_functions.ways.buttons"), remote: t("editor.kachel_functions.ways.remote"),
  tap_clock: t("editor.kachel_functions.ways.tap_clock"), wake_word: t("editor.kachel_functions.ways.wake_word"),
}));

async function save() {
  busy.value = true;
  try {
    view.value = await send<View>(route(), "PUT", draft.value);
    draft.value = JSON.parse(JSON.stringify(view.value!.functions || {}));
    ui.toast(t("editor.kachel_functions.saved"));
  } catch (error: any) { ui.toast(error.message); }
  finally { busy.value = false; }
}
</script>

<template>
  <div v-if="view" class="kachel-functions" id="kachel-functions">
    <p class="hint">{{ t("editor.kachel_functions.intro") }}</p>
    <p v-if="!view.supported" class="hint warn" data-functions="unsupported">{{ t("editor.kachel_functions.unsupported") }}</p>

    <section class="set-card" data-function="presence">
      <h4><span class="kachel-circle violet"><span class="mdi">{{ glyph("F0004") }}</span></span>{{ t("editor.kachel_functions.presence.title") }}</h4>
      <p class="hint">{{ t("editor.kachel_functions.presence.hint") }}</p>
      <div class="chips">
        <span v-for="id in presence" :key="id" class="chip">{{ nameOf(id) }}
          <button type="button" class="chip-x" :aria-label="t('editor.kachel_functions.remove')" @click="dropSensor(id)">×</button></span>
      </div>
      <UiSelect v-if="presence.length < 4" id="kachel-presence-add" :model-value="''" :options="sensors" :placeholder="t('editor.kachel_functions.presence.add')"
        @update:model-value="(id: string) => id && addSensor(id)" />
    </section>

    <section class="set-card" data-function="page_turn">
      <h4><span class="kachel-circle blue"><span class="mdi">{{ glyph("F056E") }}</span></span>{{ t("editor.kachel_functions.page_turn.title") }}</h4>
      <p class="hint">{{ t("editor.kachel_functions.page_turn.hint") }}</p>
      <div class="seg" role="group">
        <button v-for="way in PAGE_WAYS" :key="way" type="button" :data-way="way" :aria-pressed="(draft.page_turn?.ways || []).includes(way) ? 'true' : 'false'"
          @click="toggleWay('page_turn', way)">{{ wayLabels[way] }}</button>
      </div>
    </section>

    <section class="set-card" data-function="assist">
      <h4><span class="kachel-circle teal"><span class="mdi">{{ glyph("F036C") }}</span></span>{{ t("editor.kachel_functions.assist.title") }}
        <button type="button" class="switch kachel-switch" role="switch" :aria-checked="assistOn ? 'true' : 'false'" :aria-label="t('editor.kachel_functions.assist.title')"
          @click="setAssist(!assistOn)"></button></h4>
      <p class="hint">{{ t("editor.kachel_functions.assist.hint") }}</p>
      <template v-if="assistOn">
        <div class="seg" role="group">
          <button v-for="way in ASSIST_WAYS" :key="way" type="button" :data-way="way" :aria-pressed="(draft.assist?.ways || []).includes(way) ? 'true' : 'false'"
            @click="toggleWay('assist', way)">{{ wayLabels[way] }}</button>
        </div>
        <input type="text" class="kachel-pipeline" :value="draft.assist?.pipeline || ''" :placeholder="t('editor.kachel_functions.assist.pipeline')"
          @input="draft.assist = { ...(draft.assist || { ways: [] }), pipeline: ($event.target as HTMLInputElement).value }" />
      </template>
    </section>

    <section class="set-card" data-function="notices">
      <h4><span class="kachel-circle amber"><span class="mdi">{{ glyph("F009A") }}</span></span>{{ t("editor.kachel_functions.notices.title") }}</h4>
      <p class="hint">{{ t("editor.kachel_functions.notices.hint") }}</p>
      <div v-for="(domains, kind) in NOTICES" :key="kind" class="srow" :data-notice="kind">
        <span class="s-label">{{ noticeLabels[kind] }}</span>
        <div class="s-control">
          <UiSelect :id="`kachel-notice-${kind}`" :model-value="notice(kind)" :options="[['', t('editor.kachel_functions.none')], ...entitiesOf(domains)]"
            @update:model-value="(id: string) => setNotice(kind, id)" />
        </div>
      </div>
      <div class="srow" data-notice="missed">
        <span class="s-label">{{ t("editor.kachel_functions.notices.missed") }}</span>
        <div class="s-control"><button type="button" class="switch" role="switch" :aria-checked="draft.notices?.missed ? 'true' : 'false'"
          :aria-label="t('editor.kachel_functions.notices.missed')" @click="setNotice('missed', !draft.notices?.missed)"></button></div>
      </div>
    </section>

    <div class="kachel-functions-bar">
      <span class="hint" data-functions="state">{{ changed ? t("editor.kachel_functions.unsaved") : view.delivered ? t("editor.kachel_functions.delivered") : t("editor.kachel_functions.waiting") }}</span>
      <button type="button" class="btn primary" id="kachel-functions-save" :disabled="!changed || busy" @click="save">{{ t("editor.kachel_functions.save") }}</button>
    </div>
  </div>
</template>

<style scoped>
.kachel-functions { display: grid; gap: 14px; max-width: 900px; }
.set-card h4 { display: flex; align-items: center; gap: 12px; }
.kachel-circle { width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; font-size: 18px; flex: none; }
.kachel-switch { margin-left: auto; }
.violet { color: #9b6cf0; background: rgba(160, 110, 255, 0.16); }
.blue { color: #4f86f0; background: rgba(80, 140, 255, 0.16); }
.teal { color: var(--accent); background: var(--accent-soft); }
.amber { color: #d8941c; background: rgba(224, 160, 58, 0.16); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 8px; }
.chip-x { margin-left: 4px; color: var(--muted); font-size: 14px; }
.kachel-pipeline { margin-top: 10px; max-width: 360px; }
.kachel-functions-bar { display: flex; align-items: center; justify-content: flex-end; gap: 14px; }
</style>
