import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { fetchMe, getStoredToken, loginUser } from "../api/client";

export default function LoginPage({ onLogin }) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const redirect = searchParams.get("redirect") || "/app";

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const res = await loginUser({ email, password });
    setResult(res.data);
    setLoading(false);
    if (res.data?.token) {
      if (onLogin && res.data?.user) onLogin(res.data.user);
      navigate(redirect, { replace: true });
    }
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
          <div className="pill">登录</div>
          <h2 className="hero-title" style={{ fontSize: 28, marginTop: 6 }}>
            使用邮箱与密码登录
          </h2>
          <p className="hero-desc">成功后会将 token 缓存在浏览器的 localStorage，并自动带上 Authorization 头。</p>
          <div className="stats" style={{ marginTop: 10 }}>
            <div className="stat">POST /api/auth/login</div>
            <div className="stat">GET /api/auth/me</div>
            <div className="stat">Bearer token</div>
          </div>
          <div className="actions" style={{ marginTop: 12 }}>
            <Link className="ghost-btn" to={`/register?redirect=${encodeURIComponent(redirect)}`}>
              去注册
            </Link>
            <Link className="ghost-btn" to="/">
              返回首页
            </Link>
          </div>
        </div>

        <div className="card">
          <form className="row" onSubmit={onSubmit}>
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
                {loading ? "请求中..." : "登录"}
              </button>
              <button className="ghost-btn" type="button" onClick={onCheckMe} disabled={loading || !getStoredToken()}>
                查询 /me
              </button>
              <span className="pill">需要先注册或已有账号</span>
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

