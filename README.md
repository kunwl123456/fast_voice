# fast_voice（V1）

## 项目简介

fast_voice 是一个**开放平台式的 TTS（文本转语音）服务**，提供 Console（用户管理控制台）和 OpenAPI（B端集成接口）两种访问方式。

### 核心功能

- **Console（C 端用户入口）**
  - 用户系统：注册/登录、修改昵称/密码/头像
  - 订阅管理：免费版/专业版/企业版三种计划
  - 积分账户：余额查询、流水记录、管理员调账
  - API Key 管理：创建、列表、删除（仅企业版）
  - 音色管理：我的音色、公开/私有设置
  - 任务管理：TTS 合成任务、音色克隆任务
  - Dashboard：使用统计、请求日志、配额监控

- **OpenAPI（B 端集成入口）**
  - HMAC-SHA256 签名鉴权（APIKey + Secret）
  - 时间戳 + Nonce 防重放攻击
  - 幂等键（Idempotency-Key）支持
  - 异步任务：TTS 合成、音色克隆
  - 声音大厅：公开音色列表

---

## 业务规则

### 订阅计划

| 计划 | 月度积分 | 月度配额 | 克隆位 | API访问 | 商业使用 |
|------|----------|----------|--------|---------|----------|
| **免费版** | 1,000 | 100次 | 3个 | ❌ | ❌ |
| **专业版** | 10,000 | 5,000次 | 20个 | ❌ | ✅ |
| **企业版** | 100,000 | 500,000次 | 无限 | ✅ | ✅ |

### 计费规则

- **按输入文本的 UTF-8 字节数计费**
- 默认单价：`1 积分/字节`（可通过环境变量 `CREDIT_PRICE_PER_UTF8_BYTE` 配置）
- 最大文本长度：`4000 字节`（可通过 `MAX_TEXT_UTF8_BYTES` 配置）

### 扣费策略

- **预扣费**：创建任务时立即扣除积分并记录流水
- **失败退款**：任务失败时全额退款（自动记录退款流水）
- **余额不足**：创建任务前检查余额，不足时拒绝创建

### 异步任务

- **TTS/克隆任务必须异步执行**（创建任务 → 轮询查询状态）
- 任务状态机：`queued` → `running` → `succeeded` / `failed`
- Celery 队列：`tts` 队列（TTS任务）、`clone` 队列（克隆任务）

---

## 快速开始

### 1. 依赖管理（uv）

本项目使用 **uv + pyproject.toml** 管理依赖。

```bash
# 安装 uv（如果未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖（生产环境）
uv sync --no-dev

# 安装依赖（开发环境）
uv sync --extra dev

# 运行 API 服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 运行 Celery Worker
uv run celery -A app.tasks.celery_app:celery_app worker -l INFO -Q tts,clone

# 运行测试
uv run pytest -q
```

### 2. Docker 部署（推荐）

```bash
# 启动所有服务（API + Worker + Redis）
docker compose up --build
```

启动后访问：
- **API 地址**：`http://localhost:8000`
- **Swagger 文档**：`http://localhost:8000/docs`
- **OpenAPI 接入指南**：`http://localhost:8000/openapi/docs/guide`

### 3. 环境变量配置

创建 `.env` 文件（或在 docker-compose.yml 中配置）：

```bash
# 数据库（生产环境推荐 Postgres）
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/fast_voice
DATABASE_URL_SYNC=postgresql+psycopg://user:pass@localhost/fast_voice

# Redis（用于 nonce 防重放、幂等键、Celery）
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# JWT 配置
JWT_SECRET=your-secret-key-here
JWT_ACCESS_TOKEN_MINUTES=1440  # 24小时

# 管理员账号（首次启动自动创建）
ADMIN_EMAIL=admin@autogame.ai
ADMIN_PASSWORD=your-secure-password

# API Secret 加密密钥（Fernet，base64 urlsafe 32字节）
API_SECRET_ENC_KEY=your-fernet-key-here

# 签名时间窗口（秒）
SIGNATURE_TIME_WINDOW_SECONDS=300

# 计费配置
CREDIT_PRICE_PER_UTF8_BYTE=1
MAX_TEXT_UTF8_BYTES=4000

# 数据目录（生成的音频文件存储路径）
DATA_DIR=./data

# 开发模式（自动建表）
AUTO_CREATE_DB=true
```

---

## 项目结构

