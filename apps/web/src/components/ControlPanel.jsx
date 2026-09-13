import { apiPost, MODES } from "../api";
import { Pause, Play, Mic, Trash2, Users, Square, Radio, AlertTriangle } from "lucide-react";

const MODE_ICONS = { normal: Mic, meeting: Users };

export default function ControlPanel({ status, onAction }) {
  const state = status?.state || "idle";
  const mode = status?.mode || "normal";
  const running = state !== "idle";
  const paused = state === "paused";
  const sensitive = false;
  const busy = state === "processing";
  const recording = state === "recording";
  const captureWarning = status?.capture_warning;
  const micHint = status?.mic_hint;
  const micLevel = status?.mic_activity?.level ?? 0;
  const micSpeaking = status?.mic_activity?.speaking;

  const act = async (fn) => {
    await fn();
    onAction?.();
  };

  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <h3 className="text-sm font-medium text-zinc-300 mb-3">Hızlı Kontroller</h3>

      {captureWarning && (
        <div className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <p>{captureWarning}</p>
        </div>
      )}

      {status?.running && status?.mic_activity?.active && (
        <div className="mb-4 rounded-lg border border-border bg-zinc-900/50 px-3 py-2">
          <div className="flex items-center justify-between text-[11px] text-zinc-400 mb-1.5">
            <span>Mikrofon seviyesi</span>
            <span className={micSpeaking ? "text-emerald-400" : "text-zinc-500"}>
              {micSpeaking ? "Konuşma algılandı" : "Sessiz"}
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div
              className={`h-full transition-all duration-150 ${micSpeaking ? "bg-emerald-500" : "bg-zinc-600"}`}
              style={{ width: `${Math.min(100, micLevel * 800)}%` }}
            />
          </div>
          {micHint && (
            <p className="mt-2 text-[10px] text-amber-300/90 leading-relaxed">{micHint}</p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        {!running && (
          <Btn
            icon={Radio}
            label="Dinlemeyi Başlat"
            onClick={() => act(() => apiPost("/start"))}
            accent
          />
        )}

        {running && paused && (
          <Btn
            icon={Play}
            label="Devam Et"
            onClick={() => act(() => apiPost("/resume"))}
            accent
          />
        )}

        {running && !paused && !sensitive && !busy && (
          <Btn
            icon={Pause}
            label="Duraklat"
            onClick={() => act(() => apiPost("/pause"))}
          />
        )}

        {running && sensitive && (
          <Btn
            icon={Mic}
            label="Normal Moda Dön"
            onClick={() => act(() => apiPost("/mode/normal"))}
            accent
          />
        )}

        {running && (
          <Btn
            icon={Square}
            label="Dinlemeyi Durdur"
            onClick={() => act(() => apiPost("/stop"))}
            danger
          />
        )}

        <Btn
          icon={Mic}
          label="Manuel Kayıt"
          onClick={() => act(() => apiPost("/manual-record"))}
          disabled={!running || busy || recording || sensitive || paused}
        />
        <Btn
          icon={Trash2}
          label="Son Chunk Sil"
          onClick={() => act(() => apiPost("/delete-last-chunk"))}
          danger
        />
      </div>

      <p className="text-[11px] text-zinc-500 mb-2">Kayıt modu</p>
      <div className="grid grid-cols-2 gap-2">
        {MODES.map((m) => {
          const Icon = MODE_ICONS[m.id];
          const active = mode === m.id;
          return (
            <button
              key={m.id}
              onClick={() => act(() => apiPost(`/mode/${m.id}`))}
              className={`flex items-start gap-2 p-2.5 rounded-lg border text-left transition-all ${
                active
                  ? "border-emerald-500/40 bg-emerald-500/10"
                  : "border-border hover:border-zinc-600 hover:bg-panel-hover"
              }`}
            >
              <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${active ? "text-emerald-400" : "text-zinc-500"}`} />
              <div>
                <p className={`text-xs font-medium ${active ? "text-emerald-300" : "text-zinc-300"}`}>{m.label}</p>
                <p className="text-[10px] text-zinc-500">{m.desc}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Btn({ icon: Icon, label, onClick, accent, danger, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
        accent ? "bg-emerald-600 hover:bg-emerald-500 text-white"
        : danger ? "border border-red-500/30 text-red-400 hover:bg-red-500/10"
        : "border border-border text-zinc-300 hover:bg-panel-hover"
      }`}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </button>
  );
}
