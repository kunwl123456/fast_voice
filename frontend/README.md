# 前端（React + Vite）说明

## 快速开始
```bash
cd frontend
npm install
npm run dev
```
默认开发端口：5173，已在 `vite.config.js` 里代理到 Flask 默认 5000 端口。

## 页面
- 首页：快速入口导航
- 语音合成（占位）：调用占位 TTS 接口，方便调试入参
- 克隆声音（占位）：调用占位创建接口
- 发现：示例声音列表、收藏
- 积分：示例余额与流水

> 生成语音和创建语音接口为占位，可在 `src/api/client.js` 替换真实后端实现。

