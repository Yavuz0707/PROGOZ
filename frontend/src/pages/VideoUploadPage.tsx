import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { UploadCloud, AlertTriangle, CheckCircle2, Clock, Square } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, assetUrl, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { useWebSocket } from "../hooks/useWebSocket";
import type { AnalysisJob, IncidentRecord, PlateRecord } from "../types";

type ScorePoint = { t: number; score: number; label: string };
type LivePlate = { text: string; confidence: number; time_seconds?: number };
type JobMessage = Partial<AnalysisJob> & {
  type: string;
  job_id?: number;
  severity?: string;
  score?: number;
  message?: string;
  plate?: string;
  confidence?: number;
  time_seconds?: number;
  frame_number?: number;
  timestamp_sec?: number;
  fight_score?: number;
  fight_label?: string;
  event_detected?: boolean;
  processed_frames?: number;
  skipped_frames?: number;
  duration_sec?: number;
};

const SEVERITY_COLOR: Record<string, string> = {
  KAVGA: "#ef4444",
  "OLASI KAVGA": "#f97316",
  OLASI_KAVGA: "#f97316",
  ŞÜPHELİ: "#eab308",
  SUPHELI: "#eab308",
  NORMAL: "#888888",
};

function statusText(status?: string) {
  if (status === "queued") return "Analiz kuyruga alindi";
  if (status === "running") return "Video analiz ediliyor...";
  if (status === "encoding") return "Video donusturuluyor...";
  if (status === "completed") return "Analiz tamamlandi";
  if (status === "failed") return "Analiz basarisiz";
  if (status === "cancelled") return "Analiz durduruldu";
  return status || "Beklemede";
}

function statusIcon(status?: string) {
  if (status === "completed") return <CheckCircle2 size={16} className="text-emerald-400" />;
  if (status === "failed") return <AlertTriangle size={16} className="text-red-400" />;
  if (status === "cancelled") return <Square size={16} className="text-orange-400" />;
  return <Clock size={16} className="text-cyan-400 animate-pulse" />;
}

