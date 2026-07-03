import { useEffect, useState } from "react";
import { useLiveStatus } from "../hooks/useLiveStatus";
import { apiGet } from "../api";
import MarkdownView from "../components/MarkdownView";
import { RefreshCw, ExternalLink } from "lucide-react";

export default function Notes() {
  const { tick } = useLiveStatus();
  const [data, setData] = useState({ notes: "", notes_path: "" });
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    apiGet("/vault/daily")
      .then(setData)
      .catch(() => setData({ notes: "", notes_path: "" }))
      .finally(() => setLoading(false));
  };

  useEffect(load, [tick]);

  return (
    <div className="max-w-3xl space-y-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-100">AI Notları</h2>
          <p className="text-sm text-zinc-500 mt-1">Günlük özet — Obsidian ile senkron</p>
        </div>
        <button onClick={load} className="p-2 rounded-lg border border-border hover:bg-panel-hover text-zinc-400">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {!data.notes ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-zinc-500 text-sm">
          Bugün için AI notu henüz yok. Oturum bitince otomatik oluşur.
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-panel p-6">
          <MarkdownView content={data.notes} />
          {data.notes_path && (
            <p className="mt-4 pt-4 border-t border-border text-[11px] text-zinc-600 flex items-center gap-1">
              <ExternalLink className="w-3 h-3" /> {data.notes_path}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
