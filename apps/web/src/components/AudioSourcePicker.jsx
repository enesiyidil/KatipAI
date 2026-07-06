import { useEffect, useState } from "react";
import { apiGet, apiPut, apiPost } from "../api";
import { RefreshCw, Save, Monitor, CheckCircle2, AlertTriangle, Radio } from "lucide-react";

const ERROR_TR = {
  no_sources: "Uygulama seçilmedi veya tüm sistem sesi kapalı.",
  permission_denied:
    "SystemAudioCapture izni yok — Ayarlar → İzinler → «Sistem sesi izni iste».",
  helper_error: "Yakalama hatası — seçili uygulama açık mı kontrol edin.",
  process_exited: "Yakalama durdu — izin ve uygulama seçimini kontrol edin.",
};

function statusMessage(data) {
  if (data.message) return data.message;
  if (data.system_capture_active) {
    return data.capture_mode === "all"
      ? "Tüm sistem sesi dinleniyor"
      : `${data.bundle_ids?.length || 0} uygulama dinleniyor`;
  }
  if (!data.helper_ready) return "SystemAudioCapture helper derlenmemiş.";
  if (!data.system_enabled) return "Sistem sesi devre dışı (Kayıt Ayarları).";
  if (!data.listening) return "Dinleme kapalı — kayıt başlatınca uygulanır.";
  if (data.last_error) return ERROR_TR[data.last_error] || "Sistem sesi aktif değil.";
  if (!data.can_capture) return "Kaynak seçilmedi — sistem sesi dinlenmiyor.";
  return "Sistem sesi hazır değil.";
}

export default function AudioSourcePicker() {
  const [apps, setApps] = useState([]);
  const [selected, setSelected] = useState([]);
  const [captureAll, setCaptureAll] = useState(false);
  const [captureStatus, setCaptureStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [appsRes, sourcesRes] = await Promise.all([
        apiGet("/audio/apps"),
        apiGet("/audio/sources"),
      ]);
      setApps(appsRes.apps || []);
      setSelected(sourcesRes.bundle_ids || []);
      setCaptureAll(sourcesRes.capture_all_system_audio || false);
      setCaptureStatus(sourcesRes);
    } catch {
      setApps([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const refreshApps = async () => {
    const res = await apiPost("/audio/sources/refresh");
    setApps(res.apps || []);
  };

  const toggle = (bundleId) => {
    setSelected((prev) =>
      prev.includes(bundleId) ? prev.filter((id) => id !== bundleId) : [...prev, bundleId]
    );
  };

  const save = async () => {
    setSaving(true);
    setSaveMessage("");
    try {
      const res = await apiPut("/audio/sources", {
        bundle_ids: selected,
        capture_all_system_audio: captureAll,
      });
      setCaptureStatus(res);
      setSaveMessage(res.message || statusMessage(res));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setSaveMessage(String(e.message || e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="text-sm text-zinc-500">Uygulamalar yükleniyor...</p>;
  }

  const liveMsg = captureStatus ? statusMessage(captureStatus) : "";
  const liveOk = captureStatus?.system_capture_active;
  const liveWarn = captureStatus && !liveOk && captureStatus.listening;

  return (
    <div className="space-y-4">
      {captureStatus && (
        <div
          className={`rounded-lg border px-3 py-2 text-xs flex items-start gap-2 ${
            liveOk
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : liveWarn
                ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                : "border-border bg-surface/50 text-zinc-400"
          }`}
        >
          {liveOk ? (
            <Radio className="w-3.5 h-3.5 mt-0.5 shrink-0 animate-pulse" />
          ) : (
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          )}
          <div>
            <p>{liveMsg}</p>
            {captureStatus.listening && (
              <p className="text-[10px] opacity-80 mt-0.5">
                Dinleme aktif
                {captureStatus.system_capture_active ? " · sistem kanalı açık" : " · yalnızca mikrofon"}
              </p>
            )}
          </div>
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
        <input
          type="checkbox"
          checked={captureAll}
          onChange={(e) => setCaptureAll(e.target.checked)}
          className="rounded border-border"
        />
        Tüm sistem sesini dinle
      </label>

      {!captureAll && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-500">
              Dinlenecek uygulamaları seçin. Kaydedince dinleme açıksa anında uygulanır.
            </p>
            <button
              onClick={refreshApps}
              className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200"
            >
              <RefreshCw className="w-3 h-3" /> Yenile
            </button>
          </div>

          {apps.length === 0 ? (
            <p className="text-sm text-amber-400/80">
              Çalışan uygulama bulunamadı. Ses çıkaran bir uygulama açıp yenileyin.
            </p>
          ) : (
            <div className="max-h-48 overflow-y-auto space-y-1 rounded-lg border border-border p-2">
              {apps.map((app) => (
                <label
                  key={app.bundle_id}
                  className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-panel-hover cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(app.bundle_id)}
                    onChange={() => toggle(app.bundle_id)}
                    className="rounded border-border"
                  />
                  <Monitor className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                  <span className="text-sm text-zinc-300 truncate">{app.name}</span>
                  <span className="text-[10px] text-zinc-600 truncate ml-auto">{app.bundle_id}</span>
                </label>
              ))}
            </div>
          )}

          {selected.length === 0 && !captureAll && (
            <p className="text-xs text-amber-400/80">
              Hiç uygulama seçilmedi — sistem sesi dinlenmeyecek.
            </p>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium disabled:opacity-50"
        >
          {saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saving ? "Kaydediliyor..." : saved ? "Kaydedildi" : "Kaydet ve Uygula"}
        </button>
        {saveMessage && (
          <span className={`text-xs ${saved ? "text-emerald-400" : "text-red-400"}`}>{saveMessage}</span>
        )}
      </div>
    </div>
  );
}
