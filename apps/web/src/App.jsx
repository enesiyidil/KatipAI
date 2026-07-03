import { Link, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import { useLiveStatus } from "./hooks/useLiveStatus";
import Dashboard from "./pages/Dashboard";
import Timeline from "./pages/Timeline";
import Notes from "./pages/Notes";
import Transcripts from "./pages/Transcripts";
import GeneralNotes from "./pages/GeneralNotes";
import Settings from "./pages/Settings";
import ReviewQueue from "./pages/ReviewQueue";
import Jargon from "./pages/Jargon";

export default function App() {
  const { status, stats } = useLiveStatus();

  return (
    <div className="min-h-screen flex bg-surface text-zinc-100">
      <Sidebar status={status} stats={stats} />
      <main className="flex-1 p-6 lg:p-8 overflow-auto min-h-screen">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/notes" element={<Notes />} />
          <Route path="/transcripts" element={<Transcripts />} />
          <Route path="/general" element={<GeneralNotes />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/jargon" element={<Jargon />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
