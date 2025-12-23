"""
统一的 API 响应格式
所有 API 响应都应该包含 message、data 两个字段
HTTP 状态码通过响应头返回，不在 body 中重复
"""

from typing import Any, Optional
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一的 API 响应格式"""

    message: str  # 响应消息
    data: Any = None  # 响应数据


class PaginatedData(BaseModel):
    """分页数据格式"""

    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


def success_response(
    message: str = "操作成功", data: Any = None, status_code: int = 200
) -> JSONResponse:
    """
    成功响应

    Args:
        message: 成功消息
        data: 返回的数据
        status_code: HTTP 状态码（默认 200）

    Returns:
        JSONResponse

    Example:
        >>> return success_response("用户创建成功", {"user_id": 1})
        HTTP/1.1 200 OK
        {
            "message": "用户创建成功",
            "data": {"user_id": 1}
        }
    """
    return JSONResponse(
        status_code=status_code, content={"message": message, "data": data}
    )


def error_response(
    message: str = "操作失败", data: Any = None, status_code: int = 400
) -> JSONResponse:
    """
    错误响应

    Args:
        message: 错误消息
        data: 额外的错误信息（可选）
        status_code: HTTP 状态码（默认 400）

    Returns:
        JSONResponse

    Example:
        >>> return error_response("用户名已存在", {"field": "username"}, 409)
        HTTP/1.1 409 Conflict
        {
            "message": "用户名已存在",
            "data": {"field": "username"}
        }
    """
    return JSONResponse(
        status_code=status_code, content={"message": message, "data": data}
    )


def paginated_response(
    message: str = "查询成功",
    items: list[Any] = None,
    total: int = 0,
    page: int = 1,
    page_size: int = 10,
) -> JSONResponse:
    """
    分页响应

    Args:
        message: 响应消息
        items: 数据列表
        total: 总数
        page: 当前页码
        page_size: 每页大小

    Returns:
        JSONResponse

    Example:
        >>> return paginated_response("获取用户列表成功", users, 100, 1, 10)
        HTTP/1.1 200 OK
        {
            "message": "获取用户列表成功",
            "data": {
                "items": [...],
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10,
                "has_next": true,
                "has_prev": false
            }
        }
    """
    items = items or []
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return JSONResponse(
        status_code=200,
        content={
            "message": message,
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        },
    )


def created_response(message: str = "创建成功", data: Any = None) -> JSONResponse:
    """
    资源创建成功响应 (HTTP 201)

    Args:
        message: 成功消息
        data: 创建的资源数据

    Returns:
        JSONResponse
    """
    return success_response(message, data, status_code=201)


def updated_response(message: str = "更新成功", data: Any = None) -> JSONResponse:
    """
    资源更新成功响应 (HTTP 200)

    Args:
        message: 成功消息
        data: 更新后的资源数据

    Returns:
        JSONResponse
    """
    return success_response(message, data, status_code=200)


def deleted_response(message: str = "删除成功", data: Any = None) -> JSONResponse:
    """
    资源删除成功响应 (HTTP 200)

    Args:
        message: 成功消息
        data: 额外信息（可选）

    Returns:
        JSONResponse
    """
    return success_response(message, data, status_code=200)


def not_found_response(message: str = "资源不存在", data: Any = None) -> JSONResponse:
    """
    资源未找到响应 (HTTP 404)

    Args:
        message: 错误消息
        data: 额外信息

    Returns:
        JSONResponse
    """
    return error_response(message, data, status_code=404)


def unauthorized_response(message: str = "未授权", data: Any = None) -> JSONResponse:
    """
    未授权响应 (HTTP 401)

    Args:
        message: 错误消息
        data: 额外信息

    Returns:
        JSONResponse
    """
    return error_response(message, data, status_code=401)


def forbidden_response(message: str = "无权限", data: Any = None) -> JSONResponse:
    """
    禁止访问响应 (HTTP 403)

    Args:
        message: 错误消息
        data: 额外信息

    Returns:
        JSONResponse
    """
    return error_response(message, data, status_code=403)


def validation_error_response(
    message: str = "参数验证失败", errors: Optional[dict] = None
) -> JSONResponse:
    """
    参数验证错误响应 (HTTP 422)

    Args:
        message: 错误消息
        errors: 验证错误详情

    Returns:
        JSONResponse

    Example:
        >>> return validation_error_response("参数验证失败", {
        ...     "email": "邮箱格式不正确",
        ...     "password": "密码长度不足"
        ... })
        HTTP/1.1 422 Unprocessable Entity
        {
            "message": "参数验证失败",
            "data": {
                "errors": {
                    "email": "邮箱格式不正确",
                    "password": "密码长度不足"
                }
            }
        }
    """
    return error_response(message, {"errors": errors or {}}, status_code=422)


def server_error_response(
    message: str = "服务器内部错误", data: Any = None
) -> JSONResponse:
    """
    服务器错误响应 (HTTP 500)

    Args:
        message: 错误消息
        data: 错误详情（生产环境应隐藏）

    Returns:
        JSONResponse
    """
    return error_response(message, data, status_code=500)


def conflict_response(message: str = "资源冲突", data: Any = None) -> JSONResponse:
    """
    资源冲突响应 (HTTP 409)

    Args:
        message: 错误消息
        data: 冲突详情

    Returns:
        JSONResponse

    Example:
        >>> return conflict_response("邮箱已被注册", {"email": "test@example.com"})
        HTTP/1.1 409 Conflict
        {
            "message": "邮箱已被注册",
            "data": {"email": "test@example.com"}
        }
    """
    return error_response(message, data, status_code=409)


def bad_request_response(
    message: str = "请求参数错误", data: Any = None
) -> JSONResponse:
    """
    错误请求响应 (HTTP 400)

    Args:
        message: 错误消息
        data: 错误详情

    Returns:
        JSONResponse
    """
    return error_response(message, data, status_code=400)
