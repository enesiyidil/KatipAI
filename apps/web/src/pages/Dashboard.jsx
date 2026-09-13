import { useEffect, useState } from "react";
import { useLiveStatus } from "../hooks/useLiveStatus";
import ControlPanel from "../components/ControlPanel";
import { apiGet, STATE_META } from "../api";
import { Radio, Mic, Monitor, Loader2, AlertTriangle } from "lucide-react";

const LIMIT = 20;

export default function Dashboard() {
  const { status, stats, refresh, tick } = useLiveStatus();
  const [chunks, setChunks] = useState([]);

  useEffect(() => {
    apiGet("/timeline/today")
      .then((d) => setChunks((d.items || []).slice(0, LIMIT)))
      .catch(() => setChunks([]));
  }, [tick]);

  const meta = STATE_META[status?.state] || STATE_META.idle;
  const pipeline = status?.pipeline;

  return (
    <div className="space-y-6 max-w-5xl">
      <header>
        <h2 className="text-2xl font-semibold text-zinc-100">Kontrol Paneli</h2>
        <p className="text-sm text-zinc-500 mt-1">Canlı dinleme ve son kayıtlar</p>
      </header>

      {status?.capture_warning && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          {status.capture_warning}
        </div>
      )}
      {status?.mic_hint && (
        <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-300">
          {status.mic_hint}
        </div>
      )}
      {pipeline?.busy && (
        <div className="rounded-lg border border-border bg-panel px-4 py-2 text-xs text-zinc-400 flex items-center gap-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Pipeline: {pipeline.active || 0} aktif, {pipeline.pending || 0} bekleyen
        </div>
      )}

      <div className="grid lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 rounded-xl border border-border bg-panel p-5 flex flex-col items-center justify-center text-center min-h-[160px]">
          <div className={`w-14 h-14 rounded-2xl ${meta.color}/20 flex items-center justify-center mb-3`}>
            <Radio className={`w-7 h-7 ${meta.text} ${meta.pulse ? "animate-pulse" : ""}`} />
          </div>
          <p className={`text-lg font-semibold ${meta.text}`}>{meta.label}</p>
          <p className="text-xs text-zinc-500 mt-1">
            {stats ? `${stats.transcripts} transcript bugün` : "—"}
          </p>
        </div>

        <div className="lg:col-span-3">
          <ControlPanel status={status} onAction={refresh} />
        </div>
      </div>

      <section>
        <h3 className="text-sm font-medium text-zinc-400 mb-3">
          Son {LIMIT} kayıt
        </h3>
        {chunks.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-zinc-500 text-sm">
            Henüz kayıt yok. Konuşmaya başla — pending/failed satırlar da burada görünür.
          </div>
        ) : (
          <div className="space-y-2">
            {chunks.map((item) => (
              <DashChunk key={item.id} item={item} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function DashChunk({ item }) {
  const skipped = item.skip_reason === "echo" || item.skip_reason === "voice_mismatch";
  const failed = Boolean(item.processing_error);
  const pending = item.text == null && !skipped && !failed;
  const emptyText = !item.text?.trim() && !pending && !skipped && !failed;

  let body = item.text;
  let bodyClass = "text-zinc-200";
  if (pending) {
    body = "İşleniyor…";
    bodyClass = "text-zinc-500 italic";
  } else if (failed) {
    body = item.processing_error || "STT hatası";
    bodyClass = "text-red-400";
  } else if (skipped) {
    body = item.skip_reason === "echo" ? "Echo — atlandı" : "Ses eşleşmedi — atlandı";
    bodyClass = "text-zinc-500 italic";
  } else if (emptyText) {
    body = "Boş / reddedildi";
    bodyClass = "text-zinc-500 italic";
  }

  return (
    <div className="rounded-lg border border-border bg-panel px-4 py-3 flex gap-3 items-start">
      <span className="text-xs text-zinc-500 font-mono shrink-0 pt-0.5 w-10">
        {(item.time || "").slice(0, 5)}
      </span>
      {item.channel === "mic" ? (
        <Mic className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
      ) : (
        <Monitor className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
      )}
      {(failed || pending) && (
        <span className="shrink-0 mt-0.5">
          {pending ? (
            <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
          ) : (
            <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
          )}
        </span>
      )}
      <p className={`text-sm leading-relaxed flex-1 ${bodyClass}`}>{body}</p>
    </div>
  );
}
