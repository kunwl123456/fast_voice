"""
自定义 API 文档路由
提供美化的 API 文档界面
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/api-docs", tags=["文档"])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def api_documentation():
    """自定义 API 文档页面"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Fast Voice API 文档</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stoplight/elements@8/styles.min.css">
        <style>
            body {
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }
        </style>
    </head>
    <body>
        <elements-api
            apiDescriptionUrl="/openapi.json"
            router="hash"
            layout="sidebar"
            logo="https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
        />
        <script src="https://cdn.jsdelivr.net/npm/@stoplight/elements@8/web-components.min.js"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get("/playground", response_class=HTMLResponse, include_in_schema=False)
async def api_playground():
    """API 测试工具"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Fast Voice API Playground</title>
        <style>
            body {
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #1a1a1a;
                color: #e0e0e0;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 30px 20px;
                margin-bottom: 30px;
                border-radius: 8px;
            }
            .header h1 {
                margin: 0;
                font-size: 32px;
                color: white;
            }
            .section {
                background: #2a2a2a;
                padding: 25px;
                margin-bottom: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            }
            .section h2 {
                margin-top: 0;
                color: #667eea;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }
            .endpoint {
                background: #1a1a1a;
                padding: 15px;
                margin: 15px 0;
                border-radius: 6px;
                border-left: 4px solid #667eea;
            }
            .method {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                margin-right: 10px;
            }
            .method.post {
                background: #49cc90;
                color: white;
            }
            .method.get {
                background: #61affe;
                color: white;
            }
            code {
                background: #3a3a3a;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                color: #a9dc76;
            }
            pre {
                background: #1e1e1e;
                padding: 15px;
                border-radius: 6px;
                overflow-x: auto;
                border: 1px solid #3a3a3a;
            }
            pre code {
                background: transparent;
                padding: 0;
                color: #e0e0e0;
            }
            .link {
                color: #61affe;
                text-decoration: none;
            }
            .link:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎙️ Fast Voice API Playground</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">OpenAI 风格的 TTS 和语音克隆 API</p>
            </div>

            <div class="section">
                <h2>🎤 语音合成 (TTS)</h2>
                <div class="endpoint">
                    <span class="method post">POST</span>
                    <code>/api/open/tts</code>
                    <p>将文本转换为语音</p>
                    <pre><code>{
  "reference_id": "string",  // 音色ID
  "text": "string",          // 要转换的文本
  "speed": 1.0,              // 语速 (0.5-2.0)
  "volume": 0,               // 音量 (-20-20)
  "format": "mp3"            // 音频格式
}</code></pre>
                </div>
            </div>

            <div class="section">
                <h2>🎨 声音克隆</h2>
                <div class="endpoint">
                    <span class="method post">POST</span>
                    <code>/api/open/clone</code>
                    <p>上传音频样本克隆声音</p>
                </div>
            </div>

            <div class="section">
                <h2>🔐 认证方式</h2>
                <p>使用 Bearer Token 认证：</p>
                <pre><code>Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json</code></pre>
            </div>

            <div class="section">
                <h2>📚 其他文档</h2>
                <ul style="line-height: 2;">
                    <li><a class="link" href="/docs">📖 Redoc 文档</a></li>
                    <li><a class="link" href="/swagger">🔧 Swagger UI</a></li>
                    <li><a class="link" href="/openapi.json">📄 OpenAPI JSON</a></li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

