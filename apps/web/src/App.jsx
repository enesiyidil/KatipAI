import { Link, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";
import ReviewQueue from "./pages/ReviewQueue";
import Jargon from "./pages/Jargon";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/review", label: "Düzeltme Kuyruğu" },
  { to: "/jargon", label: "Jargon" },
  { to: "/settings", label: "Ayarlar" },
];

export default function App() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-56 border-r border-zinc-800 p-4 flex flex-col gap-2">
        <h1 className="text-xl font-bold text-emerald-400 mb-4">KatipAI</h1>
        {nav.map((n) => (
          <Link key={n.to} to={n.to} className="px-3 py-2 rounded hover:bg-zinc-800 text-sm">
            {n.label}
          </Link>
        ))}
      </aside>
      <main className="flex-1 p-6 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/jargon" element={<Jargon />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
