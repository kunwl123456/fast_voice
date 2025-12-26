"""
统一错误码管理

错误码格式：HTTP状态码(3位) + 模块代码(2位) + 错误序号(3位) = 8位数字
例如：40401001 = 404(未找到) + 01(用户模块) + 001(用户未找到)

模块代码分配：
    00 - 通用/系统
    01 - 用户/账户 (account)
    02 - 音色 (voices)
    03 - 克隆 (clone)
    04 - TTS
    05 - API Key
    06 - 积分 (credits)
    07 - 订阅 (subscription)
    08 - 邀请码 (invite_codes)
    09 - 数据分析 (analytics)
"""

from dataclasses import dataclass
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

# ============================================================================
# 模块代码常量
# ============================================================================


class Module:
    """模块代码"""

    COMMON = "00"  # 通用/系统
    ACCOUNT = "01"  # 用户/账户
    VOICE = "02"  # 音色
    CLONE = "03"  # 克隆
    TTS = "04"  # TTS
    API_KEY = "05"  # API Key
    CREDIT = "06"  # 积分
    SUBSCRIPTION = "07"  # 订阅
    INVITE_CODE = "08"  # 邀请码
    ANALYTICS = "09"  # 数据分析


# ============================================================================
# 错误码数据类
# ============================================================================


@dataclass(frozen=True)
class ErrorCode:
    """错误码定义"""

    code: int  # 唯一错误码
    message: str  # 默认错误消息
    http_status: int  # HTTP 状态码

    def with_message(self, message: str) -> "ErrorCode":
        """返回一个带有自定义消息的新错误码实例"""
        return ErrorCode(code=self.code, message=message, http_status=self.http_status)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


def _make_code(http_status: int, module: str, seq: int, msg: str) -> ErrorCode:
    """
    生成错误码

    Args:
        http_status: HTTP 状态码 (3位)
        module: 模块代码 (2位字符串)
        seq: 错误序号 (3位)

    Returns:
        8位整数错误码
    """
    return ErrorCode(int(f"{http_status}{module}{seq:03d}"), msg, http_status)


# ============================================================================
# 成功码
# ============================================================================


class Success:
    """成功响应码"""

    OK = ErrorCode(0, "操作成功", 200)


# ============================================================================
# 通用错误码 (模块 00)
# ============================================================================


class CommonError:
    """通用/系统错误"""

    # 400 Bad Request
    BAD_REQUEST = _make_code(HTTP_400_BAD_REQUEST, Module.COMMON, 1, "请求参数错误")
    VALIDATION_ERROR = _make_code(
        HTTP_400_BAD_REQUEST, Module.COMMON, 2, "参数验证失败"
    )
    INVALID_PAGINATION = _make_code(
        HTTP_400_BAD_REQUEST, Module.COMMON, 3, "分页参数无效"
    )

    # 401 Unauthorized
    UNAUTHORIZED = _make_code(HTTP_401_UNAUTHORIZED, Module.COMMON, 1, "未授权访问")
    TOKEN_EXPIRED = _make_code(HTTP_401_UNAUTHORIZED, Module.COMMON, 2, "令牌已过期")
    TOKEN_INVALID = _make_code(HTTP_401_UNAUTHORIZED, Module.COMMON, 3, "令牌无效")

    # 403 Forbidden
    FORBIDDEN = _make_code(HTTP_403_FORBIDDEN, Module.COMMON, 1, "无权限访问")

    # 404 Not Found
    NOT_FOUND = _make_code(HTTP_404_NOT_FOUND, Module.COMMON, 1, "资源不存在")

    # 409 Conflict
    CONFLICT = _make_code(HTTP_409_CONFLICT, Module.COMMON, 1, "资源冲突")

    # 429 Too Many Requests
    RATE_LIMITED = _make_code(
        HTTP_429_TOO_MANY_REQUESTS, Module.COMMON, 1, "请求过于频繁"
    )

    # 500 Internal Server Error
    INTERNAL_ERROR = _make_code(
        HTTP_500_INTERNAL_SERVER_ERROR, Module.COMMON, 1, "服务器内部错误"
    )
    DATABASE_ERROR = _make_code(
        HTTP_500_INTERNAL_SERVER_ERROR, Module.COMMON, 2, "数据库错误"
    )

    # 503 Service Unavailable
    SERVICE_UNAVAILABLE = _make_code(503, Module.COMMON, 1, "服务暂不可用")


# ============================================================================
# 用户/账户错误码 (模块 01)
# ============================================================================


