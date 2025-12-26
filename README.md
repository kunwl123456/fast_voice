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

### 📱 Console API（C 端用户控制台，`/console` 前缀）

#### 1. 账户与认证
- 用户注册（需要邀请码）、账号登录、获取当前用户信息
- 修改昵称、更新头像（支持文件上传和 URL）、修改密码

#### 2. 订阅管理
- 查询当前订阅计划（免费版/专业版/企业版）
- 升级订阅（自动赠送对应积分）

#### 3. 积分管理
- 查询积分余额（自动创建账户）
- 查询积分交易流水（最近 200 条）

#### 4. API Key 管理（仅企业版）
- 创建 API Key（自定义名称和有效期）
- 查看 API Key 列表（脱敏显示）
- 删除指定 API Key
- 轮换 API Key（禁用旧 Key，创建新 Key）

#### 5. 声音管理
- 我的音色列表（用户创建的音色）
- 官方音色列表（autogame 官方提供）
- 公开音色列表（社区分享，支持标签筛选和排序）
- 音色标签分类查询（性别、年龄、场景、情感等）
- 点赞/取消点赞音色
- 修改音色信息（名称、描述、标签、公开状态）

#### 6. TTS 任务
- 创建 TTS 合成任务（基于克隆音色）
- 查询任务详情和状态
- SSE 实时推送任务进度（支持 Redis Pub/Sub 和降级轮询）

#### 7. 音色克隆
- 创建克隆任务（上传音频文件）
- 查询克隆任务详情
- 自动生成音色并关联到用户

#### 8. 控制台 Dashboard
- 仪表盘概览（账户信息、订阅状态、积分余额、本月使用量）
- 每日用量统计（指定天数的 API 调用统计）
- API 请求日志（分页查询，包含请求详情和性能指标）

---

### 🔌 OpenAPI（B 端集成接口，`/openapi` 前缀）

#### 认证方式
- Bearer Token 鉴权（API Key 格式：`sk-xxxxxxxx`）
- API Key 有效期管理（创建时可自定义天数）
- 仅限企业版用户使用

#### 幂等性保证
- TTS 和克隆任务支持幂等键（`Idempotency-Key` 请求头）
- 相同幂等键重复请求返回相同结果（TTL: 1 小时）

#### TTS 服务
- 创建 TTS 合成任务（支持幂等）
- 查询任务详情和结果
- SSE 实时推送任务状态更新

#### 音色克隆
- 创建克隆任务（上传音频，支持幂等）
- 查询克隆任务状态和结果

#### 音色服务
- 官方音色列表（支持标签筛选、排序、分页）
- 公开音色列表（社区角色市场）
- 音色标签分类查询

---

### 👨‍💼 Admin API（管理员接口，`/admin` 前缀）

#### 积分管理
- 为用户充值积分（记录流水和备注）

#### 邀请码管理
- 批量生成邀请码（可设置有效期和备注）
- 查看邀请码列表（支持筛选未使用的）
- 删除未使用的邀请码

---

### 📚 文档接口（`/docs` 前缀）

- 错误码列表（支持模块和状态码筛选）
- 错误码分组查询（按模块分组）
- 错误码 Markdown 文档导出
- 错误码 HTML 预览页面（实时生成，与代码同步）

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

### 4. 开发工具

项目使用现代化的开发工具链保证代码质量：

- **pre-commit** - Git 提交时自动检查代码（Ruff + Black）
- **Ruff** - 快速的 Python 代码检查器和格式化工具
- **Black** - 自动代码格式化，统一代码风格
- **SQLAlchemy 2.0** - 异步 ORM，支持连接池配置
- **Uvicorn** - 高性能 ASGI 服务器，支持热重载

#### 快速开始

```bash
# 安装 pre-commit hooks
pre-commit install

# 开发模式启动（热重载）
python run.py

# Celery Worker 开发模式
uv run celery -A app.tasks.celery_app:celery_app worker -l DEBUG -Q tts,clone
```

📖 **详细配置请参考：[开发指南](docs/DEVELOPMENT.md)**

---

## 项目结构

