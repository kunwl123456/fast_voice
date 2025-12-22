import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import HomePage from "./pages/HomePage";
import TTSPage from "./pages/TTSPage";
import VoiceCloningPage from "./pages/VoiceCloningPage";
import DiscoveryPage from "./pages/DiscoveryPage";
import CreditsPage from "./pages/CreditsPage";
import AppPortalPage from "./pages/AppPortalPage";
import StoryStudioPage from "./pages/StoryStudioPage";
import PlanPage from "./pages/PlanPage";
import DevelopersPage from "./pages/DevelopersPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ProfilePage from "./pages/ProfilePage";
import { clearToken, fetchMe, getStoredToken, logoutUser } from "./api/client";

const links = [
  { to: "/", label: "首页" },
  { to: "/app", label: "应用" },
  { to: "/tts", label: "语音合成" },
  { to: "/voice-cloning", label: "克隆声音" },
  { to: "/discovery", label: "发现" },
  { to: "/credits", label: "积分" },
];

function RequireAuth({ children }) {
  const location = useLocation();
  const authed = !!getStoredToken();
  if (!authed) {
    const redirect = encodeURIComponent(location.pathname || "/app");
    return <Navigate to={`/auth?redirect=${redirect}`} replace />;
  }
  return children;
}

export default function App() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    fetchMe(token).then((res) => {
      if (res.status < 400) setUser(res.data);
    });
  }, []);

  const handleLogout = async () => {
    await logoutUser();
    clearToken();
    setUser(null);
  };

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">FA</div>
          <div>
            <div className="brand-title">Fish Audio</div>
            <div className="brand-sub">AI 语音合成与克隆</div>
          </div>
        </div>
        <nav className="nav">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="top-actions">
          <NavLink to="/voice-cloning" className="ghost-btn">
            克隆声音
          </NavLink>
          <NavLink to="/tts" className="primary-btn">
            立即生成
          </NavLink>
          {user ? (
            <NavLink to="/profile" className="ghost-btn">
              {user.username || user.email}
            </NavLink>
          ) : (
            <NavLink to="/auth?redirect=/app" className="ghost-btn">
              登录
            </NavLink>
          )}
        </div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route
            path="/app"
            element={
              <RequireAuth>
                <AppPortalPage user={user} />
              </RequireAuth>
            }
          />
          <Route path="/tts" element={<TTSPage />} />
          <Route path="/voice-cloning" element={<VoiceCloningPage />} />
          <Route path="/discovery" element={<DiscoveryPage />} />
          <Route path="/credits" element={<CreditsPage />} />
          <Route
            path="/story-studio"
            element={
              <RequireAuth>
                <StoryStudioPage />
              </RequireAuth>
            }
          />
          <Route
            path="/plan"
            element={
              <RequireAuth>
                <PlanPage />
              </RequireAuth>
            }
          />
          <Route
            path="/developers"
            element={
              <RequireAuth>
                <DevelopersPage />
              </RequireAuth>
            }
          />
          <Route
            path="/profile"
            element={
              <RequireAuth>
                <ProfilePage user={user} onChangeUser={setUser} onLogout={handleLogout} />
              </RequireAuth>
            }
          />
          <Route path="/login" element={<LoginPage onLogin={setUser} />} />
          <Route path="/auth" element={<LoginPage onLogin={setUser} />} />
          <Route path="/register" element={<RegisterPage onRegister={setUser} />} />
        </Routes>
      </main>
    </div>
  );
}

