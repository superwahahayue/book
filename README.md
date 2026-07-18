# 剧情导演 · 小说生成器

用本地大模型（Ollama）或线上 API，以 **galgame 式自由导演** 创作带分支的中文故事：可编辑角色卡与人物关系，手写下一步剧情指令，AI 执笔生成树状章节。

## 功能

- 📚 多部剧本库
- 👤 结构化角色资料 + 人物关系网
- 🌳 真分支剧情树：任意节点可开旁支 / 标记结局
- 🎬 导演台：手写剧情指令优先，可选 AI 辅助选项
- 🧠 Ollama / OpenAI 兼容 / Anthropic 可切换
- ✨ 粉紫糖果二次元 UI（Vue 3）

> 本版已移除定时自动续写，章节仅由导演台手动生成。

## 前置条件

1. **Python 3.10+**
2. **Node.js 18+**（前端构建 / 开发）
3. **本地模型（可选）:** [Ollama](https://ollama.com) + `ollama pull gemma4:12b`
4. **线上模型（可选）:** OpenAI 兼容或 Anthropic API Key

## 安装

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

cd frontend
npm install
cd ..
```

## 配置

```bash
cp .env.example .env
```

| 变量 | 说明 |
|------|------|
| `DEFAULT_PROVIDER` | `ollama` / `openai` / `anthropic` |
| `OLLAMA_HOST` / `OLLAMA_DEFAULT_MODEL` | 本地 Ollama |
| `OPENAI_*` / `ANTHROPIC_*` | 线上 API |
| `CHAPTER_TARGET_CHARS` | 每节点目标字数（默认 2000） |

## 运行

### 开发（推荐）

终端 1 — API：

```bash
uvicorn app.main:app --reload --port 8000
```

终端 2 — Vue：

```bash
cd frontend
npm run dev
```

浏览器打开 Vite 提示的地址（默认 http://localhost:5173 ）。

### 生产（单端口）

```bash
cd frontend
npm run build
cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 — FastAPI 托管 `frontend/dist` SPA。

## 使用流程

1. **新建故事**：填写世界观 → 可选初始角色 → 选择模型  
2. **角色 / 关系**：在工作台维护人物卡与关系  
3. **导演开篇**：手写剧情指令 → 生成根节点  
4. **分叉续写**：选中节点 → 写指令（或 AI 选项）→ 生成子节点  
5. **结局**：将叶节点标为结局；可随时从历史节点开旁支  

## 数据

SQLite 默认 `./data/novels.db`。启动时自动迁移：

- 旧 `settings` → `world_setting`
- 旧线性章节按顺序链成单路径树

建议升级前备份数据库。

## 项目结构

```
app/
  main.py           # API + SPA 托管
  models.py         # Novel / Character / Relation / Chapter(树)
  prompts.py        # 导演模式 prompt
  services/         # CRUD + 生成
  api/routes.py     # JSON API
frontend/           # Vue 3 SPA
```

## API 摘要

- `GET/POST /api/novels`
- `GET/POST /api/novels/{id}/characters` · `PATCH/DELETE /api/characters/{id}`
- `GET/POST /api/novels/{id}/relations` · `PATCH/DELETE /api/relations/{id}`
- `GET /api/novels/{id}/chapters/tree`
- `POST /api/novels/{id}/chapters/generate` · `suggest-options`
- `POST /api/chapters/{id}/regenerate` · `PATCH/DELETE /api/chapters/{id}`