```
fast_voice/
├── app/                                # 后端应用（FastAPI + SQLAlchemy + Celery）
│   ├── main.py                         # 应用入口：中间件、异常处理、路由注册
│   ├── routers.py                      # 路由注册中心：14 个 APIRouter 统一定义
│   │
│   ├── core/                           # 核心模块
│   │   ├── config.py                   # 配置管理：环境变量（Pydantic Settings）
│   │   ├── constants.py                # 常量定义：订阅计划、音色标签等
│   │   ├── db.py                       # 数据库：异步引擎/会话（带连接池）
│   │   ├── db_sync.py                  # 数据库：同步引擎（Celery 使用）
│   │   ├── models.py                   # 数据模型：User/Voice/Job/Credit 等（12 个表）
│   │   ├── schemas.py                  # Pydantic Schema：请求/响应结构
│   │   ├── deps.py                     # FastAPI 依赖：DB 会话、鉴权
│   │   ├── security.py                 # 安全：密码哈希、JWT、API Key 验证
│   │   ├── responses.py                # 统一响应：success_response/error_response
│   │   ├── exceptions.py               # 自定义异常：业务异常类
│   │   ├── error_codes.py              # 错误码定义：8 位数字编码系统
│   │   ├── middlewares.py              # 中间件：OpenAPI 请求日志
│   │   ├── openapi.py                  # OpenAPI 配置：Swagger 文档定制
│   │   └── utils.py                    # 工具函数
│   │
│   ├── api/                            # API 层
│   │   ├── views/                      # 路由处理器（从 routers 引用路由）
│   │   │   ├── account.py              # 账户与认证：注册/登录/修改
│   │   │   ├── api_keys.py             # API Key 管理：创建/删除/轮换
│   │   │   ├── console.py              # 控制台：Dashboard/统计/日志
│   │   │   ├── credits.py              # 积分管理：余额/流水
│   │   │   ├── subscription.py         # 订阅管理：查询/升级
│   │   │   ├── voices.py               # 声音管理：我的/官方/公开音色
│   │   │   ├── tts.py                  # TTS 服务：Console + OpenAPI（SSE）
│   │   │   ├── clone.py                # 克隆服务：Console + OpenAPI
│   │   │   └── docs.py                 # 文档接口：错误码查询/导出
│   │   │
│   │   ├── controller/                 # 业务控制器（业务逻辑封装）
│   │   │   ├── account.py              # 账户控制器
│   │   │   ├── api_keys.py             # API Key 控制器
│   │   │   ├── console.py              # 控制台控制器
│   │   │   ├── credits.py              # 积分控制器
│   │   │   ├── invite_codes.py         # 邀请码控制器
│   │   │   └── subscription.py         # 订阅控制器
│   │   │
│   │   └── services/                   # 基础服务层
│   │       ├── account.py              # 账户服务
│   │       ├── bootstrap.py            # 启动初始化：管理员账号
│   │       ├── billing.py              # 计费服务：扣费/退款
│   │       ├── billing_sync.py         # 同步计费（Celery）
│   │       ├── kv.py                   # KV 存储：Redis/内存
│   │       ├── idempotency.py          # 幂等键管理
│   │       ├── redis_pubsub.py         # Redis Pub/Sub：任务状态推送
│   │       ├── redis_pubsub_sync.py    # Redis Pub/Sub 同步版本
│   │       ├── storage.py              # 文件存储：本地文件管理
│   │       └── voice_tags.py           # 音色标签：配置/验证
│   │
│   ├── admin/                          # 管理员模块
│   │   └── views/                      # Admin 路由处理器
│   │       ├── credit.py               # 积分管理：充值
│   │       └── invite_codes.py         # 邀请码管理：生成/查询/删除
│   │
│   ├── tasks/                          # 异步任务（Celery）
│   │   ├── celery_app.py               # Celery 应用初始化
│   │   └── jobs.py                     # 任务定义：TTS/克隆任务
│   │
│   └── static/                         # 静态资源
│       └── avatars/                    # 用户头像
│
├── data/                               # 数据目录（运行时生成）
│   ├── avatars/                        # 用户上传的头像
│   ├── tts_outputs/                    # TTS 生成的音频
│   └── clone_datasets/                 # 克隆数据集
│
├── docs/                               # 项目文档
│   ├── DEVELOPMENT.md                  # 开发指南
│
├── scripts/                            # 脚本工具
│   ├── download_vocu_data.py           # 下载 VOCU 数据
│   ├── import_vocu_simple.py           # 导入音色数据
│   └── schema.sql                      # 数据库 Schema（参考）
│
├── test/                               # 测试代码
│   ├── run_sse_test.py                 # SSE 推送测试
│   ├── test_invite_code.py             # 邀请码测试
│   └── verify_router_refactoring.py    # 路由重构验证
│
├── docker-compose.yml                  # Docker Compose 编排
├── Dockerfile                          # Docker 镜像构建
├── pyproject.toml                      # 项目依赖（uv 管理）
├── uv.lock                             # 依赖锁文件
├── run.py                              # 本地开发启动脚本
├── .pre-commit-config.yaml             # Git Hooks 配置
└── README.md                           # 项目说明
```

### 核心架构说明

#### 路由层（统一管理）
- **`routers.py`** - 14 个 APIRouter 集中定义（prefix、tags）
- **`api/views/`** - 路由处理器实现（从 routers 引用）
- **架构优势**：集中管理、易于维护、避免重复

#### 业务层（三层架构）
- **Views** - 路由处理、参数验证、响应封装
- **Controller** - 业务逻辑编排、权限检查
- **Services** - 基础服务、数据访问、第三方调用

#### 数据层
- **Models** - SQLAlchemy ORM 模型（12 个表）
- **异步引擎** - AsyncSession（API 使用）
- **同步引擎** - Session（Celery 使用）
- **连接池** - 可配置的连接池管理

#### 任务队列
- **Celery** - 异步任务处理
- **队列分类** - tts（TTS 任务）、clone（克隆任务）
- **状态推送** - Redis Pub/Sub 实时通知

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
