import { useEffect, useState } from "react";
import { bookmarkVoice, fetchVoices } from "../api/client";

export default function DiscoveryPage() {
  const [voices, setVoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [bookmarkResult, setBookmarkResult] = useState(null);

  useEffect(() => {
    fetchVoices().then((data) => {
      setVoices(data.voices || []);
      setLoading(false);
    });
  }, []);

  const onBookmark = async (id) => {
    const data = await bookmarkVoice(id);
    setBookmarkResult(data);
  };

  return (
    <div className="card glass">
      <div className="hero" style={{ gridTemplateColumns: "2fr 3fr" }}>
        <div>
          <div className="pill">发现 · 社区声音</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            探索优质声音，灵感即刻启程
          </h2>
          <p className="hero-desc">浏览公开声音、收藏并一键使用。Redis 存储列表，示例数据自动回退。</p>
        </div>
        <div className="stats">
          <div className="stat">排序：推荐（示例）</div>
          <div className="stat">语言筛选：汉语 / 英语</div>
          <div className="stat">收藏：写入 Redis Set</div>
        </div>
      </div>

      {loading && <p>加载中...</p>}

      {!loading && (
        <div className="grid">
          {voices.map((v) => (
            <div key={v.id} className="card">
              <div className="pill">{v.language}</div>
              <h3 style={{ margin: "8px 0" }}>{v.name}</h3>
              <p className="hero-desc">{v.tags?.join(" · ")}</p>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <span className="pill">创建者：{v.creator}</span>
                <button className="ghost-btn" onClick={() => onBookmark(v.id)}>
                  收藏
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {bookmarkResult && (
        <div className="card" style={{ marginTop: 12 }}>
          <strong>收藏结果</strong>
          <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(bookmarkResult, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

