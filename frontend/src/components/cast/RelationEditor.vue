<script setup>
import { reactive, ref, computed } from 'vue'
import { api, errMsg } from '@/api/client'

const props = defineProps({
  novelId: { type: [Number, String], required: true },
  characters: { type: Array, default: () => [] },
  relations: { type: Array, default: () => [] },
})
const emit = defineEmits(['changed'])

const form = reactive({
  from_character_id: '',
  to_character_id: '',
  relation_type: '',
  description: '',
})
const err = ref('')
const saving = ref(false)

const nameOf = computed(() => {
  const m = {}
  for (const c of props.characters) m[c.id] = c.name
  return m
})

async function add() {
  if (!form.from_character_id || !form.to_character_id) {
    err.value = '请选择双方角色'
    return
  }
  if (form.from_character_id === form.to_character_id) {
    err.value = '不能与自己建立关系'
    return
  }
  saving.value = true
  err.value = ''
  try {
    await api.createRelation(props.novelId, {
      from_character_id: Number(form.from_character_id),
      to_character_id: Number(form.to_character_id),
      relation_type: form.relation_type,
      description: form.description,
    })
    form.relation_type = ''
    form.description = ''
    emit('changed')
  } catch (e) {
    err.value = errMsg(e, '添加失败')
  } finally {
    saving.value = false
  }
}

async function remove(r) {
  if (!confirm('删除这条关系？')) return
  try {
    await api.deleteRelation(r.id)
    emit('changed')
  } catch (e) {
    err.value = errMsg(e, '删除失败')
  }
}
</script>

<template>
  <div>
    <p v-if="characters.length < 2" class="muted">至少需要 2 个角色才能设置关系。</p>
    <template v-else>
      <div v-if="err" class="alert err">{{ err }}</div>
      <div class="field">
        <label class="field-label">从</label>
        <select v-model="form.from_character_id" class="select">
          <option value="">选择角色</option>
          <option v-for="c in characters" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </div>
      <div class="field">
        <label class="field-label">到</label>
        <select v-model="form.to_character_id" class="select">
          <option value="">选择角色</option>
          <option v-for="c in characters" :key="'t' + c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </div>
      <div class="field">
        <label class="field-label">关系类型</label>
        <input v-model="form.relation_type" class="input" placeholder="青梅竹马 / 对立 / 暗恋…" />
      </div>
      <div class="field">
        <label class="field-label">描述</label>
        <input v-model="form.description" class="input" placeholder="补充说明" />
      </div>
      <button type="button" class="btn btn-primary btn-sm btn-block" :disabled="saving" @click="add">
        添加关系
      </button>
    </template>

    <div class="mt-md">
      <div v-for="r in relations" :key="r.id" class="char-card">
        <div class="row between">
          <div style="font-size: 0.88rem">
            <strong>{{ nameOf[r.from_character_id] || '?' }}</strong>
            →
            <strong>{{ nameOf[r.to_character_id] || '?' }}</strong>
            <span class="badge" style="margin-left: 0.35rem">{{ r.relation_type || '关系' }}</span>
            <div v-if="r.description" class="sub" style="margin-top: 0.25rem">{{ r.description }}</div>
          </div>
          <button type="button" class="btn btn-danger btn-sm" @click="remove(r)">删</button>
        </div>
      </div>
      <p v-if="!relations.length" class="muted">暂无关系</p>
    </div>
  </div>
</template>
