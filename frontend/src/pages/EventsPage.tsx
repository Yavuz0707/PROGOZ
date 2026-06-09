import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, Film, AlertTriangle, Clock, TrendingUp } from "lucide-react";
import { api, assetUrl, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import type { Camera as CameraType, IncidentRecord } from "../types";

type SourceItem = {
  key: string;
  label: string;
  type: "video" | "camera";
  count: number;
  kavgaCount: number;
  lastAt: string;
  cameraId?: number;
  jobId?: number;
};

const SEVERITY_FILTERS = [
  { label: "TÜMÜ", value: "" },
  { label: "KAVGA", value: "KAVGA" },
  { label: "OLASI KAVGA", value: "OLASI_KAVGA" },
  { label: "ŞÜPHELİ", value: "SUPHELI" },
];

function fmtTime(seconds?: number | null) {
  if (seconds == null) return "-";
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toFixed(0).padStart(2, "0");
  return `${m}:${s}`;
}

function fmtDate(iso?: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function buildSources(incidents: IncidentRecord[], cameras: CameraType[]): SourceItem[] {
  const map = new Map<string, SourceItem>();
  for (const inc of incidents) {
    if (inc.source_type === "video") {
      const key = `video_${inc.analysis_job_id}`;
      if (!map.has(key)) {
        map.set(key, {
          key, type: "video",
          label: inc.video_filename || `Video #${inc.analysis_job_id}`,
          count: 0, kavgaCount: 0, lastAt: inc.created_at,
          jobId: inc.analysis_job_id ?? undefined,
        });
      }
      const s = map.get(key)!;
      s.count++;
      if (inc.severity === "KAVGA") s.kavgaCount++;
      if (inc.created_at > s.lastAt) s.lastAt = inc.created_at;
    } else {
      const key = `camera_${inc.camera_id}`;
      const cam = cameras.find((c) => c.id === inc.camera_id);
      if (!map.has(key)) {
        map.set(key, {
          key, type: "camera",
          label: cam?.name || `Kamera #${inc.camera_id}`,
          count: 0, kavgaCount: 0, lastAt: inc.created_at,
          cameraId: inc.camera_id ?? undefined,
        });
      }
      const s = map.get(key)!;
      s.count++;
      if (inc.severity === "KAVGA") s.kavgaCount++;
      if (inc.created_at > s.lastAt) s.lastAt = inc.created_at;
    }
  }
  return [...map.values()].sort((a, b) => b.lastAt.localeCompare(a.lastAt));
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-line bg-slate-900 p-4 animate-pulse space-y-2">
      <div className="h-3 w-3/4 rounded bg-slate-700" />
      <div className="h-3 w-1/2 rounded bg-slate-800" />
    </div>
  );
}

export default function EventsPage() {
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKey, setSelectedKey] = useState<string>("__all__");
  const [sourceTab, setSourceTab] = useState<"video" | "camera">("video");
  const [severityFilter, setSeverityFilter] = useState("");

  useEffect(() => {
    Promise.all([
      unwrap<IncidentRecord[]>(api.get("/incidents")),
      unwrap<CameraType[]>(api.get("/cameras")),
    ]).then(([incs, cams]) => {
      setIncidents(incs);
      setCameras(cams);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const allSources = useMemo(() => buildSources(incidents, cameras), [incidents, cameras]);
  const videoSources = useMemo(() => allSources.filter((s) => s.type === "video"), [allSources]);
  const cameraSources = useMemo(() => allSources.filter((s) => s.type === "camera"), [allSources]);
  const currentSources = sourceTab === "video" ? videoSources : cameraSources;

  const filteredIncidents = useMemo(() => {
    let list = incidents;
    if (selectedKey !== "__all__") {
      if (selectedKey.startsWith("video_")) {
        const jobId = Number(selectedKey.replace("video_", ""));
        list = list.filter((i) => i.analysis_job_id === jobId);
      } else if (selectedKey.startsWith("camera_")) {
        const camId = Number(selectedKey.replace("camera_", ""));
        list = list.filter((i) => i.camera_id === camId);
      }
    }
    if (severityFilter) list = list.filter((i) => i.severity === severityFilter);
    return [...list].sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [incidents, selectedKey, severityFilter]);

  const stats = useMemo(() => {
    const today = new Date().toDateString();
    const weekAgo = new Date(Date.now() - 7 * 86400000);
    return {
      today: incidents.filter((i) => new Date(i.created_at).toDateString() === today).length,
      week: incidents.filter((i) => new Date(i.created_at) >= weekAgo).length,
      kavga: incidents.filter((i) => i.severity === "KAVGA").length,
      peakHour: (() => {
        const counts: Record<number, number> = {};
        incidents.forEach((i) => {
          const h = new Date(i.created_at).getHours();
          counts[h] = (counts[h] || 0) + 1;
        });
        const peak = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
        return peak ? `${peak[0]}:00` : "-";
      })(),
    };
  }, [incidents]);

  return (
    <section className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">Olaylar</h2>
          <p className="text-sm text-slate-400">Kaynağa göre gruplandırılmış olay kayıtları</p>
        </div>
        {/* Stats Top-Right */}
        <div className="hidden xl:flex items-center gap-4 text-sm">
          <div className="text-center">
            <p className="text-slate-400 text-xs">Bugün</p>
            <p className="text-white font-semibold">{stats.today}</p>
          </div>
          <div className="text-center">
            <p className="text-slate-400 text-xs">Bu hafta</p>
            <p className="text-white font-semibold">{stats.week}</p>
          </div>
          <div className="text-center">
            <p className="text-slate-400 text-xs">En aktif saat</p>
            <p className="text-cyan-300 font-semibold">{stats.peakHour}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        {/* LEFT PANEL — Source List */}
        <aside className="space-y-2">
          {/* Tab: Kameralar / Videolar */}
          <div className="flex rounded-lg overflow-hidden border border-line">
            <button
              onClick={() => { setSourceTab("video"); setSelectedKey("__all__"); }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-sm transition ${sourceTab === "video" ? "bg-cyan-400 text-slate-950 font-semibold" : "bg-slate-950 text-slate-400 hover:text-slate-200"}`}
            >
              <Film size={14} /> Videolar
            </button>
            <button
              onClick={() => { setSourceTab("camera"); setSelectedKey("__all__"); }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-sm transition ${sourceTab === "camera" ? "bg-cyan-400 text-slate-950 font-semibold" : "bg-slate-950 text-slate-400 hover:text-slate-200"}`}
            >
              <Camera size={14} /> Kameralar
            </button>
          </div>

          {/* All sources option */}
          <button
            onClick={() => setSelectedKey("__all__")}
            className={`w-full rounded-xl border px-3 py-2.5 text-left text-sm transition ${selectedKey === "__all__" ? "border-cyan-400/60 bg-cyan-400/10 text-white" : "border-line bg-slate-900 text-slate-300 hover:border-slate-600"}`}
          >
            <span className="font-medium">Tüm Kaynaklar</span>
            <span className="ml-2 rounded-full bg-slate-700 px-1.5 py-0.5 text-xs">{incidents.length}</span>
          </button>

          {loading ? (
            Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
          ) : currentSources.length === 0 ? (
            <p className="rounded-xl border border-line bg-slate-900 p-4 text-sm text-slate-500 text-center">
              {sourceTab === "video" ? "Video analizi yok" : "Kamera kaydı yok"}
            </p>
          ) : (
            currentSources.map((src) => (
              <button
                key={src.key}
                onClick={() => setSelectedKey(src.key)}
                className={`w-full rounded-xl border px-3 py-2.5 text-left transition ${selectedKey === src.key ? "border-cyan-400/60 bg-cyan-400/10" : "border-line bg-slate-900 hover:border-slate-600"}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className={`text-sm font-medium truncate ${selectedKey === src.key ? "text-white" : "text-slate-200"}`}>
                    {src.label}
                  </p>
                  {src.kavgaCount > 0 && (
                    <span className="shrink-0 rounded-full bg-red-500/20 px-1.5 py-0.5 text-xs text-red-300">
                      {src.kavgaCount} KAVGA
                    </span>
                  )}
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                  <span>{src.count} olay</span>
                  <span>·</span>
                  <span>{fmtDate(src.lastAt)}</span>
                </div>
              </button>
            ))
          )}
        </aside>

        {/* RIGHT PANEL — Incident Cards */}
        <div className="space-y-3">
          {/* Filters */}
          <div className="flex flex-wrap gap-2">
            {SEVERITY_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setSeverityFilter(f.value)}
                className={`rounded-lg px-3 py-1.5 text-sm transition ${severityFilter === f.value ? "bg-cyan-400 text-slate-950 font-semibold" : "border border-line bg-slate-900 text-slate-300 hover:border-slate-500"}`}
              >
                {f.label}
              </button>
            ))}
            <span className="ml-auto text-sm text-slate-500 self-center">
              {filteredIncidents.length} olay
            </span>
          </div>

          {/* Incident Cards */}
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-line bg-slate-900 p-4 animate-pulse flex gap-4">
                <div className="h-20 w-28 rounded-lg bg-slate-700 shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-1/3 rounded bg-slate-700" />
                  <div className="h-3 w-2/3 rounded bg-slate-800" />
                  <div className="h-3 w-1/4 rounded bg-slate-800" />
                </div>
              </div>
            ))
          ) : filteredIncidents.length === 0 ? (
            <div className="rounded-xl border border-line bg-slate-900 p-10 text-center">
              <AlertTriangle size={32} className="mx-auto mb-3 text-slate-600" />
              <p className="text-slate-400">Filtreye uygun olay bulunamadı</p>
              <p className="text-sm text-slate-600 mt-1">Farklı bir kaynak veya seviye seçin</p>
            </div>
          ) : (
            filteredIncidents.map((inc) => (
              <div key={inc.id} className="rounded-xl border border-line bg-slate-900 p-4 flex gap-4 hover:border-slate-600 transition">
                {/* Snapshot */}
                <div className="shrink-0 w-28 h-20 rounded-lg overflow-hidden bg-slate-800 flex items-center justify-center">
                  {inc.best_snapshot_url ? (
                    <img src={assetUrl(inc.best_snapshot_url)} className="w-full h-full object-cover" alt="snapshot" />
                  ) : (
                    <AlertTriangle size={20} className="text-slate-600" />
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <SeverityBadge value={inc.severity} />
                    <span className="text-sm font-semibold text-white">
                      Skor: {inc.max_score.toFixed(0)}
                    </span>
                    {inc.best_snapshot_score && (
                      <span className="text-xs text-slate-500">peak: {inc.best_snapshot_score.toFixed(0)}</span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 text-xs text-slate-400 flex-wrap">
                    <span className="flex items-center gap-1">
                      <Clock size={11} />
                      {inc.source_type === "video"
                        ? `${fmtTime(inc.start_time_seconds)} – ${fmtTime(inc.end_time_seconds)} (${inc.duration_seconds.toFixed(1)}s)`
                        : fmtDate(inc.started_at)}
                    </span>
                    {inc.source_type === "video" && inc.start_time_seconds != null && (
                      <span className="flex items-center gap-1">
                        <TrendingUp size={11} />
                        {Math.floor((inc.start_time_seconds ?? 0) / 60)}. dakikada başladı
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
                    <span>Ort: {inc.avg_score.toFixed(0)}</span>
                    <span>·</span>
                    <span>
                      {inc.source_type === "video"
                        ? (inc.video_filename || `Video #${inc.analysis_job_id}`)
                        : cameras.find((c) => c.id === inc.camera_id)?.name || `Kamera #${inc.camera_id}`}
                    </span>
                    <span>·</span>
                    <span className={inc.status === "confirmed" ? "text-emerald-400" : inc.status === "false_positive" ? "text-red-400" : "text-slate-500"}>
                      {inc.status}
                    </span>
                  </div>
                </div>

                {/* Detail Link */}
                <Link
                  to={`/events/${inc.id}`}
                  className="shrink-0 self-center rounded-lg border border-line px-3 py-1.5 text-xs text-cyan-300 hover:bg-cyan-400/10 transition"
                >
                  Detay
                </Link>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