class AccountError:
    """用户/账户相关错误"""

    # 400 Bad Request
    INVALID_PASSWORD_FORMAT = _make_code(
        HTTP_400_BAD_REQUEST, Module.ACCOUNT, 1, "密码格式不正确"
    )
    INVALID_EMAIL_FORMAT = _make_code(
        HTTP_400_BAD_REQUEST, Module.ACCOUNT, 2, "邮箱格式不正确"
    )
    PASSWORD_TOO_WEAK = _make_code(
        HTTP_400_BAD_REQUEST, Module.ACCOUNT, 3, "密码强度不足"
    )
    AVATAR_FORMAT_ERROR = _make_code(
        HTTP_400_BAD_REQUEST, Module.ACCOUNT, 4, "头像格式不支持"
    )
    AVATAR_SIZE_ERROR = _make_code(
        HTTP_400_BAD_REQUEST, Module.ACCOUNT, 5, "头像文件过大"
    )

    # 401 Unauthorized
    LOGIN_FAILED = _make_code(
        HTTP_401_UNAUTHORIZED, Module.ACCOUNT, 1, "用户名或密码错误"
    )
    OLD_PASSWORD_WRONG = _make_code(
        HTTP_401_UNAUTHORIZED, Module.ACCOUNT, 2, "原密码错误"
    )

    # 404 Not Found
    USER_NOT_FOUND = _make_code(HTTP_404_NOT_FOUND, Module.ACCOUNT, 1, "用户不存在")

    # 409 Conflict
    EMAIL_EXISTS = _make_code(HTTP_409_CONFLICT, Module.ACCOUNT, 1, "该邮箱已被注册")
    USERNAME_EXISTS = _make_code(
        HTTP_409_CONFLICT, Module.ACCOUNT, 2, "该用户名已被使用"
    )


# ============================================================================
# 音色错误码 (模块 02)
# ============================================================================


class VoiceError:
    """音色相关错误"""

    # 400 Bad Request
    INVALID_VOICE_PARAMS = _make_code(
        HTTP_400_BAD_REQUEST, Module.VOICE, 1, "音色参数无效"
    )

    # 404 Not Found
    VOICE_NOT_FOUND = _make_code(HTTP_404_NOT_FOUND, Module.VOICE, 1, "音色不存在")

    # 409 Conflict
    VOICE_NAME_EXISTS = _make_code(HTTP_409_CONFLICT, Module.VOICE, 1, "音色名称已存在")


# ============================================================================
# 克隆错误码 (模块 03)
# ============================================================================


class CloneError:
    """克隆相关错误"""

    # 400 Bad Request
    INVALID_AUDIO_FORMAT = _make_code(
        HTTP_400_BAD_REQUEST, Module.CLONE, 1, "音频格式不支持"
    )
    AUDIO_TOO_SHORT = _make_code(HTTP_400_BAD_REQUEST, Module.CLONE, 2, "音频时长过短")
    AUDIO_TOO_LONG = _make_code(HTTP_400_BAD_REQUEST, Module.CLONE, 3, "音频时长过长")

    # 403 Forbidden
    CLONE_LIMIT_EXCEEDED = _make_code(
        HTTP_403_FORBIDDEN, Module.CLONE, 1, "克隆位已达上限"
    )

    # 404 Not Found
    CLONE_NOT_FOUND = _make_code(HTTP_404_NOT_FOUND, Module.CLONE, 1, "克隆音色不存在")

    # 409 Conflict
    CLONE_NAME_EXISTS = _make_code(
        HTTP_409_CONFLICT, Module.CLONE, 1, "克隆音色名称已存在"
    )


# ============================================================================
# TTS 错误码 (模块 04)
# ============================================================================


class TTSError:
    """TTS 相关错误"""

    # 400 Bad Request
    TEXT_TOO_LONG = _make_code(HTTP_400_BAD_REQUEST, Module.TTS, 1, "文本内容过长")
    TEXT_EMPTY = _make_code(HTTP_400_BAD_REQUEST, Module.TTS, 2, "文本内容为空")
    INVALID_TTS_PARAMS = _make_code(HTTP_400_BAD_REQUEST, Module.TTS, 3, "TTS 参数无效")

    # 402 Payment Required
    INSUFFICIENT_CREDITS = _make_code(
        HTTP_402_PAYMENT_REQUIRED, Module.TTS, 1, "积分不足"
    )

    # 500 Internal Server Error
    TTS_GENERATION_FAILED = _make_code(
        HTTP_500_INTERNAL_SERVER_ERROR, Module.TTS, 1, "语音生成失败"
    )


# ============================================================================
# API Key 错误码 (模块 05)
# ============================================================================


