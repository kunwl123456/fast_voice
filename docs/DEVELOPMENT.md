# 开发指南

本文档介绍 FastVoice 项目的开发工具配置、开发规范和最佳实践。

---

## 目录

- [开发工具配置](#开发工具配置)
  - [Git Hooks（pre-commit）](#git-hookspre-commit)
  - [数据库连接池配置](#数据库连接池配置)
  - [本地开发（热重载）](#本地开发热重载)
- [代码规范](#代码规范)
  - [代码格式化](#代码格式化)
  - [导入顺序](#导入顺序)
  - [命名规范](#命名规范)
- [最佳实践](#最佳实践)
  - [异步编程](#异步编程)
  - [数据库操作](#数据库操作)
  - [错误处理](#错误处理)

---

## 开发工具配置

### Git Hooks（pre-commit）

项目使用 pre-commit 自动检查代码质量。每次 `git commit` 时会自动运行代码检查和格式化。

#### 安装配置

```bash
# 1. 安装 pre-commit
pip install pre-commit

# 2. 安装 Git hooks
pre-commit install

# 3. 手动运行所有检查（可选）
pre-commit run --all-files
```

#### 自动执行的检查

每次提交时会自动运行：
- **ruff --fix** - 自动修复代码问题（未使用的导入、格式问题等）
- **black** - 格式化 Python 代码（统一代码风格）

#### 配置文件

`.pre-commit-config.yaml`:

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

#### 跳过检查（不推荐）

如果确实需要跳过检查（例如紧急修复）：

```bash
git commit --no-verify -m "Emergency fix"
```

---

### 数据库连接池配置

SQLAlchemy 连接池配置（仅对 PostgreSQL 生效，SQLite 使用 StaticPool）：

```bash
# 环境变量配置
DB_POOL_SIZE=10                 # 连接池大小（默认）
DB_MAX_OVERFLOW=20              # 最大溢出连接数
DB_POOL_TIMEOUT_SECONDS=30      # 获取连接超时（秒）
DB_POOL_RECYCLE_SECONDS=1800    # 连接回收时间（秒，30分钟）
```

#### 连接池参数说明

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `DB_POOL_SIZE` | 连接池基础大小 | 10-20（取决于并发量） |
| `DB_MAX_OVERFLOW` | 最大溢出连接 | 池大小的 2 倍 |
| `DB_POOL_TIMEOUT_SECONDS` | 获取连接超时 | 30 秒（API 场景） |
| `DB_POOL_RECYCLE_SECONDS` | 连接回收时间 | 1800 秒（30 分钟） |

#### 监控连接池

```python
from app.core.db import engine

# 查看连接池状态
pool = engine.pool
print(f"Pool size: {pool.size()}")
print(f"Checked out: {pool.checkedout()}")
print(f"Overflow: {pool.overflow()}")
```

---

### 本地开发（热重载）

#### API 服务开发

```bash
# 方式 1：使用 run.py（推荐，自动配置环境变量）
python run.py

# 方式 2：直接使用 uvicorn（需要手动配置环境变量）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 9000

# 方式 3：开启 DEBUG 日志
uv run uvicorn app.main:app --reload --log-level debug
```

#### Celery Worker 开发

```bash
# 开发模式启动（DEBUG 日志）
uv run celery -A app.tasks.celery_app:celery_app worker -l DEBUG -Q tts,clone

# 指定并发数（默认为 CPU 核心数）
uv run celery -A app.tasks.celery_app:celery_app worker -l INFO --concurrency=4

# 仅处理特定队列
uv run celery -A app.tasks.celery_app:celery_app worker -l INFO -Q tts
```

#### 热重载说明

- **API 服务**：`--reload` 参数会监控代码变化并自动重启
- **Celery Worker**：不支持热重载，需要手动重启
- **数据库模型**：修改模型后需要重新建表或迁移

---

## 代码规范

### 代码格式化

项目使用以下工具保证代码质量：

#### Black（代码格式化）

```bash
# 手动格式化所有代码
black .

# 检查但不修改
black --check .

# 格式化特定文件
black app/main.py
```

配置：
- 行长度：88 字符（Black 默认）
- 自动处理引号、空格、换行等

#### Ruff（代码检查）

```bash
# 自动修复问题
ruff --fix .

# 仅检查不修复
ruff check .

# 查看详细信息
ruff check . --show-files
```

Ruff 检查项：
- 未使用的导入和变量
- 代码复杂度
- 常见错误模式
- PEP 8 风格问题

---

### 导入顺序

遵循 PEP 8 导入顺序规范：

```python
# 1. 标准库导入
from __future__ import annotations
import os
import sys
from datetime import datetime
from typing import List, Optional

# 2. 第三方库导入
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 3. 本地应用导入
from app.core.models import User, Voice
from app.core.deps import get_db, require_console_user
from app.core.schemas import Response, VoiceOut
from app.routers import voices_console_router as router
```

#### 导入规则

1. **分组**：标准库、第三方库、本地应用，各组之间空一行
2. **排序**：每组内按字母顺序排序
3. **绝对导入**：优先使用绝对导入而非相对导入
4. **避免通配符**：除非必要（如 models），否则不使用 `from x import *`

---

### 命名规范

#### 变量和函数

```python
# ✅ 推荐：snake_case
user_id = 123
def get_user_by_id(user_id: int):
    pass

# ❌ 避免：camelCase
userId = 123
def getUserById(userId: int):
    pass
```

#### 类名

```python
# ✅ 推荐：PascalCase
class UserService:
    pass

class VoiceController:
    pass

# ❌ 避免：snake_case 或 camelCase
class user_service:
    pass
```

#### 常量

```python
# ✅ 推荐：UPPER_SNAKE_CASE
MAX_TEXT_LENGTH = 4000
DEFAULT_CREDIT_PRICE = 1

# ❌ 避免：普通命名
max_text_length = 4000
```

#### 私有成员

```python
# ✅ 使用下划线前缀
class MyClass:
    def __init__(self):
        self._private_var = 1
    
    def _private_method(self):
        pass

# ✅ 双下划线用于名称混淆
class MyClass:
    def __init__(self):
        self.__really_private = 1
```

---

## 最佳实践

### 异步编程

#### 使用 async/await

```python
# ✅ 推荐：异步函数
async def get_user(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

# ❌ 避免：在异步函数中使用同步代码
async def get_user_bad(db: Session, user_id: int):
    # 这会阻塞事件循环！
    return db.query(User).filter(User.id == user_id).first()
```

#### 并发操作

```python
import asyncio

# ✅ 推荐：使用 asyncio.gather 并发执行
async def get_multiple_users(db: AsyncSession, user_ids: list[int]):
    tasks = [get_user(db, uid) for uid in user_ids]
    return await asyncio.gather(*tasks)

# ❌ 避免：串行执行
async def get_multiple_users_bad(db: AsyncSession, user_ids: list[int]):
    users = []
    for uid in user_ids:
        users.append(await get_user(db, uid))  # 逐个等待
    return users
```

---

### 数据库操作

#### 使用查询构建器

```python
from sqlalchemy import select

# ✅ 推荐：使用 SQLAlchemy 2.0 风格
async def get_active_users(db: AsyncSession):
    stmt = select(User).where(User.is_active == True).order_by(User.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

# ❌ 避免：使用旧式 ORM 查询
def get_active_users_old(db: Session):
    return db.query(User).filter(User.is_active == True).order_by(User.created_at.desc()).all()
```

#### 事务处理

```python
# ✅ 推荐：使用依赖注入的 session（自动管理事务）
@router.post("/users")
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    user = User(**payload.dict())
    db.add(user)
    await db.flush()  # 获取自增 ID
    # 函数结束时自动 commit
    return user

# ✅ 推荐：需要手动控制事务时
async def transfer_credits(db: AsyncSession, from_user_id: int, to_user_id: int, amount: int):
    async with db.begin():  # 显式事务
        # 扣款
        await deduct_credits(db, from_user_id, amount)
        # 充值
        await add_credits(db, to_user_id, amount)
        # 自动 commit 或 rollback
```

#### 避免 N+1 查询

```python
from sqlalchemy.orm import selectinload

# ✅ 推荐：使用 eager loading
async def get_users_with_voices(db: AsyncSession):
    stmt = select(User).options(selectinload(User.voices))
    result = await db.execute(stmt)
    return result.scalars().all()

# ❌ 避免：在循环中查询（N+1 问题）
async def get_users_with_voices_bad(db: AsyncSession):
    users = await db.execute(select(User))
    for user in users:
        # 每个用户都会触发一次查询！
        voices = await db.execute(select(Voice).where(Voice.owner_id == user.id))
        user.voices = voices.scalars().all()
```

---

### 错误处理

#### 使用自定义异常

```python
from app.core.exceptions import NotFoundException, BadRequestException
from app.core.error_codes import VoiceError

# ✅ 推荐：抛出业务异常
async def get_voice_or_404(db: AsyncSession, voice_id: str):
    voice = await db.execute(select(Voice).where(Voice.uuid == voice_id))
    voice = voice.scalar_one_or_none()
    
    if not voice:
        raise NotFoundException(
            error=VoiceError.VOICE_NOT_FOUND,
            data={"voice_id": voice_id}
        )
    
    return voice

# ❌ 避免：返回 None 或使用通用异常
async def get_voice_bad(db: AsyncSession, voice_id: str):
    voice = await db.execute(select(Voice).where(Voice.uuid == voice_id))
    return voice.scalar_one_or_none()  # 调用方需要检查 None
```

#### 统一错误响应

```python
from app.core.responses import success_response, error_response

# ✅ 推荐：使用统一的响应格式
@router.get("/voices/{voice_id}")
async def get_voice(voice_id: str, db: AsyncSession = Depends(get_db)):
    voice = await get_voice_or_404(db, voice_id)
    return success_response("获取成功", voice.to_dict())

# 错误会被全局异常处理器捕获并返回统一格式：
# {
#     "code": 40401001,
#     "message": "音色不存在",
#     "data": {"voice_id": "xxx"}
# }
```

#### 参数验证

```python
from pydantic import BaseModel, Field, validator

# ✅ 推荐：使用 Pydantic 验证
class CreateVoiceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list)
    
    @validator("tags")
    def validate_tags(cls, v):
        if len(v) > 10:
            raise ValueError("标签数量不能超过 10 个")
        return v

# ❌ 避免：手动验证参数
@router.post("/voices")
async def create_voice_bad(name: str, description: str):
    if not name or len(name) > 50:
        raise BadRequestException(message="名称不合法")
    # ...
```

---

## 调试技巧

### 日志输出

```python
from loguru import logger

# 开发环境输出详细日志
logger.debug(f"Processing user_id: {user_id}")
logger.info(f"User {user.email} logged in")
logger.warning(f"Slow query detected: {query_time}ms")
logger.error(f"Failed to process payment: {exc}")
```

### SQL 查询日志

```python
# 在 app/core/db.py 中启用 SQL 日志
engine = create_async_engine(
    settings.database_url,
    echo=True,  # 打印所有 SQL 语句
    # ...
)
```

### 性能分析

```python
import time

async def slow_function():
    start = time.time()
    # ... 业务逻辑
    elapsed = time.time() - start
    logger.info(f"Function took {elapsed:.2f}s")
```

---

## 常见问题

### Q: pre-commit 检查失败怎么办？

A: 检查错误信息，通常是代码格式或导入顺序问题：
```bash
# 自动修复大部分问题
ruff --fix .
black .

# 重新提交
git add .
git commit -m "Fix code style"
```

### Q: 数据库连接池耗尽？

A: 检查是否有未关闭的连接或死锁：
```python
# 检查连接池状态
from app.core.db import engine
print(f"Checked out: {engine.pool.checkedout()}")

# 增加池大小
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

### Q: Celery 任务不执行？

A: 检查：
1. Worker 是否启动：`celery -A app.tasks.celery_app:celery_app inspect active`
2. Redis 是否连接：`redis-cli ping`
3. 队列名称是否匹配：任务装饰器的 `queue` 参数

---

## 相关文档

- [错误码文档](../app/core/error_codes.py) - 业务错误码定义

