## fast_voice（V1）

V1 目标：提供一个“开放平台”最小闭环，包含：
- **Console（C 端管理入口）**：登录/注册/改名/改密码、积分余额/流水、APIKey 管理、音色管理、任务管理
- **OpenAPI（B 端调用入口）**：APIKey+Secret 签名鉴权、TTS/克隆异步任务、声音大厅（公开音色列表）

V1 已确认的业务规则：
- **计费规则**：按输入文本 **UTF-8 字节数**计费
- **TTS**：必须异步（创建任务 -> 轮询查询）
- **克隆与合成**：同时支持 console 与 openapi
- **充值暂不做**：积分只支持管理员手动调账（admin_adjust）

---

## 1) 依赖管理（uv）

本项目使用 **uv + pyproject.toml** 管理依赖（不再使用 requirements.txt）。

常用命令：

```bash
# 安装依赖（生产）
uv sync --no-dev

# 安装依赖（开发/测试）
uv sync --extra dev

# 运行服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 运行 worker
uv run celery -A app.tasks.celery_app:celery_app worker -l INFO -Q tts,clone

# 跑测试
uv run pytest -q
```

> 你如果希望 Docker 构建可重复（锁版本），可以在本地执行 `uv lock` 并提交 `uv.lock`，然后在 Dockerfile 里 COPY `uv.lock` 并用 `uv sync --frozen`。

---

## 2) Docker 部署

```bash
docker compose up --build
```

启动后：
- API：`http://localhost:8000`
- Swagger（FastAPI 自动生成）：`http://localhost:8000/docs`
- OpenAPI 接入说明（自定义）：`http://localhost:8000/openapi/docs/guide`

> 目录迁移说明：旧的 `backend/` 目录在 V1 已不再使用，可以直接删除（仅为历史残留）。

---

## 3) 项目结构（每个文件/目录用途）

```
.
├─ app/                      # 后端代码（FastAPI + SQLAlchemy + Celery）
│  ├─ main.py                # FastAPI 入口：middleware(缓存 raw body)、路由挂载、启动建表、静态文件 /files
│  ├─ core/
│  │  ├─ config.py           # Settings：所有环境变量配置（DB/Redis/Celery/JWT/计费/连接池等）
│  │  └─ security.py         # 密码哈希、JWT、OpenAPI HMAC 签名、api_secret 加解密
│  ├─ db.py                  # SQLAlchemy engine/session：带连接池配置（非 SQLite）+ session_scope
│  ├─ models.py              # 数据库模型（每张表/字段用途均有注释）
│  ├─ schemas.py             # Pydantic 请求/响应结构
│  ├─ deps.py                # FastAPI 依赖：DB commit/rollback、console JWT、openapi 签名鉴权
│  ├─ routes/
│  │  ├─ console.py          # /console：注册/登录/改名/改密、余额/流水、轮换 APIKey、管理员调账
│  │  ├─ voices.py           # 音色：我的音色、公开/私有设置、公开音色列表（声音大厅）
│  │  ├─ tts.py              # TTS：创建任务(预扣费) + 查询任务（console/openapi 双入口）
│  │  ├─ clone.py            # 克隆：上传数据集->任务 + 查询任务（console/openapi 双入口）
│  │  ├─ shared.py           # 路由共享校验（音色访问权限、默认 project）
│  │  └─ openapi_docs.py     # OpenAPI 接入说明（签名/幂等/错误码）
│  ├─ services/
│  │  ├─ bootstrap.py        # 启动时创建管理员 + 默认 project + 默认 api_key
│  │  ├─ billing.py          # 计费/扣费/退款/调账（积分流水）
│  │  ├─ kv.py               # Redis/内存 KV：nonce 防重放、幂等键存储
│  │  ├─ idempotency.py      # Idempotency-Key 读写封装
│  │  └─ storage.py          # 本地文件存储：DATA_DIR、job_dir、/files URL 映射
│  └─ tasks/
│     ├─ celery_app.py       # Celery app 初始化与队列路由
│     └─ jobs.py             # 任务执行：run_tts_job/run_clone_job（V1 生成 dummy wav）
├─ tests/                    # pytest（覆盖 console 登录、openapi 签名、nonce、幂等等关键逻辑）
├─ pyproject.toml            # uv 依赖清单
├─ docker-compose.yml        # api + worker + postgres + redis
└─ Dockerfile                # 使用 astral uv 镜像构建
```

