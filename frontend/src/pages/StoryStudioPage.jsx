export default function StoryStudioPage() {
  return (
    <div className="card glass">
      <div className="hero" style={{ gridTemplateColumns: "2fr 3fr" }}>
        <div>
          <div className="pill">故事工作室</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            让角色与故事开口说话
          </h2>
          <p className="hero-desc">
            组合多个声音、台词与背景设定，快速制作互动式有声故事或角色扮演内容。此页为占位，可直接嵌入场景编排与音频轨道编辑功能。
          </p>
          <div className="stats" style={{ marginTop: 12 }}>
            <div className="stat">多角色对白</div>
            <div className="stat">情绪/语速可调</div>
            <div className="stat">可接入自定义音效</div>
          </div>
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>下一步可接入的能力</h3>
          <ul className="hero-desc" style={{ lineHeight: 1.8 }}>
            <li>按时间线编排对白、音效与背景音乐。</li>
            <li>将 TTS 生成的语音分配到不同角色并快速试听。</li>
            <li>导出 MP3/WAV 或推送到播客/有声书渠道。</li>
          </ul>
          <div className="actions">
            <a className="primary-btn" href="https://fish.audio/zh-CN/app/story-studio/" target="_blank" rel="noreferrer">
              查看官方示例
            </a>
            <span className="pill">当前为占位页</span>
          </div>
        </div>
      </div>
    </div>
  );
}

