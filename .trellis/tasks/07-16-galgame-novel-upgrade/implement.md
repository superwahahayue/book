# Implement Checklist: Galgame-style Novel Upgrade

## Phase order

### 1. Schema & migration
- [x] 扩展 `models.py`：Character, Relation；Chapter 树字段；Novel.world_setting
- [x] `migrate_schema()`：ALTER + 线性章节 backfill parent_id + settings 拷贝
- [x] 本地用现有 `data/novels.db` 或拷贝库验证迁移

### 2. Schemas & API
- [x] Pydantic：角色/关系/树节点/生成请求
- [x] routes：characters, relations, chapters tree/generate/suggest/regenerate
- [x] 调整 NovelDetail；移除 continue/auto_continue 行为
- [x] 停用 scheduler 接入（main lifespan）

### 3. Generation & prompts
- [x] 重写 prompt：角色块、关系块、路径摘要、plot_directive
- [x] `generate_child` / `generate_root` / `regenerate_node` / `suggest_options`
- [x] 去掉无指令 `try_continue` 定时路径；创建不再强制 bootstrap（或改为可选）

### 4. Vue API client
- [x] `frontend/src/api/client.js` 对齐新接口

### 5. UI theme
- [x] 设计 token（粉紫糖果）+ 深色变体
- [x] 全局布局、按钮、卡片、动效工具类

### 6. Views
- [x] LibraryView 换皮
- [x] CreateView：设定 + 可选初始角色；不自动黑箱长生成（或显式「生成开篇」）
- [x] NovelView 工作台：树 + 阅读 + 导演台 + 角色关系

### 7. SPA serving & Jinja teardown
- [x] FastAPI 托管 `frontend/dist` + SPA fallback
- [x] 移除/旁路 Jinja 页面路由
- [x] README 更新：dev（两端）/ prod（build + uvicorn）

### 8. Validation
- [x] API smoke：建角色与关系
- [x] 迁移旧库可打开（novel 2 树链验证）
- [ ] 端到端生成（需本地模型/API）
- [x] `python` 导入 app + TestClient

## Validation commands

```bash
# backend
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# frontend dev
cd frontend && npm install && npm run dev

# frontend prod assets
cd frontend && npm run build
```

## Risky files

- `app/models.py`, `app/db.py` — 数据损坏风险；先备份 DB
- `app/services/generation.py`, `app/prompts.py` — 生成行为全变
- `app/main.py` — 路由与静态资源
- `frontend/src/views/NovelView.vue` — 最大 UI 面

## Rollback points

- 迁移函数写幂等；失败不删旧列
- 功能开关不必做；用 git revert

## Done when

满足 `prd.md` Acceptance Criteria 全部勾选。
