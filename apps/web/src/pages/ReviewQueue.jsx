import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE, apiGet, apiPost } from "../api";
import { AlertTriangle, Check, Pencil, RefreshCw, Mic, Monitor, ExternalLink } from "lucide-react";

export default function ReviewQueue() {
  const [items, setItems] = useState([]);
  const [edits, setEdits] = useState({});
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");

  const load = () => {
    setLoading(true);
    apiGet("/chunks/review-queue")
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
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

  const reprocess = async (chunkId) => {
    await apiPost(`/chunks/${chunkId}/reprocess`);
    load();
  };

  const filtered = items.filter((item) => {
    if (tab === "failed") return item.kind === "failed";
    if (tab === "review") return item.kind === "review";
    return true;
  });

  return (
    <div className="max-w-2xl space-y-6">
      <header className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-100">Düzeltme Kuyruğu</h2>
          <p className="text-sm text-zinc-500 mt-1">Düşük güven ve hatalı transcript&apos;ler — sesi dinleyip düzelt</p>
        </div>
        <button onClick={load} className="p-2 rounded-lg border border-border hover:bg-panel-hover text-zinc-400">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      <div className="flex gap-2 text-xs">
        {[
          { id: "all", label: "Tümü" },
          { id: "review", label: "İnceleme" },
          { id: "failed", label: "Başarısız" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded-lg border ${
              tab === t.id
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                : "border-border text-zinc-400 hover:bg-panel-hover"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center">
          <Check className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          <p className="text-sm text-zinc-400">İncelenecek transcript yok — harika!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => (
            <ReviewCard
              key={`${item.kind}-${item.chunk_id}`}
              item={item}
              editValue={edits[item.transcript_id] ?? item.text}
              onEdit={(v) => setEdits({ ...edits, [item.transcript_id]: v })}
              onApprove={() => approve(item.chunk_id)}
              onCorrect={() => correct(item.transcript_id)}
              onReprocess={() => reprocess(item.chunk_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ReviewCard({ item, editValue, onEdit, onApprove, onCorrect, onReprocess }) {
  const isMic = item.channel === "mic";
  const isFailed = item.kind === "failed";
  const conf =
    item.confidence != null && Number.isFinite(item.confidence)
      ? item.confidence.toFixed(2)
      : "—";

  return (
    <div
      className={`rounded-xl border p-4 space-y-3 ${
        isFailed ? "border-red-500/20 bg-red-500/5" : "border-amber-500/20 bg-amber-500/5"
      }`}
    >
      <div className="flex items-center gap-2 text-xs flex-wrap">
        <AlertTriangle className={`w-3.5 h-3.5 ${isFailed ? "text-red-400" : "text-amber-400"}`} />
        <span className={isFailed ? "text-red-400" : "text-amber-400"}>
          {isFailed ? "Hata" : `Güven: ${conf}`}
        </span>
        {item.time && <span className="text-zinc-500 font-mono">{item.time}</span>}
        <span
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md ${
            isMic ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"
          }`}
        >
          {isMic ? <Mic className="w-3 h-3" /> : <Monitor className="w-3 h-3" />}
          {item.speaker || (isMic ? "Mic" : "Sistem")}
        </span>
        <span className="text-zinc-600 ml-auto">Chunk #{item.chunk_id}</span>
        {item.mode === "meeting" && item.session_id && (
          <Link
            to={`/meetings/${item.session_id}`}
            className="inline-flex items-center gap-1 text-zinc-400 hover:text-zinc-200"
          >
            <ExternalLink className="w-3 h-3" /> Toplantı
          </Link>
        )}
        {item.mode !== "meeting" && (
          <Link to="/timeline" className="inline-flex items-center gap-1 text-zinc-400 hover:text-zinc-200">
            <ExternalLink className="w-3 h-3" /> Akış
          </Link>
        )}
      </div>

      {item.has_audio && (
        <audio controls preload="none" className="w-full h-9" src={`${API_BASE}/chunks/${item.chunk_id}/audio`} />
      )}

      {isFailed && item.processing_error && (
        <p className="text-xs text-red-400/80">{item.processing_error}</p>
      )}

      <p className="text-sm text-zinc-200">{item.text || "—"}</p>

      <div className="flex gap-2 flex-wrap">
        {!isFailed && (
          <button
            onClick={onApprove}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"
          >
            <Check className="w-3.5 h-3.5" /> Doğru
          </button>
        )}
        {isFailed && (
          <button
            onClick={onReprocess}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Yeniden işle
          </button>
        )}
        {item.transcript_id && (
          <div className="flex-1 flex gap-2 min-w-[200px]">
            <input
              className="flex-1 bg-surface border border-border rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-emerald-500/50"
              placeholder="Düzeltilmiş metin..."
              value={editValue}
              onChange={(e) => onEdit(e.target.value)}
            />
            <button
              onClick={onCorrect}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border hover:bg-panel-hover text-xs text-zinc-300"
            >
              <Pencil className="w-3.5 h-3.5" /> Düzelt
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
