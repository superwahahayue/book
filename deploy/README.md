# 服务器部署包

此目录是仅用于生产环境的部署包。它从 GHCR 拉取已发布的 `0.0.3` 前端和后端镜像；服务器不需要项目源代码、`Dockerfile`、Node.js 或 Python 开发环境。

## 准备上传内容

1. 将根目录的 `.env` 复制到此 `deploy/` 目录，或将 `.env.example` 复制为 `.env` 后填写真实的模型配置和 API Key。
2. 将此目录内的 **内容** 上传到服务器 `/opt/novel-generator`。上传后目录应为：

   ```text
   /opt/novel-generator/
   ├── docker-compose.yml
   └── .env
   ```

不要将 `.env` 提交至 GitHub 或打包进公开压缩包。

## 在服务器启动

```sh
cd /opt/novel-generator
mkdir -p data
sudo chown 10001:10001 data

# GHCR 镜像为私有包时需要登录；密码使用有包读取权限的 GitHub classic PAT。
docker login ghcr.io -u superwahahayue

docker compose pull
docker compose up -d
docker compose ps
```

服务健康后，应用仅监听服务器本机的 `127.0.0.1:8000`。请使用 Caddy、Nginx 或服务器面板将域名反向代理到该地址，并配置 HTTPS。查看日志：

```sh
docker compose logs -f --tail=100
```

## 升级版本

在 GitHub 推送 `v0.0.4` 之类的版本标签后，Actions 会发布 `backend-0.0.4` 和 `frontend-0.0.4`。在服务器将两个镜像标签同时改为新版本，再执行：

```sh
docker compose pull
docker compose up -d
```
