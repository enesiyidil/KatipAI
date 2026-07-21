import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../api";
import {
  Shield, Mic, Monitor, CheckCircle2, AlertCircle, HelpCircle,
  ExternalLink, RefreshCw, Zap, Eye,
} from "lucide-react";

const STATE_STYLE = {
  granted: { icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/10" },
  denied: { icon: AlertCircle, color: "text-red-400", bg: "bg-red-500/10" },
  unknown: { icon: HelpCircle, color: "text-amber-400", bg: "bg-amber-500/10" },
  unavailable: { icon: HelpCircle, color: "text-zinc-500", bg: "bg-zinc-800" },
};

function StatusRow({ icon: Icon, label, data }) {
  const st = STATE_STYLE[data?.state] || STATE_STYLE.unknown;
  const StIcon = st.icon;
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg ${st.bg}`}>
      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${st.color}`} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-zinc-200">{label}</p>
        <p className="text-xs text-zinc-400 mt-0.5">{data?.message}</p>
        {data?.hint && <p className="text-[10px] text-zinc-500 mt-1">{data.hint}</p>}
      </div>
      <StIcon className={`w-4 h-4 shrink-0 ${st.color}`} />
    </div>
  );
}

export default function PermissionsPanel() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setStatus(await apiGet("/permissions/status"));
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  };

  const act = async (fn) => {
    setBusy(true);
    try {
      const res = await fn();
      showToast(res.message || "Tamam", res.ok !== false);
      await load();
      return res;
    } catch (e) {
      showToast(String(e.message), false);
    } finally {
      setBusy(false);
    }
  };

  const setupAll = () => act(() => apiPost("/permissions/setup"));

  const requestMic = () => act(async () => {
    showToast("Konuşun — mikrofon test ediliyor...", true);
    return apiPost("/permissions/request/microphone");
  });

  const requestSystemAudio = () => act(async () => {
    showToast("SystemAudioCapture izin penceresi açılabilir...", true);
    return apiPost("/permissions/request/system-audio");
  });

  const revealHelper = () => act(() => apiPost("/permissions/reveal/system-audio-helper"));

  const openSetting = (key) => act(() => apiPost(`/permissions/open/${key}`));

  const restartCapture = () => act(() => apiPost("/permissions/restart-capture"));

  if (loading && !status) {
    return <p className="text-sm text-zinc-500">İzin durumu yükleniyor...</p>;
  }

  if (!status) {
    return <p className="text-sm text-red-400">İzin durumu alınamadı — core çalışıyor mu?</p>;
  }

  const plat = status.platform_label || status.platform;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-zinc-500">Platform: {plat}</span>
        <button
          onClick={load}
          disabled={busy}
          className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200"
        >
          <RefreshCw className={`w-3 h-3 ${busy ? "animate-spin" : ""}`} /> Yenile
        </button>
      </div>

      <StatusRow icon={Mic} label="Mikrofon" data={status.microphone} />
      <StatusRow icon={Monitor} label="Sistem sesi" data={status.system_audio} />
      {status.platform === "macos" && (
        <StatusRow icon={Eye} label="Erişilebilirlik (Teams başlığı)" data={status.accessibility} />
      )}

      {/* Tek tuş kurulum */}
      <button
        onClick={setupAll}
        disabled={busy}
        className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium disabled:opacity-50"
      >
        <Zap className="w-4 h-4" />
        Tüm izinleri kur (tek tık)
      </button>
      <p className="text-[10px] text-zinc-500 text-center -mt-2">
        Mikrofon testi + izin ayarları açılır. Sistem sesi için ayrıca SystemAudioCapture izni gerekir.
      </p>

      {/* Adım adım butonlar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <Btn onClick={requestMic} disabled={busy} icon={Mic} label="1. Mikrofon izni iste" />
        {status.platform === "macos" && (
          <>
            <Btn onClick={() => openSetting("microphone")} disabled={busy} icon={ExternalLink} label="2. Mikrofon ayarları" />
            <Btn onClick={() => openSetting("screen_recording")} disabled={busy} icon={ExternalLink} label="3. Ekran kaydı ayarları" />
            <Btn onClick={() => openSetting("accessibility")} disabled={busy} icon={Eye} label="4. Erişilebilirlik ayarları" />
            <Btn onClick={requestSystemAudio} disabled={busy} icon={Monitor} label="5. Sistem sesi izni iste" accent />
            <Btn onClick={revealHelper} disabled={busy} icon={ExternalLink} label="Helper'ı Finder'da göster" />
          </>
        )}
        {status.platform === "windows" && (
          <Btn onClick={() => openSetting("microphone")} disabled={busy} icon={ExternalLink} label="2. Mikrofon gizliliği" />
        )}
        <Btn onClick={restartCapture} disabled={busy} icon={RefreshCw} label="Kaydı yenile" accent />
      </div>

      {status.platform === "macos" && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-200/80 space-y-1">
          <p>
            <strong>Mikrofon:</strong> Python veya Terminal/Cursor işaretli olmalı.
          </p>
          <p>
            <strong>Sistem sesi:</strong> Python/iTerm/Cursor yetmez.{" "}
            <strong>KatipAIAudioHelper</strong> (KatipAI Audio) listede açık olmalı:{" "}
            Sistem Ayarları → <strong>Ekran ve Sistem Sesi Kaydı</strong>
          </p>
          <p>
            <strong>Teams başlığı:</strong> Terminal/Cursor için{" "}
            <strong>Erişilebilirlik</strong> izni gerekir — Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik
          </p>
        </div>
      )}
      {status.platform === "windows" && (
        <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2 text-[11px] text-blue-200/80">
          Windows: <strong>Ayarlar → Gizlilik → Mikrofon</strong> — Masaüstü uygulamalarına izin verin.
          Sistem sesi capture macOS&apos;ta desteklenir.
        </div>
      )}

      {toast && (
        <p className={`text-xs text-center ${toast.ok ? "text-emerald-400" : "text-red-400"}`}>
          {toast.msg}
        </p>
      )}
    </div>
  );
}

function Btn({ onClick, disabled, icon: Icon, label, accent }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${
        accent
          ? "bg-blue-600/80 hover:bg-blue-500 text-white"
          : "border border-border text-zinc-300 hover:bg-panel-hover"
      }`}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      {label}
    </button>
  );
}
