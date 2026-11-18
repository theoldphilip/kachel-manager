<script setup lang="ts">
// Kachel Manager: the Kachel mark, the one the tablets show while they start (echod's assets/kachel.png, and the
// add-on's icon, tools/kachel_logo.py): four tiles, the top left one filled in teal, the others outlined. The outlines
// take the text colour, so the mark reads in light and dark mode. One em square unless the caller sizes it. It stands
// in for Tessera's mark in the sidebar (Sidebar.vue); Tessera's stays where a screen draws it (the home key).
</script>

<template>
  <svg class="kachel-mark" viewBox="0 0 100 100" width="1em" height="1em" aria-hidden="true">
    <rect x="2" y="2" width="44" height="44" rx="11" fill="#2BB3A3" />
    <g fill="none" stroke="currentColor" stroke-width="5">
      <rect x="56.5" y="4.5" width="39" height="39" rx="9" />
      <rect x="4.5" y="56.5" width="39" height="39" rx="9" />
      <rect x="56.5" y="56.5" width="39" height="39" rx="9" />
    </g>
  </svg>
</template>
