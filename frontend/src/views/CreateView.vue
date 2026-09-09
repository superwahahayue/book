<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, errMsg } from '@/api/client'

const router = useRouter()
const providers = ref([])
const submitting = ref(false)
const error = ref('')
const step = ref(1)
const styleReferences = ref([])
const selectedStyleReferenceId = ref('')
const styleFile = ref(null)
const styleFileInput = ref(null)
const styleUploadTitle = ref('')
const styleConsent = ref(false)
const styleUploadStatus = ref(null)
const styleUploading = ref(false)
let stylePollTimer = null

const form = reactive({
  title: '',
  genre: '',
  style: '',
  premise: '',
  world_setting: '',
  outline: '',
  provider: '',
  model: '',
})

const seeds = ref([])

const stylePendingStatuses = new Set(['queued', 'pending', 'processing', 'analyzing', 'running'])
const styleReadyStatuses = new Set(['ready', 'completed', 'complete', 'success', 'done'])
const styleFailedStatuses = new Set(['failed', 'error', 'cancelled', 'canceled'])
const styleStatusValue = computed(() => String(styleUploadStatus.value?.status || '').toLowerCase())
const styleAnalysisPending = computed(() => styleUploadStatus.value && stylePendingStatuses.has(styleStatusValue.value))
const styleBusy = computed(() => styleUploading.value || styleAnalysisPending.value)
const readyStyleReferences = computed(() => styleReferences.value.filter((item) => styleReadyStatuses.has(String(item.status || '').toLowerCase())))
const selectedStyleReference = computed(() => styleReferences.value.find((item) => String(item.id) === String(selectedStyleReferenceId.value)) || null)

const emptyChar = () => ({
  name: '',
  alias: '',
  role_title: '',
  personality: '',
  appearance: '',
  background: '',
  speech_style: '',
  notes: '',
})

const modelPlaceholder = computed(() => {
  const p = providers.value.find((x) => x.name === form.provider)
  return p ? `默认: ${p.default_model}` : '默认'
})

function stopStylePolling() {
  if (stylePollTimer) {
    clearInterval(stylePollTimer)
    stylePollTimer = null
  }
}

function isStyleReady(status) {
  return styleReadyStatuses.has(String(status || '').toLowerCase())
}

function isStyleFailed(status) {
  return styleFailedStatuses.has(String(status || '').toLowerCase())
}

function styleStatusText(status) {
  const value = String(status || '').toLowerCase()
  if (isStyleReady(value)) return '文风分析完成'
  if (isStyleFailed(value)) return '文风分析失败'
  if (value === 'queued') return '等待开始分析…'
  return '正在提炼文风特征…'
}

function profilePreview(reference) {
  const profile = reference?.style_profile
  if (!profile) return ''
  const text = typeof profile === 'string' ? profile : JSON.stringify(profile)
  return text.length > 260 ? `${text.slice(0, 260)}…` : text
}

async function loadProviders() {
  try {
    providers.value = await api.listProviders()
    const firstAvail = providers.value.find((p) => p.available) || providers.value[0]
    if (firstAvail) form.provider = firstAvail.name
  } catch (e) {
    error.value = errMsg(e, '加载提供方失败')
  }
}

async function loadStyleReferences({ quiet = false } = {}) {
  try {
    styleReferences.value = await api.listStyleReferences()
    if (styleUploadStatus.value?.id) {
      const current = styleReferences.value.find((item) => item.id === styleUploadStatus.value.id)
      if (current) {
        styleUploadStatus.value = current
        if (isStyleReady(current.status)) selectedStyleReferenceId.value = current.id
        if (isStyleReady(current.status) || isStyleFailed(current.status)) stopStylePolling()
      }
    }
  } catch (e) {
    if (!quiet) error.value = errMsg(e, '加载文风参考失败')
  }
}

function startStylePolling() {
  stopStylePolling()
  stylePollTimer = setInterval(() => loadStyleReferences({ quiet: true }), 2000)
}

function onStyleFileChange(event) {
  styleFile.value = event.target.files?.[0] || null
  error.value = ''
}

function upsertStyleReference(reference) {
  const index = styleReferences.value.findIndex((item) => item.id === reference.id)
  if (index >= 0) styleReferences.value.splice(index, 1, reference)
  else styleReferences.value.unshift(reference)
}

async function uploadStyleReference() {
  if (!styleFile.value) {
    error.value = '请选择要作为文风参考的 TXT、Markdown 或 DOCX 文件。'
    return
  }
  if (!styleConsent.value) {
    error.value = '请先确认你有权将这份文本用于创作参考。'
    return
  }
  error.value = ''
  styleUploading.value = true
  stopStylePolling()
  try {
    const reference = await api.createStyleReference(styleFile.value, {
      title: styleUploadTitle.value.trim(),
      consent: styleConsent.value,
    })
    styleUploadStatus.value = reference
    upsertStyleReference(reference)
    if (isStyleReady(reference.status)) selectedStyleReferenceId.value = reference.id
    else if (!isStyleFailed(reference.status)) startStylePolling()
  } catch (e) {
    error.value = errMsg(e, '上传文风参考失败')
  } finally {
    styleUploading.value = false
  }
}

