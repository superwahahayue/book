<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errMsg } from '@/api/client'
import StatusBadge from '@/components/StatusBadge.vue'
import StoryTree from '@/components/story/StoryTree.vue'
import CharacterPanel from '@/components/cast/CharacterPanel.vue'
import RelationEditor from '@/components/cast/RelationEditor.vue'

const props = defineProps({ id: { type: [String, Number], required: true } })
const router = useRouter()
const novel = ref(null)
const tree = ref([])
const providers = ref([])
const loading = ref(true)
const loadError = ref('')
const sideTab = ref('director')
const activeId = ref(null)
const directive = ref('')
const options = ref([])
const optionsLoading = ref(false)
const actionMsg = ref('')
const actionErr = ref('')
const isTreeOpen = ref(false)
const isComposerOpen = ref(false)
const settings = reactive({ provider: '', model: '', title: '', genre: '', style: '', premise: '', world_setting: '', outline: '' })
let timer = null

const chaptersById = computed(() => Object.fromEntries((novel.value?.chapters || []).map((chapter) => [chapter.id, chapter])))
const activeChapter = computed(() => activeId.value == null ? null : chaptersById.value[activeId.value] || null)
const hasRoot = computed(() => (novel.value?.chapters || []).some((chapter) => chapter.parent_id == null))
const paragraphs = computed(() => (activeChapter.value?.content || '').split('\n').map((line) => line.trim()).filter(Boolean))
const activePath = computed(() => {
  const path = []
  let current = activeChapter.value
  while (current) {
    path.push(current)
    current = current.parent_id == null ? null : chaptersById.value[current.parent_id]
  }
  return path.reverse()
})
const activePathIds = computed(() => activePath.value.map((chapter) => chapter.id))
const primaryNextChapter = computed(() => {
  if (!activeChapter.value) return null
  return (novel.value?.chapters || [])
    .filter((chapter) => chapter.parent_id === activeChapter.value.id)
    .sort((left, right) => Number(right.is_primary) - Number(left.is_primary) || left.index - right.index || left.id - right.id)
    .find((chapter) => chapter.is_primary) || null
})
const activeIsOnPrimaryPath = computed(() => activePath.value.every((chapter) => chapter.parent_id == null || chapter.is_primary))
const chapterLocation = computed(() => {
  if (!activeChapter.value) return ''
  if (activeChapter.value.parent_id == null) return '开篇 · 第 1 章'
  if (activeIsOnPrimaryPath.value) return `主线 · 第 ${activePath.value.length} 章`
  const branchStart = activePath.value.findIndex((chapter) => chapter.parent_id != null && !chapter.is_primary)
  return `分支剧情 · 从第 ${branchStart} 章岔开`
})
const composerMode = computed(() => {
  if (!hasRoot.value) return 'opening'
  if (!activeChapter.value) return 'select'
  return primaryNextChapter.value ? 'branch' : 'continue'
})

function pickDefaultNode(data) {
  const chapters = data.chapters || []
  const byParent = new Map()
  for (const chapter of chapters) {
    const siblings = byParent.get(chapter.parent_id) || []
    siblings.push(chapter)
    byParent.set(chapter.parent_id, siblings)
  }
  let current = (byParent.get(null) || []).sort((left, right) => left.index - right.index || left.id - right.id)[0]
  while (current) {
    const next = (byParent.get(current.id) || [])
      .sort((left, right) => Number(right.is_primary) - Number(left.is_primary) || left.index - right.index || left.id - right.id)
      .find((chapter) => chapter.is_primary)
    if (!next) break
    current = next
  }
  return current?.id || (chapters.length ? chapters[chapters.length - 1].id : null)
}

async function load(initial = false) {
  try {
    const [data, chapterTree] = await Promise.all([api.getNovel(props.id), api.chapterTree(props.id)])
    novel.value = data
    tree.value = chapterTree
    if (initial) {
      Object.assign(settings, {
        provider: data.provider || '', model: data.model || '', title: data.title, genre: data.genre,
        style: data.style, premise: data.premise, world_setting: data.world_setting || data.settings || '', outline: data.outline || '',
      })
      activeId.value = pickDefaultNode(data)
    } else if (activeId.value == null || !chaptersById.value[activeId.value]) {
      activeId.value = pickDefaultNode(data)
    }
    loadError.value = ''
  } catch (error) {
    loadError.value = errMsg(error, '加载故事失败')
  } finally {
    loading.value = false
  }
}

