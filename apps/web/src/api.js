const API = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8742/api";
export const API_BASE = API;
export const WS = import.meta.env.VITE_WS_BASE || "ws://127.0.0.1:8742/ws";

export async function apiGet(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPut(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "PUT",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPatch(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiDelete(path) {
  const res = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const STATE_META = {
  idle: { label: "Beklemede", color: "bg-zinc-500", text: "text-zinc-400" },
  listening: { label: "Dinliyor", color: "bg-emerald-500", text: "text-emerald-400", pulse: true },
  recording: { label: "Kayıt", color: "bg-red-500", text: "text-red-400", pulse: true },
  processing: { label: "İşleniyor", color: "bg-blue-500", text: "text-blue-400", pulse: true },
  paused: { label: "Duraklatıldı", color: "bg-orange-500", text: "text-orange-400" },
  sensitive: { label: "Hassas Mod", color: "bg-purple-500", text: "text-purple-400" },
  error: { label: "Hata", color: "bg-red-600", text: "text-red-500" },
};

export const MODES = [
  { id: "normal", label: "Normal", desc: "Sadece mikrofon — söylediklerin anında not olur" },
  { id: "meeting", label: "Toplantı", desc: "Mic + Teams — toplantı bitince tek seferde işlenir" },
];

export const MODE_LABELS = Object.fromEntries(MODES.map((m) => [m.id, m.label]));
