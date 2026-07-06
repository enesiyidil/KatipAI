import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiGet, WS } from "../api";

const LiveStatusContext = createContext(null);

const REFRESH_EVENTS = new Set([
  "chunk",
  "transcript_done",
  "session_finalized",
  "chunk_deleted",
]);

function handleWsMessage(msg, setStatus, setTick) {
  if (msg.event === "state") {
    setStatus((prev) => ({ ...prev, state: msg.state }));
  }
  if (msg.event === "mode") {
    setStatus((prev) => ({ ...prev, mode: msg.mode }));
  }
  if (REFRESH_EVENTS.has(msg.event)) {
    setTick((t) => t + 1);
  }
}

export function LiveStatusProvider({ children }) {
  const [status, setStatus] = useState({ state: "idle", mode: "normal" });
  const [stats, setStats] = useState(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([apiGet("/status"), apiGet("/stats/today")]);
      setStatus(s);
      setStats(st);
    } catch {
      /* server down */
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 8000);
    return () => clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    refresh();
  }, [tick, refresh]);

  useEffect(() => {
    let ws;
    let closed = false;
    let reconnectTimer;

    const connect = () => {
      ws = new WebSocket(WS);
      ws.onmessage = (e) => {
        handleWsMessage(JSON.parse(e.data), setStatus, setTick);
      };
      ws.onclose = () => {
        if (!closed) {
          reconnectTimer = setTimeout(connect, 2500);
        }
      };
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  const value = { status, stats, refresh, tick };

  return (
    <LiveStatusContext.Provider value={value}>
      {children}
    </LiveStatusContext.Provider>
  );
}

export function useLiveStatus() {
  const ctx = useContext(LiveStatusContext);
  if (!ctx) {
    throw new Error("useLiveStatus must be used within LiveStatusProvider");
  }
  return ctx;
}
