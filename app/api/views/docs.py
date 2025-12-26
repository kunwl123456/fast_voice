"""
文档相关接口

提供错误码文档、API 文档等实时预览功能
"""

from fastapi import Query
from fastapi.responses import PlainTextResponse, HTMLResponse

from app.routers import docs_router as router
from app.core.responses import success_response
from app.core.error_codes import (
    get_all_error_codes,
    get_error_codes_by_module,
    generate_error_codes_markdown,
)


@router.get("/error-codes", summary="获取所有错误码列表")
async def list_error_codes(
    module: str | None = Query(
        None, description="按模块筛选，如: COMMON, ACCOUNT, VOICE 等"
    ),
    http_status: int | None = Query(
        None, description="按 HTTP 状态码筛选，如: 400, 401, 404 等"
    ),
):
    """
    获取所有错误码列表，支持按模块和 HTTP 状态码筛选

    返回格式：
    ```json
    {
        "code": 0,
        "message": "操作成功",
        "data": [
            {
                "module": "通用/系统",
                "module_code": "COMMON",
                "name": "BAD_REQUEST",
                "code": 40000001,
                "message": "请求参数错误",
                "http_status": 400
            }
        ]
    }
    ```
    """
    codes = get_all_error_codes()

    # 按模块筛选
    if module:
        module_upper = module.upper()
        codes = [c for c in codes if c["module_code"] == module_upper]

    # 按 HTTP 状态码筛选
    if http_status:
        codes = [c for c in codes if c["http_status"] == http_status]

    return success_response(data=codes)


@router.get("/error-codes/grouped", summary="按模块分组获取错误码")
async def list_error_codes_grouped():
    """
    按模块分组获取所有错误码

    返回格式：
    ```json
    {
        "code": 0,
        "message": "操作成功",
        "data": {
            "通用/系统": {
                "module_code": "COMMON",
                "errors": [...]
            }
        }
    }
    ```
    """
    grouped = get_error_codes_by_module()
    return success_response(data=grouped)


@router.get("/error-codes/markdown", summary="获取错误码 Markdown 文档")
async def get_error_codes_markdown():
    """
    获取错误码的 Markdown 格式文档，可直接用于文档站点
    """
    markdown = generate_error_codes_markdown()
    return PlainTextResponse(content=markdown, media_type="text/markdown")


