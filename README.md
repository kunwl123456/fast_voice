# fast_voice（V1）

## 项目简介

fast_voice 是一个**开放平台式的 TTS（文本转语音）服务**，提供 Console（用户管理控制台）和 OpenAPI（B端集成接口）两种访问方式。

---

## 技术栈

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-20.10+-2496ED?style=flat&logo=docker&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0.36-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.4.0-37814A?style=flat&logo=celery&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-2.10.3-E92063?style=flat&logo=pydantic&logoColor=white)
![uv](https://img.shields.io/badge/uv-Package_Manager-DE5FE9?style=flat&logo=astral&logoColor=white)
![pre-commit](https://img.shields.io/badge/pre--commit-Enabled-FAB040?style=flat&logo=pre-commit&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-0.1.14-D7FF64?style=flat&logo=ruff&logoColor=black)
![Black](https://img.shields.io/badge/Black-24.1.0-000000?style=flat&logo=python&logoColor=white)

### 服务架构

```
┌─────────────────────────────────────────────────────────┐
│                       Nginx/Caddy                       │
│                    (可选，反向代理)                      │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI API (异步)                    │
│            Uvicorn + SQLAlchemy + Redis                 │
└─────────────────────────────────────────────────────────┘
          │                      │                    │
          ▼                      ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   PostgreSQL     │  │      Redis       │  │  Celery Worker   │
│   (主数据库)     │  │ (缓存/队列/锁)   │  │  (异步任务)      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 核心功能

- **Console（C 端用户入口）**
  - 用户系统：注册/登录、修改昵称/密码/头像（支持上传和 URL）
  - 订阅管理：免费版/专业版/企业版三种计划，升级赠送积分
  - 积分账户：余额查询、流水记录（最近 200 条）、管理员调账
  - API Key 管理：创建、列表、删除、轮换（仅企业版）
  - 音色管理：我的音色、官方音色、公开音色、标签筛选、点赞/取消点赞
  - 任务管理：TTS 合成任务、音色克隆任务（支持 SSE 实时状态推送）
  - Dashboard：仪表盘概览、每日用量统计、请求日志（分页查询）

- **OpenAPI（B 端集成入口）**
  - Bearer Token 鉴权（API Key 以 sk- 开头）
  - 有效期管理（创建时可自定义天数）
  - 幂等键（Idempotency-Key）支持（TTS 和克隆任务必填）
  - 异步任务：TTS 合成、音色克隆（支持 SSE 实时状态推送）
  - 音色服务：官方音色列表、公开音色列表（支持标签筛选）、标签分类查询

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

### 4. 开发工具配置

#### Git Hooks（pre-commit）

项目使用 pre-commit 自动检查代码质量：

```bash
# 安装 pre-commit
pip install pre-commit

# 安装 Git hooks
pre-commit install

# 手动运行所有检查
pre-commit run --all-files

# 每次 git commit 时会自动运行：
# - ruff --fix（自动修复代码问题）
# - black（格式化代码）
```

**配置文件：`.pre-commit-config.yaml`**

```yaml
default_language_version:
    python: python3.12
repos:
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.14
    hooks:
      - id: ruff
        args: [ "--fix"]

  - repo: https://github.com/psf/black-pre-commit-mirror
    rev: '24.1.0'
    hooks:
      - id: black
        language_version: python3.12
```

#### 数据库连接池配置

```bash
# SQLAlchemy 连接池（仅对 Postgres 生效，SQLite 使用 StaticPool）
DB_POOL_SIZE=10                 # 连接池大小
DB_MAX_OVERFLOW=20              # 最大溢出连接数
DB_POOL_TIMEOUT_SECONDS=30      # 获取连接超时（秒）
DB_POOL_RECYCLE_SECONDS=1800    # 连接回收时间（秒，30分钟）
```

#### 本地开发（热重载）

```bash
# 开发模式启动（支持代码热重载）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 查看日志级别
uv run uvicorn app.main:app --log-level debug

# Worker 开发模式（DEBUG 日志）
uv run celery -A app.tasks.celery_app:celery_app worker -l DEBUG -Q tts,clone
```

---

## 项目结构

```
fast_voice/
├── app/                          # 后端代码（FastAPI + SQLAlchemy + Celery）
│   ├── main.py                   # 入口：中间件、路由挂载、建表、静态文件
│   ├── core/
│   │   ├── config.py             # 配置：环境变量（DB/Redis/JWT/计费等）
│   │   ├── security.py           # 安全：密码哈希、JWT、API Key 验证
│   │   └── utils.py              # 工具函数
│   ├── db.py                     # SQLAlchemy 异步引擎/会话（带连接池）
│   ├── db_sync.py                # SQLAlchemy 同步引擎（Celery 使用）
│   ├── models.py                 # 数据模型：User/ApiKey/Voice/Job/Log 等
│   ├── schemas.py                # Pydantic 请求/响应结构
│   ├── deps.py                   # FastAPI 依赖：DB、JWT、Bearer Token 鉴权
│   ├── responses.py              # 统一响应格式（success/error）
│   ├── exceptions.py             # 自定义异常类
│   ├── subscription.py           # 订阅计划配置（免费/专业/企业版）
│   ├── voice_tags.py             # 音色标签配置和验证
│   ├── views/
│   │   ├── console.py            # Console 路由：Dashboard、使用统计、请求日志
│   │   ├── account.py            # 账户路由：注册/登录/修改信息/头像
│   │   ├── subscription.py       # 订阅路由：查询/升级订阅
│   │   ├── api_keys.py           # API Key 路由：创建/列表/删除/轮换
│   │   ├── credits.py            # 积分路由：余额/流水/管理员充值
│   │   ├── voices.py             # 音色路由：我的音色/官方音色/公开音色/标签
│   │   ├── tts.py                # TTS 路由：创建/查询任务（双入口+SSE）
│   │   ├── clone.py              # 克隆路由：创建/查询任务（双入口）
│   │   └── shared.py             # 共享校验：音色权限
│   ├── controller/
│   │   ├── account.py            # 账户控制器：注册/登录/修改
│   │   ├── api_keys.py           # API Key 控制器
│   │   ├── console.py            # 控制台控制器：Dashboard 数据
│   │   └── credits.py            # 积分控制器
│   ├── services/
│   │   ├── bootstrap.py          # 启动时创建管理员账号
│   │   ├── billing.py            # 计费：扣费/退款/调账（积分流水）
│   │   ├── billing_sync.py       # 同步计费（Celery 使用）
│   │   ├── kv.py                 # Redis/内存 KV：nonce、幂等键
│   │   ├── idempotency.py        # 幂等键读写封装
│   │   ├── credit.py             # 积分服务
│   │   └── storage.py            # 本地文件存储：DATA_DIR、job_dir、/files 映射
│   ├── tasks/
│   │   ├── celery_app.py         # Celery 初始化、队列路由
│   │   └── jobs.py               # 异步任务：run_tts_job/run_clone_job
│   └── static/
│       └── avatars/              # 静态资源：头像图片
├── data/                         # 生成的音频文件（通过 /files 访问）
├── docs/                         # 文档目录
├── test/                         # 测试代码
├── docker-compose.yml            # Docker 编排：api + worker + db + redis
├── Dockerfile                    # Docker 镜像构建（基于 astral uv）
├── pyproject.toml                # uv 依赖清单
├── uv.lock                       # 依赖锁文件
├── .pre-commit-config.yaml       # pre-commit 配置
└── README.md                     # 本文件
```

---

## OpenAPI 鉴权详解

OpenAPI 采用 **Bearer Token 鉴权**，简单安全。

### 鉴权方式

使用标准的 HTTP Authorization 头部携带 API Key：

```bash
Authorization: Bearer sk-xxxxxxxxxxxxxxxxx
```

### API Key 格式

- **前缀**：以 `sk-` 开头
- **生成**：系统自动生成，32 字节随机字符串
- **有效期**：创建时可自定义天数（`expires_days` 参数），为空则永久有效
- **管理**：通过 Console 创建、查看、删除、轮换

### 使用示例

```bash
# 获取公开音色列表
curl -X GET https://api.yourdomain.com/openapi/voices/public \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxx"

# 获取公开音色列表（带标签筛选）
curl -X GET "https://api.yourdomain.com/openapi/voices/public?tags=中文&tags=女&limit=50" \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxx"

# 创建 TTS 任务
curl -X POST https://api.yourdomain.com/openapi/tts/jobs \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "clone_job_id": "clone-job-uuid-here",
    "text": "Hello, world!",
    "speed_factor": 1.0,
    "temperature": 1.0,
    "top_k": 5,
    "top_p": 1.0,
    "webhook_url": ""
  }'
```

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
| `users` | 用户账号（邮箱/密码/昵称/头像/订阅计划/UUID 对外标识） |
| `api_keys` | API 密钥（以 sk- 开头，支持有效期管理和禁用功能） |
| `credit_accounts` | 积分账户（用户余额） |
| `credit_transactions` | 积分流水（扣费/退款/调账/订阅赠送） |
| `voices` | 音色（克隆结果，支持公开/私有、标签、点赞、使用统计） |
| `tts_jobs` | TTS 任务（异步队列，支持 webhook 回调、多种采样参数） |
| `clone_jobs` | 克隆任务（异步队列，支持标签、去噪、外部请求追踪） |
| `api_request_logs` | API 请求日志（Dashboard 统计，记录延迟和响应大小） |

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
Content-Type: application/json

{
  "name": "Production Key",
  "expires_days": 365  # 可选，不指定则永久有效
}

# 响应（API Key 以 sk- 开头）
{
  "message": "API Key 创建成功",
  "data": {
    "api_key": "sk-xxxxxxxxxxxxxxxxx",
    "name": "Production Key",
    "is_active": true,
    "expires_at": "2026-12-25T10:30:00+08:00",  # 如果指定了有效期
    "created_at": "2025-12-25T10:30:00+08:00"
  }
}
```

**使用 API Key：**

```bash
# 直接在 Authorization 头部使用
curl -X GET https://api.yourdomain.com/openapi/voices/public \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxx"
```

**API Key 轮换：**

```bash
# 轮换会禁用所有旧的 API Key，并创建一个新的
POST /console/api-keys/rotate
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "name": "Rotated Key",
  "expires_days": 365
}
```

### 3. 如何手动调账积分？

**仅管理员可操作：**

```bash
POST /console/admin/credits/recharge
Authorization: Bearer {admin_jwt_token}
Content-Type: application/json

{
  "user_id": 1,
  "amount": 10000,
  "note": "活动赠送"
}

# 响应
{
  "message": "充值成功",
  "data": {
    "user_id": 1,
    "amount": 10000,
    "new_balance": 20000,
    "note": "活动赠送"
  }
}
```
---

## 调试技巧

### 1. 启用详细日志

```python
# app/run.py
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

### 2. 查看 SQL 查询

```python
# app/db.py
engine = create_async_engine(
    settings.database_url,
    echo=True,  # 打印所有 SQL 查询
)
```

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

## 监控与告警

### 1. 性能监控指标

| 指标 | 说明 | 告警阈值 |
|------|------|----------|
| **API 响应时间** | P50/P95/P99 延迟 | P95 > 500ms |
| **数据库连接数** | 活跃连接 | > 80% 池大小 |
| **Redis 内存** | 内存使用率 | > 80% |
| **Celery 队列长度** | 待处理任务数 | > 1000 |
| **磁盘空间** | 数据目录使用率 | > 80% |
| **错误率** | 5xx 错误比例 | > 1% |

### 2. 日志聚合（ELK）

```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/fast_voice/*.log
    fields:
      service: fast_voice
      environment: production

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
```

### 3. 错误追踪（Sentry）

```python
# app/run.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://xxx@sentry.io/xxx",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment="production",
)
```

---

## 后续优化方向

### 功能增强

- [ ] 支付集成（支付宝/微信/Stripe）
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
