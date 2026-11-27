<script setup lang="ts">
// Kachel Manager: "Install Kachel OS" (Spur K, format v1 of kachel-installer-tool). The device hangs by USB at this PC;
// the page checks the browser (HTTPS, WebUSB), shows the device's profile from the add-on (signed, checked against the
// lists in the code), how to reach the download mode, and runs the read-only trial: connect, read the partition table,
// compare it with the profile. There is no write in this stage: installing comes once the trial worked on a real device.
import { computed, onMounted, ref } from "vue";
import { getJson } from "../api";
import { editorLanguage, t } from "../i18n";
import { browserCheck, comparePit, say, type Channel, type CheckRow } from "./installer";
import { readPit } from "./odin-readonly";

type View = { channels: Channel[]; manager: string | null };

const view = ref<View | null>(null);
const failed = ref("");
const chosen = ref("");
const browser = browserCheck(window);
const busy = ref(false);
const result = ref<{ ok: boolean; rows: CheckRow[] } | null>(null);
const trialError = ref("");
const log = ref<string[]>([]);
const lang = () => editorLanguage();

onMounted(async () => {
  try {
    view.value = await getJson<View>("kachel/installer");
    const usable = view.value.channels.filter((c) => c.profile && !c.problems.length);
    chosen.value = (usable.find((c) => c.channel === "stable") || usable[0] || view.value.channels.find((c) => c.present))?.channel || "";
  } catch (error: any) { failed.value = error.message; }
});

const channel = computed(() => view.value?.channels.find((c) => c.channel === chosen.value) || null);
const profile = computed(() => (channel.value && !channel.value.problems.length ? channel.value.profile : null));
const fileUrl = (name: string) => `api/kachel/installer/${encodeURIComponent(chosen.value)}/file/${encodeURIComponent(name)}`;

async function trial() {
  if (!profile.value) return;
  busy.value = true; result.value = null; trialError.value = ""; log.value = [];
  try {
    const filters = profile.value.usb.map((u) => ({ vendorId: parseInt(u.vid, 16), productId: parseInt(u.pid, 16) }));
    const usb = await navigator.usb.requestDevice({ filters });
    const pit = await readPit(usb, (line) => { log.value = [...log.value.slice(-199), line]; });
    result.value = comparePit(profile.value, pit);
  } catch (error: any) {
    trialError.value = error?.name === "NotFoundError" ? t("editor.kachel_install.no_device") : String(error?.message || error);
  } finally { busy.value = false; }
}
</script>

<template>
  <section class="kachel-install settings" id="kachel-install">
    <h1>{{ t("editor.kachel_install.title") }}</h1>
    <p class="hint">{{ t("editor.kachel_install.intro") }}</p>

    <div class="set-card" data-install="browser">
      <h4>{{ t("editor.kachel_install.browser.title") }}</h4>
      <p v-if="!browser.secure" class="hint warn" data-browser="insecure">{{ t("editor.kachel_install.browser.insecure") }}</p>
      <p v-else-if="!browser.usb" class="hint warn" data-browser="no-usb">{{ t("editor.kachel_install.browser.no_usb") }}</p>
      <p v-else class="hint" data-browser="ok">{{ t("editor.kachel_install.browser.ok") }}</p>
    </div>

    <p v-if="failed" class="hint warn">{{ failed }}</p>
    <template v-else-if="view">
      <div class="set-card" data-install="profile">
        <h4>{{ t("editor.kachel_install.profile.title") }}</h4>
        <p v-if="!view.channels.some((c) => c.present)" class="hint" data-profile="none">{{ t("editor.kachel_install.profile.none") }}</p>
        <div v-else class="seg" role="group">
          <button v-for="c in view.channels.filter((c) => c.present)" :key="c.channel" type="button" :data-channel="c.channel"
            :aria-pressed="chosen === c.channel ? 'true' : 'false'" @click="chosen = c.channel; result = null">{{ t(`editor.kachel_install.channel.${c.channel}`) }}</button>
        </div>
        <ul v-if="channel?.problems.length" class="hint warn" data-profile="problems">
          <li v-for="p in channel.problems" :key="p">{{ p }}</li>
        </ul>
        <p v-if="profile" data-profile="ok"><b>{{ say(profile.name, lang()) }}</b> · Kachel OS {{ profile.version }}</p>
      </div>

      <template v-if="profile">
        <div class="set-card" data-install="mode">
          <h4>{{ t("editor.kachel_install.mode.title") }}</h4>
          <ol class="install-steps">
            <li v-for="(step, i) in profile.mode_entry" :key="i">
              <span>{{ say(step.text, lang()) }}</span>
              <img v-if="step.image" :src="fileUrl(step.image)" alt="" loading="lazy" />
            </li>
          </ol>
        </div>

        <div class="set-card" data-install="trial">
          <h4>{{ t("editor.kachel_install.trial.title") }}</h4>
          <p class="hint">{{ t("editor.kachel_install.trial.hint") }}</p>
          <button type="button" class="btn primary" id="kachel-install-trial" :disabled="busy || !browser.usb" @click="trial">
            {{ busy ? t("editor.kachel_install.trial.busy") : t("editor.kachel_install.trial.start") }}</button>
          <p v-if="trialError" class="hint warn" data-trial="error">{{ trialError }}</p>
          <template v-if="result">
            <p :class="['hint', result.ok ? '' : 'warn']" :data-trial="result.ok ? 'match' : 'mismatch'">
              {{ result.ok ? t("editor.kachel_install.trial.match") : t("editor.kachel_install.trial.mismatch") }}</p>
            <table class="install-table">
              <thead><tr><th></th><th>{{ t("editor.kachel_install.trial.name") }}</th><th>{{ t("editor.kachel_install.trial.want") }}</th><th>{{ t("editor.kachel_install.trial.got") }}</th></tr></thead>
              <tbody><tr v-for="row in result.rows" :key="row.what + row.name" :data-row="row.name">
                <td>{{ row.ok ? "✓" : "✗" }}</td><td>{{ row.name }}</td><td>{{ row.want }}</td><td>{{ row.got }}</td></tr></tbody>
            </table>
          </template>
          <div v-if="(trialError || result) && profile.leave_mode?.length" class="hint" data-trial="leave">
            <b>{{ t("editor.kachel_install.leave") }}</b>
            <span v-for="(step, i) in profile.leave_mode" :key="i"> {{ say(step.text, lang()) }}</span>
          </div>
          <details v-if="log.length"><summary>{{ t("editor.kachel_install.trial.log") }}</summary><pre>{{ log.join("\n") }}</pre></details>
        </div>

        <div class="set-card" data-install="write">
          <h4>{{ t("editor.kachel_install.write.title") }}</h4>
          <p class="hint">{{ t("editor.kachel_install.write.later") }}</p>
        </div>
      </template>
    </template>
  </section>
</template>

<style scoped>
.kachel-install { display: grid; gap: 14px; max-width: 900px; padding: 20px; }
.install-steps { display: grid; gap: 10px; padding-left: 18px; }
.install-steps img { display: block; max-width: 260px; margin-top: 6px; border-radius: 8px; }
.install-table { border-collapse: collapse; margin-top: 8px; }
.install-table th, .install-table td { padding: 4px 10px; text-align: left; border-bottom: 1px solid var(--line); }
pre { max-height: 240px; overflow: auto; font-size: 11px; }
</style>
