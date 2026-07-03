import { useEffect, useState } from "react";
import { apiGet, apiPut, apiPost, apiPatch } from "../api";
import { RefreshCw, Save, Monitor, CheckCircle2 } from "lucide-react";

export default function AudioSourcePicker() {
  const [apps, setApps] = useState([]);
  const [selected, setSelected] = useState([]);
  const [captureAll, setCaptureAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);

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
    await apiPut("/audio/sources", { bundle_ids: selected });
    if (captureAll !== undefined) {
      await apiPatch("/settings", { capture_all_system_audio: captureAll });
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (loading) {
    return <p className="text-sm text-zinc-500">Uygulamalar yükleniyor...</p>;
  }

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
        <input
          type="checkbox"
          checked={captureAll}
          onChange={(e) => setCaptureAll(e.target.checked)}
          className="rounded border-border"
        />
        Tüm sistem sesini dinle (eski davranış)
      </label>

      {!captureAll && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-500">
              Dinlenecek uygulamaları seçin. Seçilmezse sistem sesi kaydedilmez.
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

      <button
        onClick={save}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium"
      >
        {saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
        {saved ? "Kaydedildi" : "Kaydet"}
      </button>
    </div>
  );
}
