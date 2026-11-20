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
type Assistant = { entity: string; value: string | null; options: string[] };
type View = { functions: Functions; supported: boolean; delivered: boolean; assistant?: Assistant | null };

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
    assistant.value = view.value.assistant?.value || "";
  } catch (error: any) { ui.toast(error.message); }
}
watch(() => scr.currentScreen?.id, load, { immediate: true });

// The assistant is the Kachel integration's own choice (select.<device>_assistant, kachel-verbindung 0.4.0): there once
// the tablet offers the voice assistant, set through the add-on with the rest.
const assistant = ref("");
const assistantChoices = computed(() => (view.value?.assistant?.options || []).map((option) =>
  [option, option === "preferred" ? t("editor.kachel_functions.assist.preferred") : option] as [string, string]));
const changed = computed(() => JSON.stringify(draft.value) !== JSON.stringify(view.value?.functions || {})
  || (Boolean(view.value?.assistant) && assistant.value !== (view.value?.assistant?.value || "")));
// The lists offered, worked out once per inventory (Philip, test 0.0.9-dev7: the tab took up to 30 s, every list of all of
// Home Assistant's entities): only what fits each function, by its domain and what Home Assistant calls it (its words,
// the device class among them) or its name.
type Pick = [string, string];
const label = (e: { id: string; name: string; area?: string }) => [e.id, `${e.name}${e.area ? ` · ${e.area}` : ""}`] as Pick;
const PRESENCE_WORDS = /motion|occupancy|presence|bewegung|anwesen|präsenz|belegung/i;
const FITS: Record<Notice, { domains: string[]; words: RegExp }> = {
  doorbell: { domains: ["event", "binary_sensor"], words: /doorbell|klingel|türklingel|ring/i },
  post: { domains: ["sensor", "binary_sensor", "calendar"], words: /post|brief|mail|letter/i },
  parcels: { domains: ["sensor", "calendar"], words: /paket|parcel|zustell|deliver|sendung|dhl|dpd|ups|hermes|gls|amazon/i },
  waste: { domains: ["calendar", "sensor"], words: /müll|abfall|waste|tonne|garbage|recycl|gwa|abfuhr/i },
  weather: { domains: ["weather"], words: /./ },
};
const lists = computed(() => {
  const entities = inv.inventory.entities;
  const text = (e: { name: string; words?: string; id: string }) => `${e.id} ${e.name} ${e.words || ""}`;
  const presence = entities.filter((e) => {
    const domain = e.id.split(".")[0];
    return domain === "person" || domain === "device_tracker" || (domain === "binary_sensor" && PRESENCE_WORDS.test(text(e)));
  }).map(label);
  const notices = {} as Record<Notice, Pick[]>;
  for (const kind of Object.keys(FITS) as Notice[]) {
    const { domains, words } = FITS[kind];
    notices[kind] = entities.filter((e) => domains.includes(e.id.split(".")[0]) && words.test(text(e))).slice(0, 200).map(label);
  }
  return { presence, notices };
});

// Presence: the sensors whose "on" means someone is near.
const presence = computed(() => draft.value.presence?.entities || []);
const sensors = computed(() => lists.value.presence.filter(([id]) => !presence.value.includes(id)));
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
// A question answered yes before an entity is chosen: open here, nothing stored until one is.
const open = ref(new Set<Notice>());
watch(() => scr.currentScreen?.id, () => { open.value = new Set(); });
const asked = (kind: Notice) => open.value.has(kind) || Boolean(notice(kind));
function answer(kind: Notice, yes: boolean) {
  const next = new Set(open.value);
  if (yes) next.add(kind); else { next.delete(kind); setNotice(kind, ""); }
  open.value = next;
}
const questions = computed<Record<Notice, string>>(() => ({
  doorbell: t("editor.kachel_functions.ask.doorbell"), post: t("editor.kachel_functions.ask.post"), parcels: t("editor.kachel_functions.ask.parcels"),
  waste: t("editor.kachel_functions.ask.waste"), weather: t("editor.kachel_functions.ask.weather"),
}));
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
    const body = view.value?.assistant && assistant.value && assistant.value !== view.value.assistant.value
      ? { ...draft.value, assistant: assistant.value } : draft.value;
    view.value = await send<View>(route(), "PUT", body);
    draft.value = JSON.parse(JSON.stringify(view.value!.functions || {}));
    assistant.value = view.value!.assistant?.value || assistant.value;
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
        <div v-if="view.assistant" class="srow kachel-assistant" data-assistant>
          <span class="s-label">{{ t("editor.kachel_functions.assist.pipeline") }}</span>
          <div class="s-control"><UiSelect id="kachel-assistant" :model-value="assistant" :options="assistantChoices" @update:model-value="(v: string) => assistant = v" /></div>
        </div>
        <small v-else class="hint">{{ t("editor.kachel_functions.assist.pipeline_later") }}</small>
      </template>
    </section>

    <section class="set-card" data-function="notices">
      <h4><span class="kachel-circle amber"><span class="mdi">{{ glyph("F009A") }}</span></span>{{ t("editor.kachel_functions.notices.title") }}</h4>
      <p class="hint">{{ t("editor.kachel_functions.notices.hint") }}</p>
      <!-- One question per kind of notice; a yes offers only what fits it (Philip, test 0.0.9-dev7). -->
      <div v-for="kind in (Object.keys(NOTICES) as Notice[])" :key="kind" class="kachel-notice" :data-notice="kind">
        <div class="srow">
          <span class="s-label">{{ questions[kind] }}</span>
          <div class="s-control seg" role="group">
            <button type="button" :aria-pressed="!asked(kind) ? 'true' : 'false'" @click="answer(kind, false)">{{ t("editor.kachel_functions.no") }}</button>
            <button type="button" :aria-pressed="asked(kind) ? 'true' : 'false'" @click="answer(kind, true)">{{ t("editor.kachel_functions.yes") }}</button>
          </div>
        </div>
        <div v-if="asked(kind)" class="srow kachel-notice-pick">
          <span class="s-label">{{ noticeLabels[kind] }}</span>
          <div class="s-control">
            <UiSelect v-if="lists.notices[kind].length" :id="`kachel-notice-${kind}`" :model-value="notice(kind)" :options="lists.notices[kind]"
              :placeholder="t('editor.kachel_functions.choose')" @update:model-value="(id: string) => setNotice(kind, id)" />
            <small v-else class="hint">{{ t("editor.kachel_functions.nothing_fits") }}</small>
          </div>
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
.kachel-assistant { margin-top: 8px; }
.kachel-notice + .kachel-notice { border-top: 1px solid var(--line); }
.kachel-notice-pick { padding-left: 16px; }
.kachel-functions-bar { display: flex; align-items: center; justify-content: flex-end; gap: 14px; }
</style>
