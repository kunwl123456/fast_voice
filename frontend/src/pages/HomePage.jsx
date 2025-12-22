import { Link } from "react-router-dom";

const features = [
  {
    title: "生成语音",
    desc: "几秒钟将文本转换为自然语音，支持多语言与高级参数。",
    link: "/tts",
  },
  {
    title: "克隆声音",
    desc: "上传 10-210 秒音频，快速训练专属数字分身。",
    link: "/voice-cloning",
  },
  {
    title: "探索与分享",
    desc: "发现社区优质声音，收藏并一键使用。",
    link: "/discovery",
  },
];

export default function HomePage() {
  return (
    <div className="card glass">
      <div className="hero">
        <div>
          <div className="hero-badge">S1 旗舰模型 · 情感、灵魂</div>
          <div className="hero-title">最佳 AI 文字转语音与语音克隆体验</div>
          <p className="hero-desc">
            使用先进的 AI 模型 S1，快速生成高保真、富有情感的语音，或克隆您自己的声音，打造沉浸式故事与角色体验。
          </p>
          <div className="actions">
            <Link className="primary-btn" to="/tts">
              立即生成语音
            </Link>
            <Link className="ghost-btn" to="/voice-cloning">
              克隆您的声音
            </Link>
          </div>
          <div className="stats" style={{ marginTop: 16 }}>
            <div className="stat">
              <strong>高品质模式</strong>
              <div>44.1kHz / 情感渲染</div>
            </div>
            <div className="stat">
              <strong>极速生成</strong>
              <div>秒级响应，适合批量合成</div>
            </div>
            <div className="stat">
              <strong>角色工作室</strong>
              <div>角色对话、故事场景编排</div>
            </div>
          </div>
        </div>
        <div className="card" style={{ background: "rgba(255,255,255,0.03)" }}>
          <div className="pill">实时演示 · 占位</div>
          <h3>示例提示词</h3>
          <p className="hero-desc">“请用温暖、平静的语气，向听众介绍今天的天气与穿衣建议。”</p>
          <div className="code-block">
            <pre>
{`POST /api/tts/generate
text: "欢迎来到 Fish Audio"
voice_model_id: your-voice-id
settings: { speed: 1.0, high_quality: true }`}
            </pre>
          </div>
          <div className="pill" style={{ marginTop: 12 }}>
            接口已占位，后端可直接接入推理
          </div>
        </div>
      </div>

      <div className="grid" style={{ marginTop: 16 }}>
        {features.map((f) => (
          <div key={f.title} className="card">
            <div className="pill">核心功能</div>
            <h3>{f.title}</h3>
            <p className="hero-desc">{f.desc}</p>
            <Link className="primary-btn" to={f.link}>
              前往
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