async function deleteSelectedStyleReference() {
  const reference = selectedStyleReference.value
  if (!reference || styleBusy.value) return
  if (!window.confirm(`删除“${reference.title || reference.original_filename}”的保存原文与文风档案？`)) return
  error.value = ''
  try {
    await api.deleteSourceDocument(reference.id)
    styleReferences.value = styleReferences.value.filter((item) => item.id !== reference.id)
    selectedStyleReferenceId.value = ''
    if (styleUploadStatus.value?.id === reference.id) styleUploadStatus.value = null
  } catch (e) {
    error.value = errMsg(e, '删除文风参考失败')
  }
}

onMounted(async () => {
  await Promise.all([loadProviders(), loadStyleReferences()])
})
onUnmounted(stopStylePolling)

function addChar() {
  seeds.value.push(emptyChar())
}
function removeChar(i) {
  seeds.value.splice(i, 1)
}

async function submit() {
  if (!form.title.trim()) {
    error.value = '请填写标题'
    step.value = 1
    return
  }
  error.value = ''
  submitting.value = true
  const characters = seeds.value
    .filter((c) => c.name.trim())
    .map((c) => ({ ...c, name: c.name.trim() }))
  const payload = {
    title: form.title.trim(),
    genre: form.genre,
    style: form.style,
    premise: form.premise,
    world_setting: form.world_setting,
    outline: form.outline,
    provider: form.provider || null,
    model: form.model.trim() || null,
    style_reference_id: selectedStyleReferenceId.value || null,
    characters,
  }
  try {
    const novel = await api.createNovel(payload)
    router.push(`/novels/${novel.id}`)
  } catch (e) {
    error.value = errMsg(e, '创建失败')
    submitting.value = false
  }
}
</script>

