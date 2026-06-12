const API = "http://127.0.0.1:8742/api";
const WS = "ws://127.0.0.1:8742/ws";

export async function apiGet(path) {
  const res = await fetch(`${API}${path}`);
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

export async function apiPatch(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function apiDelete(path) {
  const res = await fetch(`${API}${path}`, { method: "DELETE" });
  return res.json();
}

export function connectWS(onMessage) {
  const ws = new WebSocket(WS);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onclose = () => setTimeout(() => connectWS(onMessage), 3000);
  return ws;
}