async function loadProviders() {
  try { providers.value = await api.listProviders() } catch { /* The setting panel can still be used later. */ }
}

function selectNode(id) {
  activeId.value = id
  actionMsg.value = ''
  actionErr.value = ''
  isTreeOpen.value = false
}

function applyOption(option) { directive.value = option }

function openComic() {
  if (!activeChapter.value) return
  router.push({
    name: 'comic',
    params: { novelId: props.id, chapterId: activeChapter.value.id },
  })
}

async function suggest() {
  optionsLoading.value = true
  actionErr.value = ''
  try {
    const response = await api.suggestOptions(props.id, { node_id: activeId.value })
    options.value = response.options || []
  } catch (error) {
    actionErr.value = errMsg(error, '获取剧情建议失败')
  } finally {
    optionsLoading.value = false
  }
}

async function generate() {
  const plotDirective = directive.value.trim()
  if (!plotDirective) {
    actionErr.value = '请先写下下一步剧情。'
    return
  }
  if (hasRoot.value && activeId.value == null) {
    actionErr.value = '请先从剧情树中选择一个章节，再生成分支。'
    return
  }
  actionErr.value = ''
  actionMsg.value = ''
  try {
    await api.generateChapter(props.id, { parent_id: hasRoot.value ? activeId.value : null, plot_directive: plotDirective })
    actionMsg.value = '正在生成章节，完成后会自动刷新。'
    if (novel.value) novel.value.is_generating = true
    isComposerOpen.value = false
  } catch (error) {
    actionErr.value = errMsg(error, '启动生成失败')
  }
}

async function regenerate() {
  if (!activeChapter.value) return
  const plotDirective = directive.value.trim() || activeChapter.value.plot_directive
  if (!plotDirective) {
    actionErr.value = '请先填写用于重生成的剧情。'
    return
  }
  if (!confirm('重生成会覆盖当前章节正文，确定继续吗？')) return
  try {
    await api.regenerateChapter(activeChapter.value.id, { plot_directive: plotDirective })
    actionMsg.value = '正在重生成章节，完成后会自动刷新。'
    if (novel.value) novel.value.is_generating = true
  } catch (error) {
    actionErr.value = errMsg(error, '重生成失败')
  }
}

async function toggleEnding() {
  if (!activeChapter.value) return
  try {
    await api.updateChapter(activeChapter.value.id, { is_ending: !activeChapter.value.is_ending })
    await load()
  } catch (error) {
    actionErr.value = errMsg(error, '更新章节失败')
  }
}

async function deleteNode() {
  if (!activeChapter.value || !confirm('删除本章节及所有后续分支？此操作无法撤销。')) return
  try {
    await api.deleteChapter(activeChapter.value.id)
    activeId.value = null
    await load()
  } catch (error) {
    actionErr.value = errMsg(error, '删除章节失败')
  }
}

async function setPrimary() {
  if (!activeChapter.value || activeChapter.value.parent_id == null || activeChapter.value.is_primary) return
  try {
    await api.setPrimaryChapter(activeChapter.value.id)
    actionMsg.value = '已将此章节设为默认下一章。'
    await load()
  } catch (error) {
    actionErr.value = errMsg(error, '设置主线失败')
  }
}

async function saveSettings() {
  try {
    await api.updateNovel(props.id, { ...settings, provider: settings.provider || null, model: settings.model.trim() || null })
    actionMsg.value = '故事设定已保存。'
    await load()
  } catch (error) {
    actionErr.value = errMsg(error, '保存设定失败')
  }
}

async function removeNovel() {
  if (!confirm('确定删除整部小说吗？')) return
  try {
    await api.deleteNovel(props.id)
    router.push('/')
  } catch (error) {
    actionErr.value = errMsg(error, '删除小说失败')
  }
}