```
fast_voice/
├── app/                          # 后端代码（FastAPI + SQLAlchemy + Celery）
│   ├── main.py                   # 入口：中间件、路由挂载、建表、静态文件
│   ├── core/
│   │   ├── config.py             # 配置：环境变量（DB/Redis/JWT/计费等）
│   │   └── security.py           # 安全：密码哈希、JWT、HMAC签名、加密
│   ├── db.py                     # SQLAlchemy 异步引擎/会话（带连接池）
│   ├── models.py                 # 数据模型：User/ApiKey/Voice/Job/Log 等
│   ├── schemas.py                # Pydantic 请求/响应结构
│   ├── deps.py                   # FastAPI 依赖：DB、JWT、签名鉴权
│   ├── responses.py              # 统一响应格式（success/error）
│   ├── subscription.py           # 订阅计划配置（免费/专业/企业版）
│   ├── routes/
│   │   ├── console.py            # Console 路由：用户/订阅/积分/APIKey/Dashboard
│   │   ├── voices.py             # 音色：我的音色、公开音色列表
│   │   ├── tts.py                # TTS：创建/查询任务（双入口）
│   │   ├── clone.py              # 克隆：创建/查询任务（双入口）
│   │   ├── shared.py             # 共享校验：音色权限、默认 project
│   │   ├── openapi_docs.py       # OpenAPI 接入文档（签名/幂等/错误码）
│   │   └── api_docs.py           # API 文档路由
│   ├── services/
│   │   ├── bootstrap.py          # 启动时创建管理员账号
│   │   ├── billing.py            # 计费：扣费/退款/调账（积分流水）
│   │   ├── kv.py                 # Redis/内存 KV：nonce、幂等键
│   │   ├── idempotency.py        # 幂等键读写封装
│   │   └── storage.py            # 本地文件存储：DATA_DIR、job_dir、/files 映射
│   └── tasks/
│       ├── celery_app.py         # Celery 初始化、队列路由
│       └── jobs.py               # 异步任务：run_tts_job/run_clone_job
├── data/                         # 生成的音频文件（通过 /files 访问）
├── docker-compose.yml            # Docker 编排：api + worker + redis
├── Dockerfile                    # Docker 镜像构建（基于 astral uv）
├── pyproject.toml                # uv 依赖清单
├── uv.lock                       # 依赖锁文件
└── README.md                     # 本文件
```

---

## OpenAPI 鉴权详解

OpenAPI 采用 **APIKey + Secret 的 HMAC-SHA256 签名鉴权**，并支持 **时间戳/nonce 防重放**。

### 必须携带的请求头

| 请求头 | 说明 | 示例 |
|--------|------|------|
| `X-API-Key` | API 密钥（公开） | `sk_live_abc123...` |
| `X-Timestamp` | Unix 时间戳（秒） | `1703145600` |
| `X-Nonce` | 随机字符串（防重放） | `uuid4()` |
| `X-Signature` | HMAC-SHA256 签名（hex） | `a1b2c3d4...` |
| `Idempotency-Key` | 幂等键（仅创建任务接口必填） | `uuid4()` |

### 签名计算

#### 1. 构造 Canonical String（签名原文）

```
METHOD\n
PATH\n
QUERY\n
BODY_SHA256\n
TIMESTAMP\n
NONCE
```

**注意事项：**
- `METHOD`：大写（如 `POST`、`GET`）
- `PATH`：如 `/openapi/tts/jobs`
- `QUERY`：原始 querystring（没有则为空字符串）
- `BODY_SHA256`：请求体原始 bytes 的 sha256 hex（JSON 必须用实际发送的 bytes）
- 每个字段后接 `\n`（最后一行 NONCE 后无换行）

#### 2. 计算 HMAC-SHA256

```python
import hmac
import hashlib

signature = hmac.new(
    api_secret.encode("utf-8"),
    canonical_string.encode("utf-8"),
    hashlib.sha256
).hexdigest()
```

### 防重放逻辑

- `X-Timestamp` 必须在 `SIGNATURE_TIME_WINDOW_SECONDS` 内（默认 300 秒）
- `X-Nonce` 在时间窗口内对同一 `X-API-Key` 必须唯一
- 实现：`nonce:{api_key}:{nonce}` 通过 Redis `SET NX EX` 存储

### 幂等键（Idempotency-Key）

**仅对以下接口必填：**
- `POST /openapi/tts/jobs`
- `POST /openapi/clone/jobs`

**作用：**防止客户端重试导致重复扣费/重复任务

**实现：**
- 键格式：`idem:{user_id}:{endpoint}:{key}`
- 存储：Redis，24小时过期
- 返回：首次创建返回任务 ID，后续返回相同任务 ID

---

## 双入口能力

以下功能**同时支持 Console 与 OpenAPI**：

### 1. 声音大厅（公开音色列表）

- `GET /console/voices/public`（JWT）
- `GET /openapi/voices/public`（签名）

### 2. TTS 合成（异步任务）

- `POST /console/tts/jobs`（JWT）
- `GET /console/tts/jobs/{job_id}`（JWT）
- `POST /openapi/tts/jobs`（签名 + Idempotency-Key）
- `GET /openapi/tts/jobs/{job_id}`（签名）

### 3. 音色克隆（异步任务）

- `POST /console/clone/jobs`（JWT，multipart）
- `GET /console/clone/jobs/{job_id}`（JWT）
- `POST /openapi/clone/jobs`（签名 + Idempotency-Key，multipart）
- `GET /openapi/clone/jobs/{job_id}`（签名）

---

## 本地文件访问

所有生成/预览音频存储在 `DATA_DIR`（默认 `./data` 或容器 `/data`），通过以下方式访问：

```
GET /files/{relative_path}
```

