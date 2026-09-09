# 服务器部署包

此目录是仅用于生产环境的部署包。它从 GHCR 拉取已发布的前端和后端镜像；服务器不需要项目源代码、`Dockerfile`、Node.js 或 Python 开发环境。镜像版本由 `IMAGE_TAG` 环境变量决定。

## 准备上传内容

1. 将根目录的 `.env` 复制到此 `deploy/` 目录，或将 `.env.example` 复制为 `.env` 后填写真实的模型配置和 API Key。
2. 将此目录内的 **内容** 上传到服务器 `/opt/novel-generator/deploy`。上传后目录应为：

   ```text
   /opt/novel-generator/deploy/
   ├── docker-compose.yml
   └── .env
   ```

不要将 `.env` 提交至 GitHub 或打包进公开压缩包。

## 在服务器启动

```sh
cd /opt/novel-generator/deploy
mkdir -p data
sudo chown 10001:10001 data

# GHCR 镜像为私有包时需要登录；密码使用有包读取权限的 GitHub classic PAT。
docker login ghcr.io -u superwahahayue

IMAGE_TAG=0.0.3 docker compose pull
IMAGE_TAG=0.0.3 docker compose up -d
docker compose ps
```

服务健康后，应用仅监听服务器本机的 `127.0.0.1:8000`。请使用 Caddy、Nginx 或服务器面板将域名反向代理到该地址，并配置 HTTPS。查看日志：

```sh
docker compose logs -f --tail=100
```

### 导入文件时的 Nginx 限额

前端容器已允许最多 20 MiB 的 TXT、Markdown 或 DOCX 上传。若服务器外层也使用
Nginx 反向代理，请在对应的 `server {}` 块加入同样（或更大）的限制，否则请求会在到达
应用前被 Nginx 以 `413 Request Entity Too Large` 拒绝：

```nginx
client_max_body_size 20m;
```

## 使用独立的 Antigravity 模型代理

Antigravity 可以独立于本项目运行，但小说后端需要通过 Docker 内部网络访问它。请先完成上面的小说服务启动步骤，使 Compose 自动创建 `deploy_default` 网络。

### 1. 创建 Antigravity 的机密配置

不要把密钥写入命令历史、README、Git 仓库或公开截图。在服务器创建只允许 root 读取的环境文件：

```sh
sudo install -d -m 700 /opt/antigravity/data
sudo nano /opt/antigravity/antigravity.env
sudo chmod 600 /opt/antigravity/antigravity.env
```

文件内容如下；请填写两组不同的高强度随机值：

```dotenv
API_KEY=<Antigravity API Key>
WEB_PASSWORD=<Antigravity Web 管理密码>
ABV_MAX_BODY_SIZE=104857600
```

### 2. 启动 Antigravity

使用 `--network deploy_default` 和 `--network-alias antigravity-manager`，让小说后端能以 `antigravity-manager:8045` 找到该容器。`127.0.0.1:8045:8045` 只允许服务器本机访问管理页/API，不会开放 8045 到公网。

```sh
docker run -d --name antigravity-manager \
  --restart unless-stopped \
  --network deploy_default \
  --network-alias antigravity-manager \
  -p 127.0.0.1:8045:8045 \
  --env-file /opt/antigravity/antigravity.env \
  -v /opt/antigravity/data:/root/.antigravity_tools \
  lbjlaq/antigravity-manager:latest
```

如果 Antigravity 已经以其他网络启动，可补充连接：

```sh
docker network connect --alias antigravity-manager deploy_default antigravity-manager
```

### 3. 配置小说后端使用代理

编辑 `/opt/novel-generator/deploy/.env`，让 API Key 与 Antigravity 的 `API_KEY` 相同：

```dotenv
GEMINI_BASE_URL=http://antigravity-manager:8045
GEMINI_API_KEY=<与 Antigravity API_KEY 相同的值>
```

应用变更后，按正在部署的镜像版本重建后端，例如：

```sh
cd /opt/novel-generator/deploy
IMAGE_TAG=0.0.6 docker compose up -d --force-recreate backend
```

> 若重建或删除 `antigravity-manager` 容器，旧容器的网络连接会随之移除。重新启动时务必保留 `--network deploy_default` 和 `--network-alias antigravity-manager`；否则后端会报无法解析 `antigravity-manager`。

### 导入小说与漫画生成配置

导入支持 TXT、Markdown 和 DOCX；默认上传上限为 20 MiB。漫画功能会调用同一
Antigravity 代理的图片接口，因此 `GEMINI_BASE_URL` 与 `GEMINI_API_KEY` 仍是唯一
需要配置的连接信息。默认模型和并发上限可按实际账号配额在 `.env` 中调整：

```dotenv
COMIC_DEFAULT_IMAGE_MODEL=gemini-3-pro-image
COMIC_DEFAULT_ASPECT_RATIO=16:9
COMIC_DEFAULT_QUALITY=standard
COMIC_DEFAULT_PANEL_COUNT=6
COMIC_MAX_CONCURRENT_JOBS=1
```

保持 `COMIC_MAX_CONCURRENT_JOBS=1` 可以避免一部小说的多格图片同时冲击代理配额。
若更改了上传上限，前端容器和服务器外层 Nginx 的 `client_max_body_size` 也必须同步
提高；详见上方“导入文件时的 Nginx 限额”。

## 升级版本

在 GitHub 推送 `v0.0.4` 之类的版本标签后，Actions 会发布 `backend-0.0.4` 和 `frontend-0.0.4`。启用自动部署后，服务器会自动更新；未启用时执行：

```sh
IMAGE_TAG=0.0.4 docker compose pull
IMAGE_TAG=0.0.4 docker compose up -d --wait
```
