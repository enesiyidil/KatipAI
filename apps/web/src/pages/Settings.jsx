import { useEffect, useState } from "react";
import { apiGet, apiPatch } from "../api";

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [vaultPath, setVaultPath] = useState("");

  useEffect(() => {
    apiGet("/settings").then((s) => {
      setSettings(s);
      setVaultPath(s.vault_path || "");
    });
  }, []);

  const save = async () => {
    const updated = await apiPatch("/settings", { vault_path: vaultPath });
    setSettings(updated);
  };

  if (!settings) return <p>Yükleniyor...</p>;

  return (
    <div className="max-w-xl space-y-6">
      <h2 className="text-2xl font-semibold">Ayarlar</h2>

      <label className="block space-y-1">
        <span className="text-sm text-zinc-400">Obsidian Vault Yolu</span>
        <input
          className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2"
          value={vaultPath}
          onChange={(e) => setVaultPath(e.target.value)}
          placeholder="/Users/you/ObsidianVault"
        />
      </label>

      <button onClick={save} className="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded text-sm">
        Kaydet
      </button>

      <section className="border border-zinc-800 rounded-lg p-4 space-y-2 text-sm">
        <h3 className="font-medium">Modeller</h3>
        <p><span className="text-zinc-400">STT:</span> {settings.stt_model}</p>
        <p><span className="text-zinc-400">LLM:</span> {settings.llm_model}</p>
      </section>

      <section className="border border-zinc-700 rounded-lg p-4 opacity-60">
        <h3 className="font-medium mb-1">API Entegrasyonu</h3>
        <p className="text-sm text-zinc-400">Yakında — Google STT + Claude/Gemini. Şimdilik tamamen lokal.</p>
      </section>
    </div>
  );
}