@router.get("/error-codes/html", summary="获取错误码 HTML 预览页面")
async def get_error_codes_html():
    """
    获取错误码的 HTML 预览页面，可直接在浏览器中查看
    """
    grouped = get_error_codes_by_module()

    # 生成 HTML 页面
    html_parts = [
        """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FastVoice 错误码文档</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-yellow: #d29922;
            --accent-red: #f85149;
            --accent-purple: #a371f7;
            --border-color: #30363d;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            color: var(--text-secondary);
            margin-bottom: 2rem;
            font-size: 1.1rem;
        }
        
        .format-info {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .format-info code {
            background: var(--bg-tertiary);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-family: 'SF Mono', 'Fira Code', monospace;
            color: var(--accent-blue);
        }
        
        .search-box {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }
        
        .search-box input, .search-box select {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 0.75rem 1rem;
            color: var(--text-primary);
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }
        
        .search-box input:focus, .search-box select:focus {
            border-color: var(--accent-blue);
        }
        
        .search-box input { flex: 1; min-width: 200px; }
        
        .module-section {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 1.5rem;
            overflow: hidden;
        }
        
        .module-header {
            background: var(--bg-tertiary);
            padding: 1rem 1.5rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s;
        }
        
        .module-header:hover { background: #2d333b; }
        
        .module-header h2 {
            font-size: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .module-code {
            background: var(--accent-purple);
            color: white;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        
        .error-count {
            background: var(--bg-primary);
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .module-content { padding: 0; }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 0.875rem 1.5rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        
        th {
            background: var(--bg-primary);
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        tr:last-child td { border-bottom: none; }
        
        tr:hover td { background: rgba(88, 166, 255, 0.05); }
        
        .error-code {
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-weight: 600;
            color: var(--accent-blue);
        }
        
        .error-name {
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 0.9rem;
            color: var(--accent-yellow);
        }
        
        .http-status {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-weight: 500;
            font-size: 0.85rem;
        }
        
        .http-2xx { background: rgba(63, 185, 80, 0.2); color: var(--accent-green); }
        .http-4xx { background: rgba(210, 153, 34, 0.2); color: var(--accent-yellow); }
        .http-5xx { background: rgba(248, 81, 73, 0.2); color: var(--accent-red); }
        
        .error-hidden { display: none; }
        
        .stats {
            display: flex;
            gap: 1.5rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }
        
        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1rem 1.5rem;
            min-width: 120px;
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent-blue);
        }
        
        .stat-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .last-updated {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border-color);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 FastVoice 错误码文档</h1>
        <p class="subtitle">实时生成，保持与代码同步</p>
        
        <div class="format-info">
            <strong>📐 错误码格式</strong><br>
            <code>HTTP状态码(3位)</code> + <code>模块代码(2位)</code> + <code>错误序号(3位)</code> = <strong>8位数字</strong><br>
            <br>
            示例：<code>40401001</code> = <code>404</code>(未找到) + <code>01</code>(用户模块) + <code>001</code>(用户未找到)
        </div>
        
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="🔍 搜索错误码、名称或描述...">
            <select id="httpFilter">
                <option value="">所有 HTTP 状态</option>
                <option value="400">400 Bad Request</option>
                <option value="401">401 Unauthorized</option>
                <option value="402">402 Payment Required</option>
                <option value="403">403 Forbidden</option>
                <option value="404">404 Not Found</option>
                <option value="409">409 Conflict</option>
                <option value="410">410 Gone</option>
                <option value="429">429 Too Many Requests</option>
                <option value="500">500 Internal Error</option>
                <option value="503">503 Service Unavailable</option>
            </select>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="totalCount">0</div>
                <div class="stat-label">总错误码数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="moduleCount">0</div>
                <div class="stat-label">模块数量</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="visibleCount">0</div>
                <div class="stat-label">当前显示</div>
            </div>
        </div>
"""
    ]

    total_count = 0
    module_count = 0

    for module_name, data in grouped.items():
        module_count += 1
        error_count = len(data["errors"])
        total_count += error_count

        html_parts.append(
            f"""
        <div class="module-section">
            <div class="module-header" onclick="this.nextElementSibling.classList.toggle('error-hidden')">
                <h2>
                    <span class="module-code">{data["module_code"]}</span>
                    {module_name}
                </h2>
                <span class="error-count">{error_count} 个错误码</span>
            </div>
            <div class="module-content">
                <table>
                    <thead>
                        <tr>
                            <th>错误码</th>
                            <th>名称</th>
                            <th>HTTP 状态</th>
                            <th>描述</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        )

        for error in data["errors"]:
            http_class = (
                "http-2xx"
                if error["http_status"] < 400
                else ("http-4xx" if error["http_status"] < 500 else "http-5xx")
            )
            html_parts.append(
                f"""
                        <tr class="error-row" data-code="{error['code']}" data-name="{error['name']}" data-msg="{error['message']}" data-http="{error['http_status']}">
                            <td class="error-code">{error['code']}</td>
                            <td class="error-name">{error['name']}</td>
                            <td><span class="http-status {http_class}">{error['http_status']}</span></td>
                            <td>{error['message']}</td>
                        </tr>
"""
            )

        html_parts.append(
            """
                    </tbody>
                </table>
            </div>
        </div>
"""
        )

    html_parts.append(
        f"""
        <div class="last-updated">
            📅 实时生成 · 总计 <strong>{total_count}</strong> 个错误码 · <strong>{module_count}</strong> 个模块
        </div>
    </div>
    
    <script>
        document.getElementById('totalCount').textContent = {total_count};
        document.getElementById('moduleCount').textContent = {module_count};
        document.getElementById('visibleCount').textContent = {total_count};
        
        const searchInput = document.getElementById('searchInput');
        const httpFilter = document.getElementById('httpFilter');
        const visibleCount = document.getElementById('visibleCount');
        
        function filterErrors() {{
            const searchTerm = searchInput.value.toLowerCase();
            const httpStatus = httpFilter.value;
            let visible = 0;
            
            document.querySelectorAll('.error-row').forEach(row => {{
                const code = row.dataset.code;
                const name = row.dataset.name.toLowerCase();
                const msg = row.dataset.msg.toLowerCase();
                const http = row.dataset.http;
                
                const matchesSearch = !searchTerm || 
                    code.includes(searchTerm) || 
                    name.includes(searchTerm) || 
                    msg.includes(searchTerm);
                
                const matchesHttp = !httpStatus || http === httpStatus;
                
                if (matchesSearch && matchesHttp) {{
                    row.style.display = '';
                    visible++;
                }} else {{
                    row.style.display = 'none';
                }}
            }});
            
            visibleCount.textContent = visible;
        }}
        
        searchInput.addEventListener('input', filterErrors);
        httpFilter.addEventListener('change', filterErrors);
    </script>
</body>
</html>
"""
    )

    return HTMLResponse(content="".join(html_parts))
