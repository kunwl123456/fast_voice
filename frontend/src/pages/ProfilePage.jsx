import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  changeEmail,
  changePassword,
  fetchProfile,
  logoutUser,
  updateProfile,
  uploadAvatar,
} from "../api/client";

const blankSocials = { twitter: "", discord: "", twitch: "", github: "" };

export default function ProfilePage({ user, onChangeUser, onLogout }) {
  const navigate = useNavigate();
  const [profile, setProfile] = useState({
    username: "",
    bio: "",
    website: "",
    socials: blankSocials,
    notify_marketing: false,
    notify_api_balance: false,
    notify_api_expiry: false,
  });
  const [avatarPreview, setAvatarPreview] = useState("");
  const [emailForm, setEmailForm] = useState({ new_email: "", password: "" });
  const [pwdForm, setPwdForm] = useState({ old_password: "", new_password: "" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetchProfile().then((res) => {
      if (res.status < 400) {
        const data = res.data || {};
        setProfile({
          username: data.username || "",
          bio: data.bio || "",
          website: data.website || "",
          socials: { ...blankSocials, ...(data.socials || {}) },
          notify_marketing: !!data.notify_marketing,
          notify_api_balance: !!data.notify_api_balance,
          notify_api_expiry: !!data.notify_api_expiry,
        });
        setAvatarPreview(data.avatar_url || "");
        if (onChangeUser) onChangeUser(data);
      }
    });
  }, [onChangeUser]);

  const setField = (key, value) => setProfile((p) => ({ ...p, [key]: value }));

  const setSocial = (k, v) =>
    setProfile((p) => ({
      ...p,
      socials: { ...p.socials, [k]: v },
    }));

  const handleSaveProfile = async () => {
    setSaving(true);
    const res = await updateProfile(profile);
    setSaving(false);
    if (res.status < 400) {
      setMsg("资料已保存");
      if (onChangeUser) onChangeUser(res.data);
    } else {
      setMsg(res.data?.error || "保存失败");
    }
  };

  const handleChangePassword = async () => {
    setSaving(true);
    const res = await changePassword(pwdForm);
    setSaving(false);
    setMsg(res.data?.message || res.data?.error || "完成");
  };

  const handleChangeEmail = async () => {
    setSaving(true);
    const res = await changeEmail(emailForm);
    setSaving(false);
    if (res.status < 400) {
      setMsg("邮箱已更新");
      if (onChangeUser) onChangeUser(res.data);
    } else {
      setMsg(res.data?.error || "更新邮箱失败");
    }
  };

  const handleUploadAvatar = async (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
      const base64 = e.target?.result;
      setAvatarPreview(base64);
      const res = await uploadAvatar({ avatar: base64 });
      setMsg(res.data?.avatar_url ? "头像已更新" : res.data?.error || "上传失败");
      if (onChangeUser && res.data?.avatar_url) {
        onChangeUser({ ...(user || {}), avatar_url: res.data.avatar_url });
      }
    };
    reader.readAsDataURL(file);
  };

  const handleLogout = async () => {
    await logoutUser();
    if (onLogout) onLogout();
    navigate("/auth");
  };

  return (
    <div className="card glass">
      <div className="section-header">
        <div>
          <div className="pill">个人资料详情</div>
          <h2 className="hero-title" style={{ fontSize: 26, margin: "8px 0" }}>
            头像、昵称、社交与安全
          </h2>
          <p className="hero-desc">参考 fish.audio 设置页，支持改名、改密码、改邮箱、上传头像、注销。</p>
        </div>
        <div className="actions">
          <button className="primary-btn" onClick={handleSaveProfile} disabled={saving}>
            {saving ? "保存中..." : "保存更改"}
          </button>
          <button className="ghost-btn" onClick={handleLogout}>
            注销
          </button>
        </div>
      </div>

      {msg && (
        <div className="app-status" style={{ marginBottom: 12 }}>
          {msg}
        </div>
      )}

      <div className="profile-grid">
        <div className="profile-card card">
          <h3 style={{ marginTop: 0 }}>头像</h3>
          <p className="hero-desc">图片小于 1MB。可上传或粘贴 URL/base64。</p>
          <div className="avatar-uploader">
            <div className="avatar-preview">
              {avatarPreview ? <img src={avatarPreview} alt="avatar" /> : <span>{(profile.username || "U")[0]}</span>}
            </div>
            <label className="ghost-btn" style={{ cursor: "pointer" }}>
              选择头像
              <input
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={(e) => handleUploadAvatar(e.target.files?.[0])}
              />
            </label>
          </div>
        </div>

        <div className="profile-card card">
          <h3 style={{ marginTop: 0 }}>基本信息</h3>
          <div className="row">
            <div style={{ width: "100%" }}>
              <label>昵称</label>
              <input className="input" value={profile.username} onChange={(e) => setField("username", e.target.value)} />
            </div>
          </div>
          <div style={{ width: "100%", marginTop: 8 }}>
            <label>个人简介</label>
            <textarea
              className="input"
              rows={3}
              value={profile.bio}
              onChange={(e) => setField("bio", e.target.value)}
            />
          </div>
          <div style={{ width: "100%", marginTop: 8 }}>
            <label>个人网址 URL</label>
            <input className="input" value={profile.website} onChange={(e) => setField("website", e.target.value)} />
          </div>
        </div>

        <div className="profile-card card">
          <h3 style={{ marginTop: 0 }}>社交</h3>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px,1fr))" }}>
            {["twitter", "discord", "twitch", "github"].map((key) => (
              <div key={key} style={{ width: "100%" }}>
                <label>{key.charAt(0).toUpperCase() + key.slice(1)} 用户名</label>
                <input className="input" value={profile.socials[key]} onChange={(e) => setSocial(key, e.target.value)} />
              </div>
            ))}
          </div>
        </div>

        <div className="profile-card card">
          <h3 style={{ marginTop: 0 }}>登录 / 密码</h3>
          <div className="row">
            <div style={{ width: "100%" }}>
              <label>旧密码</label>
              <input
                className="input"
                type="password"
                value={pwdForm.old_password}
                onChange={(e) => setPwdForm({ ...pwdForm, old_password: e.target.value })}
              />
            </div>
            <div style={{ width: "100%" }}>
              <label>新密码</label>
              <input
                className="input"
                type="password"
                value={pwdForm.new_password}
                onChange={(e) => setPwdForm({ ...pwdForm, new_password: e.target.value })}
              />
            </div>
          </div>
          <div className="actions" style={{ marginTop: 8 }}>
            <button className="primary-btn" onClick={handleChangePassword} disabled={saving}>
              更换密码
            </button>
          </div>
        </div>

        <div className="profile-card card">
          <h3 style={{ marginTop: 0 }}>邮箱</h3>
          <div className="row">
            <div style={{ width: "100%" }}>
              <label>新邮箱</label>
              <input
                className="input"
                type="email"
                value={emailForm.new_email}
                onChange={(e) => setEmailForm({ ...emailForm, new_email: e.target.value })}
              />
            </div>
            <div style={{ width: "100%" }}>
              <label>密码验证</label>
              <input
                className="input"
                type="password"
                value={emailForm.password}
                onChange={(e) => setEmailForm({ ...emailForm, password: e.target.value })}
              />
            </div>
          </div>
          <div className="actions" style={{ marginTop: 8 }}>
            <button className="primary-btn" onClick={handleChangeEmail} disabled={saving}>
              更换邮箱
            </button>
          </div>
        </div>

        <div className="profile-card card">
          <h3 style={{ marginTop: 0 }}>通知</h3>
          <div className="toggle-list">
            <label className="toggle-item">
              <input
                type="checkbox"
                checked={profile.notify_marketing}
                onChange={(e) => setField("notify_marketing", e.target.checked)}
              />
              <span>营销通知</span>
            </label>
            <label className="toggle-item">
              <input
                type="checkbox"
                checked={profile.notify_api_balance}
                onChange={(e) => setField("notify_api_balance", e.target.checked)}
              />
              <span>API 余额提醒</span>
            </label>
            <label className="toggle-item">
              <input
                type="checkbox"
                checked={profile.notify_api_expiry}
                onChange={(e) => setField("notify_api_expiry", e.target.checked)}
              />
              <span>API 密钥到期通知</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}