**示例：**
- TTS 输出：`/files/tts/123/output.wav`
- 音色预览：`/files/voices/456/preview.wav`

**映射逻辑：** 见 `app/services/storage.py`

---

## 数据库模型

### 核心表

| 表名 | 说明 |
|------|------|
| `users` | 用户账号（邮箱/密码/昵称/头像/订阅计划） |
| `api_keys` | API 密钥（key/secret 加密存储） |
| `credit_accounts` | 积分账户（用户余额） |
| `credit_transactions` | 积分流水（扣费/退款/调账） |
| `voices` | 音色（克隆结果，支持公开/私有） |
| `tts_jobs` | TTS 任务（异步队列） |
| `clone_jobs` | 克隆任务（异步队列） |
| `api_request_logs` | API 请求日志（Dashboard 统计） |

### 任务状态机

```
queued    → running   → succeeded
          ↘          ↘
                       failed
```

- **queued**：已入队，等待 Worker
- **running**：Worker 正在处理
- **succeeded**：成功产出结果
- **failed**：失败（触发退款）

---

## 常见问题

### 1. 如何升级订阅计划？

```bash
# 用户自己升级（需要实现支付）
POST /console/me/subscription/upgrade
{
  "plan": "pro",        # 或 "enterprise"
  "months": 1           # 订阅月数
}

# 或管理员手动调整
# （在数据库中修改 users.subscription_plan 和 subscription_ends_at）
```

### 2. 如何创建 API Key？

**仅企业版用户可创建：**

```bash
POST /console/api-keys
Authorization: Bearer {jwt_token}
{
  "name": "Production Key"
}

# 响应（api_secret 只返回一次，请妥善保管）
{
  "api_key": "sk_live_...",
  "api_secret": "secret_..."
}
```

### 3. 如何手动调账积分？

**仅管理员可操作：**

```bash
POST /console/admin/recharge
Authorization: Bearer {admin_jwt_token}
{
  "user_id": 1,
  "amount": 10000,
  "note": "活动赠送"
}
```

### 4. 如何查看任务日志？

```bash
# 查看 Celery Worker 日志
docker compose logs -f worker

# 查看数据库任务记录
SELECT * FROM tts_jobs WHERE status = 'failed';
```

### 5. 如何清空数据库重建？

```bash
# 方式1：删除数据库文件（SQLite）
rm fast_voice.db

# 方式2：执行迁移脚本
sqlite3 fast_voice.db < migrations/000_rebuild_schema.sql

# 方式3：修改环境变量（开发环境）
AUTO_CREATE_DB=true  # 每次启动自动重建（⚠️ 会清空所有数据）
```

---

## 测试

### 运行测试

```bash
# 所有测试
uv run pytest -v

# 指定文件
uv run pytest tests/test_console.py -v

# 覆盖率报告
uv run pytest --cov=app --cov-report=html
```

### 测试覆盖

- ✅ Console：注册/登录/JWT
- ✅ OpenAPI：签名鉴权、nonce 防重放
- ✅ 幂等键（Idempotency-Key）
- ✅ 计费：扣费/退款
- ✅ 订阅：计划配置、权限校验

---

## 性能优化建议

### 1. 数据库优化

- **连接池**：已配置（`db_pool_size=10, db_max_overflow=20`）
- **索引**：已在关键字段（email, api_key, status, created_at）添加索引
- **定期清理**：`api_request_logs` 表建议保留最近 90 天数据

### 2. 缓存优化

- **Dashboard 数据**：可缓存月度使用量（Redis，5分钟过期）
- **公开音色列表**：可缓存（Redis，10分钟过期）

### 3. 异步优化

- **日志记录**：可使用消息队列异步写入（避免影响 API 响应）
- **任务投递**：已异步（Celery）

---

## 安全考虑

### 1. 密码安全

- ✅ bcrypt 哈希（自动加盐）
- ✅ 最小长度 6 字符

### 2. API Secret 安全

- ✅ Fernet 加密存储
- ✅ 只在创建时返回一次
- ✅ 列表接口脱敏显示（`sk_live_...844f`）

### 3. 防重放攻击

- ✅ 时间戳窗口（5分钟）
- ✅ Nonce 唯一性（Redis）

### 4. 幂等保护

- ✅ Idempotency-Key（24小时有效期）
- ✅ 防止重复扣费

---

## 后续优化方向

### 功能增强

- [ ] 支付集成（支付宝/微信/Stripe）
- [ ] 头像上传（目前只支持 URL）
- [ ] Webhook 通知（任务完成/余额不足）
- [ ] 邮件通知（订阅到期/配额告警）
- [ ] API Key 权限细化（读/写分离）

### 性能提升

- [ ] CDN 加速（音频文件）
- [ ] 音频流式输出（SSE/WebSocket）
- [ ] 分布式锁（Redis）
- [ ] 任务优先级队列

### 监控运维

- [ ] Prometheus 指标导出
- [ ] ELK 日志收集
- [ ] Sentry 错误追踪
- [ ] APM 性能监控

---
