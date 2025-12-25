"""账户和认证相关路由"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, File, UploadFile

from app.responses import (
    success_response,
    created_response,
    conflict_response,
    unauthorized_response,
    bad_request_response,
)
from app.deps import get_db, require_console_user
from app.models import User
from app.controller.account import (
    build_user_response,
    build_register_response,
    register_user,
    login_user,
    update_user_name,
    upload_user_avatar,
    update_user_avatar_url,
    change_user_password,
    validate_avatar_file,
)
from app.schemas import (
    Response,
    ChangePasswordIn,
    LoginIn,
    MeOut,
    RegisterIn,
    RegisterOut,
    RenameIn,
    TokenOut,
    UpdateAvatarIn,
)

router = APIRouter(prefix="/console", tags=["账户与认证"])


@router.post("/auth/register", summary="账号注册", response_model=Response[RegisterOut])
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    """
    用户注册接口

    ### 功能说明
    - 验证邮箱是否已被注册
    - 创建新用户账号
    - 自动创建积分账户
    - 赠送免费版初始积分

    ### 注册流程
    1. 检查邮箱是否已存在
    2. 创建用户记录（默认为免费版订阅）
    3. 创建积分账户（初始积分根据系统配置）
    4. 记录积分流水
    5. 返回用户基本信息
    """
    u, error = await register_user(
        db, payload.email, payload.password, payload.display_name
    )
    if error:
        return conflict_response(error, {"email": payload.email})

    user_data = await build_register_response(db, u)
    return created_response("注册成功", user_data.model_dump())


@router.post("/auth/login", summary="账号登录", response_model=Response[TokenOut])
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    """
    用户登录接口

    ### 功能说明
    - 验证用户邮箱和密码
    - 生成访问令牌（JWT Token）
    - 返回 Bearer Token 用于后续 API 调用

    ### 登录流程
    1. 根据邮箱查找用户
    2. 验证密码是否正确
    3. 生成访问令牌（包含用户标识）
    4. 返回 Token

    ### 使用说明
    获取 Token 后，在后续请求的 Header 中添加：
    ```
    Authorization: Bearer {access_token}
    ```
    """
    token, error = await login_user(db, payload.email, payload.password)
    if error:
        return unauthorized_response(error)

    token_data = TokenOut(access_token=token)
    return success_response("登录成功", token_data.model_dump())


@router.get("/me", summary="获取账号信息", response_model=Response[MeOut])
async def me(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_console_user)
):
    """
    获取当前登录用户的账号信息

    ### 功能说明
    - 获取用户基本信息
    - 获取当前订阅计划
    - 获取积分账户余额

    ### 认证要求
    需要在请求头中携带有效的访问令牌：
    ```
    Authorization: Bearer {access_token}
    ```
    """
    user_data = await build_user_response(db, user)
    return success_response("获取成功", user_data.model_dump())


@router.post("/me/rename", summary="修改昵称", response_model=Response[MeOut])
async def rename(
    payload: RenameIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    修改当前用户的昵称

    ### 功能说明
    - 更新用户的显示名称
    - 返回更新后的用户信息
    """
    await update_user_name(db, user, payload.display_name)
    user_data = await build_user_response(db, user)
    return success_response("修改成功", user_data.model_dump())


@router.post("/me/avatar/upload", summary="上传头像")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    上传用户头像图片

    ### 功能说明
    - 上传图片文件作为用户头像
    - 自动保存到服务器并生成访问 URL
    - 更新用户头像地址

    ### 文件要求
    - **支持格式**: JPG, JPEG, PNG, GIF, WebP
    - **文件大小**: 最大 5MB
    - **Content-Type**: 必须是 `image/*` 类型

    ### 存储规则
    - 文件保存路径：`data/avatars/{user_uuid}.{ext}`
    - 旧头像会被新上传的图片覆盖

    ### 返回内容
    - 更新后的用户信息（包含新的 avatar_url）
    - 积分余额
    """
    # 读取文件内容
    content = await file.read()

    # 验证文件
    is_valid, error_msg, file_ext = validate_avatar_file(
        file.content_type, file.filename, content
    )
    if not is_valid:
        return bad_request_response(error_msg)

    # 上传头像
    avatar_url, error = await upload_user_avatar(db, user, content, file_ext)
    if error:
        return bad_request_response(error)

    user_data = await build_user_response(db, user)
    return success_response("头像上传成功", user_data.model_dump())


@router.post("/me/avatar", summary="更新头像链接", response_model=Response[MeOut])
async def update_avatar(
    payload: UpdateAvatarIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    更新用户头像 URL（使用外部链接）

    ### 功能说明
    - 使用外部图片链接设置头像
    - 适用于使用第三方图片托管服务

    ### 返回内容
    - 更新后的用户信息
    - 积分余额
    """
    await update_user_avatar_url(db, user, payload.avatar_url)
    user_data = await build_user_response(db, user)
    return success_response("头像更新成功", user_data.model_dump())


@router.post("/me/change-password", summary="修改密码", response_model=Response[None])
async def change_password(
    payload: ChangePasswordIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_console_user),
):
    """
    修改当前用户的登录密码

    ### 功能说明
    - 验证原密码是否正确
    - 更新为新密码（自动加密存储）

    ### 安全说明
    - 必须提供正确的原密码
    - 密码使用 bcrypt 算法加密存储
    - 修改密码后需要重新登录
    """
    success, error = await change_user_password(
        db, user, payload.old_password, payload.new_password
    )
    if not success:
        return bad_request_response(error)
    return success_response("密码修改成功")