<template>
  <div class="container" style="max-width: 720px">
    <div class="page-head">
      <h1 class="hero-title"><span class="spark">🎛</span> 新建故事</h1>
      <p class="page-lead">先搭好世界与角色，再在导演台写下开篇——不再黑箱自动灌文。</p>
    </div>

    <div class="tabs">
      <button type="button" class="tab" :class="{ active: step === 1 }" @click="step = 1">1 · 世界</button>
      <button type="button" class="tab" :class="{ active: step === 2 }" @click="step = 2">2 · 角色</button>
      <button type="button" class="tab" :class="{ active: step === 3 }" @click="step = 3">3 · 模型</button>
    </div>

    <div v-if="error" class="alert err">{{ error }}</div>

    <div class="card card-pad">
      <!-- step 1 -->
      <div v-show="step === 1">
        <div class="field">
          <label class="field-label">标题<span class="req">*</span></label>
          <input v-model="form.title" class="input" maxlength="255" placeholder="例如：星屑恋语" />
        </div>
        <div class="field-grid">
          <div class="field">
            <label class="field-label">题材</label>
            <input v-model="form.genre" class="input" placeholder="恋爱、奇幻、校园…" />
          </div>
          <div class="field">
            <label class="field-label">文风</label>
            <input v-model="form.style" class="input" placeholder="细腻、轻喜、热血…" />
          </div>
        </div>
        <section class="style-reference-card" aria-labelledby="style-reference-title">
          <div class="style-reference-card__head">
            <div>
              <p class="style-reference-card__eyebrow">可选 · 文风参考</p>
              <h3 id="style-reference-title">从已授权文本提炼创作特征</h3>
            </div>
            <span class="badge">仅高层特征</span>
          </div>
          <p class="muted">系统会参考叙事视角、节奏、对话与意象等高层特征，帮助你创作新的原创故事，不会直接复刻原文。</p>
          <div class="field mb-0">
            <label class="field-label">选择已分析完成的参考文本</label>
            <select v-model="selectedStyleReferenceId" class="select">
              <option value="">不使用文风参考</option>
              <option v-for="reference in readyStyleReferences" :key="reference.id" :value="reference.id">
                {{ reference.title || reference.original_filename || `参考文本 #${reference.id}` }}
              </option>
            </select>
          </div>
          <div v-if="selectedStyleReference" class="style-reference-card__selected">
            <p v-if="selectedStyleReference.style_profile" class="style-profile-preview">{{ profilePreview(selectedStyleReference) }}</p>
            <button type="button" class="text-button" :disabled="styleBusy" @click="deleteSelectedStyleReference">删除这份参考</button>
          </div>

          <details class="style-reference-card__upload">
            <summary>上传新的参考文本</summary>
            <div class="field-grid mt-md">
              <div class="field">
                <label class="field-label" for="style-file">参考文件</label>
                <input
                  id="style-file"
                  ref="styleFileInput"
                  class="file-input"
                  type="file"
                  accept=".txt,.md,.markdown,.docx,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  :disabled="styleBusy"
                  @change="onStyleFileChange"
                />
              </div>
              <div class="field">
                <label class="field-label">参考名称（可选）</label>
                <input v-model="styleUploadTitle" class="input" placeholder="例如：古风叙事参考" :disabled="styleBusy" />
              </div>
            </div>
            <label class="checkbox-row">
              <input v-model="styleConsent" type="checkbox" :disabled="styleBusy" />
              <span>我确认有权使用这份文本作为创作参考。</span>
            </label>
            <button type="button" class="btn btn-ghost mt-md" :disabled="styleBusy" @click="uploadStyleReference">
              {{ styleUploading ? '正在上传…' : styleAnalysisPending ? '正在分析…' : '上传并分析文风' }}
            </button>
          </details>

          <div v-if="styleUploadStatus" class="style-upload-status" aria-live="polite">
            <span class="badge" :class="{ gen: styleAnalysisPending, ok: isStyleReady(styleUploadStatus.status) }">{{ styleStatusText(styleUploadStatus.status) }}</span>
            <span v-if="styleAnalysisPending" class="row gap-sm muted"><span class="spinner" /> 分析完成后会自动加入上方列表。</span>
            <span v-if="styleUploadStatus.error || isStyleFailed(styleUploadStatus.status)" class="style-upload-status__error">{{ styleUploadStatus.error || '请检查文件内容或模型配置后重试。' }}</span>
          </div>
        </section>
        <div class="field">
          <label class="field-label">故事简介</label>
          <textarea v-model="form.premise" class="textarea" rows="3" placeholder="一句话抓住核心冲突" />
        </div>
        <div class="field">
          <label class="field-label">世界观设定</label>
          <textarea
            v-model="form.world_setting"
            class="textarea"
            rows="4"
            placeholder="时代、规则、地点、特殊设定…"
          />
        </div>
        <div class="field">
          <label class="field-label">总大纲（可选）</label>
          <textarea v-model="form.outline" class="textarea" rows="3" placeholder="整体走向备忘，不必死板" />
        </div>
        <div class="row between">
          <span class="muted">下一步可添加初始角色</span>
          <button type="button" class="btn btn-primary" @click="step = 2">下一步 →</button>
        </div>
      </div>

      <!-- step 2 -->
      <div v-show="step === 2">
        <p class="muted mb-0" style="margin-bottom: 0.75rem">
          可先跳过，进工作台再补。也可在此添加 1～几个核心角色。
        </p>
        <div v-for="(c, i) in seeds" :key="i" class="char-card">
          <div class="row between">
            <h4>角色 {{ i + 1 }}</h4>
            <button type="button" class="btn btn-ghost btn-sm" @click="removeChar(i)">移除</button>
          </div>
          <div class="field-grid">
            <div class="field">
              <label class="field-label">姓名<span class="req">*</span></label>
              <input v-model="c.name" class="input" placeholder="姓名" />
            </div>
            <div class="field">
              <label class="field-label">身份</label>
              <input v-model="c.role_title" class="input" placeholder="女主 / 青梅…" />
            </div>
          </div>
          <div class="field">
            <label class="field-label">性格</label>
            <textarea v-model="c.personality" class="textarea" rows="2" placeholder="性格特点" />
          </div>
          <div class="field">
            <label class="field-label">外貌</label>
            <input v-model="c.appearance" class="input" placeholder="外观简述" />
          </div>
          <div class="field">
            <label class="field-label">说话风格</label>
            <input v-model="c.speech_style" class="input" placeholder="毒舌 / 温柔 / 寡言…" />
          </div>
        </div>
        <button type="button" class="btn btn-ghost btn-block" @click="addChar">＋ 添加角色</button>
        <div class="row between mt-md">
          <button type="button" class="btn btn-ghost" @click="step = 1">← 上一步</button>
          <button type="button" class="btn btn-primary" @click="step = 3">下一步 →</button>
        </div>
      </div>

      <!-- step 3 -->
      <div v-show="step === 3">
        <div class="field-grid">
          <div class="field">
            <label class="field-label">模型提供方</label>
            <select v-model="form.provider" class="select">
              <option v-for="p in providers" :key="p.name" :value="p.name" :disabled="!p.available">
                {{ p.label }}{{ p.available ? '' : '（未配置）' }}
              </option>
            </select>
          </div>
          <div class="field">
            <label class="field-label">模型名</label>
            <input v-model="form.model" class="input" list="provider-models" :placeholder="modelPlaceholder" />
            <datalist id="provider-models">
              <option v-for="model in providers.find((p) => p.name === form.provider)?.models || []" :key="model" :value="model" />
            </datalist>
          </div>
        </div>
        <p class="muted">创建后进入导演台，手写开篇指令再生成第一节点。</p>
        <div class="row between mt-md">
          <button type="button" class="btn btn-ghost" @click="step = 2">← 上一步</button>
          <button type="button" class="btn btn-primary" :disabled="submitting" @click="submit">
            {{ submitting ? '创建中…' : '✨ 创建并进入导演台' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
