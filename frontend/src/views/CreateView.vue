<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, errMsg } from '@/api/client'

const router = useRouter()
const providers = ref([])
const submitting = ref(false)
const error = ref('')
const step = ref(1)

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

onMounted(async () => {
  try {
    providers.value = await api.listProviders()
    const firstAvail = providers.value.find((p) => p.available) || providers.value[0]
    if (firstAvail) form.provider = firstAvail.name
  } catch (e) {
    error.value = errMsg(e, '加载提供方失败')
  }
})

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
