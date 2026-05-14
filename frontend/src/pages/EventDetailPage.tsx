import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import type { IncidentRecord } from "../types";

function fmt(seconds?: number) {
  if (seconds === undefined || seconds === null) return "-";
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

export default function EventDetailPage() {
  const { id } = useParams();
  const [incident, setIncident] = useState<IncidentRecord | null>(null);

  useEffect(() => {
    if (id) unwrap<IncidentRecord>(api.get(`/incidents/${id}`)).then(setIncident).catch(console.error);
  }, [id]);

  async function mark(status: "confirmed" | "false_positive" | "ignored") {
    if (!incident) return;
    const updated = await unwrap<IncidentRecord>(api.put(`/incidents/${incident.id}/status`, { status }));
    setIncident(updated);
  }

  if (!incident) return <p className="text-slate-300">Yukleniyor...</p>;

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-semibold text-white">Incident #{incident.id}</h2>
          <SeverityBadge value={incident.severity} />
        </div>
        <div className="flex gap-2">
          <button onClick={() => mark("confirmed")} className="rounded-lg border border-line px-3 py-2 text-sm">Dogru olay</button>
          <button onClick={() => mark("false_positive")} className="rounded-lg border border-red-400/50 px-3 py-2 text-sm text-red-200">Yanlis alarm</button>
          <button onClick={() => mark("ignored")} className="rounded-lg border border-line px-3 py-2 text-sm">Yoksay</button>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="panel overflow-hidden">{incident.best_snapshot_url ? <img src={incident.best_snapshot_url} className="w-full object-contain" /> : <div className="p-6 text-slate-400">Snapshot yok</div>}</div>
        <div className="panel p-4">
          <dl className="space-y-3 text-sm">
            <div><dt className="text-slate-400">Kaynak</dt><dd>{incident.source_type === "video" ? incident.video_filename : `Kamera #${incident.camera_id}`}</dd></div>
            <div><dt className="text-slate-400">Zaman</dt><dd>{incident.source_type === "video" ? `${fmt(incident.start_time_seconds)} - ${fmt(incident.end_time_seconds)}` : `${new Date(incident.started_at || incident.created_at).toLocaleString("tr-TR")} - ${incident.ended_at ? new Date(incident.ended_at).toLocaleString("tr-TR") : "-"}`}</dd></div>
            <div><dt className="text-slate-400">Sure</dt><dd>{incident.duration_seconds.toFixed(1)} sn</dd></div>
            <div><dt className="text-slate-400">Max / Ortalama Skor</dt><dd className="text-xl font-semibold text-white">{incident.max_score.toFixed(1)} / {incident.avg_score.toFixed(1)}</dd></div>
            <div><dt className="text-slate-400">Kisi ID</dt><dd>{incident.involved_track_ids.join(", ") || "-"}</dd></div>
            <div><dt className="text-slate-400">Durum</dt><dd>{incident.status}</dd></div>
          </dl>
        </div>
      </div>
      <div className="panel p-4">
        <h3 className="mb-3 font-semibold text-white">Skor Timeline</h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={incident.score_timeline}>
              <XAxis dataKey="t" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <ReferenceLine y={35} stroke="#eab308" strokeDasharray="4 4" />
              <ReferenceLine y={55} stroke="#f97316" strokeDasharray="4 4" />
              <ReferenceLine y={75} stroke="#ef4444" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="score" stroke="#22d3ee" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}
