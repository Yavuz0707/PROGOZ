import { useEffect, useMemo, useState } from "react";
import { Activity, Camera, Cpu, ShieldAlert, RectangleEllipsis, ArrowUp, ArrowDown, Minus } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, assetUrl, unwrap } from "../api/client";
import { getPlates, getPlateStats } from "../api/plates";
import { SeverityBadge } from "../components/SeverityBadge";
import type { Camera as CameraType, IncidentRecord, PlateRecord, PlateStats, SystemStatus } from "../types";

function fmtDate(iso?: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent = false,
  trend,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
  trend?: "up" | "down" | "flat";
}) {
  return (
    <div className="panel p-5 flex items-start gap-4">
      <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${accent ? "bg-cyan-400/20 text-cyan-300" : "bg-slate-800 text-slate-400"}`}>
        <Icon size={20} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-slate-400">{label}</p>
        <p className="mt-0.5 text-2xl font-bold text-white leading-tight">{value}</p>
        {sub && (
          <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-500">
            {trend === "up" && <ArrowUp size={10} className="text-emerald-400" />}
            {trend === "down" && <ArrowDown size={10} className="text-red-400" />}
            {trend === "flat" && <Minus size={10} className="text-slate-500" />}
            {sub}
          </p>
        )}
      </div>
    </div>
  );
}

const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => `${i}:00`);

export default function DashboardPage() {
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [recentPlates, setRecentPlates] = useState<PlateRecord[]>([]);
  const [plateStats, setPlateStats] = useState<PlateStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      unwrap<IncidentRecord[]>(api.get("/incidents")),
      unwrap<CameraType[]>(api.get("/cameras")),
      unwrap<SystemStatus>(api.get("/system/status")),
    ]).then(([incs, cams, sys]) => {
      setIncidents(incs);
      setCameras(cams);
      setStatus(sys);
    }).catch(console.error);

    // Plates (separate, non-blocking)
    Promise.all([
      getPlates({ show_unreadable: false }),
      getPlateStats(),
    ]).then(([ps, pst]) => {
      setRecentPlates(ps.slice(0, 5));
      setPlateStats(pst);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  // ——— Derived stats ———
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();

  const todayIncidents = useMemo(
    () => incidents.filter((i) => new Date(i.created_at).toDateString() === today),
    [incidents, today]
  );
  const yesterdayIncidents = useMemo(
    () => incidents.filter((i) => new Date(i.created_at).toDateString() === yesterday),
    [incidents, yesterday]
  );
  const todayTrend: "up" | "down" | "flat" =
    todayIncidents.length > yesterdayIncidents.length ? "up"
    : todayIncidents.length < yesterdayIncidents.length ? "down"
    : "flat";
  const trendDiff = todayIncidents.length - yesterdayIncidents.length;
  const trendLabel =
    trendDiff === 0 ? "dünle aynı"
    : trendDiff > 0 ? `dünden ${trendDiff} fazla`
    : `dünden ${Math.abs(trendDiff)} az`;

  const activeCameras = cameras.filter((c) => c.enabled);

  // Hourly event chart (last 24h)
  const hourlyData = useMemo(() => {
    const yesterday24 = new Date(Date.now() - 24 * 3600000);
    const hours = Array.from({ length: 24 }, (_, h) => ({
      hour: HOUR_LABELS[h],
      kavga: 0,
      supheli: 0,
    }));
    for (const inc of incidents) {
      const d = new Date(inc.created_at);
      if (d >= yesterday24) {
        const h = d.getHours();
        if (inc.severity === "KAVGA" || inc.severity === "OLASI_KAVGA") hours[h].kavga++;
        else if (inc.severity === "SUPHELI") hours[h].supheli++;
      }
    }
    return hours;
  }, [incidents]);

  const recentIncidents = useMemo(
    () => [...incidents].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5),
    [incidents]
  );

  if (loading && incidents.length === 0) {
    return (
      <section className="space-y-5 animate-pulse">
        <div>
          <div className="h-7 w-40 rounded bg-slate-800 mb-2" />
          <div className="h-4 w-64 rounded bg-slate-900" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="panel p-5 h-24 bg-slate-900" />
          ))}
        </div>
        <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
          <div className="panel h-64 bg-slate-900" />
          <div className="panel h-64 bg-slate-900" />
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-white">Dashboard</h2>
        <p className="text-sm text-slate-400">Kamera, analiz ve sistem sağlığı özeti</p>
      </div>

      {/* ——— ROW 1: 4 Stat Cards ——— */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={Camera}
          label="Aktif Kameralar"
          value={activeCameras.length}
          sub={`Toplam ${cameras.length} kamera`}
          accent={activeCameras.length > 0}
        />
        <StatCard
          icon={ShieldAlert}
          label="Bugünkü Olaylar"
          value={todayIncidents.length}
          sub={trendLabel}
          trend={todayTrend}
          accent={todayIncidents.length > 0}
        />
        <StatCard
          icon={RectangleEllipsis}
          label="Bugün Tespit Edilen Plaka"
          value={plateStats?.today ?? "-"}
          sub={plateStats ? `Toplam ${plateStats.total} benzersiz` : undefined}
        />
        <div className="panel p-5 flex items-start gap-4">
          <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${status?.cuda_available ? "bg-cyan-400/20 text-cyan-300" : "bg-slate-800 text-slate-400"}`}>
            <Cpu size={20} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs text-slate-400">Sistem Durumu</p>
            <p className="mt-0.5 text-sm font-bold text-white">
              {status ? (status.cuda_available ? "CUDA Aktif" : "CPU Modu") : "..."}
            </p>
            <div className="mt-1 space-y-0.5 text-xs text-slate-500">
              {status?.device_name && <p className="truncate">{status.device_name}</p>}
              <p>{status?.model || "-"} · skip:{status?.frame_skip ?? "-"}</p>
              <p className="flex items-center gap-1">
                <span className={`h-1.5 w-1.5 rounded-full ${status ? "bg-emerald-400" : "bg-slate-600"}`} />
                {status ? "Model yüklü" : "Yükleniyor"}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ——— ROW 2: Chart + Recent Events ——— */}
      <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        {/* Hourly Event Chart */}
        <div className="panel p-4">
          <h3 className="mb-4 font-semibold text-white flex items-center gap-2">
            <Activity size={16} className="text-cyan-400" />
            Son 24 Saat Olay Dağılımı
          </h3>
          <div className="h-52">
            {hourlyData.some((d) => d.kavga > 0 || d.supheli > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourlyData} barGap={2}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis
                    dataKey="hour"
                    tick={{ fill: "#64748b", fontSize: 10 }}
                    tickFormatter={(v: string) => v.replace(":00", "")}
                    interval={3}
                  />
                  <YAxis tick={{ fill: "#64748b", fontSize: 10 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                    cursor={{ fill: "#1e293b" }}
                  />
                  <Bar dataKey="kavga" name="Kavga/Olası" stackId="a" radius={[0, 0, 0, 0]}>
                    {hourlyData.map((_, i) => (
                      <Cell key={i} fill="#ef4444" fillOpacity={0.8} />
                    ))}
                  </Bar>
                  <Bar dataKey="supheli" name="Şüpheli" stackId="a" radius={[3, 3, 0, 0]}>
                    {hourlyData.map((_, i) => (
                      <Cell key={i} fill="#eab308" fillOpacity={0.6} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-600">
                Son 24 saatte olay kaydı yok
              </div>
            )}
          </div>
          <div className="mt-2 flex gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-red-500" /> Kavga / Olası Kavga</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-yellow-500/60" /> Şüpheli</span>
          </div>
        </div>

        {/* Recent Events */}
        <div className="panel overflow-hidden flex flex-col">
          <div className="flex items-center justify-between border-b border-line p-4">
            <h3 className="font-semibold text-white">Son Olaylar</h3>
            <Link to="/events" className="text-xs text-cyan-300 hover:text-cyan-100">Tümünü gör →</Link>
          </div>
          <div className="flex-1 divide-y divide-line overflow-auto">
            {recentIncidents.length > 0 ? recentIncidents.map((inc) => (
              <Link
                key={inc.id}
                to={`/events/${inc.id}`}
                className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-slate-800/50 transition"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {inc.source_type === "video"
                      ? (inc.video_filename || `Video #${inc.analysis_job_id}`)
                      : (cameras.find((c) => c.id === inc.camera_id)?.name || `Kamera #${inc.camera_id}`)}
                  </p>
                  <p className="text-xs text-slate-500">{fmtDate(inc.created_at)}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <SeverityBadge value={inc.severity} />
                  <span className="text-sm text-slate-400 tabular-nums">{inc.max_score.toFixed(0)}</span>
                </div>
              </Link>
            )) : (
              <p className="p-6 text-center text-sm text-slate-500">Henüz olay kaydı yok</p>
            )}
          </div>
        </div>
      </div>

      {/* ——— ROW 3: Camera Status + Recent Plates ——— */}
      <div className="grid gap-4 xl:grid-cols-2">
        {/* Camera Status */}
        <div className="panel overflow-hidden flex flex-col">
          <div className="flex items-center justify-between border-b border-line p-4">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <Camera size={15} className="text-slate-400" /> Kamera Durumları
            </h3>
            <Link to="/cameras" className="text-xs text-cyan-300 hover:text-cyan-100">Yönet →</Link>
          </div>
          <div className="flex-1 divide-y divide-line overflow-auto">
            {cameras.length > 0 ? cameras.map((cam) => (
              <div key={cam.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${cam.enabled ? "bg-emerald-400 shadow-[0_0_6px_#34d399]" : "bg-slate-600"}`} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white truncate">{cam.name}</p>
                    <p className="text-xs text-slate-500 truncate">{cam.location || cam.rtsp_url || cam.source_type}</p>
                  </div>
                </div>
                <div className="shrink-0 text-right text-xs text-slate-500">
                  <p className={cam.enabled ? "text-emerald-400 font-medium" : "text-slate-600"}>
                    {cam.enabled ? "Aktif" : "Pasif"}
                  </p>
                  <p>{fmtDate(cam.updated_at)}</p>
                </div>
              </div>
            )) : (
              <div className="p-6 text-center">
                <p className="text-sm text-slate-500">Kamera tanımlı değil</p>
                <Link to="/cameras" className="mt-1 text-xs text-cyan-300 hover:text-cyan-100">Kamera ekle →</Link>
              </div>
            )}
          </div>
        </div>

        {/* Recent Plates */}
        <div className="panel overflow-hidden flex flex-col">
          <div className="flex items-center justify-between border-b border-line p-4">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <RectangleEllipsis size={15} className="text-slate-400" /> Son Tespit Edilen Plakalar
            </h3>
            <Link to="/plates" className="text-xs text-cyan-300 hover:text-cyan-100">Tümünü gör →</Link>
          </div>
          <div className="flex-1 divide-y divide-line overflow-auto">
            {recentPlates.length > 0 ? recentPlates.map((p) => (
              <div key={p.id} className="flex items-center gap-3 px-4 py-3">
                {(p.crop_url || p.best_snapshot_url) && (
                  <img
                    src={assetUrl(p.crop_url || p.best_snapshot_url)}
                    className="h-9 w-14 shrink-0 rounded object-cover"
                    alt=""
                  />
                )}
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-sm font-bold text-white">{p.plate_text_normalized || p.plate_text_raw}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {p.source_type === "video"
                      ? (p.video_filename || `Video #${p.analysis_job_id}`)
                      : (cameras.find((c) => c.id === p.camera_id)?.name || p.camera_name || `Kamera #${p.camera_id}`)}
                  </p>
                </div>
                <div className="shrink-0 text-right text-xs text-slate-500">
                  <p className={p.confidence >= 0.8 ? "text-emerald-400 font-semibold" : p.confidence >= 0.5 ? "text-yellow-300" : "text-red-400"}>
                    %{Math.round(p.confidence * 100)}
                  </p>
                  <p>{fmtDate(p.last_seen_at || p.created_at)}</p>
                </div>
              </div>
            )) : (
              <div className="p-6 text-center">
                <p className="text-sm text-slate-500">Plaka tespit edilmedi</p>
                <Link to="/upload" className="mt-1 text-xs text-cyan-300 hover:text-cyan-100">Video analiz et →</Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
