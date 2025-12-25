"""FastAPI OpenAPI 配置"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


OPENAPI_DESCRIPTION = """
# Open API 说明

## 认证方式

### 控制台用户认证
使用登录接口获取的 JWT Token：
```
Authorization: Bearer <jwt_token>
```

### API Key 认证（企业版 OpenAPI）
使用企业版 API Key：
```
Authorization: Bearer <api_key>
```

**如何使用：**
1. 点击右上角 "Authorize" 按钮（🔓）
2. 在弹出的对话框中输入你的 Token（JWT 或 API Key）
3. 点击 "Authorize" 确认
4. 现在所有请求都会自动携带认证信息

## 响应说明

### 响应格式
所有接口均返回统一格式：
```json
{
  "message": "提示信息",
  "data": {} // 响应数据或错误详情
}
```

### HTTP 状态码说明

| 状态码 | 说明 | 示例场景 |
|--------|------|----------|
| 200 | 请求成功 | 数据查询、更新、删除成功 |
| 201 | 创建成功 | 资源创建成功 |
| 400 | 请求参数错误 | 参数错误，例如缺少必需参数、参数格式错误 |
| 401 | 未授权 | 未登录、token 无效或过期 |
| 403 | 无权限 | 没有操作权限 |
| 404 | 资源不存在 | 请求的资源未找到 |
| 409 | 资源冲突 | 邮箱已注册、资源已存在 |
| 422 | 参数验证失败 | 字段验证不通过 |
| 500 | 服务器内部错误 | 系统异常 |

### 错误响应示例

**400 错误请求**
```json
{
  "message": "请求参数错误",
  "data": null
}
```

**403 无权限**
```json
{
  "message": "无权限访问该资源",
  "data": null
}
```

## 数据格式规范

### 时间格式
所有时间字段统一使用以下格式：
```
YYYY-MM-DD HH:MM:SS
示例：2025-12-25 12:00:00
```
"""


def setup_openapi(app: FastAPI):
    """
    配置自定义的 OpenAPI schema，添加 Bearer Token 认证

    Args:
        app: FastAPI 应用实例

    使用方法:
        from app.controller.openapi import setup_openapi
        setup_openapi(app)
    """

    def custom_openapi():
        """自定义 OpenAPI schema 生成函数"""
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # 添加 Bearer Token 安全方案
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "输入你的 JWT Token 或 API Key（不需要加 'Bearer ' 前缀）",
            }
        }

        # 为所有接口添加全局安全要求（这样右上角会显示 Authorize 按钮）
        # 注释掉下面这行，则只有单独配置了 security 的接口才需要认证
        # openapi_schema["security"] = [{"BearerAuth": []}]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    # 将自定义函数赋值给 app.openapi
    app.openapi = custom_openapi  # type: ignore[method-assign]
