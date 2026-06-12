import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../api";

export default function Jargon() {
  const [items, setItems] = useState([]);
  const [term, setTerm] = useState("");
  const [aliases, setAliases] = useState("");

  const load = () => apiGet("/jargon").then(setItems);
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!term.trim()) return;
    await apiPost("/jargon", { term, aliases: aliases || null });
    setTerm("");
    setAliases("");
    load();
  };

  const remove = async (id) => {
    await apiDelete(`/jargon/${id}`);
    load();
  };

  return (
    <div className="max-w-xl space-y-4">
      <h2 className="text-2xl font-semibold">Jargon Sözlüğü</h2>
      <p className="text-zinc-400 text-sm">Proje adları, kısaltmalar — STT ve LLM'e enjekte edilir.</p>

      <div className="flex gap-2">
        <input
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2"
          placeholder="Terim"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
        />
        <input
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2"
          placeholder="Alternatifler (virgülle)"
          value={aliases}
          onChange={(e) => setAliases(e.target.value)}
        />
        <button onClick={add} className="bg-emerald-600 px-4 rounded text-sm">Ekle</button>
      </div>

      <ul className="space-y-2">
        {items.map((j) => (
          <li key={j.id} className="flex justify-between border border-zinc-800 rounded px-3 py-2">
            <span>
              <strong>{j.term}</strong>
              {j.aliases && <span className="text-zinc-400 text-sm ml-2">({j.aliases})</span>}
            </span>
            <button onClick={() => remove(j.id)} className="text-red-400 text-sm">Sil</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
