<script setup>
defineProps({
  node: { type: Object, required: true },
  activeId: { type: [Number, null], default: null },
  depth: { type: Number, default: 0 },
})
defineEmits(['select'])
</script>

<template>
  <div class="story-node" :class="{ 'story-node--root': depth === 0 }">
    <button
      type="button"
      class="story-node__button"
      :class="{ 'is-active': activeId === node.id }"
      :aria-current="activeId === node.id ? 'page' : undefined"
      @click="$emit('select', node.id)"
    >
      <span class="story-node__marker" aria-hidden="true" />
      <span class="story-node__content">
        <span class="story-node__title">{{ node.title || `章节 #${node.id}` }}</span>
        <span v-if="node.plot_directive" class="story-node__summary">{{ node.plot_directive }}</span>
      </span>
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
        :depth="depth + 1"
        @select="$emit('select', $event)"
      />
    </div>
  </div>
</template>

<script>
export default { name: 'StoryTreeNode' }
</script>
