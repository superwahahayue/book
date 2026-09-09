<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, errMsg } from '@/api/client'

const props = defineProps({
  novelId: { type: [String, Number], required: true },
  chapterId: { type: [String, Number], required: true },
  comicId: { type: [String, Number], default: null },
})

const router = useRouter()
const chapter = ref(null)
const comic = ref(null)
const loading = ref(true)
const creating = ref(false)
const retryingPanelId = ref(null)
const error = ref('')
const actionMsg = ref('')
let pollTimer = null

const form = reactive({
  visual_style: '彩色日系动画分镜，角色表情鲜明，电影感光影',
  // Empty values intentionally let COMIC_DEFAULT_* on the server decide.
  image_model: '',
  aspect_ratio: '',
  quality: '',
})

const pendingStatuses = new Set(['queued', 'pending', 'processing', 'storyboarding', 'rendering', 'generating', 'running'])
const readyStatuses = new Set(['ready', 'completed', 'complete', 'success', 'done'])
const failedStatuses = new Set(['failed', 'error', 'partial', 'cancelled', 'canceled'])

const comicStatus = computed(() => String(comic.value?.status || '').toLowerCase())
const isPending = computed(() => comic.value && pendingStatuses.has(comicStatus.value))
const isReady = computed(() => comic.value && readyStatuses.has(comicStatus.value))
const isFailed = computed(() => comic.value && failedStatuses.has(comicStatus.value))
const comicError = computed(() => comic.value?.error || comic.value?.last_error || '')
const panels = computed(() => (comic.value?.panels || []).slice().sort((left, right) => panelNumber(left) - panelNumber(right)))
const completedPanelCount = computed(() => panels.value.filter((panel) => readyStatuses.has(String(panel.status || '').toLowerCase()) && panel.image_url).length)

function isTerminal(status) {
  const value = String(status || '').toLowerCase()
  return readyStatuses.has(value) || failedStatuses.has(value)
}

function statusText(status) {
  const value = String(status || '').toLowerCase()
  if (readyStatuses.has(value)) return '漫画已完成'
  if (value === 'partial') return '部分分镜生成失败'
  if (failedStatuses.has(value)) return '漫画生成未完成'
  if (value === 'storyboarding') return '正在拆分漫画分镜…'
  if (value === 'rendering' || value === 'generating') return '正在绘制分镜…'
  if (value === 'queued') return '等待开始生成…'
  return '正在处理中…'
}

function panelStatusText(panel) {
  const value = String(panel.status || '').toLowerCase()
  if (readyStatuses.has(value) && panel.image_url) return '已绘制'
  if (failedStatuses.has(value)) return '绘制失败'
  if (value === 'rendering' || value === 'generating') return '绘制中'
  if (value === 'queued') return '等待绘制'
  return '准备中'
}

function panelScene(panel) {
  return panel.scene_description || panel.storyboard || panel.description || panel.narration || '分镜说明生成后会显示在这里。'
}

function panelDialogue(panel) {
  return panel.dialogue || panel.caption || panel.text || ''
}

function panelNarration(panel) {
  return panel.narration || ''
}

