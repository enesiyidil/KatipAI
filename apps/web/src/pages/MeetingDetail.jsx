import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useLiveStatus } from "../hooks/useLiveStatus";
import { API_BASE, apiGet, apiPatch, apiPost } from "../api";
import MarkdownView from "../components/MarkdownView";
import {
  ArrowLeft, Users, Clock, Loader2, RefreshCw, Pencil, Check, X, AlertCircle,
} from "lucide-react";

const STATE_BADGE = {
  recording: { label: "Kaydediliyor", className: "bg-red-500/15 text-red-400" },
  processing: { label: "İşleniyor", className: "bg-blue-500/15 text-blue-400" },
  ready: { label: "Hazır", className: "bg-emerald-500/15 text-emerald-400" },
  failed: { label: "Hata", className: "bg-red-500/15 text-red-300" },
};

function formatWhen(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function MeetingDetail() {
  const { id } = useParams();
  const { tick } = useLiveStatus();
  const [meeting, setMeeting] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiGet(`/meetings/${id}`)
      .then((data) => {
        setMeeting(data);
        setTitleDraft(data.title || "");
      })
      .catch(() => setMeeting(null))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(load, [load, tick]);

  const saveTitle = async () => {
    const title = titleDraft.trim();
    if (!title) return;
    setBusy(true);
    try {
      const updated = await apiPatch(`/meetings/${id}`, { title });
      setMeeting((prev) => (prev ? { ...prev, ...updated } : prev));
      setEditing(false);
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  };

  const reprocess = async () => {
    setBusy(true);
    try {
      await apiPost(`/meetings/${id}/reprocess`);
      load();
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  };

  if (loading && !meeting) {
    return (
      <div className="flex items-center gap-2 text-zinc-500 text-sm py-12 justify-center">
        <Loader2 className="w-4 h-4 animate-spin" /> Yükleniyor...
      </div>
    );
  }

  if (!meeting) {
    return (
      <div className="max-w-3xl space-y-4">
        <Link to="/meetings" className="inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200">
          <ArrowLeft className="w-4 h-4" /> Toplantılara dön
        </Link>
        <p className="text-red-400 text-sm">Toplantı bulunamadı.</p>
      </div>
    );
  }

  const badge = STATE_BADGE[meeting.processing_state] || STATE_BADGE.processing;
  const isProcessing = meeting.processing_state === "processing" || meeting.processing_state === "recording";

  return (
    <div className="max-w-3xl space-y-6">
      <Link to="/meetings" className="inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200">
        <ArrowLeft className="w-4 h-4" /> Toplantılar
      </Link>

      <header className="space-y-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center shrink-0">
            <Users className="w-5 h-5 text-purple-400" />
          </div>
          <div className="min-w-0 flex-1">
            {editing ? (
              <div className="flex items-center gap-2">
                <input
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  className="flex-1 bg-surface border border-border rounded-lg px-3 py-1.5 text-lg font-semibold text-zinc-100"
                  autoFocus
                />
                <button onClick={saveTitle} disabled={busy} className="p-2 text-emerald-400 hover:bg-emerald-500/10 rounded-lg">
                  <Check className="w-4 h-4" />
                </button>
                <button onClick={() => setEditing(false)} className="p-2 text-zinc-400 hover:bg-panel-hover rounded-lg">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 group">
                <h2 className="text-2xl font-semibold text-zinc-100">{meeting.title}</h2>
                <button
                  onClick={() => setEditing(true)}
                  className="p-1.5 text-zinc-600 hover:text-zinc-300 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Pencil className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
            <div className="flex items-center gap-2 mt-1 flex-wrap text-sm text-zinc-500">
              <span>{formatWhen(meeting.started_at)}</span>
              {meeting.duration_label && (
                <span className="inline-flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {meeting.duration_label}
                </span>
              )}
              {meeting.participants_hint && (
                <span className="text-zinc-400">· {meeting.participants_hint}</span>
              )}
              <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${badge.className}`}>
                {badge.label}
              </span>
            </div>
          </div>
          <button onClick={load} className="p-2 rounded-lg border border-border hover:bg-panel-hover text-zinc-400">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {meeting.stereo_path && (
          <div className="rounded-lg border border-border bg-panel px-4 py-3 space-y-2">
            <p className="text-xs text-zinc-500">Tam toplantı kaydı (stereo)</p>
            <audio controls preload="none" className="w-full h-9" src={`${API_BASE}/meetings/${meeting.id}/audio`} />
          </div>
        )}

        {meeting.processing_state === "failed" && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 flex items-start gap-3">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-red-300">İşleme hatası</p>
              <p className="text-xs text-red-400/80 mt-1">{meeting.processing_error || "Bilinmeyen hata"}</p>
              <button
                onClick={reprocess}
                disabled={busy}
                className="mt-3 px-3 py-1.5 rounded-lg bg-red-600/80 hover:bg-red-500 text-white text-xs font-medium disabled:opacity-50"
              >
                Yeniden işle
              </button>
            </div>
          </div>
        )}
      </header>

      <section className="space-y-3">
        <h3 className="text-sm font-medium text-zinc-300">AI Özet</h3>
        {isProcessing && !meeting.summary ? (
          <div className="rounded-xl border border-border bg-panel p-8 space-y-3 animate-pulse">
            <div className="h-3 bg-zinc-800 rounded w-3/4" />
            <div className="h-3 bg-zinc-800 rounded w-full" />
            <div className="h-3 bg-zinc-800 rounded w-5/6" />
          </div>
        ) : meeting.summary ? (
          <div className="rounded-xl border border-border bg-panel p-6">
            <MarkdownView content={meeting.summary} />
          </div>
        ) : (
          <p className="text-sm text-zinc-500">Özet henüz yok.</p>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-medium text-zinc-300">Transcript</h3>
        {isProcessing && (!meeting.transcript || meeting.transcript.length === 0) ? (
          <div className="rounded-xl border border-border bg-panel p-8 flex items-center gap-2 text-zinc-500 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Transcript hazırlanıyor...
          </div>
        ) : meeting.transcript?.length > 0 ? (
          <div className="rounded-xl border border-border bg-panel divide-y divide-border">
            {meeting.transcript.map((line) => (
              <TranscriptLine key={line.chunk_id} line={line} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-zinc-500">Transcript henüz yok.</p>
        )}
      </section>
    </div>
  );
}

function TranscriptLine({ line }) {
  const isBen = line.speaker === "Ben";
  return (
    <div className="px-4 py-3 flex gap-3">
      <span className="text-[11px] font-mono text-zinc-600 w-10 shrink-0 pt-0.5">{line.time}</span>
      <div className="min-w-0 flex-1 space-y-2">
        <span
          className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
            isBen ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"
          }`}
        >
          {line.speaker}
        </span>
        <p className="text-sm text-zinc-300">{line.text || "—"}</p>
        <audio
          controls
          preload="none"
          className="w-full h-8"
          src={`${API_BASE}/chunks/${line.chunk_id}/audio`}
        />
      </div>
    </div>
  );
}
