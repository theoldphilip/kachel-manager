<script setup lang="ts">
// The mark of the home key, one em square unless the caller sizes it: the sidebar's brand button, and the home key
// wherever the editor shows it. Inside another <svg> (the mockup's top bar) it takes x, y, width and height like any
// nested svg.
// Kachel Manager: the Kachel mark (four tiles, the top left one filled in teal, as src/kachel/KachelMark.vue and the
// tablets' start picture), not Tessera's mosaic: no Kachel device draws Tessera's mark (Philip, 2026-11-20).
</script>

<template>
  <svg class="tessera-mark kachel-home-mark" viewBox="0 0 100 100" width="1em" height="1em" aria-hidden="true">
    <rect x="2" y="2" width="44" height="44" rx="11" fill="#2BB3A3" />
    <g fill="none" stroke="#5f6a70" stroke-width="6">
      <rect x="56.5" y="4.5" width="39" height="39" rx="9" />
      <rect x="4.5" y="56.5" width="39" height="39" rx="9" />
      <rect x="56.5" y="56.5" width="39" height="39" rx="9" />
    </g>
  </svg>
</template>
