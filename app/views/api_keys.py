"""API Key 管理相关路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.responses import (
    success_response,
    created_response,
    forbidden_response,
    not_found_response,
)
from app.deps import get_db, require_console_user
from app.models import User
from app.controller.api_keys import (
    check_enterprise_permission,
    create_user_api_key,
    delete_user_api_key,
    list_user_api_keys,
    rotate_user_api_key,
)
from app.schemas import Response, ApiKeyListItem, ApiKeyOut, CreateApiKeyIn

router = APIRouter(prefix="/console", tags=["API Key 管理"])


@router.get(
    "/api-keys", summary="列出 API Key", response_model=Response[ApiKeyListItem]
)
async def list_api_keys(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """
    获取当前用户的所有 API Keys

    ### 功能说明
    - 列出用户创建的所有 API Key
    - 显示 Key 的状态和有效期
    - API Key 部分脱敏显示

    ### 权限要求
    - **仅限企业版用户**使用
    - 其他订阅计划用户会返回 403 错误

    ### 排序规则
    按创建时间倒序排列（最新的在前）
    """
    if not check_enterprise_permission(user):
        return forbidden_response("API访问需要企业版订阅")

    api_keys_list = await list_user_api_keys(db, user)
    api_keys_data = [k.model_dump() for k in api_keys_list]

    return success_response("获取成功", api_keys_data)


@router.post("/api-keys", summary="创建 API Key", response_model=Response[ApiKeyOut])
async def create_api_key(
    payload: CreateApiKeyIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    创建新的 API Key

    ### 功能说明
    - 生成新的 API Key（格式：sk-xxx）
    - 设置 Key 的名称和有效期
    - 返回完整的 Key 内容（仅此一次显示）

    ### 权限要求
    - **仅限企业版用户**使用

    ### 安全提示
    ⚠️ **API Key 仅在创建时完整显示一次，请妥善保管！**

    后续查询只会显示脱敏后的 Key，无法查看完整内容。

    ### 使用说明
    创建后，在 API 请求头中使用：
    ```
    Authorization: Bearer {api_key}
    ```
    """
    if not check_enterprise_permission(user):
        return forbidden_response("API访问需要企业版订阅")

    api_key_data = await create_user_api_key(
        db, user, payload.name, payload.expires_days
    )
    return created_response("API Key 创建成功", api_key_data.model_dump())


@router.delete(
    "/api-keys/{key_id}", summary="删除 API Key", response_model=Response[None]
)
async def delete_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    删除指定的 API Key

    ### 功能说明
    - 永久删除指定的 API Key
    - 删除后该 Key 立即失效
    - 无法恢复，请谨慎操作

    ### 安全验证
    - 只能删除属于当前用户的 API Key
    - 删除不存在或不属于自己的 Key 会返回 404 错误

    ### 返回内容
    - 成功消息

    ### 使用场景
    - Key 泄露需要立即作废
    - 定期轮换 API Key
    - 清理不再使用的 Key
    """
    key = await delete_user_api_key(db, user, key_id)
    if not key:
        return not_found_response("API Key 不存在", {"key_id": key_id})

    return success_response("删除成功")


@router.post(
    "/api-keys/rotate", summary="轮换 API Key", response_model=Response[ApiKeyOut]
)
async def rotate_api_key(
    payload: CreateApiKeyIn = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    轮换 API Key（禁用旧 Key，创建新 Key）

    ### 功能说明
    - 创建一个新的 API Key
    - 自动禁用所有旧的 API Key
    - 确保安全的 Key 更新流程

    ### 权限要求
    - **仅限企业版用户**使用

    ### 轮换流程
    1. 生成新的 API Key
    2. 禁用所有旧的 API Key（is_active = false）
    3. 返回新的 Key（仅此一次显示完整内容）

    ### 安全提示
    ⚠️ **轮换后，所有旧的 API Key 将立即失效！**

    请确保：
    - 更新所有使用旧 Key 的服务
    - 妥善保管新的 Key

    ### 使用场景
    - 定期安全轮换
    - Key 可能泄露时紧急更换
    - 批量禁用所有旧 Key
    """
    if not check_enterprise_permission(user):
        return forbidden_response("API访问需要企业版订阅")

    # 确定 API Key 名称和有效期
    name = "Production Key"
    expires_days = payload.expires_days if payload else None

    api_key_data = await rotate_user_api_key(db, user, name, expires_days)
    return created_response("API Key 轮换成功", api_key_data.model_dump())
