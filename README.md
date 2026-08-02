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

## Docker 镜像发布与部署

项目的后端和前端由根目录的多阶段 `Dockerfile` 分别构建。以下命令使用当前发布版本 `0.0.3`；后续发布时请将两个标签同时替换为新版本号。

### 本地构建与检查

```bash
docker build --target backend -t ghcr.io/superwahahayue/novel-generator:backend-0.0.3 .
docker build --target frontend -t ghcr.io/superwahahayue/novel-generator:frontend-0.0.3 .
docker image ls ghcr.io/superwahahayue/novel-generator
```

### 网络受限时使用本地 7898 代理

下列设置仅在**当前终端进程**有效；关闭终端或新开终端后需要重新设置。它不会修改 Docker Desktop 的全局配置，也不会影响其他应用。

PowerShell：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7898'
$env:HTTPS_PROXY='http://127.0.0.1:7898'
$env:NO_PROXY='localhost,127.0.0.1'
docker pull python:3.12-slim
```

Git Bash：

```bash
export HTTP_PROXY=http://127.0.0.1:7898
export HTTPS_PROXY=http://127.0.0.1:7898
export NO_PROXY=localhost,127.0.0.1
docker pull python:3.12-slim
```

若希望长期让 Docker Desktop 使用代理，请在 Docker Desktop 的 **Settings → Resources → Proxies** 中配置；不要仅编辑 Docker Engine 的 `daemon.json`，Docker Desktop 的代理设置应在 Proxies 页面管理。参见 [Docker Desktop 代理说明](https://docs.docker.com/desktop/settings-and-maintenance/settings/#proxies)。

### 登录并推送到 GitHub Container Registry（GHCR）

1. 在 GitHub 创建 **Personal access token (classic)**，至少勾选 `write:packages`。不要使用 GitHub 登录密码，也不要把令牌写入 `.env`、README、Git 提交或聊天记录。参见 [GitHub Container Registry 认证说明](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry)。
2. 登录 GHCR：

   ```bash
   docker login ghcr.io -u superwahahayue
   ```

   在 `Password:` 提示处粘贴刚创建的 PAT。看到 `Login Succeeded` 后再继续。

3. 推荐通过 GitHub Actions 自动构建并发布：提交代码后创建并推送版本标签，例如：

   ```bash
   git tag v0.0.4
   git push origin v0.0.4
   ```

   工作流会自动发布 `backend-0.0.4`、`frontend-0.0.4` 以及对应的提交 SHA 标签。可在 GitHub 仓库的 **Actions** 页面查看进度。

   若已配置生产部署，镜像发布成功后还会自动将最新的 `deploy/docker-compose.yml` 上传到服务器，并以 `0.0.4` 作为 `IMAGE_TAG` 拉取、启动并等待容器健康。服务器的 `.env` 和 `data/` 不会被覆盖。

   首次启用自动部署前，在仓库 **Settings → Environments → production** 添加以下 Environment Secrets：

   | Secret | 含义 |
   |---|---|
   | `DEPLOY_HOST` | 服务器 IP 或域名 |
   | `DEPLOY_PORT` | SSH 端口，例如 `22` |
   | `DEPLOY_USER` | 部署用户，例如 `root` |
   | `DEPLOY_SSH_PRIVATE_KEY_B64` | 仅供部署使用的 SSH 私钥 Base64 单行文本；可避免换行符导致的解析错误 |
   | `DEPLOY_KNOWN_HOSTS` | 服务器 SSH 主机指纹；可用 `ssh-keyscan -H 服务器IP` 获取 |

   建议为 `production` 启用“Required reviewers”，使每个版本在发布镜像后先等待确认再更新服务器。

4. 如需在本机手动发布，则在已设置代理的同一终端推送两个镜像：

   ```bash
   docker push ghcr.io/superwahahayue/novel-generator:backend-0.0.3
   docker push ghcr.io/superwahahayue/novel-generator:frontend-0.0.3
   ```

5. 在服务器或另一台机器上部署时，先将 `deploy/docker-compose.yml` 的两个 `image:` 标签改为目标版本，再执行：

   ```bash
   cd deploy
   docker compose pull
   docker compose up -d
   docker compose ps
   ```

首次推送的镜像包默认是私有的；需要其他机器或用户拉取时，应在 GitHub Packages 中调整包可见性或为其授予读取权限。

## 常见问题

| 现象 | 处理方式 |
|---|---|
| `No module named uvicorn` 或 `No module named fastapi` | 激活虚拟环境后执行 `python -m pip install -r requirements.txt`。 |
| Git Bash 报 `...python.exe: command not found` | 使用 `./.venv/Scripts/python.exe`，或先执行 `source .venv/Scripts/activate`；路径使用 `/`。 |
| 页面可打开但生成章节失败 | 检查 `.env` 中的 `DEFAULT_PROVIDER` 与对应 API Key、模型名和服务地址；使用 Ollama 时确认服务已启动且模型已拉取。 |
| 未登录时页面空白、没有登录/注册界面，或页面提示无法连接认证服务 | 前端依赖后端的 `/api/auth/me` 初始化状态。确认后端正在 `http://localhost:8000` 运行：`python -m uvicorn app.main:app --reload --port 8000`；不要只启动 `npm run dev`。 |
| 前端请求连接不到 API / Vite 显示代理错误 | 确认后端正在 `http://localhost:8000` 运行；检查 8000 端口未被其他程序占用，并保持 Vite 使用默认代理配置。 |
| 登录或注册后仍回到登录页 | 确认浏览器允许本地站点 Cookie；开发环境保持 `AUTH_COOKIE_SECURE=false`，部署到 HTTPS 后才设置为 `true`。也请确认浏览器访问地址一致（不要在 `localhost` 与 `127.0.0.1` 间来回切换）。 |
| 普通用户看不到旧小说 | 这是权限设计：未归属的历史小说只会由第一个登录/注册的管理员自动认领。将管理员邮箱加入 `ADMIN_EMAILS` 后，用该账号登录一次。 |
| Windows 执行 `Activate.ps1` 被阻止 | 可在当前 PowerShell 会话执行 `Set-ExecutionPolicy -Scope Process Bypass` 后重试，或直接使用 `.\.venv\Scripts\python.exe -m ...`。 |
| `docker version` 无法连接 daemon，或提示 Docker Engine 未运行 | 启动 Docker Desktop，等待状态变为 Running 后执行 `docker version` 再重试。 |
| 构建/拉取时报 `auth.docker.io:443` 超时、TLS 握手失败或无法连接 | 先确认本地代理服务正在监听 `127.0.0.1:7898`，然后按“网络受限时使用本地 7898 代理”一节在**同一终端**设置 `HTTP_PROXY` 和 `HTTPS_PROXY`，再用 `docker pull python:3.12-slim` 验证。 |
| `docker login ghcr.io` 返回 `denied` | 用户名应为 GitHub 用户名；密码必须是有 `write:packages` 权限的 **classic PAT**，不是 GitHub 账号密码。可先执行 `docker logout ghcr.io` 再重新登录。 |
| `docker push` 返回 `unauthorized` 或 `denied` | 重新执行 `docker login ghcr.io -u superwahahayue`，核对 PAT 未过期且含 `write:packages`；组织启用 SSO 时，还需在 GitHub 授权该令牌使用 SSO。 |
| 服务器 `docker compose pull` 找不到镜像或拉取旧版本 | 核对 `deploy/docker-compose.yml` 中 `image:` 标签与已推送标签完全一致，例如 `backend-0.0.3` 和 `frontend-0.0.3`；私有包还需先在服务器执行 `docker login ghcr.io`。 |
| GitHub Actions 发布镜像时对 `ghcr.io/.../blobs/...` 返回 `403 Forbidden` | 该镜像包曾通过命令行手动推送，尚未关联到仓库。打开 [novel-generator 包设置](https://github.com/users/superwahahayue/packages/container/novel-generator/settings)，在 **Manage Actions access** 点击 **Add repository**，选择 `superwahahayue/book` 并授予 **Write**（或 **Admin**）权限；随后在 Actions 页面重新运行失败的工作流。工作流已声明 `packages: write`，无需将 PAT 写进仓库 Secret。 |
| GitHub Actions 部署任务提示部署 Secret 为空 | 在仓库 **Settings → Environments → production** 配置 `DEPLOY_HOST`、`DEPLOY_PORT`、`DEPLOY_USER`、`DEPLOY_SSH_PRIVATE_KEY_B64`、`DEPLOY_KNOWN_HOSTS`；私钥必须与服务器 `authorized_keys` 中的公钥配对。 |
| 加载 SSH 私钥提示 `error in libcrypto` | 不要直接保存多行私钥。使用 `DEPLOY_SSH_PRIVATE_KEY_B64`，其值为私钥文件的 Base64 单行文本；工作流会在运行时还原并校验私钥。 |
| 自动部署 SSH 连接失败或主机身份校验失败 | 确认 `DEPLOY_KNOWN_HOSTS` 是通过 `ssh-keyscan -H 服务器IP` 获取的完整输出；不要为了绕过校验改用 `StrictHostKeyChecking=no`。 |
| 其他 GitHub Actions 发布镜像失败 | 在仓库 **Actions** 日志中检查错误；确认工作流由 `v*` 版本标签触发，且仓库未禁止 `GITHUB_TOKEN` 写入 Packages。 |
| Compose 启动后 8000 端口无法访问 | 检查端口是否被占用：Windows 可用 `Get-NetTCPConnection -LocalPort 8000`；停止冲突服务，或修改 Compose 的端口映射后重启。 |
| 后端显示 `unhealthy`，前端没有启动 | 健康检查不得访问需登录的 `/api/novels`（未登录会返回 `401`）。使用仓库当前部署配置，或将检查地址改为 `http://127.0.0.1:8000/`，然后执行 `docker compose up -d --force-recreate`。 |
| 容器反复重启或显示 `unhealthy` | 在 `deploy/` 目录运行 `docker compose logs -f --tail=100`；确认 `.env` 已创建、模型服务地址可从容器访问、以及 `data/` 目录可写。 |
| 更新镜像后数据丢失 | SQLite 数据应保存在挂载目录 `data/`，不要删除该目录。升级前备份 `data/novels.db`，并使用 `docker compose up -d` 更新容器。 |

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
