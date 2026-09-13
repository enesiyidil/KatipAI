import { useEffect, useState } from "react";
import { apiGet, apiPatch } from "../api";
import { Save, Shield, Cpu, FolderOpen, CheckCircle2, Volume2 } from "lucide-react";
import AudioSourcePicker from "../components/AudioSourcePicker";
import VoiceProfileSection from "../components/VoiceProfileSection";
import PermissionsPanel from "../components/PermissionsPanel";

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [vaultPath, setVaultPath] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    apiGet("/settings").then((s) => { setSettings(s); setVaultPath(s.vault_path || ""); });
  }, []);

  const save = async () => {
    const updated = await apiPatch("/settings", { vault_path: vaultPath });
    setSettings(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const patchSetting = async (fields) => {
    const updated = await apiPatch("/settings", fields);
    setSettings(updated);
  };

  if (!settings) return <div className="text-zinc-500 text-sm">Yükleniyor...</div>;

  return (
    <div className="max-w-xl space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-zinc-100">Ayarlar</h2>
        <p className="text-sm text-zinc-500 mt-1">Vault, ses ayrımı, modeller ve gizlilik</p>
      </header>

      <section className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Shield className="w-4 h-4 text-emerald-400" /> İzinler ve Kurulum
        </div>
        <PermissionsPanel />
      </section>

      <section className="rounded-xl border border-border bg-panel p-5 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <FolderOpen className="w-4 h-4 text-emerald-400" /> Obsidian Vault
        </div>
        <input
          className="w-full bg-surface border border-border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-emerald-500/50"
          value={vaultPath}
          onChange={(e) => setVaultPath(e.target.value)}
          placeholder="/Users/you/ObsidianVault"
        />
        <button
          onClick={save}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium"
        >
          {saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? "Kaydedildi" : "Kaydet"}
        </button>
      </section>

      <section className="rounded-xl border border-border bg-panel p-5 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Volume2 className="w-4 h-4 text-emerald-400" /> Ses Kaynakları
        </div>
        <AudioSourcePicker />
      </section>

      <section className="rounded-xl border border-border bg-panel p-5 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Volume2 className="w-4 h-4 text-blue-400" /> Echo Bastırma
        </div>
        <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.echo_suppression_enabled}
            onChange={(e) => patchSetting({ echo_suppression_enabled: e.target.checked })}
          />
          Hoparlör yankısını filtrele (mic ↔ system)
        </label>
        <div>
          <label className="text-[11px] text-zinc-500">
            Korelasyon eşiği: {(settings.echo_correlation_threshold * 100).toFixed(0)}%
          </label>
          <input
            type="range"
            min="50"
            max="90"
            value={Math.round(settings.echo_correlation_threshold * 100)}
            onChange={(e) => patchSetting({ echo_correlation_threshold: Number(e.target.value) / 100 })}
            className="w-full mt-1"
            disabled={!settings.echo_suppression_enabled}
          />
        </div>
      </section>

      <section className="rounded-xl border border-border bg-panel p-5 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Volume2 className="w-4 h-4 text-purple-400" /> Ses Profili
        </div>
        <VoiceProfileSection settings={settings} onSettingsChange={setSettings} />
      </section>

      <section className="rounded-xl border border-border bg-panel p-5 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Volume2 className="w-4 h-4 text-emerald-400" /> Kayıt Ayarları
        </div>
        <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.mic_enabled}
            onChange={(e) => patchSetting({ mic_enabled: e.target.checked })}
          />
          Mikrofon etkin
        </label>
        <label className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.system_enabled}
            onChange={(e) => patchSetting({ system_enabled: e.target.checked })}
          />
          Sistem sesi etkin
        </label>
        <p className="text-[10px] text-zinc-600">
          Mic/sistem anahtarları anında uygulanır. Uygulama seçimi için yukarıdaki «Kaydet ve Uygula» yeterli.
        </p>
        <div>
          <label className="text-[11px] text-zinc-500">VAD eşiği: {settings.vad_threshold}</label>
          <input
            type="range"
            min="30"
            max="90"
            value={Math.round(settings.vad_threshold * 100)}
            onChange={(e) => patchSetting({ vad_threshold: Number(e.target.value) / 100 })}
            className="w-full mt-1"
          />
        </div>
        <div>
          <label className="text-[11px] text-zinc-500">Min ses seviyesi: {settings.min_audio_rms}</label>
          <input
            type="range"
            min="5"
            max="30"
            value={Math.round(settings.min_audio_rms * 1000)}
            onChange={(e) => patchSetting({ min_audio_rms: Number(e.target.value) / 1000 })}
            className="w-full mt-1"
          />
        </div>
      </section>

      <section className="rounded-xl border border-border bg-panel p-5 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Cpu className="w-4 h-4 text-emerald-400" /> Modeller
        </div>
        <Row label="STT" value={settings.stt_model} />
        <Row label="STT Fallback" value={settings.stt_fallback_model} />
        <Row label="LLM" value={settings.llm_model} />
        <Row label="LLM Fallback" value={settings.llm_fallback_model} />
      </section>

      <section className="rounded-xl border border-border bg-panel p-5 space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Shield className="w-4 h-4 text-emerald-400" /> Gizlilik
        </div>
        <p className="text-sm text-zinc-400">Tüm ses ve transcript verisi bu bilgisayarda kalır.</p>
        <div className="rounded-lg bg-zinc-800/50 px-3 py-2 text-xs text-zinc-500">
          API entegrasyonu: {settings.api_note}
        </div>
      </section>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] text-zinc-500 uppercase tracking-wide">{label}</span>
      <span className="text-xs text-zinc-300 font-mono truncate">{value}</span>
    </div>
  );
}
