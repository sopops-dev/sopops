<script setup lang="ts">
import { useData, withBase } from "vitepress";
const { page } = useData();
</script>

<template>
  <p v-if="page.relativePath !== '404.md'" class="agent-links">
    <a :href="withBase('/' + page.relativePath)">Read as Markdown</a>
    <span aria-hidden="true"> · </span>
    <a :href="withBase('/llms.txt')">Agent index</a>
  </p>
</template>

<style scoped>
.agent-links { margin: 0 0 1rem; font-size: 0.875rem; color: var(--vp-c-text-2); }
.agent-links a { text-decoration: underline; text-underline-offset: 3px; }
</style>
