<script setup lang="ts">
// Kachel Manager: where Tessera offers a troubleshooting report for its website (ReportPanel), the Kachel Manager sends
// nothing there (kachel.TESSERA_SITE): a problem is reported as an issue on GitHub (kachel.ISSUES), by the person.
import { computed } from "vue";
import { t } from "../i18n";
import { glyph } from "../model/topbar";
import Icon from "../components/ui/Icon.vue";
import { useInventoryStore } from "../stores/inventory";

const inv = useInventoryStore();
const issues = computed(() => inv.inventory.editor_features?.issues || "https://github.com/theoldphilip/kachel-manager/issues");
</script>

<template>
  <section class="set-card" id="settings-kachel-issue">
    <h4><span class="mdi">{{ glyph("F02D7") }}</span>{{ t("editor.kachel_issue.title") }}</h4>
    <p class="hint">{{ t("editor.kachel_issue.hint") }}</p>
    <div class="s-action">
      <a class="btn quiet" id="kachel-issue" :href="`${issues}/new`" target="_blank" rel="noopener">{{ t("editor.kachel_issue.button") }}<Icon name="arrow-right" /></a>
    </div>
  </section>
</template>
