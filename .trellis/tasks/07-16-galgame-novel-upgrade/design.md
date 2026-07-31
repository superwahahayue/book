# Design: Galgame-style Novel Upgrade

## Architecture

```
Vue SPA (粉紫二次元 UI)
  ├─ Library / Create / Novel Workspace
  │    ├─ Reading panel (current node)
  │    ├─ Story tree panel
  │    ├─ Character & relation editor
  │    └─ Director dock (directive + AI options + generate)
  └─ axios → /api/*

FastAPI
  ├─ /api/*  JSON (novels, characters, relations, chapters/tree, generate)
  ├─ Static: frontend/dist (SPA)
  └─ Services: novel / character / generation (no scheduler)
SQLite
  novels | characters | relations | chapters (tree)
```

## Data Model

### `novels`（演进）

| 字段 | 说明 |
|------|------|
| 保留 | id, title, genre, premise, style, outline, provider, model, is_generating, last_error, created_at, updated_at |
| 新增/重命名 | `world_setting` Text（由旧 `settings` 迁移） |
| 废弃逻辑 | `auto_continue`, `interval_minutes`, `running_summary`（列可保留不读，或迁移后忽略） |

### `characters`（新）

- id, novel_id (FK CASCADE)
- name, alias, role_title（身份）, personality, appearance, background, speech_style, notes
- sort_order int, created_at

### `relations`（新）

- id, novel_id
- from_character_id, to_character_id
- relation_type (短标签), description
- UNIQUE 可选 (from, to, type) 或允许重复由用户管理

### `chapters`（演进为树）

| 字段 | 说明 |
|------|------|
| 保留 | id, novel_id, title, content, summary, created_at |
| 新增 | `parent_id` NULLABLE FK self, `plot_directive` Text, `is_ending` bool default false |
| 调整 | `index` 改为可选展示序（同父下排序）或废弃；列表 API 返回树而非扁平 index 序 |

**树不变量**

- 根：`parent_id IS NULL`（一部小说允许多根？**MVP：仅一个根**；旁支必须挂在某节点下）
- 删除节点：级联删除子树，或禁止删非叶（推荐：**删节点级联子树 + 前端二次确认**）

### 旧数据迁移

1. `settings` → `world_setting`（列拷贝）
2. 章节按 `novel_id, index` 排序：第一章 `parent_id=null`，其后 `parent_id=prev.id`
3. `plot_directive` 空；`is_ending=false`
4. `auto_continue` 全部视为 false

实现：`app/db.py` 在 `init_db` 后调用 `migrate_schema()`（PRAGMA table_info + ALTER + backfill）。

## API（草案）

### Novels
- `GET/POST /api/novels`
- `GET/PATCH/DELETE /api/novels/{id}` — Detail 含 characters, relations, chapter_tree 或分接口
- 去掉对 auto_continue 调度的副作用

### Characters
- `GET/POST /api/novels/{id}/characters`
- `PATCH/DELETE /api/characters/{id}`

### Relations
- `GET/POST /api/novels/{id}/relations`
- `PATCH/DELETE /api/relations/{id}`

### Chapters / Director
- `GET /api/novels/{id}/chapters/tree` — 嵌套或邻接表 + 前端建树
- `GET /api/chapters/{id}` — 单节点 + 路径面包屑
- `POST /api/novels/{id}/chapters/generate`  
  body: `{ parent_id: number | null, plot_directive: string, as_root?: bool }`  
  → 202 + 后台生成子节点（或根）
- `POST /api/novels/{id}/chapters/suggest-options`  
  body: `{ node_id: number }` → AI 返回 2–4 条短剧情选项（同步或短超时）
- `POST /api/chapters/{id}/regenerate`  
  body: `{ plot_directive: string }` → 覆盖正文（busy 锁）
- `PATCH /api/chapters/{id}` — title, is_ending, content 手改（可选 MVP：至少 is_ending + title）
- `DELETE /api/chapters/{id}` — 级联子树

废弃：`POST .../continue` 无指令续写；scheduler 同步 API。

## Generation Flow

```
generate(parent_id, directive):
  lock novel
  load novel + characters + relations
  path = root..parent (if parent)
  prompt = build(settings, chars, rels, path summaries, parent tail, directive)
  raw = provider.generate
  parse title/body → summary
  insert chapter(parent_id, directive, ...)
  unlock
```

**Suggest options**：轻量 prompt，基于路径与角色，要求 JSON/分行输出 2–4 条「下一步剧情」短句。

**Bootstrap**：创建小说 **不再**自动生成大纲+第1章；可选单独接口 `POST .../generate` 且 `parent_id=null` 生成根。Outline 字段可保留为用户可编辑的「总大纲」或弱化。

## Frontend Structure

```
frontend/src/
  styles/theme.css          # 粉紫设计 token + 动效
  views/
    LibraryView.vue
    CreateView.vue          # 分步：基本信息 → 初始角色(可选) → 完成
    NovelView.vue           # 工作台布局
  components/
    story/StoryTree.vue
    story/DirectorDock.vue
    story/ChapterReader.vue
    cast/CharacterPanel.vue
    cast/RelationEditor.vue
    ui/*                    # 按钮、卡片、Modal、Toast
```

**Novel 工作台布局（桌面）**

- 左：剧情树
- 中：当前章节阅读
- 右/底：导演台 + Tab（角色 | 关系 | 设定 | 模型）

**动效**：页面 enter fade-up、卡片 hover lift、生成中 pulse/进度条、树节点展开 spring、按钮 tap scale。可用纯 CSS + 少量 transition；不必上重型动画库（可选 `@vueuse/motion` 若需要）。

## Serving SPA

`main.py`：

1. mount `/api`
2. mount `/assets` from `frontend/dist/assets`
3. catch-all `GET /{path}` → `index.html`（排除 `/api`）
4. 移除 Jinja `web_router` 或改为重定向

开发：Vite `:5173` proxy `/api` 不变。

## Scheduler Removal

- `lifespan` 不再 `scheduler.start/shutdown`
- 删除或掏空 `app/scheduler.py` 调用点
- UI/ schema 去掉 auto_continue 控件

## Trade-offs

| 点 | 选择 | 原因 |
|----|------|------|
| 无 Alembic | 启动时迁移 | 项目小、单文件 SQLite |
| 创建不自动写第1章 | 手动导演 | 符合自由导演 |
| 重生成覆盖 | 确认后覆盖 | 避免 silent 丢文；旁支走新建 |
| 单根 | MVP 简单 | 多根可用「假根」以后再加 |
| 纯 CSS 动效 | 少依赖 | 够用且好控 |

## Rollback

- DB 迁移向前兼容列；若失败保留旧列读取逻辑一版
- Git 回退前端与 API；SQLite 建议升级前备份 `data/novels.db`
