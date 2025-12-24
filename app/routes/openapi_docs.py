from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/openapi", tags=["openapi-docs"])


@router.get("/docs/api-reference")
def openapi_api_reference(request: Request):
    """
    V2：自动生成的 OpenAPI 接口文档（适用于前端渲染）。

    自动从 FastAPI 路由中提取所有 /openapi 前缀的接口信息，
    包括路径、方法、参数、请求体、响应等完整信息。
    """
    app = request.app

    # 获取 FastAPI 生成的 OpenAPI 规范
    openapi_schema = app.openapi()

    # 提取 tags 信息（包含模块描述）
    tags_info = _extract_tags_info(openapi_schema)

    # 提取所有 /openapi 前缀的路径
    api_endpoints = {}

    for path, path_item in openapi_schema.get("paths", {}).items():
        # 只处理 /openapi 开头的路径（排除 /openapi/docs）
        if path.startswith("/openapi/") and not path.startswith("/openapi/docs"):
            # 按模块分组
            parts = path.split("/")
            if len(parts) >= 3:
                module = parts[2]  # tts, clone, voices 等

                if module not in api_endpoints:
                    api_endpoints[module] = {
                        "name": module.upper(),
                        "description": tags_info.get(module, ""),
                        "endpoints": [],
                    }

                # 提取每个 HTTP 方法
                for method, operation in path_item.items():
                    if method.lower() in ["get", "post", "put", "patch", "delete"]:
                        endpoint_info = {
                            "path": path,
                            "method": method.upper(),
                            "description": operation.get("description", ""),
                            "parameters": _extract_parameters(operation),
                            "requestBody": _extract_request_body(
                                operation, openapi_schema
                            ),
                            "responses": _extract_responses(operation, openapi_schema),
                        }
                        api_endpoints[module]["endpoints"].append(endpoint_info)

    # 转换为列表格式
    modules = list(api_endpoints.values())

    # 按模块名称排序
    modules.sort(key=lambda x: x["name"])

    return {
        "version": "1.0.0",
        "title": "Fast Voice OpenAPI Reference",
        "description": "OpenAPI Document",
        "base_url": "/openapi",
        "modules": modules,
        "auth": {
            "type": "Bearer Token (API Key)",
            "description": "所有接口需要在请求头中携带 API Key",
            "required_headers": ["Authorization: Bearer sk-xxxxxx"],
            "note": "API Key 以 'sk-' 开头，在 Authorization 请求头中使用 Bearer Token 格式",
        },
    }


def _extract_tags_info(openapi_schema: dict) -> dict[str, str]:
    """
    从 OpenAPI schema 中提取 tags 信息
    返回 {tag_name: description} 的映射
    """
    tags_map = {}
    tags = openapi_schema.get("tags", [])

    for tag in tags:
        tag_name = tag.get("name", "")
        tag_description = tag.get("description", "")
        if tag_name:
            tags_map[tag_name] = tag_description

    return tags_map


def _extract_parameters(operation: dict) -> list[dict]:
    """提取接口参数（路径参数、查询参数、请求头）"""
    params = []

    for param in operation.get("parameters", []):
        param_info = {
            "name": param.get("name", ""),
            "in": param.get("in", ""),  # path, query, header, cookie
            "description": param.get("description", ""),
            "required": param.get("required", False),
            "schema": param.get("schema", {}),
            "example": param.get("example"),
        }
        params.append(param_info)

    return params


def _extract_request_body(operation: dict, openapi_schema: dict) -> dict | None:
    """提取请求体信息"""
    request_body = operation.get("requestBody")
    if not request_body:
        return None

    content = request_body.get("content", {})
    body_info = {
        "required": request_body.get("required", False),
        "description": request_body.get("description", ""),
        "content_types": {},
    }

    for content_type, media_type in content.items():
        schema = media_type.get("schema", {})

        # 解析 schema（可能包含 $ref）
        resolved_schema = _resolve_schema_ref(schema, openapi_schema)

        body_info["content_types"][content_type] = {
            "schema": resolved_schema,
            "example": media_type.get("example"),
            "examples": media_type.get("examples"),
        }

    return body_info


def _extract_responses(operation: dict, openapi_schema: dict) -> dict:
    """提取响应信息"""
    responses = {}

    for status_code, response in operation.get("responses", {}).items():
        content = response.get("content", {})
        response_info = {
            "description": response.get("description", ""),
            "content_types": {},
        }

        for content_type, media_type in content.items():
            schema = media_type.get("schema", {})
            resolved_schema = _resolve_schema_ref(schema, openapi_schema)

            response_info["content_types"][content_type] = {
                "schema": resolved_schema,
                "example": media_type.get("example"),
            }

        responses[status_code] = response_info

    return responses


def _resolve_schema_ref(
    schema: dict, openapi_schema: dict, max_depth: int = 5, current_depth: int = 0
) -> dict:
    """递归解析 schema 中的 $ref 引用，支持泛型类型"""
    if current_depth >= max_depth:
        return {"type": "object", "description": "（嵌套层级过深，已省略）"}

    if not isinstance(schema, dict):
        return schema

    # 创建结果的副本，避免修改原始 schema
    result = {}

    # 处理 $ref 引用
    if "$ref" in schema:
        ref_path = schema["$ref"]
        # 解析引用路径，格式如：#/components/schemas/TTSCreatIn
        parts = ref_path.split("/")

        if parts[0] == "#" and len(parts) >= 3:
            # 导航到引用的 schema
            ref_schema = openapi_schema
            for part in parts[1:]:
                ref_schema = ref_schema.get(part, {})

            # 递归解析引用的 schema（避免无限递归）
            resolved = _resolve_schema_ref(
                ref_schema, openapi_schema, max_depth, current_depth + 1
            )

            # 处理泛型 Response 类型：展开 data 字段的实际类型
            if isinstance(resolved, dict) and "properties" in resolved:
                props = resolved.get("properties", {})
                # 检查是否是 Response 包装器（包含 message 和 data 字段）
                if "message" in props and "data" in props:
                    # 如果 data 字段还有 $ref，继续解析
                    data_schema = props["data"]
                    if isinstance(data_schema, dict) and "$ref" in data_schema:
                        props["data"] = _resolve_schema_ref(
                            data_schema, openapi_schema, max_depth, current_depth + 1
                        )
                    resolved["properties"] = props

            return resolved

    # 复制所有非特殊字段
    for key, value in schema.items():
        if key not in ["allOf", "anyOf", "oneOf", "properties", "items"]:
            result[key] = value

    # 处理 allOf, anyOf, oneOf
    for key in ["allOf", "anyOf", "oneOf"]:
        if key in schema:
            result[key] = [
                _resolve_schema_ref(s, openapi_schema, max_depth, current_depth + 1)
                for s in schema[key]
            ]

    # 处理对象属性
    if "properties" in schema:
        resolved_props = {}
        for prop_name, prop_schema in schema["properties"].items():
            resolved_props[prop_name] = _resolve_schema_ref(
                prop_schema, openapi_schema, max_depth, current_depth + 1
            )
        result["properties"] = resolved_props

    # 处理数组项
    if "items" in schema:
        result["items"] = _resolve_schema_ref(
            schema["items"], openapi_schema, max_depth, current_depth + 1
        )

    return result if result else schema
