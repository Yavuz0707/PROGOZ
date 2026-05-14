import { useEffect, useState } from "react";
import { Activity, Camera, Cpu, ShieldAlert } from "lucide-react";
import { api, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { StatCard } from "../components/StatCard";
import type { Camera as CameraType, IncidentRecord, SystemStatus } from "../types";

export default function DashboardPage() {
  const [events, setEvents] = useState<IncidentRecord[]>([]);
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const fightCount = events.filter((e) => e.severity === "KAVGA").length;

  useEffect(() => {
    unwrap<IncidentRecord[]>(api.get("/incidents")).then(setEvents).catch(console.error);
    unwrap<CameraType[]>(api.get("/cameras")).then(setCameras).catch(console.error);
    unwrap<SystemStatus>(api.get("/system/status")).then(setStatus).catch(console.error);
  }, []);

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-white">Dashboard</h2>
        <p className="text-sm text-slate-400">Kamera, analiz ve sistem sagligi ozeti</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={Camera} label="Toplam kamera" value={cameras.length} detail={`${cameras.filter((c) => c.enabled).length} aktif kayit`} />
        <StatCard icon={ShieldAlert} label="Bugunku olay" value={events.length} detail={`${fightCount} KAVGA seviyesi`} />
        <StatCard icon={Cpu} label="CUDA" value={status?.cuda_available ? "Aktif" : "Pasif"} detail={status?.cuda_device || "CPU fallback"} />
        <StatCard icon={Activity} label="Model" value={status?.model || "..."} detail={`Frame skip: ${status?.frame_skip ?? "-"}`} />
      </div>
      <div className="panel overflow-hidden">
        <div className="border-b border-line p-4">
          <h3 className="font-semibold text-white">Son Olaylar</h3>
        </div>
        <div className="divide-y divide-line">
          {events.slice(0, 8).map((event) => (
            <div key={event.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div>
                <p className="font-medium text-white">#{event.id} {event.source_type}</p>
                <p className="text-sm text-slate-400">{new Date(event.created_at).toLocaleString("tr-TR")}</p>
              </div>
              <div className="flex items-center gap-3">
                <SeverityBadge value={event.severity} />
                <span className="text-sm text-slate-300">{event.max_score.toFixed(1)}</span>
              </div>
            </div>
          ))}
          {events.length === 0 && <p className="p-4 text-sm text-slate-400">Henuz olay kaydi yok.</p>}
        </div>
      </div>
    </section>
  );
}
