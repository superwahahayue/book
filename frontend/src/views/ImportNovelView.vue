<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errMsg } from '@/api/client'

const router = useRouter()
const providers = ref([])
const file = ref(null)
const uploadInput = ref(null)
const uploading = ref(false)
const deletingSource = ref(false)
const error = ref('')
const importJob = ref(null)
let pollTimer = null

const form = reactive({
  title: '',
  genre: '',
  style: '',
  provider: '',
  model: '',
})

const pendingStatuses = new Set(['queued', 'pending', 'processing', 'importing', 'analyzing', 'running'])
const readyStatuses = new Set(['ready', 'completed', 'complete', 'success', 'done'])
const failedStatuses = new Set(['failed', 'error', 'cancelled', 'canceled'])

const normalizedStatus = computed(() => String(importJob.value?.status || '').toLowerCase())
const isPending = computed(() => importJob.value && pendingStatuses.has(normalizedStatus.value))
const isFailed = computed(() => importJob.value && failedStatuses.has(normalizedStatus.value))
const isReady = computed(() => importJob.value && readyStatuses.has(normalizedStatus.value))
const importedNovelId = computed(() => importJob.value?.novel_id || importJob.value?.result_novel_id || null)
const canOpenNovel = computed(() => Boolean(importedNovelId.value) && !isFailed.value)
const modelPlaceholder = computed(() => {
  const provider = providers.value.find((item) => item.name === form.provider)
  return provider ? `默认: ${provider.default_model}` : '使用默认模型'
})

