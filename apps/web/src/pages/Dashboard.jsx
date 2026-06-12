import { useEffect, useState } from "react";
import { apiGet, connectWS } from "../api";

const STATE_LABELS = {
  idle: "Beklemede",
  listening: "Dinliyor",
  recording: "Kayıt alınıyor",
  processing: "İşleniyor",
  paused: "Duraklatıldı",
  sensitive: "Hassas mod",
  error: "Hata",
};

const STATE_COLORS = {
  idle: "bg-zinc-600",
  listening: "bg-emerald-500",
  recording: "bg-red-500 animate-pulse",
  processing: "bg-blue-500",
  paused: "bg-orange-500",
  sensitive: "bg-purple-500",
  error: "bg-red-700",
};

export default function Dashboard() {
  const [status, setStatus] = useState({ state: "idle", mode: "normal" });
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    apiGet("/status").then(setStatus);
    apiGet("/sessions/today").then(setSessions);
    connectWS((msg) => {
      if (msg.event === "state") setStatus((s) => ({ ...s, state: msg.state }));
      if (msg.event === "transcript_done" || msg.event === "session_finalized") {
        apiGet("/sessions/today").then(setSessions);
      }
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className={`w-4 h-4 rounded-full ${STATE_COLORS[status.state] || "bg-zinc-600"}`} />
        <div>
          <h2 className="text-2xl font-semibold">{STATE_LABELS[status.state] || status.state}</h2>
          <p className="text-zinc-400 text-sm">Mod: {status.mode}</p>
        </div>
      </div>

      <section>
        <h3 className="text-lg font-medium mb-3">Bugünün Oturumları</h3>
        {sessions.length === 0 ? (
          <p className="text-zinc-500">Henüz oturum yok. Konuşmaya başlayın — VAD otomatik kaydedecek.</p>
        ) : (
          <ul className="space-y-3">
            {sessions.map((s) => (
              <li key={s.id} className="border border-zinc-800 rounded-lg p-4">
                <div className="text-sm text-zinc-400">{new Date(s.started_at).toLocaleTimeString("tr-TR")}</div>
                <p className="mt-1">{s.summary || "Özet henüz üretilmedi..."}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