onMounted(async () => {
  await Promise.all([load(true), loadProviders()])
  timer = setInterval(() => { if (novel.value?.is_generating) load() }, 4000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div v-if="loading" class="container loading-page">
    <div class="skeleton sk-title" />
    <div class="skeleton sk-line" />
  </div>
  <div v-else-if="loadError" class="container"><div class="alert err">{{ loadError }}</div></div>

  <div v-else class="novel-shell">
    <header class="novel-toolbar container">
      <div class="novel-toolbar__identity">
        <button type="button" class="back-link" @click="router.push('/')">← 书库</button>
        <h1>{{ novel.title }}</h1>
        <div class="novel-toolbar__meta">
          <StatusBadge :generating="novel.is_generating" />
          <span v-if="novel.genre" class="badge">{{ novel.genre }}</span>
          <span>{{ novel.chapter_count }} 个章节 · {{ novel.character_count }} 位角色</span>
        </div>
      </div>
      <div class="novel-toolbar__actions">
        <button type="button" class="btn btn-ghost btn-sm" @click="isTreeOpen = true">章节目录</button>
        <button type="button" class="btn btn-primary btn-sm" @click="isComposerOpen = true">续写故事</button>
        <button type="button" class="btn btn-danger btn-sm desktop-only" @click="removeNovel">删除</button>
      </div>
    </header>

    <div v-if="novel.is_generating" class="container generation-notice"><span class="spinner" /> AI 正在写作，完成后将自动更新。</div>
    <div v-if="novel.last_error" class="container alert err">上次生成失败：{{ novel.last_error }}</div>
    <div v-if="actionErr" class="container alert err">{{ actionErr }}</div>
    <div v-if="actionMsg" class="container alert ok">{{ actionMsg }}</div>

    <div class="story-workspace container">
      <aside class="tree-pane" :class="{ 'is-open': isTreeOpen }">
        <div class="pane-heading">
          <div><span class="pane-kicker">STORY MAP</span><h2>章节目录</h2></div>
          <button type="button" class="pane-close mobile-only" aria-label="关闭目录" @click="isTreeOpen = false">×</button>
        </div>
        <StoryTree :nodes="tree" :active-id="activeId" :active-path-ids="activePathIds" @select="selectNode" />
      </aside>

      <section class="reading-surface" aria-live="polite">
        <template v-if="activeChapter">
          <header class="reading-surface__header">
            <div>
              <p class="reading-eyebrow">{{ activeChapter.is_ending ? '故事结局' : chapterLocation }}</p>
              <h2>{{ activeChapter.title || `章节 #${activeChapter.id}` }}</h2>
            </div>
            <div class="chapter-actions">
              <button v-if="primaryNextChapter" type="button" class="text-button" @click="selectNode(primaryNextChapter.id)">阅读下一章 →</button>
              <button type="button" class="text-button" @click="openComic">生成本章漫画</button>
              <button v-if="activeChapter.parent_id != null && !activeChapter.is_primary" type="button" class="text-button" @click="setPrimary">设为主线下一章</button>
              <button type="button" class="text-button" @click="toggleEnding">{{ activeChapter.is_ending ? '取消结局' : '标为结局' }}</button>
              <button type="button" class="text-button text-button--danger" @click="deleteNode">删除</button>
            </div>
          </header>
          <nav v-if="activePath.length > 1" class="chapter-breadcrumb" aria-label="当前章节路径"><button v-for="chapter in activePath" :key="chapter.id" type="button" :class="{ active: chapter.id === activeChapter.id }" @click="selectNode(chapter.id)">{{ chapter.title || `第 ${chapter.index} 章` }}</button></nav>
          <div v-if="activeChapter.plot_directive" class="chapter-prompt"><span>本章指令</span>{{ activeChapter.plot_directive }}</div>
          <article class="novel-reader">
            <p v-for="(paragraph, index) in paragraphs" :key="index">{{ paragraph }}</p>
            <p v-if="!paragraphs.length" class="novel-reader__empty">这章还没有正文。</p>
          </article>
        </template>
        <div v-else class="reading-empty">
          <span>✦</span>
          <h2>从一个场景开始</h2>
          <p>在右侧写下开篇画面，生成故事的第一章。</p>
          <button type="button" class="btn btn-primary" @click="isComposerOpen = true">开始创作</button>
        </div>
      </section>

      <aside class="composer-pane" :class="{ 'is-open': isComposerOpen }">
        <div class="pane-heading composer-pane__heading">
          <div><span class="pane-kicker">CREATE</span><h2>创作面板</h2></div>
          <button type="button" class="pane-close mobile-only" aria-label="关闭创作面板" @click="isComposerOpen = false">×</button>
        </div>
        <div class="composer-tabs" role="tablist" aria-label="创作工具">
          <button type="button" :class="{ active: sideTab === 'director' }" @click="sideTab = 'director'">续写</button>
          <button type="button" :class="{ active: sideTab === 'cast' }" @click="sideTab = 'cast'">角色</button>
          <button type="button" :class="{ active: sideTab === 'relation' }" @click="sideTab = 'relation'">关系</button>
          <button type="button" :class="{ active: sideTab === 'settings' }" @click="sideTab = 'settings'">设定</button>
        </div>

        <section v-show="sideTab === 'director'" class="composer-section">
          <p class="composer-hint">{{ composerMode === 'opening' ? '写下开篇场景，生成故事的第一章。' : composerMode === 'branch' ? '当前章节已有默认下一章；本次生成会创建一条新的分支。' : composerMode === 'continue' ? '当前章节尚无下一章；本次生成会续写主线。' : '请先从章节目录中选择一个章节。' }}</p>
          <div class="field"><label class="field-label" for="plot-directive">下一步剧情</label><textarea id="plot-directive" v-model="directive" class="textarea composer-textarea" rows="7" placeholder="例如：雨夜的天台上，她终于鼓起勇气告白，却被意外来访的人打断。" /></div>
          <div class="composer-actions">
            <button type="button" class="btn btn-primary btn-block" :disabled="novel.is_generating || composerMode === 'select'" @click="generate">{{ composerMode === 'opening' ? '生成开篇' : composerMode === 'branch' ? '创建新分支' : '续写主线' }}</button>
            <button v-if="activeChapter" type="button" class="btn btn-ghost btn-block" :disabled="novel.is_generating" @click="regenerate">重生成当前章节</button>
            <button type="button" class="text-button" :disabled="optionsLoading || novel.is_generating" @click="suggest">{{ optionsLoading ? '正在构思…' : '让 AI 提供三个方向' }}</button>
          </div>
          <div v-if="options.length" class="story-options"><p>选择一个方向填入剧情</p><button v-for="(option, index) in options" :key="index" type="button" :class="{ selected: directive === option }" @click="applyOption(option)">{{ option }}</button></div>
        </section>

        <section v-show="sideTab === 'cast'" class="composer-section"><CharacterPanel :novel-id="id" :characters="novel.characters" @changed="load()" /></section>
        <section v-show="sideTab === 'relation'" class="composer-section"><RelationEditor :novel-id="id" :characters="novel.characters" :relations="novel.relations" @changed="load()" /></section>
        <section v-show="sideTab === 'settings'" class="composer-section settings-form">
          <div class="field"><label class="field-label">标题</label><input v-model="settings.title" class="input" /></div>
          <div class="field-grid"><div class="field"><label class="field-label">题材</label><input v-model="settings.genre" class="input" /></div><div class="field"><label class="field-label">文风</label><input v-model="settings.style" class="input" /></div></div>
          <div class="field"><label class="field-label">故事简介</label><textarea v-model="settings.premise" class="textarea" rows="3" /></div>
          <div class="field"><label class="field-label">世界设定</label><textarea v-model="settings.world_setting" class="textarea" rows="4" /></div>
          <div class="field"><label class="field-label">大纲</label><textarea v-model="settings.outline" class="textarea" rows="3" /></div>
          <div class="field"><label class="field-label">模型提供商</label><select v-model="settings.provider" class="select"><option v-for="provider in providers" :key="provider.name" :value="provider.name" :disabled="!provider.available">{{ provider.label }}</option></select></div>
          <div class="field"><label class="field-label">模型</label><input v-model="settings.model" class="input" list="settings-provider-models" placeholder="使用默认模型" /><datalist id="settings-provider-models"><option v-for="model in providers.find((provider) => provider.name === settings.provider)?.models || []" :key="model" :value="model" /></datalist></div>
          <button type="button" class="btn btn-primary btn-block" @click="saveSettings">保存设定</button>
        </section>
      </aside>
    </div>

    <div v-if="isTreeOpen || isComposerOpen" class="workspace-backdrop" @click="isTreeOpen = false; isComposerOpen = false" />
    <nav class="mobile-story-nav mobile-only" aria-label="移动端故事操作"><button type="button" @click="isTreeOpen = true">目录</button><button type="button" class="mobile-story-nav__primary" @click="isComposerOpen = true">{{ primaryNextChapter ? '新建分支' : '续写主线' }}</button><button type="button" @click="sideTab = 'cast'; isComposerOpen = true">角色</button></nav>
  </div>
</template>
