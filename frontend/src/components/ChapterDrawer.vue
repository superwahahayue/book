<script setup>
const props = defineProps({
  open: Boolean,
  chapters: { type: Array, default: () => [] },
  activeIndex: { type: Number, default: 0 },
})
const emit = defineEmits(['close', 'jump'])
</script>

<template>
  <teleport to="body">
    <transition name="backdrop">
      <div v-if="open" class="drawer-backdrop" @click="emit('close')"></div>
    </transition>
    <transition name="drawer">
      <aside v-if="open" class="drawer">
        <header class="drawer-head">
          <h3>目录</h3>
          <span class="muted text-sm">{{ chapters.length }} 章</span>
          <button class="icon-btn" @click="emit('close')" title="关闭">✕</button>
        </header>
        <nav class="toc">
          <button
            v-for="ch in chapters"
            :key="ch.id"
            class="toc-item"
            :class="{ active: ch.index === activeIndex }"
            @click="emit('jump', ch.index)"
          >
            <span class="toc-num">{{ String(ch.index).padStart(2, '0') }}</span>
            <span class="toc-title">{{ ch.title || `第${ch.index}章` }}</span>
          </button>
          <p v-if="chapters.length === 0" class="muted text-sm" style="padding:1rem">暂无章节</p>
        </nav>
      </aside>
    </transition>
  </teleport>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed; inset: 0; z-index: 70;
  background: rgba(30, 24, 16, .45); backdrop-filter: blur(2px);
}
.drawer {
  position: fixed; top: 0; right: 0; z-index: 71;
  width: min(340px, 85vw); height: 100%;
  background: var(--surface-solid);
  border-left: 1px solid var(--line);
  box-shadow: var(--shadow-lg);
  display: flex; flex-direction: column;
}
.drawer-head {
  display: flex; align-items: center; gap: .7rem;
  padding: 1.1rem 1.3rem; border-bottom: 1px solid var(--line);
}
.drawer-head h3 { margin: 0; font-size: 1.15rem; }
.drawer-head .icon-btn { margin-left: auto; }
.toc { overflow-y: auto; padding: .6rem; flex: 1; }
.toc-item {
  display: flex; align-items: baseline; gap: .7rem; width: 100%;
  padding: .65rem .8rem; margin-bottom: .15rem;
  background: transparent; border: none; border-radius: 8px;
  cursor: pointer; text-align: left;
  color: var(--ink-soft); font-family: var(--font-sans); font-size: .92rem;
  transition: background .15s, color .15s, padding-left .18s var(--ease-out);
}
.toc-item:hover { background: rgba(83, 109, 120, 0.08); color: var(--ink); padding-left: 1.1rem; }
.toc-item.active { background: rgba(83, 109, 120, 0.12); color: var(--purple-deep); font-weight: 600; }
.toc-num {
  font-family: var(--font-serif); font-size: .8rem;
  color: var(--pink-deep); opacity: .8; flex-shrink: 0; min-width: 1.6em;
}
.toc-item.active .toc-num { opacity: 1; }
.toc-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
