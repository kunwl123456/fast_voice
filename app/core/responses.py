"""
统一的 API 响应格式
所有 API 响应都应该包含 code、message、data 三个字段
- code: 业务错误码（0 表示成功，非 0 表示错误）
- message: 响应消息
- data: 响应数据
HTTP 状态码通过响应头返回
"""

from typing import Any
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.error_codes import ErrorCode, Success


class ApiResponse(BaseModel):
    """统一的 API 响应格式"""

    code: int = 0  # 业务错误码（0 表示成功）
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
            "code": 0,
            "message": "用户创建成功",
            "data": {"user_id": 1}
        }
    """
    return JSONResponse(
        status_code=status_code,
        content={"code": Success.OK.code, "message": message, "data": data},
    )


def error_response(
    error: ErrorCode,
    message: str | None = None,
    data: Any = None,
) -> JSONResponse:
    """
    错误响应

    Args:
        error: 错误码对象
        message: 自定义错误消息（可选，默认使用错误码的消息）
        data: 额外的错误信息（可选）

    Returns:
        JSONResponse

    Example:
        >>> from app.core.error_codes import AccountError
        >>> return error_response(AccountError.EMAIL_EXISTS)
        HTTP/1.1 409 Conflict
        {
            "code": 40901001,
            "message": "该邮箱已被注册",
            "data": null
        }
    """
    return JSONResponse(
        status_code=error.http_status,
        content={
            "code": error.code,
            "message": message or error.message,
            "data": data,
        },
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
            "code": 0,
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
            "code": Success.OK.code,
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
