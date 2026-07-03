import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, FileText, Sparkles, BookMarked,
  AlertCircle, Settings, Mic, Tags,
} from "lucide-react";
import { STATE_META, MODE_LABELS } from "../api";

const links = [
  { to: "/", icon: LayoutDashboard, label: "Kontrol Paneli" },
  { to: "/timeline", icon: Mic, label: "Canlı Akış" },
  { to: "/notes", icon: Sparkles, label: "AI Notları" },
  { to: "/transcripts", icon: FileText, label: "Transcript" },
  { to: "/general", icon: BookMarked, label: "Genel Notlar" },
  { to: "/review", icon: AlertCircle, label: "Düzeltme" },
  { to: "/jargon", icon: Tags, label: "Jargon" },
  { to: "/settings", icon: Settings, label: "Ayarlar" },
];

export default function Sidebar({ status, stats }) {
  const meta = STATE_META[status?.state] || STATE_META.idle;

  return (
    <aside className="w-60 shrink-0 border-r border-border bg-panel flex flex-col h-screen sticky top-0">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
            <Mic className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <h1 className="font-semibold text-zinc-100 tracking-tight">KatipAI</h1>
            <p className="text-[11px] text-zinc-500">Lokal not asistanı</p>
          </div>
        </div>
      </div>

      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg bg-surface/80">
          <span className={`w-2.5 h-2.5 rounded-full ${meta.color} ${meta.pulse ? "animate-pulse-dot" : ""}`} />
          <div className="min-w-0">
            <p className={`text-sm font-medium ${meta.text}`}>{meta.label}</p>
            <p className="text-[11px] text-zinc-500 truncate">
              Mod: {MODE_LABELS[status?.mode] || status?.mode || "Normal"}
            </p>
          </div>
        </div>
        {stats && (
          <div className="grid grid-cols-3 gap-1 mt-2 text-center">
            {[
              { v: stats.chunks, l: "Chunk" },
              { v: stats.transcripts, l: "Transcript" },
              { v: stats.review_pending, l: "İnceleme" },
            ].map((s) => (
              <div key={s.l} className="py-1.5 rounded-md bg-surface/50">
                <p className="text-sm font-semibold text-zinc-200">{s.v}</p>
                <p className="text-[10px] text-zinc-500">{s.l}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-emerald-500/10 text-emerald-400 font-medium"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-panel-hover"
              }`
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
            {label === "Düzeltme" && stats?.review_pending > 0 && (
              <span className="ml-auto text-[10px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full">
                {stats.review_pending}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-border text-[11px] text-zinc-600">
        Tüm veri lokal · Obsidian sync
      </div>
    </aside>
  );
}