export default function VideoUploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [analysisMode, setAnalysisMode] = useState("fast");
  const [saveProcessedVideo, setSaveProcessedVideo] = useState(false);
  const [debugScoring, setDebugScoring] = useState(false);
  const [onlyIncidents, setOnlyIncidents] = useState(true);
  const [plateRecognitionEnabled, setPlateRecognitionEnabled] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [system, setSystem] = useState<Record<string, unknown> | null>(null);

  // Real-time data from WebSocket
  const [scoreSeries, setScoreSeries] = useState<ScorePoint[]>([]);
  const [livePlates, setLivePlates] = useState<LivePlate[]>([]);
  const scoreSeriesRef = useRef<ScorePoint[]>([]);

  const { lastMessage } = useWebSocket<JobMessage>(job && job.id ? `/ws/jobs/${job.id}` : null);

  const playableVideoUrl =
    job?.status === "completed" && job?.processed_url
      ? `${assetUrl(job.processed_url)}?t=${job.id}-${job.processed_video_size || 0}`
      : undefined;

  // Chart data: prefer live score series during analysis, incidents after completion
  const chartData = useMemo(() => {
    if (scoreSeries.length > 0) return scoreSeries.map((p) => ({ t: p.t, score: p.score }));
    return incidents.map((e, i) => ({ t: e.start_time_seconds ?? i, score: e.max_score }));
  }, [scoreSeries, incidents]);

  useEffect(() => {
    // Clear any persisted job state from previous sessions
    localStorage.removeItem("lastJobId");
    localStorage.removeItem("analysisState");

    // Only reconnect to ACTIVE jobs; completed / failed jobs are ignored so
    // the page always starts clean — no old data shown on load.
    unwrap<AnalysisJob[]>(api.get("/uploads/jobs"))
      .then((jobs) => {
        const latest = jobs[0];
        if (!latest) return null;
        if (["completed", "failed"].includes(latest.status)) return null;
        return unwrap<{ job: AnalysisJob; incidents: IncidentRecord[]; plates: PlateRecord[] }>(
          api.get(`/uploads/jobs/${latest.id}/result`)
        );
      })
      .then((result) => {
        if (!result) return;
        setJob(result.job);
        poll(result.job.id);
      })
      .catch((err) => {
        if (String(err.message || "").includes("Yetki hatasi")) navigate("/login");
      });

    unwrap<Record<string, unknown>>(api.get("/system/status"))
      .then(setSystem)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!lastMessage) return;
    const msg = lastMessage;

    if (msg.type === "frame_score") {
      const point: ScorePoint = {
        t: msg.timestamp_sec ?? 0,
        score: msg.fight_score ?? 0,
        label: msg.fight_label ?? "NORMAL",
      };
      scoreSeriesRef.current = [...scoreSeriesRef.current.slice(-300), point];
      setScoreSeries([...scoreSeriesRef.current]);
    }

    if (msg.type === "plate_detected" && msg.plate) {
      setLivePlates((prev) => {
        const exists = prev.find((p) => p.text === msg.plate);
        if (exists) return prev;
        return [{ text: msg.plate!, confidence: msg.confidence ?? 0, time_seconds: msg.time_seconds }, ...prev.slice(0, 29)];
      });
      setLog((prev) => [`Plaka: ${msg.plate} %${Math.round((msg.confidence ?? 0) * 100)}`, ...prev]);
    }

    if (msg.type === "job_log") setLog((prev) => [String(msg.message), ...prev]);

    if (msg.type === "incident") {
      setLog((prev) => [`Olay: ${msg.severity} skor=${Number(msg.score ?? 0).toFixed(1)}`, ...prev]);
    }

    if (msg.type === "job_progress") {
      setJob((prev) => prev ? { ...prev, ...msg } : prev);
    }

    if (msg.type === "analysis_complete") {
      const dur = msg.duration_sec != null ? `${msg.duration_sec.toFixed(1)}s` : "";
      setLog((prev) => [
        `Analiz bitti — ${msg.processed_frames ?? 0} frame islendi, ${msg.skipped_frames ?? 0} atlandi${dur ? `, süre: ${dur}` : ""}`,
        ...prev,
      ]);
    }

    if (msg.type === "analysis_cancelled") {
      setLog((prev) => [
        `Analiz durduruldu — ${msg.processed_frames ?? 0} frame islendi`,
        ...prev,
      ]);
      setJob((prev) => (prev ? { ...prev, status: "cancelled" } : prev));
    }
  }, [lastMessage]);

  async function upload() {
    if (!file) {
      setError("Video dosyasi secilmedi.");
      return;
    }
    setSubmitting(true);
    setError("");
    setIncidents([]);
    setLog(["Analiz istegi gonderiliyor..."]);
    setScoreSeries([]);
    scoreSeriesRef.current = [];
    setLivePlates([]);
    setJob({ id: 0, filename: file.name, status: "queued", progress: 0, total_frames: 0, processed_frames: 0, current_stage: "queued" });

    const form = new FormData();
    form.append("file", file);
    form.append("analysis_mode", analysisMode);
    form.append("save_processed_video", String(saveProcessedVideo));
    form.append("debug_scoring", String(debugScoring));
    form.append("debug_log", String(debugScoring));
    form.append("fast_result", String(onlyIncidents));
    form.append("only_incidents", String(onlyIncidents));
    form.append("plate_recognition_enabled", String(plateRecognitionEnabled));

    try {
      const created = await unwrap<AnalysisJob>(api.post("/uploads/analyze", form));
      setLog(["Video yuklendi; analiz baslatildi."]);
      setJob(created);
      poll(created.id);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Analiz baslatilamadi.";
      setError(message);
      setLog((prev) => [message, ...prev]);
      setJob(null);
      if (message.includes("Yetki hatasi")) navigate("/login");
    } finally {
      setSubmitting(false);
    }
  }

  async function poll(id: number) {
    const timer = window.setInterval(async () => {
      try {
        const result = await unwrap<{ job: AnalysisJob; incidents: IncidentRecord[]; plates: PlateRecord[] }>(
          api.get(`/uploads/jobs/${id}/result`)
        );
        setJob(result.job);
        if (result.job.status === "completed") {
          setIncidents(result.incidents || []);
          setScoreSeries([]);
          scoreSeriesRef.current = [];
        }
        if (result.job.status === "failed") setError(result.job.error_message || "Analiz basarisiz oldu.");
        if (["completed", "failed", "cancelled"].includes(result.job.status)) window.clearInterval(timer);
      } catch (err: unknown) {
        window.clearInterval(timer);
        const message = err instanceof Error ? err.message : "Analiz durumu alinamadi.";
        setError(message);
        setLog((prev) => [message, ...prev]);
        if (message.includes("Yetki hatasi")) navigate("/login");
      }
    }, 2000);
  }

  const isRunning = job?.status === "running" || job?.status === "encoding" || job?.status === "queued";
  const progress = job ? Math.round(job.progress) : 0;
  const processedFrames = job?.processed_frames ?? 0;
  const totalFrames = job?.total_frames ?? 0;

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-white">Video Analiz</h2>
        <p className="text-sm text-slate-400">Dosya yukle, analiz ilerlemesini gercek zamanli izle.</p>
      </div>

      {/* Upload Controls */}
      <div className="panel p-4 space-y-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <label className="focus-ring flex min-h-24 flex-1 cursor-pointer items-center justify-center rounded-lg border border-dashed border-cyan-400/50 bg-cyan-400/6 p-4 text-center">
            <input className="hidden" type="file" accept="video/*" onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] || null)} />
            <span className="flex items-center gap-2 text-slate-200">
              <UploadCloud size={20} />
              {file?.name || "Video sec (MP4, AVI, MKV...)"}
            </span>
          </label>
          <select
            value={analysisMode}
            onChange={(e) => setAnalysisMode(e.target.value)}
            className="rounded-lg border border-line bg-slate-950 px-3 py-3 text-sm text-slate-100"
          >
            <option value="fast">Hizli (dusuk gecikme)</option>
            <option value="balanced">Dengeli</option>
            <option value="accurate">Detayli (en hassas)</option>
          </select>
          <button
            type="button"
            onClick={upload}
            disabled={!file || submitting || isRunning}
            className="focus-ring rounded-lg bg-cyan-400 px-6 py-3 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Yukleniyor..." : "Analizi Baslat"}
          </button>
          {job?.status === "running" && job.id > 0 && (
            <button
              type="button"
              onClick={() => api.post(`/uploads/jobs/${job.id}/cancel`).catch(() => {})}
              className="focus-ring flex items-center gap-2 rounded-lg bg-red-600 px-6 py-3 font-semibold text-white hover:bg-red-500"
            >
              <Square size={16} fill="currentColor" />
              Analizi Durdur
            </button>
          )}
        </div>

        <div className="flex flex-wrap gap-4 text-sm text-slate-300">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={plateRecognitionEnabled} onChange={(e) => setPlateRecognitionEnabled(e.target.checked)} />
            Plaka tanima
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={saveProcessedVideo} onChange={(e) => setSaveProcessedVideo(e.target.checked)} />
            Islenmis video kaydet
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={debugScoring} onChange={(e) => setDebugScoring(e.target.checked)} />
            Debug log
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={onlyIncidents} onChange={(e) => setOnlyIncidents(e.target.checked)} />
            Sadece olaylar
          </label>
        </div>

        {system && (
          <div className="rounded-lg border border-line bg-slate-950/60 p-2 text-xs text-slate-400">
            CUDA: {system.cuda_available ? <span className="text-emerald-400">Aktif</span> : <span className="text-red-400">Pasif</span>}
            {" "}— {String(system.cuda_device || "CPU")} | Mod: <span className="text-cyan-300">{analysisMode}</span> | FFmpeg: {system.ffmpeg_available ? "var" : "yok"}
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-400/40 bg-red-400/10 p-3 text-sm text-red-100 flex items-center gap-2">
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {/* Progress Bar */}
        {job && (
          <div className="space-y-1">
            <div className="flex justify-between text-sm text-slate-300">
              <span className="flex items-center gap-1">{statusIcon(job.status)} {statusText(job.status)}</span>
              <span className="tabular-nums">
                {totalFrames > 0
                  ? `${processedFrames.toLocaleString()} / ${totalFrames.toLocaleString()} frame — ${progress}%`
                  : processedFrames > 0
                  ? `${processedFrames.toLocaleString()} frame islendi`
                  : `${progress}%`}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full bg-cyan-400 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            {job.error_message && <p className="text-sm text-red-200">{job.error_message}</p>}
          </div>
        )}
      </div>

      {/* Processed Video */}
      {playableVideoUrl && (
        <video key={playableVideoUrl} className="panel w-full bg-black rounded-xl" controls src={playableVideoUrl} />
      )}

      {/* Empty state — show until user starts an analysis */}
      {!job && (
        <div className="panel p-10 text-center text-slate-500">
          <UploadCloud size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Analiz başlatmak için yukarıdan video seçin.</p>
        </div>
      )}

      {/* Live Analysis Grid — only shown when a job is active or just completed */}
      {job && <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        {/* Score Chart */}
        <div className="panel p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-white">
              {isRunning ? "Canli Kavga Skoru" : "Olay Skoru Grafigi"}
            </h3>
            {isRunning && scoreSeries.length > 0 && (
              <span className="text-xs text-slate-400 tabular-nums">
                {scoreSeries.length} nokta
              </span>
            )}
          </div>
          <div className="h-52">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ffffff" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#ffffff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
                  <XAxis dataKey="t" tickFormatter={(v: number) => `${v.toFixed(0)}s`} tick={{ fill: "#444444", fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: "#444444", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#141414", border: "1px solid #2a2a2a", borderRadius: 8 }}
                    labelFormatter={(v: number) => `${Number(v).toFixed(1)}s`}
                    formatter={(v: number) => [`${v.toFixed(1)}`, "Skor"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#ffffff"
                    strokeWidth={2}
                    fill="url(#scoreGrad)"
                    dot={false}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-slate-500">
                {isRunning ? "Skor verisi bekleniyor..." : "Analiz baslatildiginda grafik dolacak"}
              </div>
            )}
          </div>

          {/* Log */}
          <div className="mt-3 max-h-28 overflow-auto space-y-0.5">
            {log.map((line, i) => (
              <p key={i} className="text-xs text-slate-500">{line}</p>
            ))}
            {log.length === 0 && <p className="text-xs text-slate-600">Log bekleniyor...</p>}
          </div>
        </div>

        {/* Right Panel: Incidents + Live Plates */}
        <div className="space-y-4">
          {/* Incidents Summary */}
          <div className="panel p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-white">Olay Ozeti</h3>
              {job?.status === "completed" && (
                <div className="flex gap-2 text-xs">
                  <Link className="text-cyan-300 hover:text-cyan-100" to="/events">Olaylar</Link>
                  <span className="text-slate-600">|</span>
                  <Link className="text-cyan-300 hover:text-cyan-100" to={`/plates?analysis_job_id=${job.id}`}>Plakalar</Link>
                </div>
              )}
            </div>
            <div className="space-y-2 max-h-48 overflow-auto">
              {incidents.length > 0 ? incidents.map((inc) => (
                <div key={inc.id} className="flex items-center justify-between rounded-lg bg-slate-950/60 p-2.5">
                  <div className="text-xs text-slate-400">
                    <p>{inc.start_time_seconds?.toFixed(1)}s – {inc.end_time_seconds?.toFixed(1)}s</p>
                    <p>{inc.duration_seconds.toFixed(1)} sn</p>
                  </div>
                  <SeverityBadge value={inc.severity} />
                  <span className="text-sm font-semibold text-white">{inc.max_score.toFixed(0)}</span>
                </div>
              )) : (
                <p className="text-sm text-slate-500 text-center py-4">
                  {isRunning ? "Analiz devam ediyor..." : "Olay bulunamadi"}
                </p>
              )}
            </div>
            {job?.status === "completed" && (
              <p className="mt-2 text-xs text-slate-500">
                {incidents.length} olay · {job.plate_count || livePlates.length || 0} plaka
              </p>
            )}
          </div>

          {/* Live Detected Plates */}
          <div className="panel p-4">
            <h3 className="font-semibold text-white mb-3">
              Tespit Edilen Plakalar
              {livePlates.length > 0 && (
                <span className="ml-2 rounded-full bg-cyan-400/20 px-2 py-0.5 text-xs text-cyan-300">
                  {livePlates.length}
                </span>
              )}
            </h3>
            <div className="space-y-1.5 max-h-48 overflow-auto">
              {livePlates.length > 0 ? livePlates.map((p, i) => (
                <div key={i} className="flex items-center justify-between rounded bg-slate-950/60 px-3 py-1.5">
                  <span className="font-mono text-sm font-bold text-white">{p.text}</span>
                  <div className="text-right text-xs text-slate-400">
                    <p>%{Math.round(p.confidence * 100)}</p>
                    {p.time_seconds !== undefined && <p>{p.time_seconds.toFixed(1)}s</p>}
                  </div>
                </div>
              )) : (
                <p className="text-sm text-slate-500 text-center py-4">
                  {plateRecognitionEnabled ? (isRunning ? "Plaka bekleniyor..." : "Plaka tespit edilmedi") : "Plaka tanima kapalı"}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>}

      {/* Live Score Indicator */}
      {job && isRunning && scoreSeries.length > 0 && (() => {
        const last = scoreSeries[scoreSeries.length - 1];
        const color = SEVERITY_COLOR[last.label] || "#888888";
        return (
          <div
            className="panel p-4 flex items-center justify-between"
            style={{ borderColor: `${color}40` }}
          >
            <div>
              <p className="text-xs text-slate-400">Anlık Skor</p>
              <p className="text-3xl font-bold" style={{ color }}>{last.score.toFixed(0)}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-400">Durum</p>
              <SeverityBadge value={last.label.replace(" ", "_").toUpperCase()} />
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-400">Zaman</p>
              <p className="text-sm text-slate-300">{last.t.toFixed(1)}s</p>
            </div>
          </div>
        );
      })()}

      {/* Performance Stats */}
      {job?.performance && (
        <div className="panel grid gap-2 p-4 text-sm text-slate-300 md:grid-cols-3 xl:grid-cols-4">
          {Object.entries(job.performance)
            .filter(([, v]) => v !== null && typeof v !== "object")
            .map(([key, value]) => (
              <div key={key} className="rounded-lg bg-slate-950/60 px-3 py-2">
                <p className="text-xs text-slate-500">{key}</p>
                <p className="font-medium text-white">{String(value)}</p>
              </div>
            ))}
        </div>
      )}
    </section>
  );
}
