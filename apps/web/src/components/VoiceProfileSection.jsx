import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiDelete, apiPatch } from "../api";
import { Mic, Trash2, CheckCircle2, AlertCircle } from "lucide-react";

const ENROLL_SECONDS = 30;
const TEST_SECONDS = 5;

export default function VoiceProfileSection({ settings, onSettingsChange }) {
  const [status, setStatus] = useState(null);
  const [recording, setRecording] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [testScore, setTestScore] = useState(null);
  const [error, setError] = useState(null);
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  const loadStatus = () => {
    apiGet("/voice/status").then(setStatus).catch(() => setStatus(null));
  };

  useEffect(() => { loadStatus(); }, []);

  const startRecording = async (seconds, onDone) => {
    setError(null);
    setTestScore(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRef.current = { stream, recorder };
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        await onDone(blob);
        setRecording(false);
        setCountdown(0);
      };

      recorder.start();
      setRecording(true);
      setCountdown(seconds);
      timerRef.current = setInterval(() => {
        setCountdown((c) => {
          if (c <= 1) {
            clearInterval(timerRef.current);
            recorder.stop();
            return 0;
          }
          return c - 1;
        });
      }, 1000);
    } catch (e) {
      setError("Mikrofon erişimi reddedildi: " + e.message);
    }
  };

  const uploadBlob = async (blob, path) => {
    const form = new FormData();
    form.append("file", blob, "recording.webm");
    const res = await fetch(`http://127.0.0.1:8742/api${path}`, { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  };

  const enroll = () => startRecording(ENROLL_SECONDS, async (blob) => {
    try {
      await uploadBlob(blob, "/voice/enroll");
      loadStatus();
    } catch (e) {
      setError(String(e.message));
    }
  });

  const test = () => startRecording(TEST_SECONDS, async (blob) => {
    try {
      const res = await uploadBlob(blob, "/voice/test");
      setTestScore(res);
    } catch (e) {
      setError(String(e.message));
    }
  });

  const deleteProfile = async () => {
    await apiDelete("/voice/profile");
    loadStatus();
    setTestScore(null);
  };

  const updateFilter = async (field, value) => {
    const updated = await apiPatch("/settings", { [field]: value });
    onSettingsChange?.(updated);
  };

  if (!status) {
    return <p className="text-sm text-zinc-500">Ses profili yükleniyor...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        {status.enrolled ? (
          <span className="inline-flex items-center gap-1 text-sm text-emerald-400">
            <CheckCircle2 className="w-4 h-4" /> Profil kayıtlı ({status.sample_count} örnek)
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-sm text-zinc-500">
            <AlertCircle className="w-4 h-4" /> Henüz kayıt yok
          </span>
        )}
        {!status.model_ready && (
          <span className="text-[10px] text-amber-400">ONNX model yok — spektral fallback kullanılıyor</span>
        )}
      </div>

      {status.enrollment_text ? (
        <blockquote className="text-xs text-zinc-400 italic border-l-2 border-zinc-700 pl-3">
          {status.enrollment_text}
        </blockquote>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={enroll}
          disabled={recording}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium disabled:opacity-50"
        >
          <Mic className="w-3.5 h-3.5" />
          {recording ? `Kaydediliyor ${countdown}s...` : status.enrolled ? "Profili Yenile" : "Sesimi Tanıt (30s)"}
        </button>
        {status.enrolled && (
          <>
            <button
              onClick={test}
              disabled={recording}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border text-zinc-300 text-xs hover:bg-panel-hover disabled:opacity-50"
            >
              Test Et (5s)
            </button>
            <button
              onClick={deleteProfile}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-red-500/30 text-red-400 text-xs hover:bg-red-500/10"
            >
              <Trash2 className="w-3.5 h-3.5" /> Sil
            </button>
          </>
        )}
      </div>

      {testScore && (
        <div className={`text-sm ${testScore.match ? "text-emerald-400" : "text-amber-400"}`}>
          Eşleşme skoru: {(testScore.score * 100).toFixed(0)}% (eşik: {(testScore.threshold * 100).toFixed(0)}%)
          — {testScore.label}
        </div>
      )}

      {error && <p className="text-xs text-red-400">{error}</p>}

      <div className="space-y-2 pt-2 border-t border-border">
        <p className="text-xs text-zinc-500">Mikrofon filtresi</p>
        <div className="flex flex-wrap gap-3">
          {[
            { id: "off", label: "Kapalı" },
            { id: "prefer", label: "Etiketle (Bilinmeyen)" },
            { id: "strict", label: "Sadece benim sesim" },
          ].map((m) => (
            <label key={m.id} className="flex items-center gap-1.5 text-xs text-zinc-300 cursor-pointer">
              <input
                type="radio"
                name="voice_filter"
                checked={(settings?.voice_filter_mode || "off") === m.id}
                onChange={() => updateFilter("voice_filter_mode", m.id)}
              />
              {m.label}
            </label>
          ))}
        </div>
        <div>
          <label className="text-[11px] text-zinc-500">
            Eşik: {((settings?.voice_match_threshold ?? 0.75) * 100).toFixed(0)}%
          </label>
          <input
            type="range"
            min="60"
            max="90"
            value={Math.round((settings?.voice_match_threshold ?? 0.75) * 100)}
            onChange={(e) => updateFilter("voice_match_threshold", Number(e.target.value) / 100)}
            className="w-full mt-1"
          />
        </div>
      </div>
    </div>
  );
}
