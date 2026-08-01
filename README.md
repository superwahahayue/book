# 剧情导演 · 小说生成器

使用本地大模型或线上 API，以自由导演的方式创作带分支的中文故事：维护角色卡与人物关系，手写下一步剧情指令，再由 AI 生成树状章节。

## 功能

- 多部剧本库、结构化角色资料与人物关系网
- 支持从任意章节开旁支、标记结局的剧情树
- 导演台：手写剧情指令优先，可选 AI 辅助选项
- Gemini 代理、Ollama、OpenAI 兼容服务与 Anthropic 可切换
- Vue 3 前端与 FastAPI JSON API

> 章节仅由导演台手动生成，不包含定时自动续写功能。

## 前置条件

1. Python 3.10+（推荐 Python 3.12）
2. Node.js 18+（前端开发或构建时需要）
3. 至少一种可用的模型服务：本地 [Ollama](https://ollama.com)、Gemini 兼容代理、OpenAI 兼容 API 或 Anthropic API

## 安装

在项目根目录执行。安装包含后端 Python 依赖和前端 Node.js 依赖。

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

cd frontend
npm ci
cd ..
```

### Windows Git Bash

Git Bash 使用 `/` 路径分隔符；不要使用 PowerShell 的 `.\` 或反斜杠路径写法。

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt

cd frontend
npm ci
cd ..
```

若不想激活虚拟环境，也可使用：

```bash
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

cd frontend
npm ci
cd ..
```

`npm ci` 会按仓库中的 `package-lock.json` 精确安装依赖；没有锁文件或正在更新依赖时可改用 `npm install`。

## 配置模型

先创建本地配置文件。`.env` 已在 Git 忽略列表中，**不要提交 API Key**。

PowerShell：

```powershell
Copy-Item .env.example .env
```

Git Bash、macOS 或 Linux：

```bash
cp .env.example .env
```

程序可以在未配置模型时启动并进行故事、角色和章节数据管理，但生成章节前必须在 `.env` 配置一种模型服务。默认提供方是 `gemini`，且默认地址为本地代理 `http://127.0.0.1:8045`；没有填写 `GEMINI_API_KEY` 或未启动代理时，生成会失败。

| 配置项 | 说明 |
|---|---|
| `DEFAULT_PROVIDER` | 选择 `gemini`、`ollama`、`openai` 或 `anthropic` |
| `GEMINI_BASE_URL` / `GEMINI_API_KEY` | Gemini 兼容代理地址与密钥 |
| `OLLAMA_HOST` / `OLLAMA_DEFAULT_MODEL` | 本地或远程 Ollama 服务及模型 |
| `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_DEFAULT_MODEL` | OpenAI 或兼容 API |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_DEFAULT_MODEL` | Anthropic Claude API |
| `CHAPTER_TARGET_CHARS` | 每个节点的目标字数，默认 `2000` |
| `ADMIN_EMAILS` | 逗号分隔的管理员邮箱；匹配账号注册后可访问所有小说 |
| `AUTH_SESSION_DAYS` | 登录会话有效期，默认 `30` 天 |
| `AUTH_COOKIE_SECURE` | HTTPS 部署设为 `true`；本地 HTTP 开发保持 `false` |

### 用户与管理员

首次使用时，用户可在网页注册、登录和退出。普通用户只能访问自己创建的小说及其角色、关系和章节；`ADMIN_EMAILS` 中的邮箱注册后自动成为管理员，可访问所有内容。

启用认证前已经存在的小说会暂时没有归属。首个成功注册或登录的管理员会自动认领这些历史小说；普通用户无法查看未认领的历史数据。生产环境应使用 HTTPS，并将 `AUTH_COOKIE_SECURE=true`。

例如，使用本地 Ollama：

```dotenv
DEFAULT_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_DEFAULT_MODEL=gemma4:12b
```

然后在另一终端启动 Ollama 并拉取模型：

```bash
ollama pull gemma4:12b
```

例如，使用 OpenAI 或其他兼容服务：

```dotenv
DEFAULT_PROVIDER=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=你的密钥
OPENAI_DEFAULT_MODEL=gpt-4o-mini
```

其他变量及默认值见 [.env.example](.env.example)。

## 运行

### 开发模式（推荐）

在终端 1，从项目根目录启动 API：

```bash
python -m uvicorn app.main:app --reload --port 8000
```

使用 `python -m uvicorn` 可以确保调用当前虚拟环境安装的 Uvicorn，而不是依赖系统 PATH。

在终端 2 启动前端：

```bash
cd frontend
npm run dev
```

打开 <http://localhost:5173>。Vite 会将 `/api` 请求自动转发至后端 `http://localhost:8000`。

后端启动后可访问：

- API 文档：<http://localhost:8000/docs>
- 接口验证：<http://localhost:8000/api/novels>

### 单端口运行

构建前端后，FastAPI 会托管 `frontend/dist`：

```bash
cd frontend
npm run build
cd ..
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 <http://localhost:8000>。

### Docker Compose

Docker Compose 会启动独立的 FastAPI 与 Nginx 容器；Nginx 默认仅绑定本机 `127.0.0.1:8000`，SQLite 数据保存在项目目录的 `data/` 中。

```bash
# 先按“配置模型”一节创建并填写 .env
docker compose up --build
```

本机访问 <http://localhost:8000>。后台运行请使用：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=100
```

远程部署、Docker 中访问主机 Ollama、备份恢复与 HTTPS 配置见 [DEPLOY.md](DEPLOY.md)。

## 常见问题

| 现象 | 处理方式 |
|---|---|
| `No module named uvicorn` 或 `No module named fastapi` | 激活虚拟环境后执行 `python -m pip install -r requirements.txt`。 |
| Git Bash 报 `...python.exe: command not found` | 使用 `./.venv/Scripts/python.exe`，或先执行 `source .venv/Scripts/activate`；路径使用 `/`。 |
| 页面可打开但生成章节失败 | 检查 `.env` 中的 `DEFAULT_PROVIDER` 与对应 API Key、模型名和服务地址；使用 Ollama 时确认服务已启动且模型已拉取。 |
| 前端请求连接不到 API | 确认后端正在 `http://localhost:8000` 运行，再查看 Vite 终端是否显示代理错误。 |
| Windows 执行 `Activate.ps1` 被阻止 | 可在当前 PowerShell 会话执行 `Set-ExecutionPolicy -Scope Process Bypass` 后重试，或直接使用 `.\.venv\Scripts\python.exe -m ...`。 |

## 使用流程

1. 新建故事：填写世界观、可选初始角色并选择模型。
2. 在工作台维护角色卡与人物关系。
3. 写入剧情指令，生成根章节。
4. 选中章节，继续写指令或使用 AI 选项生成子章节。
5. 将叶节点标记为结局，或从任意历史节点开新旁支。

## 数据

SQLite 默认保存到 `./data/novels.db`。启动时会自动迁移旧数据：

- `settings` 字段迁移为 `world_setting`
- 旧线性章节会按顺序转换为单路径剧情树

升级前建议备份 `data/novels.db`。

## 项目结构

```text
app/                 # FastAPI 应用、模型服务与 JSON API
  main.py            # 应用入口与前端静态文件托管
  api/routes.py      # /api 路由
  services/          # CRUD 与章节生成
  providers/         # 各模型服务适配器
frontend/            # Vue 3 单页应用
  src/               # 页面、组件、路由与 API 客户端
```

## API 摘要

- `GET/POST /api/novels`
- `GET/POST /api/novels/{id}/characters`、`PATCH/DELETE /api/characters/{id}`
- `GET/POST /api/novels/{id}/relations`、`PATCH/DELETE /api/relations/{id}`
- `GET /api/novels/{id}/chapters/tree`
- `POST /api/novels/{id}/chapters/generate`
- `POST /api/novels/{id}/chapters/suggest-options`
- `POST /api/chapters/{id}/regenerate`、`PATCH/DELETE /api/chapters/{id}`
