<script setup>
import TopBar from '@/components/TopBar.vue'
</script>

<template>
  <TopBar />
  <main>
    <router-view v-slot="{ Component }">
      <transition name="route" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  </main>
</template>
