import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../api";
import { Plus, Trash2, Tag } from "lucide-react";

export default function Jargon() {
  const [items, setItems] = useState([]);
  const [term, setTerm] = useState("");
  const [aliases, setAliases] = useState("");

  const load = () => apiGet("/jargon").then(setItems);
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!term.trim()) return;
    await apiPost("/jargon", { term, aliases: aliases || null });
    setTerm(""); setAliases("");
    load();
  };

  return (
    <div className="max-w-xl space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-zinc-100">Jargon Sözlüğü</h2>
        <p className="text-sm text-zinc-500 mt-1">Proje adları, kısaltmalar — STT ve LLM'e enjekte edilir</p>
      </header>

      <div className="rounded-xl border border-border bg-panel p-4 space-y-3">
        <div className="flex gap-2">
          <input
            className="flex-1 bg-surface border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500/50"
            placeholder="Terim (örn. KatipAI)"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <input
            className="flex-1 bg-surface border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500/50"
            placeholder="Alternatifler (virgülle)"
            value={aliases}
            onChange={(e) => setAliases(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <button onClick={add} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium inline-flex items-center gap-1">
            <Plus className="w-4 h-4" /> Ekle
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-zinc-500 text-center py-8">Henüz jargon eklenmemiş.</p>
      ) : (
        <div className="space-y-2">
          {items.map((j) => (
            <div key={j.id} className="flex items-center gap-3 rounded-lg border border-border bg-panel px-4 py-3 group">
              <Tag className="w-4 h-4 text-emerald-500/60 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-zinc-200">{j.term}</p>
                {j.aliases && <p className="text-xs text-zinc-500">{j.aliases}</p>}
              </div>
              <button
                onClick={() => apiDelete(`/jargon/${j.id}`).then(load)}
                className="p-1.5 rounded-md text-zinc-600 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
