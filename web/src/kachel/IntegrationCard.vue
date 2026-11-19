<script setup lang="ts">
// Kachel Manager: the Home Assistant integration `kachel` under Settings (screen_manager/app/kachel_integration.py). The
// add-on carries it and writes it into Home Assistant's folder only when Install is pressed; it never restarts Home
// Assistant itself, it only says that a restart is needed to load the version it wrote.
import { onMounted, ref } from "vue";
import { getJson, send } from "../api";
import { t } from "../i18n";
import { useUiStore } from "../stores/ui";

type Status = { installed: boolean; current: boolean; version: string; there: string | null; loaded: string | null; restart: boolean; path: string };

const ui = useUiStore();
const status = ref<Status | null>(null);
const busy = ref(false);

onMounted(async () => {
  try { status.value = await getJson<Status>("kachel/integration"); } catch { /* the card says it is still loading */ }
});

async function install() {
  busy.value = true;
  try {
    status.value = await send<Status>("kachel/integration", "POST");
    ui.toast(t("editor.settings.kachel_integration.written"));
  } catch (error: any) {
    ui.toast(error.message);
  } finally {
    busy.value = false;
  }
}

function said(s: Status) {
  if (!s.installed) return t("editor.settings.kachel_integration.not_installed");
  if (!s.current) return t("editor.settings.kachel_integration.newer", { there: s.there || "?", version: s.version });
  if (s.restart) return t("editor.settings.kachel_integration.restart", { version: s.version });
  return t("editor.settings.kachel_integration.running", { version: s.version });
}
</script>

<template>
  <section class="card" id="kachel-integration">
    <h2>{{ t("editor.settings.kachel_integration.title") }}</h2>
    <p>{{ t("editor.settings.kachel_integration.text") }}</p>
    <div class="actions">
      <button v-if="!status || !status.current" type="button" id="kachel-integration-install" class="btn primary" :disabled="!status || busy" @click="install">
        {{ status?.installed ? t("editor.settings.kachel_integration.update", { version: status.version }) : t("editor.settings.kachel_integration.install") }}
      </button>
      <span id="kachel-integration-status" class="chip" :class="!status || !status.installed ? '' : !status.current || status.restart ? 'update' : 'good'" role="status">
        {{ status ? said(status) : t("editor.common.loading") }}
      </span>
    </div>
    <i18n-t keypath="editor.settings.kachel_integration.writes" tag="small" scope="global">
      <template #path><code>{{ status?.path || "/homeassistant/custom_components/kachel" }}</code></template>
    </i18n-t>
  </section>
</template>
