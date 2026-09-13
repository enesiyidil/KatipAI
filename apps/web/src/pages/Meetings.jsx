import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useLiveStatus } from "../hooks/useLiveStatus";
import { apiGet } from "../api";
import { Users, RefreshCw, Loader2, ChevronRight, Clock } from "lucide-react";
import MarkdownView from "../components/MarkdownView";

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
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Meetings() {
  const { tick } = useLiveStatus();
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    apiGet("/meetings")
      .then(setMeetings)
      .catch(() => setMeetings([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, [tick]);

  return (
    <div className="max-w-3xl space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-zinc-100">Toplantılar</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Toplantı modunda kaydedilen oturumlar — AI özeti ve transcript
          </p>
        </div>
        <button
          onClick={load}
          className="p-2 rounded-lg border border-border hover:bg-panel-hover text-zinc-400"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {loading && meetings.length === 0 ? (
        <div className="flex items-center gap-2 text-zinc-500 text-sm py-12 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> Yükleniyor...
        </div>
      ) : meetings.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-zinc-500 text-sm space-y-2">
          <Users className="w-8 h-8 mx-auto text-zinc-600" />
          <p>Henüz toplantı kaydı yok.</p>
          <p className="text-xs">Toplantı moduna geçip bir toplantı kaydedin.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {meetings.map((m) => (
            <MeetingCard key={m.id} meeting={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function MeetingCard({ meeting }) {
  const badge = STATE_BADGE[meeting.processing_state] || STATE_BADGE.processing;

  return (
    <Link
      to={`/meetings/${meeting.id}`}
      className="block rounded-xl border border-border bg-panel p-4 hover:border-zinc-600 transition-colors group"
    >
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-purple-500/10 flex items-center justify-center shrink-0">
          <Users className="w-4 h-4 text-purple-400" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-medium text-zinc-100 truncate">{meeting.title}</h3>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${badge.className}`}>
              {badge.label}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1 text-[11px] text-zinc-500 flex-wrap">
            <span>{formatWhen(meeting.started_at)}</span>
            {meeting.duration_label && (
              <span className="inline-flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {meeting.duration_label}
              </span>
            )}
            {meeting.participants_hint && (
              <span className="text-zinc-400">{meeting.participants_hint}</span>
            )}
          </div>
          {meeting.summary_snippet && (
            <div className="mt-3 text-xs text-zinc-400 line-clamp-3 prose prose-invert prose-sm max-w-none">
              <MarkdownView content={meeting.summary_snippet} />
            </div>
          )}
          {meeting.processing_state === "processing" && !meeting.summary_snippet && (
            <p className="mt-2 text-xs text-blue-400/80">Transcript ve özet hazırlanıyor…</p>
          )}
        </div>
        <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 shrink-0 mt-1" />
      </div>
    </Link>
  );
}
