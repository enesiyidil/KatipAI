import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useLiveStatus } from "../hooks/useLiveStatus";
import { apiGet } from "../api";
import MarkdownView from "../components/MarkdownView";
import { RefreshCw, ExternalLink } from "lucide-react";

export default function Transcripts() {
  const { tick } = useLiveStatus();
  const [data, setData] = useState({ transcript: "" });
  const [loading, setLoading] = useState(true);
  const [vaultError, setVaultError] = useState(false);

  const load = () => {
    setLoading(true);
    setVaultError(false);
    apiGet("/vault/daily")
      .then(setData)
      .catch(() => {
        setData({ transcript: "" });
        setVaultError(true);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [tick]);

  return (
    <div className="max-w-3xl space-y-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-100">Transcript</h2>
          <p className="text-sm text-zinc-500 mt-1">Bugünkü ham konuşma kaydı (Obsidian vault)</p>
        </div>
        <button onClick={load} className="p-2 rounded-lg border border-border hover:bg-panel-hover text-zinc-400">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {(vaultError || !data.transcript) && (
        <div className="rounded-lg border border-border bg-panel px-4 py-3 text-sm text-zinc-400">
          Vault boş veya erişilemiyor olabilir. Canlı kayıtlar için{" "}
          <Link to="/timeline" className="text-emerald-400 hover:underline inline-flex items-center gap-1">
            Canlı Akış <ExternalLink className="w-3 h-3" />
          </Link>
          {" "}sayfasına bakın (veritabanı).
        </div>
      )}

      {!data.transcript ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-zinc-500 text-sm">
          Bugün vault transcript yok.
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-panel p-6">
          <MarkdownView content={data.transcript} />
        </div>
      )}
    </div>
  );
}
