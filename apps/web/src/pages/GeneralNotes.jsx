import { useEffect, useState } from "react";
import { useLiveStatus } from "../hooks/useLiveStatus";
import { apiGet } from "../api";
import MarkdownView from "../components/MarkdownView";
import { BookMarked, RefreshCw, Info } from "lucide-react";

export default function GeneralNotes() {
  const { tick } = useLiveStatus();
  const [data, setData] = useState({ content: "" });
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    apiGet("/vault/general")
      .then(setData)
      .catch(() => setData({ content: "" }))
      .finally(() => setLoading(false));
  };

  useEffect(load, [tick]);

  return (
    <div className="max-w-3xl space-y-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-100 flex items-center gap-2">
            <BookMarked className="w-6 h-6 text-emerald-400" /> Genel Notlar
          </h2>
          <p className="text-sm text-zinc-500 mt-1">Kalıcı notlar — sesli komutla eklenir</p>
        </div>
        <button onClick={load} className="p-2 rounded-lg border border-border hover:bg-panel-hover text-zinc-400">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 flex gap-3 text-sm text-emerald-200/80">
        <Info className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
        <p>
          Konuşurken <strong className="text-emerald-300">"bunu genel notlara ekle"</strong> veya{" "}
          <strong className="text-emerald-300">"genel not olarak …"</strong> de —
          not Obsidian <code className="text-xs bg-emerald-500/10 px-1 rounded">general/Notlar.md</code> dosyasına yazılır.
        </p>
      </div>

      {!data.content || data.content.length < 50 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-zinc-500 text-sm">
          Henüz genel not yok.
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-panel p-6">
          <MarkdownView content={data.content} />
        </div>
      )}
    </div>
  );
}
