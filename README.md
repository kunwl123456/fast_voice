# fast_voice（V1）

## 项目简介

fast_voice 是一个**开放平台式的 TTS（文本转语音）服务**，提供 Console（用户管理控制台）和 OpenAPI（B端集成接口）两种访问方式。

---

## 技术栈

### 核心框架

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.11+ | 编程语言 |
| **FastAPI** | 0.115.6 | Web 框架（异步 API） |
| **Uvicorn** | 0.34.0 | ASGI 服务器 |
| **SQLAlchemy** | 2.0.36 | ORM（异步支持） |
| **Pydantic** | 2.10.3 | 数据验证 |
| **Celery** | 5.4.0 | 分布式任务队列 |

### 数据库

| 组件 | 版本 | 说明 |
|------|------|------|
| **PostgreSQL** | 16 | 生产环境数据库（推荐） |
| **asyncpg** | 0.30.0 | Postgres 异步驱动（SQLAlchemy） |
| **psycopg** | 3.2.3 | Postgres 同步驱动（Celery） |
| **SQLite** | - | 本地开发/测试（通过 aiosqlite） |
| **aiosqlite** | 0.20.0 | SQLite 异步驱动 |

### 缓存与队列

| 组件 | 版本 | 用途 |
|------|------|------|
| **Redis** | 7 | Nonce 防重放、幂等键、Celery Broker |
| **redis-py** | 5.2.1 | Redis Python 客户端 |

### 安全与加密

| 组件 | 版本 | 用途 |
|------|------|------|
| **passlib** | 1.7.4 | 密码哈希（bcrypt） |
| **bcrypt** | 4.0.1 | bcrypt 加密算法 |
| **python-jose** | 3.3.0 | JWT 签发与验证 |

### 依赖管理

| 工具 | 说明 |
|------|------|
| **uv** | Astral 出品的极速 Python 包管理器 |
| **pyproject.toml** | 项目依赖清单（PEP 621） |
| **uv.lock** | 依赖锁文件（可重复构建） |

### 开发工具

| 工具 | 版本 | 用途 |
|------|------|------|
| **pytest** | 8.3.4 | 测试框架 |
| **httpx** | 0.28.1 | HTTP 客户端（测试用） |
| **Docker** | - | 容器化部署 |
| **Docker Compose** | - | 多容器编排 |

### 容器化

```dockerfile
# 基础镜像：Astral uv 官方镜像
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# 特点：
# - 预装 uv，无需单独安装
# - Python 3.11 + Debian Bookworm
# - 镜像体积小，构建速度快
```

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
  - 用户系统：注册/登录、修改昵称/密码/头像
  - 订阅管理：免费版/专业版/企业版三种计划
  - 积分账户：余额查询、流水记录、管理员调账
  - API Key 管理：创建、列表、删除（仅企业版）
  - 音色管理：我的音色、公开/私有设置
  - 任务管理：TTS 合成任务、音色克隆任务
  - Dashboard：使用统计、请求日志、配额监控

- **OpenAPI（B 端集成入口）**
  - Bearer Token 鉴权（API Key 以 sk- 开头）
  - 有效期管理（默认 1 年）
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

# 计费配置
CREDIT_PRICE_PER_UTF8_BYTE=1
MAX_TEXT_UTF8_BYTES=4000

# 数据目录（生成的音频文件存储路径）
DATA_DIR=./data

# 开发模式（自动建表）
AUTO_CREATE_DB=true
```

### 4. 开发工具配置

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
```

---

### 数据库管理

#### 连接数据库（本地开发）

```bash
# SQLite
sqlite3 fast_voice.db
.tables              # 查看所有表
.schema users        # 查看表结构

# PostgreSQL
psql -U postgres -d fast_voice
\dt                  # 查看所有表
\d+ users            # 查看表结构
```

#### 执行迁移脚本

```bash
# SQLite
sqlite3 fast_voice.db < migrations/004_add_user_avatar.sql

# PostgreSQL
psql -U postgres -d fast_voice -f migrations/004_add_user_avatar.sql
```

#### 数据备份与恢复

