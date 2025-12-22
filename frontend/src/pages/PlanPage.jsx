const mockPlans = [
  {
    name: "免费体验",
    price: "¥0",
    highlights: ["每日限量额度", "基础 TTS 试听", "公共声音库"],
  },
  {
    name: "创作者",
    price: "¥59 / 月",
    highlights: ["高品质模式", "更高并发与额度", "优先客服支持"],
  },
  {
    name: "团队",
    price: "¥199 / 月",
    highlights: ["团队协作与席位", "独立用量统计", "企业级 SLA"],
  },
];

export default function PlanPage() {
  return (
    <div className="card glass">
      <div className="hero" style={{ gridTemplateColumns: "2fr 3fr" }}>
        <div>
          <div className="pill">管理会员</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            升级以解锁高品质与更高额度
          </h2>
          <p className="hero-desc">对齐官网“立即升级”入口，后端可接入真实的订阅/订单系统。</p>
          <div className="stats" style={{ marginTop: 10 }}>
            <div className="stat">支持月度/年度</div>
            <div className="stat">额度用量可查</div>
            <div className="stat">团队席位</div>
          </div>
        </div>
        <div className="grid">
          {mockPlans.map((p) => (
            <div key={p.name} className="card">
              <div className="pill">方案</div>
              <h3 style={{ margin: "8px 0" }}>{p.name}</h3>
              <div className="hero-title" style={{ fontSize: 22, margin: "6px 0" }}>
                {p.price}
              </div>
              <ul className="hero-desc" style={{ paddingLeft: 16, lineHeight: 1.8, margin: "8px 0" }}>
                {p.highlights.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
              <div className="actions">
                <button className="primary-btn">立即升级（占位）</button>
                <span className="pill">接入支付后可跳转</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

