<script setup>
import { computed } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  activeId: { type: [Number, null], default: null },
  activePathIds: { type: Array, default: () => [] },
  depth: { type: Number, default: 0 },
  isInBranch: { type: Boolean, default: false },
})
defineEmits(['select'])

const isBranch = computed(() => props.depth > 0 && (props.isInBranch || !props.node.is_primary))
const routeLabel = computed(() => {
  if (props.depth === 0) return '开篇'
  if (isBranch.value) return props.node.is_primary ? '分支续写' : '分支'
  return `主线 · 第 ${props.depth + 1} 章`
})
</script>

<template>
  <div class="story-node" :class="{ 'story-node--root': depth === 0, 'is-primary': node.is_primary, 'is-active-path': activePathIds.includes(node.id) }">
    <button
      type="button"
      class="story-node__button"
      :class="{ 'is-active': activeId === node.id }"
      :aria-current="activeId === node.id ? 'page' : undefined"
      @click="$emit('select', node.id)"
    >
      <span class="story-node__marker" aria-hidden="true" />
      <span class="story-node__content">
        <span class="story-node__route">{{ routeLabel }}</span>
        <span class="story-node__title">{{ node.title || `章节 #${node.id}` }}</span>
        <span v-if="node.plot_directive" class="story-node__summary">{{ node.plot_directive }}</span>
      </span>
      <span v-if="node.is_primary && depth > 0" class="story-node__primary">下一章</span>
      <span v-if="node.is_ending" class="story-node__ending">结局</span>
    </button>
    <div
      v-if="node.children?.length"
      class="story-node__children"
      :class="{ 'story-node__children--flat': depth >= 1 }"
    >
      <StoryTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :active-id="activeId"
        :active-path-ids="activePathIds"
        :depth="depth + 1"
        :is-in-branch="isBranch"
        @select="$emit('select', $event)"
      />
    </div>
  </div>
</template>

<script>
export default { name: 'StoryTreeNode' }
</script>
