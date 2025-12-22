import axios from "axios";

export const api = axios.create({
  baseURL: "/",
});

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

