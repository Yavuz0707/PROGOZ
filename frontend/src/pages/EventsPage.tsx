import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import type { IncidentRecord } from "../types";

const tabs = [
  { label: "Tum Olaylar", value: "" },
  { label: "Video Analizleri", value: "video" },
  { label: "Canli Kameralar", value: "camera" }
];

function fmt(seconds?: number) {
  if (seconds === undefined || seconds === null) return "-";
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

export default function EventsPage() {
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [sourceType, setSourceType] = useState("");
  const [severity, setSeverity] = useState("");
  const [minScore, setMinScore] = useState("");

  useEffect(() => {
    unwrap<IncidentRecord[]>(
      api.get("/incidents", { params: { source_type: sourceType || undefined, severity: severity || undefined, min_score: minScore || undefined } })
    ).then(setIncidents).catch(console.error);
  }, [sourceType, severity, minScore]);

  const stats = useMemo(() => ({
    total: incidents.length,
    kavga: incidents.filter((i) => i.severity === "KAVGA").length,
    olasi: incidents.filter((i) => i.severity === "OLASI_KAVGA").length,
    supheli: incidents.filter((i) => i.severity === "SUPHELI").length,
    today: incidents.filter((i) => new Date(i.created_at).toDateString() === new Date().toDateString()).length
  }), [incidents]);

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-white">Olaylar</h2>
        <p className="text-sm text-slate-400">Frame kayitlari yerine gruplanmis incident listesi.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-5">
        {[
          ["Toplam", stats.total],
          ["KAVGA", stats.kavga],
          ["Olasi", stats.olasi],
          ["Supheli", stats.supheli],
          ["Bugun", stats.today]
        ].map(([label, value]) => <div key={label} className="panel p-4"><p className="text-xs text-slate-400">{label}</p><p className="text-2xl font-semibold text-white">{value}</p></div>)}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {tabs.map((tab) => (
          <button key={tab.label} onClick={() => setSourceType(tab.value)} className={`rounded-lg px-4 py-2 text-sm ${sourceType === tab.value ? "bg-cyan-400 text-slate-950" : "border border-line bg-slate-950 text-slate-300"}`}>
            {tab.label}
          </button>
        ))}
        <select className="rounded-lg border border-line bg-slate-950 px-3 py-2 text-sm" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">Tum seviyeler</option>
          <option value="SUPHELI">SUPHELI</option>
          <option value="OLASI_KAVGA">OLASI_KAVGA</option>
          <option value="KAVGA">KAVGA</option>
        </select>
        <input className="rounded-lg border border-line bg-slate-950 px-3 py-2 text-sm" placeholder="Min skor" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
      </div>
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="bg-slate-950/80 text-slate-400">
            <tr><th className="p-3">ID</th><th>Seviye</th><th>Kaynak</th><th>Baslangic</th><th>Sure</th><th>Max</th><th>Ortalama</th><th>Snapshot</th><th>Durum</th><th></th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {incidents.map((incident) => (
              <tr key={incident.id}>
                <td className="p-3">#{incident.id}</td>
                <td><SeverityBadge value={incident.severity} /></td>
                <td>{incident.source_type === "video" ? incident.video_filename || `Video #${incident.analysis_job_id}` : `Kamera #${incident.camera_id}`}</td>
                <td>{incident.source_type === "video" ? `${fmt(incident.start_time_seconds)} - ${fmt(incident.end_time_seconds)}` : new Date(incident.started_at || incident.created_at).toLocaleString("tr-TR")}</td>
                <td>{incident.duration_seconds.toFixed(1)} sn</td>
                <td>{incident.max_score.toFixed(1)}</td>
                <td>{incident.avg_score.toFixed(1)}</td>
                <td>{incident.best_snapshot_url ? <img src={incident.best_snapshot_url} className="h-12 w-20 rounded object-cover" /> : "-"}</td>
                <td className="text-slate-300">{incident.status}</td>
                <td><Link className="text-cyan-300 hover:text-cyan-100" to={`/events/${incident.id}`}>Detay</Link></td>
              </tr>
            ))}
            {incidents.length === 0 && <tr><td colSpan={10} className="p-5 text-slate-400">Filtreye uygun incident yok.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