class ApiKeyError:
    """API Key 相关错误"""

    # 400 Bad Request
    INVALID_API_KEY_NAME = _make_code(
        HTTP_400_BAD_REQUEST, Module.API_KEY, 1, "API Key 名称无效"
    )

    # 401 Unauthorized
    API_KEY_INVALID = _make_code(
        HTTP_401_UNAUTHORIZED, Module.API_KEY, 1, "API Key 无效"
    )
    API_KEY_EXPIRED = _make_code(
        HTTP_401_UNAUTHORIZED, Module.API_KEY, 2, "API Key 已过期"
    )
    API_KEY_DISABLED = _make_code(
        HTTP_401_UNAUTHORIZED, Module.API_KEY, 3, "API Key 已禁用"
    )

    # 403 Forbidden
    API_ACCESS_DENIED = _make_code(
        HTTP_403_FORBIDDEN, Module.API_KEY, 1, "API 访问需要企业版订阅"
    )

    # 404 Not Found
    API_KEY_NOT_FOUND = _make_code(
        HTTP_404_NOT_FOUND, Module.API_KEY, 1, "API Key 不存在"
    )


# ============================================================================
# 积分错误码 (模块 06)
# ============================================================================


class CreditError:
    """积分相关错误"""

    # 400 Bad Request
    INVALID_CREDIT_AMOUNT = _make_code(
        HTTP_400_BAD_REQUEST, Module.CREDIT, 1, "积分数量无效"
    )

    # 402 Payment Required
    INSUFFICIENT_BALANCE = _make_code(
        HTTP_402_PAYMENT_REQUIRED, Module.CREDIT, 1, "积分余额不足"
    )

    # 404 Not Found
    CREDIT_ACCOUNT_NOT_FOUND = _make_code(
        HTTP_404_NOT_FOUND, Module.CREDIT, 1, "积分账户不存在"
    )
    TRANSACTION_NOT_FOUND = _make_code(
        HTTP_404_NOT_FOUND, Module.CREDIT, 2, "交易记录不存在"
    )


# ============================================================================
# 订阅错误码 (模块 07)
# ============================================================================


class SubscriptionError:
    """订阅相关错误"""

    # 400 Bad Request
    INVALID_PLAN = _make_code(
        HTTP_400_BAD_REQUEST, Module.SUBSCRIPTION, 1, "无效的订阅计划"
    )
    INVALID_DURATION = _make_code(
        HTTP_400_BAD_REQUEST, Module.SUBSCRIPTION, 2, "无效的订阅时长"
    )

    # 402 Payment Required
    PAYMENT_REQUIRED = _make_code(
        HTTP_402_PAYMENT_REQUIRED, Module.SUBSCRIPTION, 1, "需要付款"
    )
    PAYMENT_FAILED = _make_code(
        HTTP_402_PAYMENT_REQUIRED, Module.SUBSCRIPTION, 2, "支付失败"
    )

    # 403 Forbidden
    PLAN_DOWNGRADE_NOT_ALLOWED = _make_code(
        HTTP_403_FORBIDDEN, Module.SUBSCRIPTION, 1, "不允许降级订阅"
    )
    FEATURE_NOT_IN_PLAN = _make_code(
        HTTP_403_FORBIDDEN, Module.SUBSCRIPTION, 2, "当前订阅计划不支持此功能"
    )

    # 409 Conflict
    SUBSCRIPTION_ACTIVE = _make_code(
        HTTP_409_CONFLICT, Module.SUBSCRIPTION, 1, "已有有效订阅"
    )


# ============================================================================
# 邀请码错误码 (模块 08)
# ============================================================================


class InviteCodeError:
    """邀请码相关错误"""

    # 400 Bad Request
    INVALID_INVITE_CODE_FORMAT = _make_code(
        HTTP_400_BAD_REQUEST, Module.INVITE_CODE, 1, "邀请码格式无效"
    )

    # 404 Not Found
    INVITE_CODE_NOT_FOUND = _make_code(
        HTTP_404_NOT_FOUND, Module.INVITE_CODE, 1, "邀请码不存在"
    )

    # 409 Conflict
    INVITE_CODE_USED = _make_code(
        HTTP_409_CONFLICT, Module.INVITE_CODE, 1, "邀请码已被使用"
    )

    # 410 Gone
    INVITE_CODE_EXPIRED = _make_code(410, Module.INVITE_CODE, 1, "邀请码已过期")


# ============================================================================
# 数据分析错误码 (模块 09)
# ============================================================================


class AnalyticsError:
    """数据分析相关错误"""

    # 400 Bad Request
    INVALID_STATS_PERIOD = _make_code(
        HTTP_400_BAD_REQUEST, Module.ANALYTICS, 2, "统计周期无效"
    )

    # 404 Not Found
    LOG_NOT_FOUND = _make_code(HTTP_404_NOT_FOUND, Module.ANALYTICS, 1, "日志不存在")


