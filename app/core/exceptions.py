"""
统一异常定义

所有异常类都支持错误码，可以在抛出异常时指定具体的错误码
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.error_codes import ErrorCode


class AppException(Exception):
    """
    应用基础异常类

    所有业务异常都应该继承此类，支持错误码和自定义消息
    """

    def __init__(
        self,
        message: str | None = None,
        error: "ErrorCode | None" = None,
        data: Any = None,
    ):
        """
        初始化异常

        Args:
            message: 自定义错误消息（可选，默认使用错误码的消息）
            error: 错误码对象（可选）
            data: 额外的错误数据（可选）
        """
        self.error = error
        self.data = data

        # 确定最终的错误消息
        if message:
            self.message = message
        elif error:
            self.message = error.message
        else:
            self.message = "未知错误"

        super().__init__(self.message)

    @property
    def code(self) -> int:
        """获取错误码"""
        if self.error:
            return self.error.code
        return 0

    @property
    def http_status(self) -> int:
        """获取 HTTP 状态码"""
        if self.error:
            return self.error.http_status
        return 500


class AuthenticationException(AppException):
    """鉴权错误"""

    def __init__(
        self,
        message: str | None = None,
        error: "ErrorCode | None" = None,
        data: Any = None,
    ):
        if error is None:
            from app.core.error_codes import CommonError

            error = CommonError.UNAUTHORIZED
        super().__init__(message, error, data)


class PermissionException(AppException):
    """权限错误"""

    def __init__(
        self,
        message: str | None = None,
        error: "ErrorCode | None" = None,
        data: Any = None,
    ):
        if error is None:
            from app.core.error_codes import CommonError

            error = CommonError.FORBIDDEN
        super().__init__(message, error, data)


class NotFoundException(AppException):
    """未找到"""

    def __init__(
        self,
        message: str | None = None,
        error: "ErrorCode | None" = None,
        data: Any = None,
    ):
        if error is None:
            from app.core.error_codes import CommonError

            error = CommonError.NOT_FOUND
        super().__init__(message, error, data)


class BadRequestException(AppException):
    """请求参数错误"""

    def __init__(
        self,
        message: str | None = None,
        error: "ErrorCode | None" = None,
        data: Any = None,
    ):
        if error is None:
            from app.core.error_codes import CommonError

            error = CommonError.BAD_REQUEST
        super().__init__(message, error, data)


class ConflictException(AppException):
    """资源冲突"""

    def __init__(
        self,
        message: str | None = None,
        error: "ErrorCode | None" = None,
        data: Any = None,
    ):
        if error is None:
            from app.core.error_codes import CommonError

            error = CommonError.CONFLICT
        super().__init__(message, error, data)


class InternalServerException(AppException):
    """服务器内部错误"""

    def __init__(
        self,
        message: str | None = None,
        error: "ErrorCode | None" = None,
        data: Any = None,
    ):
        if error is None:
            from app.core.error_codes import CommonError

            error = CommonError.INTERNAL_ERROR
        super().__init__(message, error, data)
