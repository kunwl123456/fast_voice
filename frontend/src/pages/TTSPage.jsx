import { useState } from "react";
import { placeholderTTS } from "../api/client";

export default function TTSPage() {
  const [text, setText] = useState("在此编辑您的文本以转换为语音。");
  const [voiceModelId, setVoiceModelId] = useState("");
  const [status, setStatus] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setStatus("loading");
    const res = await placeholderTTS({
      text,
      voice_model_id: voiceModelId || null,
      settings: {
        speed: 1.0,
        volume: 0.0,
        temperature: 0.9,
        top_p: 0.9,
        high_quality: true,
      },
    });
    setStatus(res.data);
  };

  return (
    <div className="card glass">
      <div className="hero">
        <div>
          <div className="pill">文本转语音 · 占位接口</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            让文字在几秒内开口说话
          </h2>
          <p className="hero-desc">支持速度、温度、Top P、高品质模式等参数，满足情感化合成需求。</p>
          <div className="stats" style={{ marginTop: 12 }}>
            <div className="stat">S1 (Latest)</div>
            <div className="stat">高品质模式 ON</div>
            <div className="stat">快捷键：Ctrl + Enter</div>
          </div>
        </div>
        <div className="card">
          <form onSubmit={onSubmit} className="row">
            <div style={{ width: "100%" }}>
              <label>输入文本</label>
              <textarea className="input" rows={6} value={text} onChange={(e) => setText(e.target.value)} />
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <label>声音模型ID（可选）</label>
              <input className="input" value={voiceModelId} onChange={(e) => setVoiceModelId(e.target.value)} />
            </div>
            <div className="actions" style={{ marginTop: 6 }}>
              <button className="primary-btn" type="submit">
                生成并播放（占位）
              </button>
              <span className="pill">返回 501 · 后端待接入</span>
            </div>
          </form>
        </div>
      </div>
      {status && (
        <div className="card" style={{ marginTop: 12 }}>
          <strong>接口返回</strong>
          <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(status, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

