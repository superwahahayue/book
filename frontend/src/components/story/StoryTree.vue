<script setup>
import StoryTreeNode from './StoryTreeNode.vue'

defineProps({
  nodes: { type: Array, default: () => [] },
  activeId: { type: [Number, null], default: null },
})
defineEmits(['select'])
</script>

<template>
  <nav class="story-tree" aria-label="剧情章节">
    <p v-if="!nodes.length" class="story-tree__empty">尚无章节。从右侧写下开篇指令，开始你的故事。</p>
    <StoryTreeNode
      v-for="node in nodes"
      :key="node.id"
      :node="node"
      :active-id="activeId"
      :depth="0"
      @select="$emit('select', $event)"
    />
  </nav>
</template>
