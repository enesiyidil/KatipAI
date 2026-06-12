import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api";

export default function ReviewQueue() {
  const [items, setItems] = useState([]);
  const [edits, setEdits] = useState({});

  const load = () => apiGet("/chunks/review-queue").then(setItems);
  useEffect(() => { load(); }, []);

  const approve = async (chunkId) => {
    await apiPost(`/chunks/${chunkId}/approve`);
    load();
  };

  const correct = async (transcriptId, chunkId) => {
    const text = edits[transcriptId];
    if (!text) return;
    await apiPost(`/transcripts/${transcriptId}/correct`, { corrected_text: text, approved: true });
    load();
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Düzeltme Kuyruğu</h2>
      <p className="text-zinc-400 text-sm">Düşük güven skorlu transcript'ler — onaylayın veya düzeltin.</p>

      {items.length === 0 ? (
        <p className="text-zinc-500">İncelenecek transcript yok.</p>
      ) : (
        items.map((item) => (
          <div key={item.transcript_id} className="border border-amber-800/50 bg-amber-950/20 rounded-lg p-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-amber-400">Güven: {item.confidence}</span>
              <span className="text-zinc-500">Chunk #{item.chunk_id}</span>
            </div>
            <p>{item.text}</p>
            <p className="text-sm text-zinc-400">Bu doğru mu?</p>
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => approve(item.chunk_id)} className="bg-emerald-700 px-3 py-1 rounded text-sm">
                Evet, doğru
              </button>
              <input
                className="flex-1 min-w-[200px] bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
                placeholder="Düzeltilmiş metin..."
                value={edits[item.transcript_id] || item.text}
                onChange={(e) => setEdits({ ...edits, [item.transcript_id]: e.target.value })}
              />
              <button
                onClick={() => correct(item.transcript_id, item.chunk_id)}
                className="bg-blue-700 px-3 py-1 rounded text-sm"
              >
                Düzelt ve öğren
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
