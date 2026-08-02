# Docker 服务器部署说明

本项目使用两个容器运行：Nginx 容器提供 Vue 前端并将 `/api` 转发至 FastAPI 后端；后端不直接暴露到宿主机。SQLite 数据库通过卷挂载保存在 Compose 文件同级的 `data/` 目录，因此重建或升级容器不会删除数据。

当前发布镜像：

- 后端：`ghcr.io/superwahahayue/novel-generator:backend-0.0.3`
- 前端：`ghcr.io/superwahahayue/novel-generator:frontend-0.0.3`

## 服务器要求

- Docker Engine 24+ 与 Docker Compose 插件
- 至少 1 GB 可用磁盘空间，另需为 SQLite 数据和模型服务预留空间
- 可访问的模型服务：线上 API 最适合服务器；也可使用宿主机或其他机器上的 Ollama
- 建议使用域名和 HTTPS 反向代理。Compose 默认只监听本机 `127.0.0.1:8000`，不会直接对公网开放

## 首次部署

### 1. 准备部署文件

在服务器创建部署目录，只需上传下列两个文件：

- `deploy/docker-compose.yml`
- `.env.example`（上传后改名为 `.env` 并填写配置）

例如：

```sh
mkdir -p ~/novel-generator
cd ~/novel-generator
# 将本地的 deploy/docker-compose.yml 和 .env.example 上传到这里
cp .env.example .env
```

请勿上传本地的 `.venv`、`frontend/node_modules`、源代码或包含旧数据的 `data/`，除非这是一次有意的数据迁移。

### 2. 创建数据目录

后端容器以固定的非 root 用户（UID/GID `10001`）运行。创建持久化目录并授权：

```sh
mkdir -p data
sudo chown 10001:10001 data
```

### 3. 配置 `.env`

编辑 `.env`，至少选择一种模型服务并填写对应密钥或地址。API 密钥仅保留在服务器的 `.env` 中，不要提交到 Git，也不要上传到公开仓库。

生产环境必须设置：

```dotenv
# 用逗号分隔管理员邮箱；管理员可查看所有用户的小说
ADMIN_EMAILS=admin@example.com

# 外部通过 HTTPS 访问时必须开启；本地 HTTP 调试时保持 false
AUTH_COOKIE_SECURE=true
```

使用线上 OpenAI 兼容 API 的示例：

```dotenv
DEFAULT_PROVIDER=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=替换为你的密钥
OPENAI_DEFAULT_MODEL=gpt-4o-mini
```

### 4. 登录并拉取私有镜像

GHCR 镜像默认可能为私有包。服务器首次拉取时，使用拥有读取权限的 GitHub **classic PAT** 登录；不要输入 GitHub 账户密码。

```sh
docker login ghcr.io -u superwahahayue
docker compose pull
```

若服务器网络需通过代理访问镜像仓库，请按 [README 的 7898 代理说明](README.md#网络受限时使用本地-7898-代理) 为当前终端或 Docker Desktop 配置代理后再拉取。

### 5. 启动与验证

```sh
docker compose up -d
docker compose ps
docker compose logs -f --tail=100
```

所有服务显示为 `running` 且健康检查通过后，应用已在服务器本机的 `http://127.0.0.1:8000` 提供服务。可通过 SSH 验证：

```sh
curl -I http://127.0.0.1:8000/
```

## 配置 HTTPS 与公网访问

不要把应用端口直接暴露到公网。请使用 Caddy、Nginx 或服务器面板的反向代理，将域名转发至 `127.0.0.1:8000`，并由反向代理签发和续期 TLS 证书。

以 Caddy 为例：

```caddyfile
novel.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

将 `novel.example.com` 换成实际域名，并确认 DNS 已指向该服务器。HTTPS 配置完成后保持 `AUTH_COOKIE_SECURE=true`，否则浏览器不会在安全环境中正确保护登录会话。

## 使用宿主机或远程 Ollama

### Ollama 在 Docker 宿主机运行

在服务器启动 Ollama，然后在 `.env` 设置：

```dotenv
DEFAULT_PROVIDER=ollama
OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_DEFAULT_MODEL=gemma4:12b
```

Compose 已将 Linux 下的 `host.docker.internal` 映射到 Docker 宿主机。Ollama 必须监听一个容器可访问的地址；模型文件和 GPU 配置由 Ollama 自身管理。

### Ollama 在另一台机器运行

将地址换为实际可访问的内网地址，例如：

```dotenv
OLLAMA_HOST=http://192.0.2.10:11434
```

确认服务器防火墙和远端 Ollama 的监听策略允许该连接；不要把未受保护的 Ollama 端口直接暴露到公网。

## 升级与回滚

### 升级

1. 在 `docker-compose.yml` 中将后端和前端 `image:` 标签同时改为新版本。
2. 拉取并重建服务：

   ```sh
   docker compose pull
   docker compose up -d
   docker compose ps
   ```

`data/` 目录会被保留。升级前建议先按下节备份数据库。

### 回滚

将两个 `image:` 标签改回已验证可用的旧版本，然后执行：

```sh
docker compose pull
docker compose up -d
```

后端和前端应使用同一发布批次的版本，避免 API 与页面不兼容。

## 备份与恢复数据库

备份前短暂停止服务，以取得一致的 SQLite 文件：

```sh
docker compose stop
tar -czf novels-data-$(date +%F).tar.gz data/
docker compose start
```

将备份文件保存到部署目录以外的位置。恢复时停止服务，用备份中的 `data/` 替换当前目录，再启动服务：

```sh
docker compose stop
# 解压备份并确认其中的 data/ 目录替换了当前 data/
docker compose start
```

恢复后如出现权限错误，重新执行：

```sh
sudo chown -R 10001:10001 data
```

## 排查问题

| 现象 | 处理方式 |
|---|---|
| `docker compose pull` 无权访问或找不到镜像 | 执行 `docker login ghcr.io -u superwahahayue`，确认 PAT 有包读取权限，并检查镜像标签是否存在。 |
| 后端显示 `unhealthy`，前端因此未启动 | 当前健康检查访问无需登录的后端根路径。若 Compose 文件仍检查 `/api/novels`，请将其改为 `http://127.0.0.1:8000/` 后执行 `docker compose up -d --force-recreate`；`/api/novels` 需要登录，会返回 `401`。 |
| 其他容器不断重启或显示 `unhealthy` | 执行 `docker compose logs -f --tail=100`；检查 `.env`、模型服务地址和 `data/` 目录权限。 |
| 浏览器无法访问域名 | 先在服务器执行 `curl -I http://127.0.0.1:8000/`；若成功，检查反向代理、DNS、证书与防火墙。 |
| 登录成功后又回到登录页 | 确认网站通过 HTTPS 访问且 `AUTH_COOKIE_SECURE=true`；不要在 `localhost`、IP 和正式域名之间混用浏览器地址。 |
| 更新后看似仍是旧页面 | 检查两个镜像标签是否已同步更新，并执行 `docker compose pull && docker compose up -d`；可随后清除浏览器缓存后重试。 |
| 数据库无法写入或数据丢失 | 确认 `./data:/app/data` 挂载仍存在，且宿主机 `data/` 归 UID/GID `10001` 所有；不要删除该目录。 |