```bash
# SQLite 备份
cp fast_voice.db fast_voice.db.backup

# PostgreSQL 备份
pg_dump -U postgres fast_voice > backup.sql

# PostgreSQL 恢复
psql -U postgres fast_voice < backup.sql
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

OpenAPI 采用 **Bearer Token 鉴权**，简单安全。

### 鉴权方式

使用标准的 HTTP Authorization 头部携带 API Key：

```bash
Authorization: Bearer sk-xxxxxxxxxxxxxxxxx
```

### API Key 格式

- **前缀**：以 `sk-` 开头
- **生成**：系统自动生成，32 字节随机字符串
- **有效期**：默认 1 年，可在创建时自定义
- **管理**：通过 Console 创建、查看、删除

### 使用示例

```bash
# 获取公开音色列表
curl -X GET https://api.yourdomain.com/openapi/voices/public \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxx"

# 创建 TTS 任务
curl -X POST https://api.yourdomain.com/openapi/tts/jobs \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "voice_id": 1,
    "text": "Hello, world!"
  }'
```

### Python 客户端示例

```python
import requests

# API Key（从 Console 创建）
API_KEY = "sk-xxxxxxxxxxxxxxxxx"

# 请求头
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 创建 TTS 任务
response = requests.post(
    "https://api.yourdomain.com/openapi/tts/jobs",
    headers={
        **headers,
        "Idempotency-Key": "unique-request-id-123"
    },
    json={
        "voice_id": 1,
        "text": "Hello, world!"
    }
)

print(response.json())
# {"message": "任务创建成功", "data": {"job_id": 123, "status": "queued"}}
```

### 有效期管理

- 创建时自动设置有效期（默认 1 年）
- 过期后 API Key 自动失效
- 可通过 Console 查看剩余有效期
- 建议定期轮换 API Keys

### 幂等键（Idempotency-Key）

**仅对以下接口必填：**
- `POST /openapi/tts/jobs`
- `POST /openapi/clone/jobs`

**作用：**防止客户端重试导致重复扣费/重复任务

**实现：**
- 键格式：`idem:{user_id}:{endpoint}:{key}`
- 存储：Redis，24小时过期
- 返回：首次创建返回任务 ID，后续返回相同任务 ID

**使用建议：**
- 使用 UUID 或其他唯一标识
- 同一 Idempotency-Key 24 小时内只会创建一次任务
- 不同任务使用不同的 Idempotency-Key

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
| `api_keys` | API 密钥（以 sk- 开头，支持有效期管理） |
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

# 响应（API Key 以 sk- 开头，默认有效期 1 年）
{
  "message": "API Key 创建成功",
  "data": {
    "api_key": "sk-xxxxxxxxxxxxxxxxx",
    "expires_at": "2026-12-23T10:30:00+08:00"
  }
}
```

**使用 API Key：**

```bash
# 直接在 Authorization 头部使用
curl -X GET https://api.yourdomain.com/openapi/voices/public \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxx"
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

### 测试最佳实践

#### 1. 使用 Fixture 管理测试数据

```python
import pytest
from app.db import AsyncSessionLocal
from app.models import User
from app.core.security import hash_password

@pytest.fixture
async def test_user():
    """创建测试用户"""
    async with AsyncSessionLocal() as db:
        user = User(
            email="test@example.com",
            password_hash=hash_password("password123"),
            display_name="Test User"
        )
        db.add(user)
        await db.commit()
        yield user
        await db.delete(user)
        await db.commit()
```

#### 2. Mock 外部依赖

```python
from unittest.mock import patch

@patch('app.tasks.jobs.run_tts_job.apply_async')
async def test_create_tts_job(mock_celery):
    """测试 TTS 任务创建（不真正执行 Celery）"""
    mock_celery.return_value.id = "mock-task-id"
    # 测试逻辑...
```

#### 3. 测试数据库隔离

```bash
# 使用独立的测试数据库
DATABASE_URL=sqlite+aiosqlite:///./test.db uv run pytest
```

---

## 开发工作流

### 1. 新功能开发流程

```bash
# 1. 创建功能分支
git checkout -b feature/new-feature

# 2. 编写代码
# - 修改 models.py（如需新增表）
# - 修改 schemas.py（请求/响应）
# - 修改 routes/（API 端点）
# - 修改 services/（业务逻辑）

# 3. 编写迁移脚本（如有数据库变更）
vim migrations/005_add_new_feature.sql

# 4. 编写测试
vim tests/test_new_feature.py
uv run pytest tests/test_new_feature.py -v

# 5. 代码检查
ruff check app/
mypy app/

# 6. 格式化代码
black app/ tests/
isort app/ tests/

# 7. 提交代码
git add .
git commit -m "feat: 新增 XXX 功能"
git push origin feature/new-feature

# 8. 创建 Pull Request
```

### 2. Bug 修复流程

```bash
# 1. 创建修复分支
git checkout -b fix/bug-description

