# 后端（Flask）说明

## 快速开始
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

## 路由概览
- `GET /health` 健康检查
- `POST /api/auth/login` 示例登录
- `GET /api/auth/me` 获取当前用户（示例数据）
- `POST /api/tts/generate` 文本转语音（占位，待实现）
- `POST /api/voice-cloning/upload` 上传源音频（示例）
- `POST /api/voice-cloning/create` 创建声音（占位，待实现）
- `GET /api/voice-cloning/status/<id>` 查看训练状态
- `GET /api/discovery/voices` 声音列表（示例）
- `GET /api/discovery/voices/<id>` 声音详情（示例）
- `POST /api/discovery/bookmark` 收藏声音
- `GET /api/credits/balance` 积分余额
- `GET /api/credits/transactions` 积分流水

## Redis 说明
- 发现模块使用 Redis 持久化声音列表与收藏集合，默认连接 `redis://localhost:6379/0`。
- 若 Redis 不可用将自动回退到内置示例数据，接口仍可使用。

## 测试
```bash
cd backend
pytest
```

