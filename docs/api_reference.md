# fast_voice API 参考文档

本文档整理 `app/views` 目录中的所有对外接口（Console 与 OpenAPI），所有字段说明参考 `app/schemas.py`。

## 基础信息

### 鉴权方式
- **Console 路由**：`/console/**`，使用用户 JWT（通过登录接口获取）
- **OpenAPI 路由**：`/openapi/**`，使用 Bearer Token（API Key 以 `sk-` 开头）

### 通用响应格式
```json
{
  "message": "提示信息",
  "data": { ...响应体数据... }
}
```

**字段说明：**
- `message` (string)：提示信息
- `data` (object)：响应体数据

### 状态码说明
```
200 OK                  - 请求成功
400 Bad Request         - 请求参数错误
401 Unauthorized        - 未授权/Token 无效
403 Forbidden          - 禁止访问
404 Not Found          - 资源不存在
429 Too Many Requests  - 请求频率超限
500 Server Error       - 服务器内部错误
```

---

## 账号管理

### 用户注册

#### 接口地址
```
POST /auth/register
```

#### 请求头
```
Content-Type: application/json
```

#### 请求参数 (RegisterIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 用户邮箱地址 |
| password | string | 是 | 登录密码（6-72个字符） |
| display_name | string | 否 | 显示名称（最多100个字符，可选） |
| invite_code | string | 是 | 邀请码（必须） |

#### 返回数据 (RegisterOut)
```json
{
  "message": "注册成功",
  "data": {
    "id": "user-uuid",
    "email": "user@example.com",
    "display_name": "用户昵称",
    "avatar_url": "",
    "is_admin": false,
    "subscription_plan": "free",
    "subscription_ends_at": null,
    "credit_balance": 10000
  }
}
```

**返回字段说明：**
- `id` (string)：用户 UUID
- `email` (string)：邮箱地址
- `display_name` (string)：显示名称
- `avatar_url` (string)：头像 URL
- `is_admin` (boolean)：是否管理员
- `subscription_plan` (string)：订阅计划（free/pro/enterprise）
- `subscription_ends_at` (string|null)：订阅到期时间
- `credit_balance` (integer)：积分余额

#### CURL 示例
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123",
    "display_name": "测试用户",
    "invite_code": "your-invite-code"
  }'
