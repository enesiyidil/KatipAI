import { useEffect, useState } from "react";
import { useLiveStatus } from "../hooks/useLiveStatus";
import { apiGet } from "../api";
import { Mic, Monitor, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

export default function Timeline() {
  const { tick } = useLiveStatus();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiGet("/timeline/today")
      .then((d) => setItems(d.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [tick]);

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-zinc-100">Canlı Akış</h2>
        <p className="text-sm text-zinc-500 mt-1">Bugünkü tüm kayıtlar — WebSocket ile anlık güncellenir</p>
      </header>

      {loading && items.length === 0 ? (
        <div className="flex items-center gap-2 text-zinc-500 text-sm py-12 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> Yükleniyor...
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-zinc-500 text-sm">
          Henüz kayıt yok. Mikrofonuna konuşmaya başla.
        </div>
      ) : (
        <div className="relative">
          <div className="absolute left-[19px] top-2 bottom-2 w-px bg-border" />
          <div className="space-y-3">
            {items.map((item) => (
              <TimelineCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TimelineCard({ item }) {
  const isMic = item.channel === "mic";
  const skipped = item.skip_reason === "echo" || item.skip_reason === "voice_mismatch";
  const pending = item.text == null && !skipped;
  const emptySkipped = skipped && item.text === "";
  const lowConf = item.confidence != null && item.confidence < -0.5;
  const lowVoice = item.voice_match_score != null && item.voice_match_score < 0.75;

  return (
    <div className="relative pl-10">
      <div className={`absolute left-2.5 top-3 w-3 h-3 rounded-full border-2 border-surface ${
        skipped ? "bg-zinc-700" : pending ? "bg-zinc-600" : lowConf ? "bg-amber-500" : "bg-emerald-500"
      }`} />
      <div className="rounded-xl border border-border bg-panel p-4 hover:border-zinc-600 transition-colors">
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span className="text-xs font-mono text-zinc-500">{item.time}</span>
          <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md ${
            isMic ? "bg-blue-500/10 text-blue-400" : "bg-purple-500/10 text-purple-400"
          }`}>
            {isMic ? <Mic className="w-3 h-3" /> : <Monitor className="w-3 h-3" />}
            {isMic ? "Mikrofon" : "Sistem"}
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-zinc-800 text-zinc-400">{item.speaker}</span>
          {item.skip_reason === "echo" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-orange-500/10 text-orange-400">
              Echo ({((item.echo_score || 0) * 100).toFixed(0)}%)
            </span>
          )}
          {item.skip_reason === "voice_mismatch" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-amber-500/10 text-amber-400">
              Ses eşleşmedi
            </span>
          )}
          {lowVoice && !skipped && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-amber-500/10 text-amber-400">
              Düşük ses skoru
            </span>
          )}
          {item.source_app && (
            <span className="text-[10px] text-zinc-600 truncate max-w-[120px]">{item.source_app}</span>
          )}
          <span className="text-[10px] text-zinc-600 ml-auto">{(item.duration_ms / 1000).toFixed(1)}s</span>
        </div>

        {emptySkipped ? (
          <p className="text-sm text-zinc-500 italic">
            {item.skip_reason === "echo" ? "Echo nedeniyle atlandı" : "Ses profiline uymadı — atlandı"}
          </p>
        ) : pending ? (
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Transcript işleniyor...
          </div>
        ) : (
          <>
            <p className="text-sm text-zinc-200 leading-relaxed">{item.text}</p>
            <div className="flex items-center gap-2 mt-2">
              {lowConf || item.needs_review ? (
                <span className="inline-flex items-center gap-1 text-[10px] text-amber-400">
                  <AlertTriangle className="w-3 h-3" /> Düşük güven ({item.confidence?.toFixed(2)})
                </span>
              ) : item.text ? (
                <span className="inline-flex items-center gap-1 text-[10px] text-emerald-500/80">
                  <CheckCircle2 className="w-3 h-3" /> OK
                </span>
              ) : null}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
