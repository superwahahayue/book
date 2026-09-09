<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { api, errMsg } from '@/api/client'
import StatusBadge from '@/components/StatusBadge.vue'

const router = useRouter()
const novels = ref([])
const loading = ref(true)
const error = ref('')
let timer = null

async function load() {
  try {
    novels.value = await api.listNovels()
    error.value = ''
  } catch (e) {
    error.value = errMsg(e, '加载书库失败')
  } finally {
    loading.value = false
  }
}

function scheduleRefresh() {
  timer = setInterval(() => {
    if (novels.value.some((n) => n.is_generating)) load()
  }, 5000)
}

function open(id) {
  router.push(`/novels/${id}`)
}

function fmtDate(s) {
  const d = new Date(s)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

onMounted(() => {
  load()
  scheduleRefresh()
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="container">
    <div class="page-head row between row-wrap gap-md">
      <div>
        <h1 class="hero-title"><span class="spark">✨</span> 我的创作库</h1>
        <p class="page-lead">像 galgame 一样导演每一条分支剧情</p>
      </div>
      <div class="row row-wrap gap-sm">
        <RouterLink to="/import" class="btn btn-ghost">⇧ 导入小说</RouterLink>
        <RouterLink to="/create" class="btn btn-primary">＋ 开启新故事</RouterLink>
      </div>
    </div>

    <div v-if="loading" class="book-grid">
      <div v-for="i in 3" :key="i" class="card card-pad">
        <div class="skeleton sk-title" />
        <div class="skeleton sk-line" style="width: 40%" />
        <div class="skeleton sk-line" style="width: 75%; margin-top: 1rem" />
      </div>
    </div>

    <div v-else-if="error" class="alert err">{{ error }}</div>

    <div v-else-if="novels.length === 0" class="card">
      <div class="empty-state">
        <span class="emoji">🌸</span>
        <p>还没有故事哦，去创造第一个世界吧</p>
        <div class="row row-wrap gap-sm mt-md">
          <RouterLink to="/import" class="btn btn-ghost">导入已有小说</RouterLink>
          <RouterLink to="/create" class="btn btn-primary">开始创作</RouterLink>
        </div>
      </div>
    </div>

    <div v-else class="book-grid">
      <article
        v-for="(n, i) in novels"
        :key="n.id"
        v-reveal="i * 50"
        class="book-card card"
        @click="open(n.id)"
      >
        <div class="book-spine" />
        <div class="book-body">
          <span class="sparkle">♡</span>
          <h3>{{ n.title }}</h3>
          <div class="meta">
            <span v-if="n.genre">{{ n.genre }}</span>
            <span>{{ n.chapter_count }} 节点</span>
            <span>{{ n.character_count }} 角色</span>
          </div>
          <div class="row gap-sm mt-sm">
            <StatusBadge :generating="n.is_generating" />
            <span class="muted">{{ fmtDate(n.updated_at) }}</span>
          </div>
          <p v-if="n.last_error" class="muted" style="color: var(--err); margin-top: 0.4rem; font-size: 0.78rem">
            {{ n.last_error }}
          </p>
        </div>
      </article>
    </div>
  </div>
</template>
