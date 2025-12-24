class AuthenticationException(Exception):
    """鉴权错误"""


class PermissionException(Exception):
    """权限错误"""


class NotFoundException(Exception):
    """未找到"""