function panelNumber(panel, fallback = '') {
  return panel.panel_index ?? panel.index ?? panel.order ?? fallback
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadComic(id = comic.value?.id) {
  if (!id) return
  try {
    comic.value = await api.getComic(id)
    if (isTerminal(comic.value.status)) stopPolling()
  } catch (e) {
    error.value = errMsg(e, '加载漫画进度失败')
    stopPolling()
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => loadComic(), 2000)
}

async function loadChapter() {
  try {
    chapter.value = await api.getChapter(props.chapterId)
  } catch (e) {
    error.value = errMsg(e, '加载章节失败')
  }
}

function saveComicToUrl(nextComic) {
  if (!nextComic?.id) return
  router.replace({
    name: 'comic',
    params: { novelId: props.novelId, chapterId: props.chapterId },
    query: { comic: nextComic.id },
  })
}

async function createComic() {
  error.value = ''
  actionMsg.value = ''
  creating.value = true
  stopPolling()
  try {
    comic.value = await api.createComic(props.novelId, {
      chapter_id: Number(props.chapterId),
      visual_style: form.visual_style.trim() || null,
      image_model: form.image_model.trim() || null,
      aspect_ratio: form.aspect_ratio,
      quality: form.quality,
    })
    saveComicToUrl(comic.value)
    actionMsg.value = '已创建漫画任务，分镜与图片会陆续显示。'
    await loadComic(comic.value.id)
    if (!isTerminal(comic.value?.status)) startPolling()
  } catch (e) {
    error.value = errMsg(e, '创建漫画任务失败')
  } finally {
    creating.value = false
  }
}

async function retryPanel(panel) {
  error.value = ''
  actionMsg.value = ''
  retryingPanelId.value = panel.id
  try {
    await api.retryComicPanel(panel.id)
    actionMsg.value = `已重新提交第 ${panelNumber(panel)} 格。`
    await loadComic()
    startPolling()
  } catch (e) {
    error.value = errMsg(e, '重试分镜失败')
  } finally {
    retryingPanelId.value = null
  }
}

function goBack() {
  router.push(`/novels/${props.novelId}`)
}

watch(() => props.comicId, async (id) => {
  if (id && String(id) !== String(comic.value?.id || '')) {
    await loadComic(id)
    if (!isTerminal(comic.value?.status)) startPolling()
  }
})

onMounted(async () => {
  await Promise.all([loadChapter(), props.comicId ? loadComic(props.comicId) : Promise.resolve()])
  loading.value = false
  if (comic.value && !isTerminal(comic.value.status)) startPolling()
})
onUnmounted(stopPolling)
</script>

<template>
  <div class="container comic-page">
    <div class="page-head row between row-wrap gap-md">
      <div>
        <button type="button" class="back-link" @click="goBack">← 返回小说</button>
        <h1 class="hero-title"><span class="spark">▦</span> 章节漫画</h1>
        <p class="page-lead">{{ chapter?.title || `章节 #${chapterId}` }} · 先生成分镜，再逐格绘制插图。</p>
      </div>
      <button type="button" class="btn btn-ghost" @click="goBack">回到阅读</button>
    </div>

    <div v-if="loading" class="card card-pad"><div class="skeleton sk-title" /><div class="skeleton sk-line" /></div>
    <div v-else>
      <div v-if="error" class="alert err">{{ error }}</div>
      <div v-if="actionMsg" class="alert ok">{{ actionMsg }}</div>

      <section class="card card-pad comic-options">
        <div class="row between row-wrap gap-sm">
          <div>
            <h2>绘制设置</h2>
            <p class="muted">默认会生成 4–8 格彩色横向分镜。图像生成可能需要几分钟。</p>
          </div>
          <span v-if="comic" class="badge" :class="{ gen: isPending, ok: isReady }">{{ statusText(comic.status) }}</span>
        </div>
        <div class="field">
          <label class="field-label">画面风格</label>
          <textarea v-model="form.visual_style" class="textarea" rows="2" :disabled="creating || isPending" placeholder="例如：水墨国风、彩色日系动画、黑白漫画线稿…" />
        </div>
        <div class="field-grid">
          <div class="field">
            <label class="field-label">图像模型</label>
            <input v-model="form.image_model" class="input" :disabled="creating || isPending" placeholder="留空使用服务器默认模型" />
          </div>
          <div class="field">
            <label class="field-label">画幅</label>
            <select v-model="form.aspect_ratio" class="select" :disabled="creating || isPending">
              <option value="">使用服务器默认</option>
              <option value="16:9">16:9 横向</option>
              <option value="9:16">9:16 纵向</option>
              <option value="1:1">1:1 方形</option>
              <option value="4:3">4:3</option>
              <option value="3:4">3:4</option>
            </select>
          </div>
        </div>
        <div class="field">
            <label class="field-label">质量</label>
            <select v-model="form.quality" class="select" :disabled="creating || isPending">
              <option value="">使用服务器默认</option>
              <option value="standard">标准</option>
            <option value="hd">高质量</option>
          </select>
        </div>
        <button type="button" class="btn btn-primary" :disabled="creating || isPending" @click="createComic">
          {{ creating ? '正在创建任务…' : comic && !isFailed ? '重新生成本章漫画' : '生成本章漫画' }}
        </button>
      </section>

      <section v-if="comic" class="comic-result" aria-live="polite">
        <div class="comic-result__head row between row-wrap gap-md">
          <div>
            <p class="comic-result__eyebrow">COMIC STORYBOARD</p>
            <h2>{{ isPending ? statusText(comic.status) : statusText(comic.status) }}</h2>
            <p class="muted">已完成 {{ completedPanelCount }} / {{ panels.length }} 格。图片会安全地通过你的登录会话加载。</p>
          </div>
          <span v-if="isPending" class="row gap-sm muted"><span class="spinner" /> 请保持此页面打开，进度会自动刷新。</span>
        </div>
        <div v-if="comicError || isFailed" class="alert err">{{ comicError || '部分分镜没有完成。你可以重试失败的单格。' }}</div>

        <div v-if="!panels.length && isPending" class="card card-pad comic-waiting">
          <span class="spinner" /> 正在根据章节内容编排分镜…
        </div>
        <div v-else-if="!panels.length" class="card card-pad comic-waiting">暂时还没有可显示的分镜。</div>
        <div v-else class="comic-grid">
          <article v-for="(panel, index) in panels" :key="panel.id" class="comic-panel card">
            <div class="comic-panel__media">
              <img v-if="panel.image_url" :src="panel.image_url" :alt="`第 ${panelNumber(panel, index + 1)} 格漫画`" />
              <div v-else class="comic-panel__placeholder">
                <span v-if="!isTerminal(panel.status)" class="spinner" />
                <span v-else>暂未生成图片</span>
              </div>
            </div>
            <div class="comic-panel__body">
              <div class="row between gap-sm">
                <h3>第 {{ panelNumber(panel, index + 1) }} 格</h3>
                <span class="badge" :class="{ gen: !isTerminal(panel.status), ok: readyStatuses.has(String(panel.status || '').toLowerCase()) }">{{ panelStatusText(panel) }}</span>
              </div>
              <p>{{ panelScene(panel) }}</p>
              <p v-if="panelNarration(panel)" class="comic-panel__narration">{{ panelNarration(panel) }}</p>
              <p v-if="panelDialogue(panel)" class="comic-panel__dialogue">{{ panelDialogue(panel) }}</p>
              <p v-if="panel.error" class="comic-panel__error">{{ panel.error }}</p>
              <button
                v-if="failedStatuses.has(String(panel.status || '').toLowerCase())"
                type="button"
                class="btn btn-ghost btn-sm"
                :disabled="retryingPanelId === panel.id"
                @click="retryPanel(panel)"
              >
                {{ retryingPanelId === panel.id ? '正在重试…' : '重试这一格' }}
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>
