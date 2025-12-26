"""账户数据访问服务层"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User


async def update_user(
    db: AsyncSession,
    user: User,
    update_fn: Callable[[User], None],
) -> None:
    """
    通用的用户信息更新函数

    ### 功能说明
    - 提供统一的用户更新接口
    - 自动处理数据库会话的 add 和 flush 操作
    - 使用回调函数模式，支持任意字段更新

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - update_fn: 更新回调函数，接收 user 对象并修改其属性

    ### 使用示例
    ```python
    # 更新用户昵称
    await update_user(db, user, lambda u: setattr(u, 'display_name', '新昵称'))

    # 更新多个字段
    def update_multiple(u: User):
        u.display_name = '新昵称'
        u.avatar_url = 'https://example.com/avatar.jpg'
    await update_user(db, user, update_multiple)
    ```
    """
    update_fn(user)
    db.add(user)
    await db.flush()


async def update_user_field(
    db: AsyncSession,
    user: User,
    field_name: str,
    field_value: any,
) -> None:
    """
    更新用户单个字段（简化版）

    ### 参数
    - db: 数据库会话
    - user: 用户对象
    - field_name: 字段名称
    - field_value: 字段值

    ### 使用示例
    ```python
    await update_user_field(db, user, 'display_name', '新昵称')
    await update_user_field(db, user, 'avatar_url', 'https://example.com/avatar.jpg')
    ```
    """
    setattr(user, field_name, field_value)
    db.add(user)
    await db.flush()