---

## 4) OpenAPI 鉴权（详细）

OpenAPI 采用 **APIKey + Secret 的 HMAC-SHA256 请求签名**，并且支持 **timestamp/nonce 防重放**。

### 4.1 必须携带的请求头
- `X-API-Key`：项目的 api_key
- `X-Timestamp`：unix 秒
- `X-Nonce`：随机串（在时间窗内不可重复）
- `X-Signature`：签名（hex）
- `Idempotency-Key`：仅对“创建任务”接口必填（`POST /openapi/tts/jobs`、`POST /openapi/clone/jobs`）

### 4.2 Canonical String（签名原文）

```
METHOD\n
PATH\n
QUERY\n
BODY_SHA256\n
TIMESTAMP\n
NONCE
```

注意：
- `METHOD`：大写（GET/POST）
- `PATH`：例如 `/openapi/tts/jobs`
- `QUERY`：原始 querystring（没有就空字符串）
- `BODY_SHA256`：对 **请求体原始 bytes** 做 sha256 的 hex（JSON 必须用实际发送的 bytes）

### 4.3 防重放逻辑
- `X-Timestamp` 必须在 `SIGNATURE_TIME_WINDOW_SECONDS` 内
- `X-Nonce` 在该窗口内对同一 `X-API-Key` 必须唯一  
  - 实现：`nonce:{api_key}:{nonce}` 用 Redis `SET NX EX`（见 `app/deps.py`）

---

## 5) TTS 排队/扣费/幂等（详细）

### 5.1 异步队列（Celery）
- 创建任务：API 写入 `tts_jobs`（status=queued）后，投递 Celery 任务 `run_tts_job(job_id)`
- Worker 消费队列 `tts`，执行推理并写入本地文件 `DATA_DIR/tts/.../output.wav`

### 5.2 扣费策略（预扣费 + 失败退款）
- 创建任务时：
  - 计算 `text_utf8_bytes = len(text.encode("utf-8"))`
  - `cost_credits = text_utf8_bytes * CREDIT_PRICE_PER_UTF8_BYTE`
  - 执行 `consume` 预扣并写流水（见 `app/services/billing.py`）
- Worker 失败时：
  - 置 `status=failed`
  - 写 `refund` 流水全额退款（见 `app/tasks/jobs.py`）

### 5.3 幂等（Idempotency-Key）
为避免客户重试导致重复扣费/重复任务：
- `POST /openapi/tts/jobs` 必须带 `Idempotency-Key`
- 服务端用 `idem:{project_id}:{endpoint}:{key}` 存储 job_id（见 `app/services/idempotency.py`）

---

## 5.4 双入口能力

以下能力 **同时支持 console 与 openapi**：

- **声音大厅（公开音色列表）**
  - `GET /console/voices/public`
  - `GET /openapi/voices/public`

- **TTS（异步任务）**
  - `POST /console/tts/jobs`（JWT）
  - `GET /console/tts/jobs/{job_id}`（JWT）
  - `POST /openapi/tts/jobs`（签名 + Idempotency-Key）
  - `GET /openapi/tts/jobs/{job_id}`（签名）

- **克隆（异步任务）**
  - `POST /console/clone/jobs`（JWT，multipart）
  - `GET /console/clone/jobs/{job_id}`（JWT）
  - `POST /openapi/clone/jobs`（签名 + Idempotency-Key，multipart）
  - `GET /openapi/clone/jobs/{job_id}`（签名）

---

## 6) 本地文件访问（/files）

所有生成/预览音频落在 `DATA_DIR`（默认 `./data` 或容器 `/data`），并通过：
- `GET /files/{relative_path}`

映射逻辑见 `app/services/storage.py`。

---
