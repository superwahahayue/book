<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const progress = ref(0)

function onScroll() {
  const h = document.documentElement
  const scrollable = h.scrollHeight - h.clientHeight
  progress.value = scrollable > 0 ? (h.scrollTop / scrollable) * 100 : 0
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
})
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <div class="reading-progress" :style="{ width: progress + '%' }"></div>
</template>

<style scoped>
.reading-progress {
  position: fixed; top: 0; left: 0; z-index: 60;
  height: 3px; background: var(--grad-main);
  box-shadow: 0 0 8px rgba(83, 109, 120, 0.3);
  transition: width .1s linear;
}
</style>
