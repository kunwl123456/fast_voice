import axios from "axios";

export const api = axios.create({
  baseURL: "/",
});

function setAuthHeader(token) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export function persistToken(token) {
  try {
    if (typeof localStorage !== "undefined" && token) {
      localStorage.setItem("fa_token", token);
      setAuthHeader(token);
    }
  } catch (e) {
    // ignore storage failure
  }
}

export function clearToken() {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem("fa_token");
    }
  } catch (e) {
    // ignore
  }
  setAuthHeader(null);
}

export function getStoredToken() {
  try {
    if (typeof localStorage !== "undefined") {
      const token = localStorage.getItem("fa_token");
      if (token) setAuthHeader(token);
      return token;
    }
  } catch (e) {
    return null;
  }
  return null;
}

export async function fetchVoices(params = {}) {
  const res = await api.get("/api/discovery/voices", { params });
  return res.data;
}

export async function fetchVoiceDetail(id) {
  const res = await api.get(`/api/discovery/voices/${id}`);
  return res.data;
}

export async function bookmarkVoice(voice_model_id) {
  const res = await api.post("/api/discovery/bookmark", { voice_model_id });
  return res.data;
}

export async function fetchCredits() {
  const [balanceRes, txRes] = await Promise.all([
    api.get("/api/credits/balance"),
    api.get("/api/credits/transactions"),
  ]);
  return { balance: balanceRes.data.balance, transactions: txRes.data.transactions };
}

export async function placeholderTTS(payload) {
  // 按用户要求，后端占位接口会返回 501
  const res = await api.post("/api/tts/generate", payload, { validateStatus: () => true });
  return res;
}

export async function placeholderCreateVoice(payload) {
  const res = await api.post("/api/voice-cloning/create", payload, { validateStatus: () => true });
  return res;
}

export async function registerUser(payload) {
  const res = await api.post("/api/auth/register", payload, { validateStatus: (s) => s < 500 });
  if (res.data?.token) persistToken(res.data.token);
  return res;
}

export async function loginUser(payload) {
  const res = await api.post("/api/auth/login", payload, { validateStatus: (s) => s < 500 });
  if (res.data?.token) persistToken(res.data.token);
  return res;
}

export async function fetchMe(token) {
  const tk = token || getStoredToken();
  if (tk) setAuthHeader(tk);
  const res = await api.get("/api/auth/me", { validateStatus: (s) => s < 500 });
  return res;
}

export async function fetchProfile() {
  const res = await api.get("/api/auth/profile", { validateStatus: (s) => s < 500 });
  return res;
}

export async function updateProfile(payload) {
  const res = await api.patch("/api/auth/profile", payload, { validateStatus: (s) => s < 500 });
  return res;
}

export async function changePassword(payload) {
  const res = await api.post("/api/auth/password/change", payload, { validateStatus: (s) => s < 500 });
  return res;
}

export async function changeEmail(payload) {
  const res = await api.post("/api/auth/email/change", payload, { validateStatus: (s) => s < 500 });
  return res;
}

export async function uploadAvatar(payload) {
  const res = await api.post("/api/auth/avatar", payload, { validateStatus: (s) => s < 500 });
  return res;
}

export async function logoutUser() {
  const res = await api.post("/api/auth/logout", {}, { validateStatus: (s) => s < 500 });
  clearToken();
  return res;
}

