import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api";
import { AlertTriangle, Check, Pencil, RefreshCw } from "lucide-react";

export default function ReviewQueue() {
  const [items, setItems] = useState([]);
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    apiGet("/chunks/review-queue").then(setItems).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const approve = async (chunkId) => {
    await apiPost(`/chunks/${chunkId}/approve`);
    load();
  };

  const correct = async (transcriptId) => {
    const text = edits[transcriptId];
    if (!text?.trim()) return;
    await apiPost(`/transcripts/${transcriptId}/correct`, { corrected_text: text, approved: true });
    load();
  };

  return (
    <div className="max-w-2xl space-y-6">
      <header className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-100">Düzeltme Kuyruğu</h2>
          <p className="text-sm text-zinc-500 mt-1">Düşük güven skorlu transcript'ler</p>
        </div>
        <button onClick={load} className="p-2 rounded-lg border border-border hover:bg-panel-hover text-zinc-400">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center">
          <Check className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          <p className="text-sm text-zinc-400">İncelenecek transcript yok — harika!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.transcript_id} className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-amber-400">Güven: {item.confidence}</span>
                <span className="text-zinc-600 ml-auto">Chunk #{item.chunk_id}</span>
              </div>
              <p className="text-sm text-zinc-200">{item.text}</p>
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => approve(item.chunk_id)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"
                >
                  <Check className="w-3.5 h-3.5" /> Doğru
                </button>
                <div className="flex-1 flex gap-2 min-w-[200px]">
                  <input
                    className="flex-1 bg-surface border border-border rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-emerald-500/50"
                    placeholder="Düzeltilmiş metin..."
                    value={edits[item.transcript_id] ?? item.text}
                    onChange={(e) => setEdits({ ...edits, [item.transcript_id]: e.target.value })}
                  />
                  <button
                    onClick={() => correct(item.transcript_id)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border hover:bg-panel-hover text-xs text-zinc-300"
                  >
                    <Pencil className="w-3.5 h-3.5" /> Düzelt
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