```

---

### 用户登录

#### 接口地址
```
POST /auth/login
```

#### 请求头
```
Content-Type: application/json
```

#### 请求参数 (LoginIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 用户邮箱地址 |
| password | string | 是 | 登录密码 |

#### 返回数据 (LoginOut)
```json
{
  "message": "登录成功",
  "data": {
    "id": "user-uuid",
    "email": "user@example.com",
    "display_name": "用户昵称",
    "avatar_url": "",
    "is_admin": false,
    "subscription_plan": "free",
    "subscription_ends_at": null,
    "credit_balance": 10000,
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
}
```

**返回字段说明：**
- `id` (string)：用户 UUID
- `email` (string)：邮箱地址
- `display_name` (string)：显示名称
- `avatar_url` (string)：头像 URL
- `is_admin` (boolean)：是否管理员
- `subscription_plan` (string)：订阅计划（free/pro/enterprise）
- `subscription_ends_at` (string|null)：订阅到期时间
- `credit_balance` (integer)：积分余额
- `access_token` (string)：JWT 访问令牌
- `token_type` (string)：令牌类型（默认 bearer）

#### CURL 示例
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

---

### 获取账号信息

#### 接口地址
```
GET /me
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据 (MeOut)
```json
{
  "message": "获取成功",
  "data": {
    "id": "user-uuid",
    "email": "user@example.com",
    "display_name": "用户昵称",
    "avatar_url": "",
    "is_admin": false,
    "subscription_plan": "free",
    "subscription_ends_at": null,
    "credit_balance": 10000
  }
}
```

**返回字段说明：**
- `id` (string)：用户 UUID
- `email` (string)：邮箱地址
- `display_name` (string)：显示名称
- `avatar_url` (string)：头像 URL
- `is_admin` (boolean)：是否管理员
- `subscription_plan` (string)：订阅计划（free/pro/enterprise）
- `subscription_ends_at` (string|null)：订阅到期时间
- `credit_balance` (integer)：积分余额

#### CURL 示例
```bash
curl -X GET http://localhost:8000/me \
  -H "Authorization: Bearer <your_jwt_token>"
```

---

### 修改昵称

#### 接口地址
```
POST /me/rename
```

#### 请求头
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

#### 请求参数 (RenameIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| display_name | string | 是 | 新的显示名称（1-100个字符） |

#### 返回数据
返回 MeOut 格式数据（同"获取账号信息"）

---

### 修改密码

#### 接口地址
```
POST /me/change-password
```

#### 请求头
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

#### 请求参数 (ChangePasswordIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| old_password | string | 是 | 原密码 |
| new_password | string | 是 | 新密码（6-72个字符） |

#### 返回数据
```json
{
  "message": "密码修改成功",
  "data": null
}
```

---

### 上传头像

#### 接口地址
```
POST /me/avatar/upload
```

#### 请求头
```
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 头像图片文件 |

#### 文件要求
- **支持格式**: JPG, JPEG, PNG, GIF, WebP
- **文件大小**: 最大 5MB
- **Content-Type**: 必须是 `image/*` 类型

#### 返回数据
返回 MeOut 格式数据

#### CURL 示例
```bash
curl -X POST http://localhost:8000/me/avatar/upload \
  -H "Authorization: Bearer <jwt_token>" \
  -F "file=@/path/to/avatar.jpg"
```

---

### 更新头像链接

#### 接口地址
```
POST /me/avatar
```

#### 请求头
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

#### 请求参数 (UpdateAvatarIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| avatar_url | string | 是 | 头像URL链接（最多512字符） |

#### 返回数据
返回 MeOut 格式数据

---

## 订阅管理

### 查询订阅信息

#### 接口地址
```
GET /subscription
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据 (SubscriptionInfo)
```json
{
  "message": "获取成功",
  "data": {
    "plan": "free",
    "plan_name": "免费版",
    "status": "active",
    "ends_at": null,
    "features": {
      "monthly_credits": 1000,
      "monthly_quota": 100,
      "clone_limit": 3,
      "api_access": false
    }
  }
}
```

**返回字段说明：**
- `plan` (string)：订阅计划代码（free/pro/enterprise）
- `plan_name` (string)：计划名称（免费版/专业版/企业版）
- `status` (string)：订阅状态（active/expired/cancelled）
- `ends_at` (string|null)：订阅到期时间
- `features` (object)：功能特性列表

---

### 获取所有订阅计划配置

#### 接口地址
```
GET /subscription/plans
```

#### 请求头
不需要认证（公开接口）

#### 返回数据 (PlanConfigOut[])
```json
{
  "message": "获取成功",
  "data": [
    {
      "plan": "free",
      "name": "免费版",
      "monthly_credits": 1000,
      "monthly_quota": 100,
      "clone_limit": 3,
      "api_access": false,
      "commercial_use": false,
      "priority_support": false
    },
    {
      "plan": "pro",
      "name": "专业版",
      "monthly_credits": 10000,
      "monthly_quota": 5000,
      "clone_limit": 20,
      "api_access": false,
      "commercial_use": true,
      "priority_support": false
    },
    {
      "plan": "enterprise",
      "name": "企业版",
      "monthly_credits": 100000,
      "monthly_quota": 500000,
      "clone_limit": -1,
      "api_access": true,
      "commercial_use": true,
      "priority_support": true
    }
  ]
}
```

**返回字段说明 (PlanConfigOut)：**
- `plan` (string)：订阅计划代码（free/pro/enterprise）
- `name` (string)：计划名称
- `monthly_credits` (integer)：每月赠送积分
- `monthly_quota` (integer)：月度请求配额
- `clone_limit` (integer)：克隆位限制（-1表示无限）
- `api_access` (boolean)：是否提供API访问
- `commercial_use` (boolean)：是否允许商业使用
- `priority_support` (boolean)：是否提供优先支持

---

### 升级订阅

#### 接口地址
```
POST /subscription/upgrade
```

#### 请求头
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

#### 请求参数 (UpgradeSubscriptionIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| plan | string | 是 | 目标计划：pro或enterprise |
| months | integer | 否 | 订阅月数（1-12，默认1） |

---

## 音色管理

### 获取官方音色列表

#### 接口地址
```
GET /console/voices/official
GET /openapi/voices/official
```

#### 请求头
```
# Console
Authorization: Bearer <jwt_token>

# OpenAPI
Authorization: Bearer sk-<api_key>
```

#### 请求参数 (Query)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tags | array[string] | 否 | 标签筛选（可传递多个标签，满足任一即返回） |
| limit | integer | 否 | 每页返回数量（1-100，默认20） |
| offset | integer | 否 | 偏移量，用于分页（默认0） |
| orderBy | string | 否 | 排序字段：likes(点赞)/usage(使用次数)/chars(生成字符数)/createdAt(创建时间，默认) |

#### 返回数据
```json
{
  "message": "获取成功",
  "data": [
    {
      "id": "voice-uuid",
      "name": "音色名称",
      "avatar_url": "https://example.com/avatar.jpg",
      "description": "音色描述",
      "tags": ["中文", "女", "青年"],
      "is_public": true,
      "preview_audio_url": "/files/voices/xxx/preview.mp3",
      "clone_job_uuid": "clone-job-uuid",
      "likes_count": 100,
      "generated_chars_count": 50000,
      "usage_count": 200,
      "created_at": "2025-12-25 10:00:00"
    }
  ]
}
```

**返回字段说明 (VoiceOut)：**
- `id` (string)：音色 UUID
- `name` (string)：音色名称
- `avatar_url` (string)：音色头像 URL
- `description` (string)：音色描述
- `tags` (array[string])：音色标签列表
- `is_public` (boolean)：是否公开
- `preview_audio_url` (string)：预览音频 URL
- `clone_job_uuid` (string)：克隆任务 UUID（用于 TTS）
- `likes_count` (integer)：点赞数
- `generated_chars_count` (integer)：生成字符数
- `usage_count` (integer)：使用次数
- `created_at` (string)：创建时间

#### CURL 示例
```bash
# 获取前20个官方音色
curl -X GET "http://localhost:8000/console/voices/official?limit=20&offset=0" \
  -H "Authorization: Bearer <your_jwt_token>"

# 筛选中文女声，按点赞数排序
curl -X GET "http://localhost:8000/console/voices/official?tags=中文&tags=女&orderBy=likes&limit=10" \
  -H "Authorization: Bearer <your_jwt_token>"
```

---

### 获取公开音色列表

#### 接口地址
```
GET /console/voices/public
GET /openapi/voices/public
```

请求参数、返回格式与官方音色列表相同（参见上方 VoiceOut 字段说明）。

---

### 获取我的音色列表

#### 接口地址
```
GET /console/voices/mine
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据
返回格式同官方音色列表（VoiceOut 数组）。

---

### 更新音色信息

#### 接口地址
```
PATCH /console/voices/{voice_id}
```

#### 请求头
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

#### 请求参数 (VoiceUpdateIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| description | string | 否 | 音色描述（可选） |
| is_public | boolean | 否 | 是否公开（可选） |
| tags | array[string] | 否 | 音色标签列表（只能使用预设标签） |

#### 返回数据
返回 VoiceOut 格式数据

---

### 修改音色名称

#### 接口地址
```
PATCH /console/voices/{voice_uuid}/name
```

#### 请求头
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

#### 请求参数 (VoiceRenameIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 音色名称（1-120字符） |

#### 返回数据
返回 VoiceOut 格式数据

---

### 获取音色标签

#### 接口地址
```
GET /console/voices/tags
GET /openapi/voices/tags
```

#### 请求头
```
Authorization: Bearer <jwt_token or api_key>
```

#### 返回数据
```json
{
  "message": "获取成功",
  "data": {
    "语言": ["中文", "英文", "日语", "韩语"],
    "性别": ["男", "女"],
    "年龄": ["少年", "青年", "中年", "老年"],
    "情感": ["温柔", "活泼", "沉稳", "冷酷"]
  }
}
```

---

### 点赞音色

#### 接口地址
```
POST /console/voices/{voice_uuid}/like
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据
返回 VoiceOut 格式数据（点赞数已更新）

---

### 取消点赞音色

#### 接口地址
```
DELETE /console/voices/{voice_uuid}/like
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据
返回 VoiceOut 格式数据（点赞数已更新）

---

## 文本转语音（TTS）

### 创建 TTS 任务

#### 接口地址
```
POST /console/tts/jobs
POST /openapi/tts/jobs
```

#### 请求头
```
# Console
Authorization: Bearer <jwt_token>
Content-Type: application/json

# OpenAPI
Authorization: Bearer sk-<api_key>
Content-Type: application/json
Idempotency-Key: <unique_key>  # OpenAPI 必填
```

#### 请求参数 (TTSCreatIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| clone_job_id | string | 是 | 克隆任务的 UUID（/console/clone/jobs 返回的 data.id） |
| text | string | 是 | 要转换的文本 |
| speed_factor | float | 否 | 语速，可选；未提供则使用默认值 1.0 |
| temperature | float | 否 | 采样温度，可选；未提供则使用默认值 1.0 |
| top_k | integer | 否 | 采样 top_k，可选；默认 5 |
| top_p | float | 否 | 采样 top_p，可选；默认 1.0 |
| webhook_url | string | 否 | Webhook 回调地址，任务完成时调用；可选（最多512字符） |

#### 返回数据 (JobOut)
```json
{
  "message": "TTS 任务创建成功",
  "data": {
    "id": "job-uuid",
    "status": "queued",
    "error": ""
  }
}
```

**返回字段说明：**
- `id` (string)：任务 UUID
- `status` (string)：任务状态（queued/running/succeeded/failed）
- `error` (string)：错误信息（如有）

#### CURL 示例
```bash
# Console 路由
curl -X POST http://localhost:8000/console/tts/jobs \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "clone_job_id": "clone-job-uuid",
    "text": "你好，欢迎使用 fast_voice",
    "speed_factor": 1.0,
    "temperature": 1.0,
    "top_k": 5,
    "top_p": 1.0
  }'

# OpenAPI 路由
curl -X POST http://localhost:8000/openapi/tts/jobs \
  -H "Authorization: Bearer sk-xxxxxxxxx" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "clone_job_id": "clone-job-uuid",
    "text": "你好，欢迎使用 fast_voice"
  }'
```

---

### 查询 TTS 任务

#### 接口地址
```
GET /console/tts/jobs/{job_uuid}
GET /openapi/tts/jobs/{job_uuid}
```

#### 请求头
```
Authorization: Bearer <jwt_token or api_key>
```

#### 返回数据 (TTSJobOut)
```json
{
  "message": "获取成功",
  "data": {
    "id": "job-uuid",
    "status": "succeeded",
    "error": "",
    "voice_uuid": "voice-uuid",
    "text_utf8_bytes": 30,
    "cost_credits": 30,
    "tags": ["中文", "女"],
    "speed_factor": 1.0,
    "temperature": 1.0,
    "top_k": 5,
    "top_p": 1.0,
    "output_audio_url": "/files/tts/1_job-uuid/output.mp3"
  }
}
```

**返回字段说明：**
- `id` (string)：任务 UUID
- `status` (string)：任务状态
- `error` (string)：错误信息（如有）
- `voice_uuid` (string)：使用的音色 UUID
- `text_utf8_bytes` (integer)：文本字节数（UTF-8编码）
- `cost_credits` (integer)：消耗的积分数
- `tags` (array[string])：音色标签
- `speed_factor` (float)：语速系数
- `temperature` (float)：采样温度
- `top_k` (integer)：采样 top_k 参数
- `top_p` (float)：采样 top_p 参数
- `output_audio_url` (string)：输出音频 URL

#### CURL 示例
```bash
curl -X GET http://localhost:8000/console/tts/jobs/<job_uuid> \
  -H "Authorization: Bearer <jwt_token>"
```

---

### 实时订阅 TTS 状态（SSE）

#### 接口地址
```
GET /console/tts/jobs/{job_uuid}/events
GET /openapi/tts/jobs/{job_uuid}/events
```

#### 请求头
```
Authorization: Bearer <jwt_token or api_key>
Accept: text/event-stream
```

#### SSE 事件类型

**1. status 事件**：任务状态变更
```
event: status
data: {"job_id":"job-uuid","status":"running","timestamp":1735123456.789}
```

**2. ping 事件**：心跳（默认15秒）
```
event: ping
data: {"job_id":"job-uuid","status":"running","timestamp":1735123456.789}
```

**3. complete 事件**：任务完成
```
event: complete
data: {"job_id":"job-uuid","status":"succeeded","data":{...TTSJobOut}}
```

**4. error 事件**：错误
```
event: error
data: {"message":"任务不存在","code":"not_found"}
```

**5. timeout 事件**：超时
```
event: timeout
data: {"message":"任务处理超时","elapsed_seconds":300}
```

#### CURL 示例
```bash
# PowerShell
curl.exe -N "http://localhost:8000/console/tts/jobs/<job_uuid>/events" `
  -H "Accept: text/event-stream" `
  -H "Authorization: Bearer <jwt_token>" `
  --http1.1

# Bash/Linux
curl --no-buffer "http://localhost:8000/console/tts/jobs/<job_uuid>/events" \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer <jwt_token>" \
  --http1.1
```

---

### 获取 TTS 生成历史列表

#### 接口地址
```
GET /console/tts/history
GET /openapi/tts/history
```

#### 请求头
```
Authorization: Bearer <jwt_token or api_key>
```

#### 请求参数 (Query)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码（从1开始，默认1） |
| page_size | integer | 否 | 每页数量（1-100，默认20） |

#### 返回数据 (TTSHistoryListOut)
```json
{
  "message": "获取历史记录成功",
  "data": {
    "items": [
      {
        "id": "job-uuid",
        "status": "succeeded",
        "text": "你好，欢迎使用 fast_voice",
        "voice_uuid": "voice-uuid",
        "voice_name": "音色名称",
        "voice_avatar_url": "https://example.com/avatar.jpg",
        "output_audio_url": "/files/tts/1_job-uuid/output.mp3",
        "cost_credits": 30,
        "created_at": "2025-12-25T10:00:00",
        "error": ""
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

**返回字段说明：**

TTSHistoryItemOut 字段：
- `id` (string)：任务 UUID
- `status` (string)：任务状态
- `text` (string)：输入文本
- `voice_uuid` (string)：使用的音色 UUID
- `voice_name` (string)：音色名称
- `voice_avatar_url` (string)：音色头像 URL
- `output_audio_url` (string)：输出音频 URL
- `cost_credits` (integer)：消耗的积分数
- `created_at` (string)：创建时间（ISO 8601格式）
- `error` (string)：错误信息（如有）

分页字段：
- `items` (array)：历史记录列表
- `total` (integer)：总记录数
- `page` (integer)：当前页码
- `page_size` (integer)：每页数量

#### CURL 示例
```bash
curl -X GET "http://localhost:8000/console/tts/history?page=1&page_size=20" \
  -H "Authorization: Bearer <jwt_token>"
```

---

### 删除 TTS 生成历史记录

#### 接口地址
```
DELETE /console/tts/history/{job_uuid}
DELETE /openapi/tts/history/{job_uuid}
```

#### 请求头
```
Authorization: Bearer <jwt_token or api_key>
```

#### 返回数据
```json
{
  "message": "删除成功",
  "data": {
    "job_uuid": "job-uuid"
  }
}
```

#### CURL 示例
```bash
curl -X DELETE http://localhost:8000/console/tts/history/<job_uuid> \
  -H "Authorization: Bearer <jwt_token>"
```

---

## 声音克隆

### 创建克隆任务

#### 接口地址
```
POST /console/clone/jobs
POST /openapi/clone/jobs
```

#### 请求头
```
# Console
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

# OpenAPI
Authorization: Bearer sk-<api_key>
Content-Type: multipart/form-data
Idempotency-Key: <unique_key>  # OpenAPI 必填
```

#### 请求参数 (CloneCreateIn + 文件)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| voice_name | string | 是 | 音色名称 |
| avatar_url | string | 否 | 头像 URL（可选） |
| description | string | 否 | 音色描述（可选） |
| tags | array | 否 | 标签列表（JSON 数组） |
| is_public | boolean | 否 | 是否公开（默认为 false） |
| remove_background_noise | boolean | 否 | 是否去除背景噪音（默认为 false） |
| audio_file | file | 是 | 音频文件（multipart 上传） |

#### 返回数据 (CloneCreateOut)
```json
{
  "message": "克隆任务创建成功",
  "data": {
    "id": "clone-job-uuid",
    "status": "queued",
    "error": "",
    "voice_name": "我的音色",
    "avatar_url": "",
    "description": "音色描述",
    "tags": ["中文", "女"],
    "user_id": "user-uuid",
    "created_at": "2025-12-25 10:00:00",
    "preview_audio_url": ""
  }
}
```

**返回字段说明：**
- `id` (string)：任务 UUID
- `status` (string)：任务状态
- `error` (string)：错误信息（如有）
- `voice_name` (string)：音色名称
- `avatar_url` (string)：头像 URL
- `description` (string)：音色描述
- `tags` (array[string])：标签列表
- `user_id` (string)：用户 UUID
- `created_at` (string)：创建时间
- `preview_audio_url` (string)：预览音频 URL

#### CURL 示例
```bash
curl -X POST http://localhost:8000/console/clone/jobs \
  -H "Authorization: Bearer <jwt_token>" \
  -F "voice_name=我的音色" \
  -F "description=音色描述" \
  -F "tags=[\"中文\",\"女\"]" \
  -F "is_public=false" \
  -F "remove_background_noise=false" \
  -F "audio_file=@/path/to/audio.wav"
```

---

### 查询克隆任务

#### 接口地址
```
GET /console/clone/jobs/{job_uuid}
GET /openapi/clone/jobs/{job_uuid}
```

#### 请求头
```
Authorization: Bearer <jwt_token or api_key>
```

#### 返回数据 (CloneJobOut)
```json
{
  "message": "获取成功",
  "data": {
    "id": "clone-job-uuid",
    "status": "succeeded",
    "error": "",
    "voice_name": "我的音色",
    "avatar_url": "",
    "description": "音色描述",
    "tags": ["中文", "女"],
    "user_id": "user-uuid",
    "created_at": "2025-12-25 10:00:00",
    "preview_audio_url": "/files/voices/xxx/preview.mp3",
    "result_voice_uuid": "voice-uuid"
  }
}
```

**返回字段说明：**
- `id` (string)：任务 UUID
- `status` (string)：任务状态
- `error` (string)：错误信息（如有）
- `voice_name` (string)：音色名称
- `avatar_url` (string)：头像 URL
- `description` (string)：音色描述
- `tags` (array[string])：标签列表
- `user_id` (string)：用户 UUID
- `created_at` (string)：创建时间
- `preview_audio_url` (string)：预览音频 URL
- `result_voice_uuid` (string|null)：克隆成功后生成的音色 UUID

#### CURL 示例
```bash
curl -X GET http://localhost:8000/console/clone/jobs/<clone_job_uuid> \
  -H "Authorization: Bearer <jwt_token>"
```

---

## 控制台概览

### Dashboard 概览

#### 接口地址
```
GET /console/analytics/dashboard
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据 (DashboardOut)
```json
{
  "message": "获取成功",
  "data": {
    "user_id": "user-uuid",
    "email": "user@example.com",
    "plan_name": "免费版",
    "plan_status": "active",
    "monthly_usage": 50,
    "monthly_quota": 100,
    "usage_percent": 50.0,
    "next_billing_date": "2026-01-01",
    "credit_balance": 10000,
    "clone_count": 2,
    "clone_limit": 3,
    "api_access_enabled": false
  }
}
```

**返回字段说明：**
- `user_id` (string)：用户 UUID
- `email` (string)：邮箱地址
- `plan_name` (string)：订阅计划名称
- `plan_status` (string)：订阅状态（active/expired）
- `monthly_usage` (integer)：本月使用量（API 调用次数）
- `monthly_quota` (integer)：月度配额（根据计划不同）
- `usage_percent` (float)：使用率百分比
- `next_billing_date` (string)：下一个账单日期
- `credit_balance` (integer)：积分余额
- `clone_count` (integer)：已克隆音色数量
- `clone_limit` (integer)：音色克隆上限（-1表示无限）
- `api_access_enabled` (boolean)：是否启用 API 访问

---

### 每日用量统计

#### 接口地址
```
GET /console/analytics/usage-stats
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 请求参数 (Query)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| days | integer | 否 | 查询天数（1-30天，默认7） |

#### 返回数据
```json
{
  "message": "获取成功",
  "data": [
    {
      "date": "2025-12-25",
      "total_requests": 100,
      "successful_requests": 95,
      "failed_requests": 5
    }
  ]
}
```

**返回字段说明 (UsageStatsOut)：**
- `date` (string)：日期（YYYY-MM-DD 格式）
- `total_requests` (integer)：总请求数
- `successful_requests` (integer)：成功请求数（状态码 200）
- `failed_requests` (integer)：失败请求数

---

### API 请求日志

#### 接口地址
```
GET /console/analytics/request-logs
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 请求参数 (Query)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码（从1开始，默认1） |
| page_size | integer | 否 | 每页数量（1-200，默认50） |

#### 返回数据 (PaginatedRequestLogs)
```json
{
  "message": "获取成功",
  "data": {
    "items": [
      {
        "id": 1,
        "timestamp": "2025-12-25 10:00:00",
        "endpoint": "/console/tts/jobs",
        "method": "POST",
        "status_code": 200,
        "latency_ms": 150,
        "response_size": 1024,
        "error_message": ""
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

**返回字段说明：**

RequestLogOut 字段：
- `id` (integer)：日志 ID
- `timestamp` (string)：请求时间
- `endpoint` (string)：请求路径
- `method` (string)：HTTP 方法
- `status_code` (integer)：响应状态码
- `latency_ms` (integer)：响应延迟（毫秒）
- `response_size` (integer)：响应大小（字节）
- `error_message` (string)：错误消息（如有）

分页字段：
- `items` (array)：日志列表
- `total` (integer)：总记录数
- `page` (integer)：当前页码
- `page_size` (integer)：每页条数
- `total_pages` (integer)：总页数
- `has_next` (boolean)：是否有下一页
- `has_prev` (boolean)：是否有上一页

---

## 积分管理

### 查询积分余额

#### 接口地址
```
GET /console/credits/balance
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据 (CreditAccountOut)
```json
{
  "message": "获取成功",
  "data": {
    "user_id": "user-uuid",
    "balance": 10000
  }
}
```

**返回字段说明：**
- `user_id` (string)：用户 UUID
- `balance` (integer)：积分余额

---

### 查询积分流水

#### 接口地址
```
GET /console/credits/transactions
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据
```json
{
  "message": "获取成功",
  "data": [
    {
      "id": 1,
      "tx_type": "consume",
      "amount": -100,
      "ref_type": "tts",
      "ref_id": "job-uuid",
      "note": "TTS 任务消费",
      "created_at": "2025-12-25 10:00:00"
    }
  ]
}
```

**返回字段说明 (CreditTxOut)：**
- `id` (integer)：交易 ID
- `tx_type` (string)：交易类型（subscription/recharge/consume/refund）
- `amount` (integer)：金额（正数为收入，负数为支出）
- `ref_type` (string)：关联类型
- `ref_id` (string)：关联 ID
- `note` (string)：备注说明
- `created_at` (string)：交易时间

---

### 管理员充值

#### 接口地址
```
POST /console/credits/admin/recharge
```

#### 请求头
```
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json
```

#### 请求参数 (RechargeIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 目标用户的 UUID |
| amount | integer | 是 | 充值金额（必须为正整数） |
| note | string | 否 | 备注说明（可选） |

---

## API Key 管理

### 获取 API Key 列表

#### 接口地址
```
GET /console/api-keys
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据
```json
{
  "message": "获取成功",
  "data": [
    {
      "id": 1,
      "name": "Production Key",
      "api_key_masked": "sk-...xxxxx",
      "is_active": true,
      "expires_at": "2026-12-25 10:00:00",
      "created_at": "2025-12-25 10:00:00"
    }
  ]
}
```

**返回字段说明 (ApiKeyListItem)：**
- `id` (integer)：API Key ID
- `name` (string)：密钥名称
- `api_key_masked` (string)：脱敏显示的 Key（如 sk-...）
- `is_active` (boolean)：是否激活
- `expires_at` (string|null)：过期时间（null 表示永久有效）
- `created_at` (string)：创建时间

---

### 创建 API Key

#### 接口地址
```
POST /console/api-keys
```

#### 请求头
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

#### 请求参数 (CreateApiKeyIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 密钥名称（可选，最多100字符） |
| expires_days | integer | 否 | 有效期天数（null表示永不过期，最小1天） |

#### 返回数据 (ApiKeyOut)
```json
{
  "message": "API Key 创建成功",
  "data": {
    "api_key": "sk-xxxxxxxxxxxxxxxx",
    "expires_at": "2026-12-25 10:00:00"
  }
}
```

**返回字段说明：**
- `api_key` (string)：完整的 API Key（仅创建时显示一次）
- `expires_at` (string|null)：过期时间（null 表示永不过期）

#### CURL 示例
```bash
curl -X POST http://localhost:8000/console/api-keys \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Key",
    "expires_days": 365
  }'
```

---

### 删除 API Key

#### 接口地址
```
DELETE /console/api-keys/{api_key}
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

---

### 轮换 API Key

#### 接口地址
```
POST /console/api-keys/rotate
```

#### 请求头
```
Authorization: Bearer <jwt_token>
```

#### 返回数据
返回 ApiKeyOut 格式数据（新的 API Key，旧 key 失效）

---

## 邀请码管理（管理员）

### 生成邀请码

#### 接口地址
```
POST /console/invite-codes/
```

#### 请求头
```
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json
```

#### 请求参数 (CreateInviteCodeIn)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| count | integer | 否 | 生成数量（1-100，默认1） |
| expires_days | integer | 否 | 有效期天数（null表示永不过期） |
| note | string | 否 | 备注说明（最多255字符） |

#### 返回数据 (BatchInviteCodesOut)
```json
{
  "message": "邀请码生成成功",
  "data": {
    "codes": ["CODE-ABC123", "CODE-DEF456", "CODE-GHI789"],
    "count": 3,
    "expires_at": "2026-12-25 10:00:00"
  }
}
```

**返回字段说明：**
- `codes` (array[string])：生成的邀请码列表
- `count` (integer)：生成数量
- `expires_at` (string|null)：过期时间（null 表示永不过期）

#### CURL 示例
```bash
curl -X POST http://localhost:8000/console/invite-codes/ \
  -H "Authorization: Bearer <admin_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "count": 5,
    "expires_days": 30,
    "note": "测试邀请码"
  }'
```

---

### 获取邀请码列表

#### 接口地址
```
GET /console/invite-codes/
```

#### 请求头
```
Authorization: Bearer <admin_jwt_token>
```

#### 请求参数 (Query)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| only_unused | boolean | 否 | 是否仅显示未使用的邀请码（默认 false） |

#### 返回数据 (InviteCodeOut[])
```json
{
  "message": "获取成功",
  "data": [
    {
      "id": 1,
      "code": "CODE-ABC123",
      "is_used": false,
      "used_by_email": null,
      "expires_at": "2026-12-25 10:00:00",
      "note": "测试邀请码",
      "created_at": "2025-12-25 10:00:00",
      "used_at": null
    }
  ]
}
```

**返回字段说明 (InviteCodeOut)：**
- `id` (integer)：邀请码 ID
- `code` (string)：邀请码
- `is_used` (boolean)：是否已使用
- `used_by_email` (string|null)：使用者邮箱
- `expires_at` (string|null)：过期时间
- `note` (string)：备注说明
- `created_at` (string)：创建时间
- `used_at` (string|null)：使用时间

#### CURL 示例
```bash
# 获取所有邀请码
curl -X GET http://localhost:8000/console/invite-codes/ \
  -H "Authorization: Bearer <admin_jwt_token>"

# 仅获取未使用的邀请码
curl -X GET "http://localhost:8000/console/invite-codes/?only_unused=true" \
  -H "Authorization: Bearer <admin_jwt_token>"
```

---

### 删除邀请码

#### 接口地址
```
DELETE /console/invite-codes/{code_id}
```

#### 请求头
```
Authorization: Bearer <admin_jwt_token>
```

#### 返回数据
```json
{
  "message": "删除成功",
  "data": null
}
```

#### CURL 示例
```bash
curl -X DELETE http://localhost:8000/console/invite-codes/1 \
  -H "Authorization: Bearer <admin_jwt_token>"
```

---

## 错误响应示例

### 400 Bad Request
```json
{
  "message": "请求参数错误",
  "data": {
    "detail": "text 字段不能为空"
  }
}
```

### 401 Unauthorized
```json
{
  "message": "未授权",
  "data": {
    "detail": "Token 无效或已过期"
  }
}
```

### 404 Not Found
```json
{
  "message": "资源不存在",
  "data": {
    "job_uuid": "xxx"
  }
}
```

### 429 Too Many Requests
```json
{
  "message": "请求频率超限",
  "data": {
    "detail": "请稍后再试"
  }
}
```

---

## 调试提示

### 1. SSE 测试建议
- 使用 `curl --no-buffer ... --http1.1` 避免缓冲
- 可看到周期性的 `ping` 心跳（默认15秒）
- 配置项：`tts_stream_heartbeat_seconds`（心跳间隔）、`tts_stream_timeout_seconds`（超时时间）

### 2. 鉴权说明
- **Console 路由**：使用用户 JWT（通过 `/auth/login` 获取）
- **OpenAPI 路由**：使用 API Key（通过 `/console/api-keys` 创建，以 `sk-` 开头）

### 3. 幂等键
- OpenAPI 的 TTS 和克隆任务创建接口需要 `Idempotency-Key` 头部
- 相同幂等键的重复请求会返回同一任务
- 幂等键有效期：3600秒（1小时）

### 4. 任务状态
- `queued`：已入队等待处理
- `running`：正在处理
- `succeeded`：成功完成
- `failed`：处理失败

### 5. 文件访问
- 生成的音频通过 `/files/{relative_path}` 访问
- 例如：`/files/tts/1_job-uuid/output.mp3`
- 音色预览：`/files/voices/xxx/preview.mp3`

### 6. 计费规则
- 按输入文本的 UTF-8 字节数计费
- 默认单价：1 积分/字节（可配置）
- 最大文本长度：4000 字节（可配置）
- 失败任务会全额退款

### 7. 订阅计划
| 计划 | 月度积分 | 月度配额 | 克隆位 | API访问 | 商业使用 | 优先支持 |
|------|----------|----------|--------|---------|----------|----------|
| 免费版 | 1,000 | 100次 | 3个 | ❌ | ❌ | ❌ |
| 专业版 | 10,000 | 5,000次 | 20个 | ❌ | ✅ | ❌ |
| 企业版 | 100,000 | 500,000次 | 无限 | ✅ | ✅ | ✅ |
