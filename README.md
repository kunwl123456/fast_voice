# Fish Audio 示例代码结构

生成自需求文档的前后端骨架，便于继续实现。

## 目录
- `backend/` Flask 后端
  - 路由按功能拆分，TTS/创建声音接口为占位
  - `tests/` pytest 示例
- `frontend/` React + Vite 前端
  - 代理到后端 `/api`，占位页面方便联调
- `Fish_Audio_需求文档.md` 原需求文档

## 快速启动
### 后端
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

## 注意
- `POST /api/tts/generate`、`POST /api/voice-cloning/create` 已按要求预留，占位返回 501。可直接在对应路由内接入真实逻辑。
- 更多接口示例见 `backend/README.md` 与 `frontend/README.md`。
- 发现模块使用 Redis 持久化数据（默认 redis://localhost:6379/0），Redis 不可用时自动回退示例数据。

