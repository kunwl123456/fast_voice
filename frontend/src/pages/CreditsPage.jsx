import { useEffect, useState } from "react";
import { fetchCredits } from "../api/client";

export default function CreditsPage() {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchCredits().then(setData);
  }, []);

  return (
    <div className="card glass">
      <div className="hero" style={{ gridTemplateColumns: "2fr 3fr" }}>
        <div>
          <div className="pill">积分与用量</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            透明可控的积分消费
          </h2>
          <p className="hero-desc">查询余额与流水，便于估算 TTS 与克隆成本。</p>
        </div>
        {data && (
          <div className="stats">
            <div className="stat">余额：{data.balance}</div>
            <div className="stat">流水记录：{data.transactions.length} 条</div>
          </div>
        )}
      </div>

      {!data && <p>加载中...</p>}
      {data && (
        <div className="card">
          <strong>积分流水</strong>
          <ul>
            {data.transactions.map((t) => (
              <li key={t.id}>
                {t.description} · {t.amount}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

