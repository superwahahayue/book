<script setup>
defineProps({
  generating: { type: Boolean, default: false },
  ending: { type: Boolean, default: false },
  text: { type: String, default: '' },
})
</script>

<template>
  <span v-if="generating" class="badge gen">生成中…</span>
  <span v-else-if="ending" class="badge end">结局</span>
  <span v-else-if="text" class="badge">{{ text }}</span>
</template>