# 2. 编写失败测试（重现 Bug）
vim tests/test_bug.py
uv run pytest tests/test_bug.py -v  # 应该失败

# 3. 修复代码
vim app/routes/xxx.py

# 4. 验证测试通过
uv run pytest tests/test_bug.py -v  # 应该成功

# 5. 提交代码
git commit -m "fix: 修复 XXX 问题"
```

### 3. 数据库迁移流程

```bash
# 1. 编写迁移脚本
vim migrations/006_add_new_column.sql

# 2. 本地测试迁移
sqlite3 fast_voice.db < migrations/006_add_new_column.sql

# 3. 验证表结构
sqlite3 fast_voice.db
.schema table_name

# 4. 更新 models.py
vim app/models.py

# 5. 重启服务测试
uv run uvicorn app.main:app --reload

# 6. 提交代码
git add migrations/006_add_new_column.sql app/models.py
git commit -m "feat: 数据库新增 XXX 字段"
```

### 4. 代码审查清单

- [ ] 代码符合 PEP 8 规范
- [ ] 所有函数/类有类型注解
- [ ] 关键逻辑有注释说明
- [ ] 新增功能有对应测试
- [ ] 数据库变更有迁移脚本
- [ ] API 变更更新了文档
- [ ] 敏感信息（密钥、密码）未硬编码
- [ ] 错误处理完整（try/except）
- [ ] 日志记录适当（logger.info/error）

---

## 调试技巧

### 1. 启用详细日志

```python
# app/main.py
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

### 2. 使用 pdb 调试

```python
# 在需要调试的地方插入
import pdb; pdb.set_trace()

# 或使用 breakpoint()（Python 3.7+）
breakpoint()
```

### 3. 查看 SQL 查询

```python
# app/db.py
engine = create_async_engine(
    settings.database_url,
    echo=True,  # 打印所有 SQL 查询
)
```

### 4. 测试 OpenAPI 签名

```python
# 使用内置的签名工具测试
from app.core.security import compute_signature

canonical_string = "POST\n/openapi/tts/jobs\n\nsha256...\n1703145600\nnonce123"
signature = compute_signature(api_secret, canonical_string)
print(signature)
```

### 5. Docker 日志查看

```bash
# 查看 API 日志
docker compose logs -f api

# 查看 Worker 日志
docker compose logs -f worker

# 查看所有日志
docker compose logs -f

# 查看最近 100 行
docker compose logs --tail=100 api
```

### 6. Redis 调试

```bash
# 进入 Redis 容器
docker compose exec redis redis-cli

# 查看所有键
KEYS *

# 查看 nonce 键
KEYS nonce:*

# 查看幂等键
KEYS idem:*

# 查看键的值和过期时间
GET nonce:sk_live_xxx:uuid123
TTL nonce:sk_live_xxx:uuid123
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

## 安全考虑

### 1. 密码安全

- ✅ bcrypt 哈希（自动加盐）
- ✅ 最小长度 6 字符

### 2. API Key 安全

- ✅ 以 `sk-` 开头，32 字节随机字符串
- ✅ 支持有效期管理（默认 1 年）
- ✅ 列表接口脱敏显示（`sk-...xxx`）
- ✅ 支持随时禁用/删除

### 3. 有效期管理

- ✅ 创建时设置有效期（默认 1 年）
- ✅ 过期自动失效
- ✅ 支持查看剩余有效期

### 4. 幂等保护

- ✅ Idempotency-Key（24小时有效期）
- ✅ 防止重复扣费

---

## 生产部署

### 部署清单

#### 1. 环境准备

- [ ] 服务器（推荐 Ubuntu 22.04 LTS）
- [ ] Docker + Docker Compose
- [ ] PostgreSQL 16（或 RDS）
- [ ] Redis 7（或 ElastiCache）
- [ ] 域名 + SSL 证书
- [ ] 防火墙配置（开放 80/443 端口）

#### 2. 安全配置

```bash
# 生成强密钥
JWT_SECRET=$(openssl rand -hex 32)

# 修改默认管理员密码
ADMIN_PASSWORD=$(openssl rand -base64 16)
```

#### 3. 生产环境变量

```bash
# .env.production
DATABASE_URL=postgresql+asyncpg://user:strong_pass@db_host:5432/fast_voice
DATABASE_URL_SYNC=postgresql+psycopg://user:strong_pass@db_host:5432/fast_voice
REDIS_URL=redis://:redis_pass@redis_host:6379/0
CELERY_BROKER_URL=redis://:redis_pass@redis_host:6379/1
CELERY_RESULT_BACKEND=redis://:redis_pass@redis_host:6379/2

