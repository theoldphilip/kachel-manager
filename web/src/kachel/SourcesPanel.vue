<script setup lang="ts">
// Kachel Manager: the sources of a Spezialanzeige, its tab "Sources" (screen_manager/app/kachel_sources.py). The device
// says in its hello which sources its task needs (the room's temperature, the light, the power meter …); here an entity
// is picked for each, and the room's name. A source left empty is off: the device hides its button.
import { computed, ref, watch } from "vue";
import { getJson, send } from "../api";
import { editorLanguage, t } from "../i18n";
import UiSelect from "../components/ui/UiSelect.vue";
import { useScreenStore } from "../stores/screen";
import { useUiStore } from "../stores/ui";

type Offered = { key: string; name: Record<string, string>; domains: string[]; device_class: string[]; required: boolean };
type View = {
  kind: string; offered: Offered[]; sources: Record<string, string>; room: string | null; area: string | null;
  choices: Record<string, [string, string][]>; supported: boolean; delivered: boolean;
};

const scr = useScreenStore();
const ui = useUiStore();
const view = ref<View | null>(null);
const sources = ref<Record<string, string>>({});
const room = ref("");
const busy = ref(false);

const route = () => `screens/${encodeURIComponent(scr.currentScreen!.id)}/kachel/sources`;
function take(next: View) {
  view.value = next;
  sources.value = { ...(next.sources || {}) };
  room.value = next.room || "";
}
async function load() {
  view.value = null;
  if (!scr.currentScreen || scr.currentScreen.virtual) return;
  try { take(await getJson<View>(route())); } catch (error: any) { ui.toast(error.message); }
}
watch(() => scr.currentScreen?.id, load, { immediate: true });

// The device names each source in German and English; the editor's language first, then English, then its key.
const nameOf = (source: Offered) => source.name[editorLanguage().slice(0, 2)] || source.name.en || source.name.de || source.key;
const missing = computed(() => (view.value?.offered || []).filter((s) => s.required && !sources.value[s.key]).map((s) => s.key));
const changed = computed(() => JSON.stringify(sources.value) !== JSON.stringify(view.value?.sources || {})
  || room.value.trim() !== (view.value?.room || ""));
function choose(key: string, entity: string) {
  const next = { ...sources.value };
  if (entity) next[key] = entity; else delete next[key];
  sources.value = next;
}

async function save() {
  busy.value = true;
  try {
    take(await send<View>(route(), "PUT", { sources: sources.value, room: room.value.trim() || null }));
    ui.toast(t("editor.kachel_sources.saved"));
  } catch (error: any) { ui.toast(error.message); }
  finally { busy.value = false; }
}
</script>

<template>
  <div v-if="view" class="kachel-sources" id="kachel-sources">
    <p class="hint">{{ t("editor.kachel_sources.intro") }}</p>
    <p v-if="!view.supported" class="hint warn" data-sources="unsupported">{{ t("editor.kachel_sources.unsupported") }}</p>

    <section class="set-card" data-source="room">
      <h4>{{ t("editor.kachel_sources.room.title") }}</h4>
      <p class="hint">{{ view.area ? t("editor.kachel_sources.room.area", { area: view.area }) : t("editor.kachel_sources.room.no_area") }}</p>
      <input id="kachel-room" v-model="room" class="input" type="text" maxlength="60" :placeholder="view.area || ''" />
    </section>

    <section class="set-card" data-source="list">
      <h4>{{ t("editor.kachel_sources.title") }}</h4>
      <p v-if="!view.offered.length" class="hint" data-sources="none">{{ t("editor.kachel_sources.none") }}</p>
      <div v-for="source in view.offered" :key="source.key" class="srow" :data-source="source.key">
        <span class="s-label">{{ nameOf(source) }}<small v-if="source.required" class="req" :class="{ missing: missing.includes(source.key) }">
          {{ t("editor.kachel_sources.required") }}</small></span>
        <div class="s-control">
          <UiSelect v-if="(view.choices[source.key] || []).length" :id="`kachel-source-${source.key}`" :model-value="sources[source.key] || ''"
            :options="[['', t('editor.kachel_sources.off')], ...view.choices[source.key]]" @update:model-value="(id: string) => choose(source.key, id)" />
          <small v-else class="hint">{{ t("editor.kachel_sources.nothing_fits") }}</small>
        </div>
      </div>
      <p class="hint">{{ t("editor.kachel_sources.off_hint") }}</p>
    </section>

    <div class="kachel-sources-bar">
      <span class="hint" data-sources="state">{{ changed ? t("editor.kachel_sources.unsaved") : view.delivered ? t("editor.kachel_sources.delivered") : t("editor.kachel_sources.waiting") }}</span>
      <button type="button" class="btn primary" id="kachel-sources-save" :disabled="!changed || busy" @click="save">{{ t("editor.kachel_sources.save") }}</button>
    </div>
  </div>
</template>

<style scoped>
.kachel-sources { display: grid; gap: 14px; max-width: 900px; }
.req { margin-left: 8px; color: var(--muted); }
.req.missing { color: var(--danger, #d9534f); }
.kachel-sources-bar { display: flex; align-items: center; justify-content: flex-end; gap: 14px; }
</style>