# ============================================================================
# 错误码快速索引（用于通过 code 查找错误码定义）
# ============================================================================


# 所有错误码类列表（用于遍历）
_ERROR_CLASSES = [
    ("通用", "COMMON", CommonError),
    ("用户", "ACCOUNT", AccountError),
    ("音色", "VOICE", VoiceError),
    ("克隆", "CLONE", CloneError),
    ("TTS", "TTS", TTSError),
    ("API Key", "API_KEY", ApiKeyError),
    ("积分", "CREDIT", CreditError),
    ("订阅", "SUBSCRIPTION", SubscriptionError),
    ("邀请码", "INVITE_CODE", InviteCodeError),
    ("数据分析", "ANALYTICS", AnalyticsError),
]


def get_error_code_by_value(code: int) -> ErrorCode | None:
    """
    通过错误码值查找错误码定义

    Args:
        code: 错误码值

    Returns:
        ErrorCode 对象或 None
    """
    for _, _, error_class in _ERROR_CLASSES:
        for attr_name in dir(error_class):
            if attr_name.startswith("_"):
                continue
            attr = getattr(error_class, attr_name)
            if isinstance(attr, ErrorCode) and attr.code == code:
                return attr

    return None


def get_all_error_codes() -> list[dict]:
    """
    获取所有错误码列表（用于文档/预览）

    Returns:
        错误码列表，每个元素包含 module, name, code, message, http_status
    """
    result = []

    for module_name, module_code, error_class in _ERROR_CLASSES:
        for attr_name in dir(error_class):
            if attr_name.startswith("_"):
                continue
            attr = getattr(error_class, attr_name)
            if isinstance(attr, ErrorCode):
                result.append(
                    {
                        "module": module_name,
                        "module_code": module_code,
                        "name": attr_name,
                        "code": attr.code,
                        "message": attr.message,
                        "http_status": attr.http_status,
                    }
                )

    # 按错误码排序
    result.sort(key=lambda x: x["code"])
    return result


def get_error_codes_by_module() -> dict[str, list[dict]]:
    """
    按模块分组获取所有错误码

    Returns:
        按模块分组的错误码字典
    """
    grouped = {}

    for module_name, module_code, error_class in _ERROR_CLASSES:
        codes = []
        for attr_name in dir(error_class):
            if attr_name.startswith("_"):
                continue
            attr = getattr(error_class, attr_name)
            if isinstance(attr, ErrorCode):
                codes.append(
                    {
                        "name": attr_name,
                        "code": attr.code,
                        "message": attr.message,
                        "http_status": attr.http_status,
                    }
                )

        # 按 HTTP 状态码排序
        codes.sort(key=lambda x: (x["http_status"], x["code"]))
        grouped[module_name] = {
            "module_code": module_code,
            "errors": codes,
        }

    return grouped


def generate_error_codes_markdown() -> str:
    """
    生成错误码的 Markdown 文档

    Returns:
        Markdown 格式的错误码文档
    """
    lines = [
        "# 错误码文档",
        "",
        "## 格式说明",
        "",
        "错误码格式：`HTTP状态码(3位) + 模块代码(2位) + 错误序号(3位) = 8位数字`",
        "",
        "例如：`40401001` = `404`(未找到) + `01`(用户模块) + `001`(用户未找到)",
        "",
        "## 模块代码",
        "",
        "| 代码 | 模块 |",
        "|------|------|",
    ]

    for module_name, module_code, _ in _ERROR_CLASSES:
        lines.append(f"| {module_code} | {module_name} |")

    lines.extend(["", "## 错误码列表", ""])

    grouped = get_error_codes_by_module()
    for module_name, data in grouped.items():
        lines.append(f"### {module_name} (模块 {data['module_code']})")
        lines.append("")
        lines.append("| 错误码 | 名称 | HTTP状态 | 描述 |")
        lines.append("|--------|------|----------|------|")

        for error in data["errors"]:
            lines.append(
                f"| `{error['code']}` | `{error['name']}` | {error['http_status']} | {error['message']} |"
            )

        lines.append("")

    return "\n".join(lines)


# ============================================================================
# 便捷导出
# ============================================================================

__all__ = [
    # 基础类
    "ErrorCode",
    "Module",
    "Success",
    # 错误码类
    "CommonError",
    "AccountError",
    "VoiceError",
    "CloneError",
    "TTSError",
    "ApiKeyError",
    "CreditError",
    "SubscriptionError",
    "InviteCodeError",
    "AnalyticsError",
    # 工具函数
    "get_error_code_by_value",
    "get_all_error_codes",
    "get_error_codes_by_module",
    "generate_error_codes_markdown",
]