JWT_SECRET=<生成的强密钥>
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=<强密码>

# 生产环境关闭自动建表
AUTO_CREATE_DB=false
ADMIN_BOOTSTRAP=true

# 性能优化
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT_SECONDS=30
DB_POOL_RECYCLE_SECONDS=1800
```

#### 4. Nginx 反向代理

```nginx
# /etc/nginx/sites-available/fast_voice
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 限制请求体大小（音频上传）
    client_max_body_size 100M;

    # 超时配置
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件（音频）
    location /files/ {
        proxy_pass http://127.0.0.1:8000/files/;
        proxy_buffering off;
        add_header Cache-Control "public, max-age=3600";
    }
}
```

#### 5. Systemd 服务（非 Docker）

```ini
# /etc/systemd/system/fast-voice-api.service
[Unit]
Description=Fast Voice API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/fast_voice
Environment="PATH=/opt/fast_voice/.venv/bin"
EnvironmentFile=/opt/fast_voice/.env.production
ExecStart=/usr/local/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/fast-voice-worker.service
[Unit]
Description=Fast Voice Celery Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/fast_voice
Environment="PATH=/opt/fast_voice/.venv/bin"
EnvironmentFile=/opt/fast_voice/.env.production
ExecStart=/usr/local/bin/uv run celery -A app.tasks.celery_app:celery_app worker -l INFO -Q tts,clone --concurrency=4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable fast-voice-api fast-voice-worker
sudo systemctl start fast-voice-api fast-voice-worker

# 查看状态
sudo systemctl status fast-voice-api
sudo systemctl status fast-voice-worker
```

#### 6. Docker Compose 生产配置

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  api:
    build: .
    restart: always
    env_file: .env.production
    volumes:
      - /opt/fast_voice/data:/data
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build: .
    restart: always
    command: ["uv", "run", "celery", "-A", "app.tasks.celery_app:celery_app", "worker", "-l", "INFO", "-Q", "tts,clone", "--concurrency=4"]
    env_file: .env.production
    volumes:
      - /opt/fast_voice/data:/data
    depends_on:
      - db
      - redis

  db:
    image: postgres:16
    restart: always
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_DB: fast_voice
    volumes:
      - /opt/fast_voice/pgdata:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"

  redis:
    image: redis:7
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - /opt/fast_voice/redis:/data
    ports:
      - "127.0.0.1:6379:6379"
```

```bash
# 启动生产环境
docker compose -f docker-compose.prod.yml up -d

# 查看日志
docker compose -f docker-compose.prod.yml logs -f

# 重启服务
docker compose -f docker-compose.prod.yml restart api worker
```

#### 7. 数据库初始化

```bash
# 执行所有迁移脚本
for f in migrations/*.sql; do
    psql -U postgres -d fast_voice -f "$f"
done

# 或手动创建表（如果 AUTO_CREATE_DB=false）
psql -U postgres -d fast_voice -f schema.sql
```

#### 8. 监控与日志

```bash
# 日志轮转（/etc/logrotate.d/fast-voice）
/var/log/fast_voice/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 www-data www-data
    sharedscripts
    postrotate
        systemctl reload fast-voice-api
    endscript
}

# Prometheus 监控（可选）
# 安装 prometheus-fastapi-instrumentator
uv add prometheus-fastapi-instrumentator

# app/main.py
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

#### 9. 备份策略

```bash
# 数据库自动备份脚本
#!/bin/bash
# /opt/scripts/backup-db.sh
BACKUP_DIR=/opt/backups/fast_voice
DATE=$(date +%Y%m%d_%H%M%S)

# 备份数据库
pg_dump -U postgres fast_voice | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# 备份音频文件
tar -czf $BACKUP_DIR/data_$DATE.tar.gz /opt/fast_voice/data

# 删除 30 天前的备份
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

# 添加到 crontab
# 0 2 * * * /opt/scripts/backup-db.sh
```

#### 10. 健康检查

```python
# app/routes/health.py
from fastapi import APIRouter
from app.db import AsyncSessionLocal

router = APIRouter()

@router.get("/health")
async def health_check():
    """健康检查端点"""
    # 检查数据库连接
    try:
        async with AsyncSessionLocal() as db:
            await db.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "error"
    
    return {
        "status": "ok" if db_status == "ok" else "error",
        "database": db_status,
    }
```

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
# app/main.py
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
