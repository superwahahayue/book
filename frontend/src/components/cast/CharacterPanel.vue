<script setup>
import { reactive, ref } from 'vue'
import { api, errMsg } from '@/api/client'

const props = defineProps({
  novelId: { type: [Number, String], required: true },
  characters: { type: Array, default: () => [] },
})
const emit = defineEmits(['changed'])

const editing = ref(null)
const form = reactive({
  name: '',
  alias: '',
  role_title: '',
  personality: '',
  appearance: '',
  background: '',
  speech_style: '',
  notes: '',
})
const msg = ref('')
const err = ref('')
const saving = ref(false)

function blank() {
  Object.assign(form, {
    name: '',
    alias: '',
    role_title: '',
    personality: '',
    appearance: '',
    background: '',
    speech_style: '',
    notes: '',
  })
}

function startCreate() {
  editing.value = 'new'
  blank()
  msg.value = ''
  err.value = ''
}

function startEdit(c) {
  editing.value = c.id
  Object.assign(form, {
    name: c.name,
    alias: c.alias,
    role_title: c.role_title,
    personality: c.personality,
    appearance: c.appearance,
    background: c.background,
    speech_style: c.speech_style,
    notes: c.notes,
  })
  msg.value = ''
  err.value = ''
}

function cancel() {
  editing.value = null
}

async function save() {
  if (!form.name.trim()) {
    err.value = '姓名必填'
    return
  }
  saving.value = true
  err.value = ''
  try {
    const payload = { ...form, name: form.name.trim() }
    if (editing.value === 'new') {
      await api.createCharacter(props.novelId, payload)
    } else {
      await api.updateCharacter(editing.value, payload)
    }
    msg.value = '已保存'
    editing.value = null
    emit('changed')
  } catch (e) {
    err.value = errMsg(e, '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(c) {
  if (!confirm(`删除角色「${c.name}」及其相关关系？`)) return
  try {
    await api.deleteCharacter(c.id)
    emit('changed')
  } catch (e) {
    err.value = errMsg(e, '删除失败')
  }
}
</script>

<template>
  <div>
    <div class="row between mb-0" style="margin-bottom: 0.65rem">
      <span class="muted">{{ characters.length }} 位角色</span>
      <button type="button" class="btn btn-primary btn-sm" @click="startCreate">＋ 角色</button>
    </div>
    <div v-if="err" class="alert err">{{ err }}</div>
    <div v-if="msg" class="alert ok">{{ msg }}</div>

    <div v-if="editing !== null" class="char-card" style="border-color: var(--purple)">
      <h4>{{ editing === 'new' ? '新角色' : '编辑角色' }}</h4>
      <div class="field">
        <label class="field-label">姓名<span class="req">*</span></label>
        <input v-model="form.name" class="input" />
      </div>
      <div class="field-grid">
        <div class="field">
          <label class="field-label">别名</label>
          <input v-model="form.alias" class="input" />
        </div>
        <div class="field">
          <label class="field-label">身份</label>
          <input v-model="form.role_title" class="input" />
        </div>
      </div>
      <div class="field">
        <label class="field-label">性格</label>
        <textarea v-model="form.personality" class="textarea" rows="2" />
      </div>
      <div class="field">
        <label class="field-label">外貌</label>
        <input v-model="form.appearance" class="input" />
      </div>
      <div class="field">
        <label class="field-label">背景</label>
        <textarea v-model="form.background" class="textarea" rows="2" />
      </div>
      <div class="field">
        <label class="field-label">说话风格</label>
        <input v-model="form.speech_style" class="input" />
      </div>
      <div class="field">
        <label class="field-label">备注</label>
        <input v-model="form.notes" class="input" />
      </div>
      <div class="row gap-sm">
        <button type="button" class="btn btn-primary btn-sm" :disabled="saving" @click="save">
          保存
        </button>
        <button type="button" class="btn btn-ghost btn-sm" @click="cancel">取消</button>
      </div>
    </div>

    <div v-for="c in characters" :key="c.id" class="char-card">
      <div class="row between">
        <div>
          <h4>{{ c.name }} <span v-if="c.alias" class="muted">（{{ c.alias }}）</span></h4>
          <div class="sub">{{ c.role_title || '未设身份' }}</div>
        </div>
        <div class="row gap-sm">
          <button type="button" class="btn btn-ghost btn-sm" @click="startEdit(c)">编辑</button>
          <button type="button" class="btn btn-danger btn-sm" @click="remove(c)">删</button>
        </div>
      </div>
      <p v-if="c.personality" class="muted" style="margin: 0.4rem 0 0; font-size: 0.82rem">
        {{ c.personality }}
      </p>
    </div>
    <p v-if="!characters.length && editing === null" class="muted">还没有角色，点右上角添加～</p>
  </div>
</template>
