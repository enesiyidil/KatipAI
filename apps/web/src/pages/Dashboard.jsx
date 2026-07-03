import { useEffect, useState } from "react";
import { useLiveStatus } from "../hooks/useLiveStatus";
import ControlPanel from "../components/ControlPanel";
import { apiGet, STATE_META } from "../api";
import { Radio, Mic, Monitor } from "lucide-react";

const LIMIT = 20;

export default function Dashboard() {
  const { status, stats, refresh, tick } = useLiveStatus();
  const [chunks, setChunks] = useState([]);

  useEffect(() => {
    apiGet("/timeline/today")
      .then((d) =>
        setChunks(
          d.items.filter((i) => i.text?.trim()).slice(0, LIMIT)
        )
      )
      .catch(() => setChunks([]));
  }, [tick]);

  const meta = STATE_META[status?.state] || STATE_META.idle;

  return (
    <div className="space-y-6 max-w-5xl">
      <header>
        <h2 className="text-2xl font-semibold text-zinc-100">Kontrol Paneli</h2>
        <p className="text-sm text-zinc-500 mt-1">Canlı dinleme ve son transcript'ler</p>
      </header>

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
          Son {LIMIT} transcript
        </h3>
        {chunks.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-zinc-500 text-sm">
            Henüz transcript yok. Konuşmaya başla.
          </div>
        ) : (
          <div className="space-y-2">
            {chunks.map((item) => (
              <div
                key={item.id}
                className="rounded-lg border border-border bg-panel px-4 py-3 flex gap-3 items-start"
              >
                <span className="text-xs text-zinc-500 font-mono shrink-0 pt-0.5 w-10">
                  {item.time.slice(0, 5)}
                </span>
                {item.channel === "mic" ? (
                  <Mic className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
                ) : (
                  <Monitor className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                )}
                <p className="text-sm text-zinc-200 leading-relaxed flex-1">{item.text}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
