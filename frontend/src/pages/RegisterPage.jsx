import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchMe, registerUser } from "../api/client";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const res = await registerUser({ email, password, username });
    setResult(res.data);
    setLoading(false);
  };

  const onCheckMe = async () => {
    setLoading(true);
    const res = await fetchMe();
    setResult(res.data);
    setLoading(false);
  };

  return (
    <div className="card glass">
      <div className="hero" style={{ gridTemplateColumns: "2fr 3fr" }}>
        <div>
          <div className="pill">注册</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            创建账号并自动登录
          </h2>
          <p className="hero-desc">成功后会返回 token 并写入 localStorage，可直接访问 /api/auth/me 校验。</p>
          <div className="stats" style={{ marginTop: 10 }}>
            <div className="stat">POST /api/auth/register</div>
            <div className="stat">返回 token</div>
            <div className="stat">内存/Redis 双写</div>
          </div>
          <div className="actions" style={{ marginTop: 12 }}>
            <Link className="ghost-btn" to="/login">
              去登录
            </Link>
            <button className="ghost-btn" type="button" onClick={() => navigate(-1)}>
              返回
            </button>
          </div>
        </div>

        <div className="card">
          <form className="row" onSubmit={onSubmit}>
            <div style={{ width: "100%" }}>
              <label>用户名</label>
              <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div style={{ width: "100%" }}>
              <label>邮箱</label>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div style={{ width: "100%" }}>
              <label>密码</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <div className="actions">
              <button className="primary-btn" type="submit" disabled={loading}>
                {loading ? "提交中..." : "注册并登录"}
              </button>
              <button className="ghost-btn" type="button" onClick={onCheckMe} disabled={loading}>
                查询 /me
              </button>
              <span className="pill">成功后自动带上 token</span>
            </div>
          </form>
          {result && (
            <div className="app-status" style={{ marginTop: 10 }}>
              <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

