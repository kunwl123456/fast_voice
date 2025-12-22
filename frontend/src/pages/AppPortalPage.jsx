import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { fetchVoices, placeholderTTS } from "../api/client";

const navSections = [
  {
    title: "总览",
    items: [
      { label: "首页", to: "/app" },
      { label: "发现", to: "/discovery" },
    ],
  },
  {
    title: "产品",
    items: [
      { label: "语音合成", to: "/tts" },
      { label: "克隆声音", to: "/voice-cloning" },
      { label: "故事工作室", to: "/story-studio" },
    ],
  },
  {
    title: "平台",
    items: [{ label: "管理会员", to: "/plan" }],
  },
  {
    title: "开发者",
    items: [{ label: "API 与 SDK", to: "/developers" }],
  },
];

const quickActions = [
  {
    title: "克隆您自己的声音",
    desc: "使用我们先进的 AI 技术创建您的声音数字副本",
    to: "/voice-cloning",
  },
  {
    title: "幻想角色扮演",
    desc: "创建沉浸式音频体验，使角色栩栩如生",
    to: "/story-studio",
  },
  {
    title: "生成语音",
    desc: "在几秒钟内将任何文本转换为自然语音",
    to: "/tts",
  },
];

export default function AppPortalPage() {
  const location = useLocation();
  const [prompt, setPrompt] = useState("介绍一下 Fish Audio S1，并推荐一个适合旁白的声音。");
  const [generateResult, setGenerateResult] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [voices, setVoices] = useState([]);
  const [voiceLoading, setVoiceLoading] = useState(true);

  useEffect(() => {
    fetchVoices()
      .then((data) => setVoices(data.voices || []))
      .catch(() => setVoices([]))
      .finally(() => setVoiceLoading(false));
  }, []);

  const activeMap = useMemo(() => new Set([location.pathname]), [location.pathname]);

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await placeholderTTS({
        text: prompt,
        settings: {
          speed: 1.0,
          high_quality: true,
          temperature: 0.9,
          top_p: 0.9,
        },
      });
      setGenerateResult(res.data);
    } catch (err) {
      setGenerateResult({ error: err?.message || "请求失败" });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="app-shell">
      <aside className="app-sidebar card">
        <div className="brand" style={{ marginBottom: 12 }}>
          <div className="brand-mark">FA</div>
          <div>
            <div className="brand-title">Fish Audio</div>
            <div className="brand-sub">打开应用</div>
          </div>
        </div>

        {navSections.map((section) => (
          <div key={section.title} className="sidebar-section">
            <div className="sidebar-title">{section.title}</div>
            <div className="sidebar-list">
              {section.items.map((item) => {
                const isActive = activeMap.has(item.to);
                return (
                  <Link key={item.to} to={item.to} className={isActive ? "sidebar-link active" : "sidebar-link"}>
                    <span>{item.label}</span>
                    {isActive && <span className="pill">当前</span>}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}

        <div className="sidebar-cta">
          <Link className="primary-btn" to="/plan">
            立即升级
          </Link>
          <Link className="ghost-btn" to="/developers">
            开发者入口
          </Link>
        </div>
      </aside>

      <div className="app-main">
        <section className="card glass app-hero-grid">
          <div>
            <div className="hero-badge">介绍 S1</div>
            <h1 className="hero-title" style={{ fontSize: 32, marginTop: 8 }}>
              旗舰模型，最佳语音克隆性能
            </h1>
            <p className="hero-desc" style={{ marginTop: 6 }}>
              Fish Audio S1 提供高保真、富有情感的声音表现，适合播客、故事、对话与角色演绎等场景。
            </p>
            <div className="stats" style={{ marginTop: 12 }}>
              <div className="stat">44.1kHz 情感渲染</div>
              <div className="stat">极速生成 · 秒级响应</div>
              <div className="stat">支持多语言 / 情绪</div>
            </div>
          </div>

          <div className="card app-input-card">
            <label>说些什么</label>
            <textarea
              className="input"
              rows={5}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="示例：请用温暖的语气朗读一段迎新祝福"
            />
            <div className="actions" style={{ marginTop: 8 }}>
              <button className="primary-btn" onClick={handleGenerate} disabled={isGenerating}>
                {isGenerating ? "生成中..." : "生成试听（占位）"}
              </button>
              <span className="pill">调用 /api/tts/generate</span>
            </div>
            {generateResult && (
              <div className="app-status">
                <div className="hero-desc">接口返回（占位）：</div>
                <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{JSON.stringify(generateResult, null, 2)}</pre>
              </div>
            )}
          </div>
        </section>

        <section className="grid app-quick-grid">
          {quickActions.map((action) => (
            <Link key={action.title} to={action.to} className="card app-quick-card">
              <div className="pill">快速开始</div>
              <h3 style={{ margin: "8px 0" }}>{action.title}</h3>
              <p className="hero-desc" style={{ margin: 0 }}>{action.desc}</p>
            </Link>
          ))}
        </section>

        <section className="card glass">
          <div className="section-header">
            <h3 style={{ margin: 0 }}>发现精选声音</h3>
            <Link className="ghost-btn" to="/discovery">
              查看更多
            </Link>
          </div>
          {voiceLoading && <p className="hero-desc">加载中...</p>}
          {!voiceLoading && (
            <div className="grid">
              {(voices || []).slice(0, 3).map((v) => (
                <div key={v.id} className="card">
                  <div className="pill">{v.language}</div>
                  <h4 style={{ margin: "6px 0" }}>{v.name}</h4>
                  <p className="hero-desc" style={{ marginTop: 4 }}>{v.tags?.join(" · ")}</p>
                  <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                    <span className="pill">创建者：{v.creator}</span>
                    <Link className="primary-btn" to="/tts" style={{ padding: "6px 10px" }}>
                      试听
                    </Link>
                  </div>
                </div>
              ))}
              {(voices || []).length === 0 && <p className="hero-desc">暂无数据，后端可接入 Redis/数据库。</p>}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

