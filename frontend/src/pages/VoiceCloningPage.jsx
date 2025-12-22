import { useState } from "react";
import { placeholderCreateVoice } from "../api/client";

export default function VoiceCloningPage() {
  const [uploadId, setUploadId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [resp, setResp] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    const res = await placeholderCreateVoice({
      upload_id: uploadId,
      name,
      description,
      type: "public",
      tags: ["示例"],
    });
    setResp(res.data);
  };

  return (
    <div className="card glass">
      <div className="hero">
        <div>
          <div className="pill">克隆声音 · 占位接口</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            训练专属数字分身
          </h2>
          <p className="hero-desc">上传 10-210 秒音频，一键创建语音模型，支持公开 / 不公开展示 / 私有。</p>
          <div className="stats" style={{ marginTop: 10 }}>
            <div className="stat">格式：WAV / MP3 / FLAC / M4A / MP4</div>
            <div className="stat">大小：≤ 32MB</div>
            <div className="stat">推荐时长：30s</div>
          </div>
        </div>
        <div className="card">
          <p className="hero-desc">上传接口可直接调用 `POST /api/voice-cloning/upload`，此处展示创建接口占位。</p>
          <form onSubmit={onSubmit} className="row">
            <div style={{ flex: 1, minWidth: 220 }}>
              <label>上传ID</label>
              <input className="input" value={uploadId} onChange={(e) => setUploadId(e.target.value)} required />
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <label>名称</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div style={{ width: "100%" }}>
              <label>描述</label>
              <textarea className="input" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <div className="actions">
              <button className="primary-btn" type="submit">
                创建（占位）
              </button>
              <span className="pill">返回 501 · 后端待接入</span>
            </div>
          </form>
        </div>
      </div>
      {resp && (
        <div className="card" style={{ marginTop: 12 }}>
          <strong>接口返回</strong>
          <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(resp, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