function statusText(status) {
  const value = String(status || '').toLowerCase()
  if (readyStatuses.has(value)) return '导入完成'
  if (failedStatuses.has(value)) return '导入失败'
  if (value === 'analyzing') return '正在分析章节与故事脉络…'
  if (value === 'importing') return '正在建立章节目录…'
  if (value === 'queued') return '等待开始处理…'
  return '正在处理…'
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function refreshJob() {
  if (!importJob.value?.id) return
  try {
    const next = await api.getImport(importJob.value.id)
    importJob.value = { ...importJob.value, ...next }
    if (readyStatuses.has(String(next.status || '').toLowerCase()) || failedStatuses.has(String(next.status || '').toLowerCase())) {
      stopPolling()
    }
  } catch (e) {
    error.value = errMsg(e, '获取导入进度失败')
    stopPolling()
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(refreshJob, 2000)
}

function onFileChange(event) {
  file.value = event.target.files?.[0] || null
  error.value = ''
}

async function loadProviders() {
  try {
    providers.value = await api.listProviders()
    const firstAvailable = providers.value.find((provider) => provider.available)
    if (firstAvailable) form.provider = firstAvailable.name
  } catch (e) {
    error.value = errMsg(e, '加载模型提供方失败')
  }
}

async function submit() {
  if (!file.value) {
    error.value = '请选择要导入的 TXT、Markdown 或 DOCX 文件。'
    return
  }
  error.value = ''
  uploading.value = true
  stopPolling()
  try {
    importJob.value = await api.importNovel(file.value, {
      title: form.title.trim(),
      genre: form.genre.trim(),
      style: form.style.trim(),
      provider: form.provider || null,
      model: form.model.trim() || null,
    })
    if (!isReady.value && !isFailed.value) startPolling()
  } catch (e) {
    error.value = errMsg(e, '导入任务创建失败')
  } finally {
    uploading.value = false
  }
}

function openNovel() {
  if (importedNovelId.value) router.push(`/novels/${importedNovelId.value}`)
}

async function deleteImportedSource() {
  if (!importJob.value?.id || deletingSource.value) return
  if (!window.confirm('删除保存的原始导入文件？已建立的小说章节不会被删除。')) return
  deletingSource.value = true
  error.value = ''
  try {
    await api.deleteSourceDocument(importJob.value.id)
    importJob.value = null
  } catch (e) {
    error.value = errMsg(e, '删除原始导入文件失败')
  } finally {
    deletingSource.value = false
  }
}

onMounted(loadProviders)
onUnmounted(stopPolling)
</script>

<template>
  <div class="container import-page" style="max-width: 760px">
    <div class="page-head row between row-wrap gap-md">
      <div>
        <button type="button" class="back-link" @click="router.push('/')">← 返回书库</button>
        <h1 class="hero-title"><span class="spark">⇧</span> 导入已有小说</h1>
        <p class="page-lead">导入后会保留章节主线，你可以从最后一章继续创作或建立分支。</p>
      </div>
    </div>

    <div v-if="error" class="alert err">{{ error }}</div>

    <section class="card card-pad">
      <div class="field">
        <label class="field-label" for="novel-file">小说文件<span class="req">*</span></label>
        <input
          id="novel-file"
          ref="uploadInput"
          class="file-input"
          type="file"
          accept=".txt,.md,.markdown,.docx,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          :disabled="uploading || isPending"
          @change="onFileChange"
        />
        <span class="field-help">支持 TXT、Markdown、DOCX。系统会识别常见的“第…章”与 Markdown 章节标题。</span>
      </div>

      <div class="field-grid">
        <div class="field">
          <label class="field-label">导入后的标题（可选）</label>
          <input v-model="form.title" class="input" maxlength="255" placeholder="留空则使用文件名" :disabled="uploading || isPending" />
        </div>
        <div class="field">
          <label class="field-label">题材（可选）</label>
          <input v-model="form.genre" class="input" placeholder="奇幻、悬疑、校园…" :disabled="uploading || isPending" />
        </div>
      </div>
      <div class="field">
        <label class="field-label">续写文风提示（可选）</label>
        <input v-model="form.style" class="input" placeholder="如：克制、明快、诗性…" :disabled="uploading || isPending" />
      </div>

      <details class="import-options">
        <summary>高级选项：后续续写使用的模型</summary>
        <div class="field-grid mt-md">
          <div class="field">
            <label class="field-label">模型提供方</label>
            <select v-model="form.provider" class="select" :disabled="uploading || isPending">
              <option value="">使用服务器默认</option>
              <option v-for="provider in providers" :key="provider.name" :value="provider.name" :disabled="!provider.available">
                {{ provider.label }}{{ provider.available ? '' : '（未配置）' }}
              </option>
            </select>
          </div>
          <div class="field">
            <label class="field-label">模型名</label>
            <input v-model="form.model" class="input" list="import-provider-models" :placeholder="modelPlaceholder" :disabled="uploading || isPending" />
            <datalist id="import-provider-models">
              <option v-for="model in providers.find((provider) => provider.name === form.provider)?.models || []" :key="model" :value="model" />
            </datalist>
          </div>
        </div>
      </details>

      <button type="button" class="btn btn-primary" :disabled="uploading || isPending" @click="submit">
        {{ uploading ? '正在上传…' : isPending ? '正在导入…' : '导入并建立章节' }}
      </button>
    </section>

    <section v-if="importJob" class="card card-pad import-status" aria-live="polite">
      <div class="row between row-wrap gap-sm">
        <div>
          <p class="import-status__eyebrow">导入任务</p>
          <h2>{{ importJob.title || importJob.original_filename || file?.name || '小说文件' }}</h2>
        </div>
        <span class="badge" :class="{ ok: isReady, gen: isPending }">{{ statusText(importJob.status) }}</span>
      </div>
      <div v-if="isPending" class="row gap-sm muted"><span class="spinner" /> {{ statusText(importJob.status) }}</div>
      <p v-if="importJob.error || isFailed" class="alert err import-status__error">{{ importJob.error || '导入未能完成，请检查文件内容后重试。' }}</p>
      <div v-if="canOpenNovel" class="row row-wrap gap-sm mt-md">
        <button type="button" class="btn btn-primary" @click="openNovel">打开并继续创作</button>
        <button type="button" class="btn btn-ghost" :disabled="deletingSource" @click="deleteImportedSource">
          {{ deletingSource ? '正在删除…' : '删除保存的原始文件' }}
        </button>
        <span class="muted">已建立小说主线，可直接从最后一章续写。</span>
      </div>
    </section>
  </div>
</template>
