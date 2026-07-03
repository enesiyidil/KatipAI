import { useCallback, useEffect, useState } from "react";
import { apiGet, connectWS } from "../api";

export function useLiveStatus() {
  const [status, setStatus] = useState({ state: "idle", mode: "normal" });
  const [stats, setStats] = useState(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([apiGet("/status"), apiGet("/stats/today")]);
      setStatus(s);
      setStats(st);
    } catch { /* server down */ }
  }, []);

  useEffect(() => {
    refresh();
    const off = connectWS((msg) => {
      if (msg.event === "state") setStatus((p) => ({ ...p, state: msg.state }));
      if (msg.event === "mode") setStatus((p) => ({ ...p, mode: msg.mode }));
      if (["chunk", "transcript_done", "session_finalized"].includes(msg.event)) {
        setTick((t) => t + 1);
      }
    });
    const iv = setInterval(refresh, 8000);
    return () => { off(); clearInterval(iv); };
  }, [refresh]);

  useEffect(() => { refresh(); }, [tick, refresh]);

  return { status, stats, refresh, tick };
}
