import { Link } from "react-router-dom";

export default function DevelopersPage() {
  return (
    <div className="card glass">
      <div className="hero" style={{ gridTemplateColumns: "2fr 3fr" }}>
        <div>
          <div className="pill">开发者</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            API / SDK 与联调入口
          </h2>
          <p className="hero-desc">
            提供 TTS、克隆声音等接口的调用示例。当前页面为占位，可进一步接入 OpenAPI、密钥管理、用量统计与示例代码下载。
          </p>
          <div className="stats" style={{ marginTop: 10 }}>
            <div className="stat">RESTful 接口</div>
            <div className="stat">返还 JSON 结构</div>
            <div className="stat">可扩展 SDK</div>
          </div>
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>快速请求示例</h3>
          <div className="code-block">
            <pre style={{ margin: 0 }}>
{`POST /api/tts/generate
{
  "text": "你好，Fish Audio！",
  "voice_model_id": "your-voice-id",
  "settings": { "speed": 1.0, "high_quality": true }
}`}
            </pre>
          </div>
          <div className="code-block" style={{ marginTop: 12 }}>
            <pre style={{ margin: 0 }}>
{`POST /api/voice-cloning/create
{
  "upload_id": "upload-token",
  "name": "我的数字分身",
  "description": "用于旁白/角色"
}`}
            </pre>
          </div>
          <div className="actions" style={{ marginTop: 12 }}>
            <Link className="primary-btn" to="/tts">
              去调试 TTS
            </Link>
            <Link className="ghost-btn" to="/voice-cloning">
              去调试克隆
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

