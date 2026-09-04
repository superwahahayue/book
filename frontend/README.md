# 小说生成器 · 前端 (Vue 3)

前后端分离的前端项目。开发时通过 Vite dev server 运行，`/api` 请求代理到 FastAPI 后端（`:8000`）。

## 技术栈

- Vue 3（`<script setup>`）
- Vue Router 4
- Axios
- Vite 6
- 纯手写 CSS 设计系统（书籍质感 · 米纸/墨色/朱砂），支持深色模式

## 目录结构

```
frontend/
├── index.html
├── vite.config.js          # dev server + /api 代理配置
├── src/
│   ├── main.js             # 入口，恢复主题
│   ├── App.vue             # 根组件（顶栏 + 路由出口）
│   ├── router/index.js     # 路由：书库 / 新建 / 小说详情
│   ├── api/client.js       # axios 封装，所有接口集中于此
│   ├── styles/main.css     # 全局设计系统与主题变量
│   ├── components/
│   │   ├── TopBar.vue      # 顶栏 + 深浅色切换
│   │   └── StatusBadge.vue # 生成状态徽章
│   └── views/
│       ├── LibraryView.vue # 书库（书架卡片）
│       ├── CreateView.vue  # 新建小说表单
│       └── NovelView.vue   # 阅读页 + 设置/大纲编辑
```

## 开发

先启动后端（项目根目录）：

```bash
# 在 D:\workspace\personal\book 下
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

再启动前端：

```bash
cd frontend
npm install      # 首次
npm run dev      # http://localhost:5288
```

浏览器打开 http://localhost:5288 。前端调用 `/api/*` 会自动代理到 `:8000`。

## 构建部署

```bash
npm run build    # 产物输出到 frontend/dist
```

`dist/` 可交给 Nginx 独立部署，或由 FastAPI 托管（记得把生产域名加入后端 `.env` 的 `CORS_ORIGINS`）。

## 修改样式

所有设计变量集中在 `src/styles/main.css` 顶部的 `:root` / `:root[data-theme="dark"]`：
调色板、圆角、阴影、字体都在那里，改一处即可全局生效。
