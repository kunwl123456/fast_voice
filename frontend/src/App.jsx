import { NavLink, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import TTSPage from "./pages/TTSPage";
import VoiceCloningPage from "./pages/VoiceCloningPage";
import DiscoveryPage from "./pages/DiscoveryPage";
import CreditsPage from "./pages/CreditsPage";

const links = [
  { to: "/", label: "首页" },
  { to: "/tts", label: "语音合成" },
  { to: "/voice-cloning", label: "克隆声音" },
  { to: "/discovery", label: "发现" },
  { to: "/credits", label: "积分" },
];

export default function App() {
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
        </div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/tts" element={<TTSPage />} />
          <Route path="/voice-cloning" element={<VoiceCloningPage />} />
          <Route path="/discovery" element={<DiscoveryPage />} />
          <Route path="/credits" element={<CreditsPage />} />
        </Routes>
      </main>
    </div>
  );
}

