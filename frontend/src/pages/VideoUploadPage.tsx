import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { UploadCloud } from "lucide-react";
import { Link } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { useWebSocket } from "../hooks/useWebSocket";
import type { AnalysisJob, IncidentRecord } from "../types";

type JobMessage = Partial<AnalysisJob> & { type: string; job_id: number; severity?: string; score?: number; message?: string };

export default function VideoUploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [log, setLog] = useState<string[]>([]);
  const [analysisMode, setAnalysisMode] = useState("fast");
  const [saveProcessedVideo, setSaveProcessedVideo] = useState(false);
  const [debugScoring, setDebugScoring] = useState(false);
  const [fastResult, setFastResult] = useState(false);
  const [system, setSystem] = useState<Record<string, any> | null>(null);
  const { lastMessage } = useWebSocket<JobMessage>(job ? `/ws/jobs/${job.id}` : null);
  const chartData = useMemo(() => incidents.map((e, index) => ({ index: index + 1, score: e.max_score })), [incidents]);
  const playableVideoUrl = job?.status === "completed" && job?.processed_url ? `${job.processed_url}?t=${job.id}-${job.processed_video_size || 0}` : undefined;

  useEffect(() => {
    unwrap<AnalysisJob[]>(api.get("/uploads/jobs"))
      .then((jobs) => {
        const latest = jobs[0];
        if (!latest) return;
        return unwrap<{ job: AnalysisJob; incidents: IncidentRecord[] }>(api.get(`/uploads/jobs/${latest.id}/result`));
      })
      .then((result) => {
        if (!result) return;
        setJob(result.job);
        setIncidents(result.incidents || []);
      })
      .catch(console.error);
    unwrap<Record<string, any>>(api.get("/system/status")).then(setSystem).catch(console.error);
  }, []);

  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === "event") setLog((prev) => [`Olay: ${lastMessage.severity} ${Number(lastMessage.score).toFixed(1)}`, ...prev]);
    if (lastMessage.type === "job_log") setLog((prev) => [String(lastMessage.message), ...prev]);
  }, [lastMessage]);

  async function upload() {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("analysis_mode", analysisMode);
    form.append("save_processed_video", String(saveProcessedVideo));
    form.append("debug_scoring", String(debugScoring));
    form.append("fast_result", String(fastResult));
    const created = await unwrap<AnalysisJob>(api.post("/uploads/analyze", form));
    setIncidents([]);
    setLog(["Video yuklendi; analiz arka planda baslatildi."]);
    setJob(created);
    poll(created.id);
  }

  async function poll(id: number) {
    const timer = window.setInterval(async () => {
      const result = await unwrap<{ job: AnalysisJob; incidents: IncidentRecord[] }>(api.get(`/uploads/jobs/${id}/result`));
      setJob(result.job);
      setIncidents(result.incidents || []);
      if (["completed", "failed"].includes(result.job.status)) window.clearInterval(timer);
    }, 1500);
  }

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-white">Video Analiz</h2>
        <p className="text-sm text-slate-400">Dosya yukle, background analiz ilerlemesini izle, sonucu oynat.</p>
      </div>
      <div className="panel p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <label className="focus-ring flex min-h-28 flex-1 cursor-pointer items-center justify-center rounded-lg border border-dashed border-cyan-400/50 bg-cyan-400/6 p-4 text-center">
            <input className="hidden" type="file" accept="video/*" onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] || null)} />
            <span className="flex items-center gap-2 text-slate-200"><UploadCloud size={20} /> {file?.name || "Video sec"}</span>
          </label>
          <select value={analysisMode} onChange={(event) => setAnalysisMode(event.target.value)} className="rounded-lg border border-line bg-slate-950 px-3 py-3 text-sm text-slate-100">
            <option value="fast">Hizli Analiz</option>
            <option value="balanced">Dengeli</option>
            <option value="accurate">Detayli</option>
          </select>
          <button onClick={upload} disabled={!file || job?.status === "running" || job?.status === "encoding"} className="focus-ring rounded-lg bg-cyan-400 px-5 py-3 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50">
            Analizi Baslat
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-300">
          <label className="flex items-center gap-2"><input type="checkbox" checked={saveProcessedVideo} onChange={(e) => setSaveProcessedVideo(e.target.checked)} /> Islenmis video uret</label>
          <span className="text-slate-500">Varsayilan: sadece olaylari cikar</span>
          <label className="flex items-center gap-2"><input type="checkbox" checked={debugScoring} onChange={(e) => setDebugScoring(e.target.checked)} /> Debug log acik</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={fastResult} onChange={(e) => setFastResult(e.target.checked)} /> Hizli sonuc modu</label>
        </div>
        {system && (
          <div className="mt-3 rounded-lg border border-line bg-slate-950/60 p-3 text-xs text-slate-300">
            CUDA: {system.cuda_available ? "aktif" : "pasif"} {system.device_name || system.cuda_device || "CPU"} | Mod: {analysisMode} | FFmpeg: {system.ffmpeg_available ? "var" : "yok"}
          </div>
        )}
        {job && (
          <div className="mt-4">
            <div className="mb-2 flex justify-between text-sm text-slate-300"><span>{job.status === "encoding" ? "Analiz tamamlandi, video donusturuluyor..." : job.status}</span><span>{Math.round(job.progress)}%</span></div>
            <div className="h-3 overflow-hidden rounded bg-slate-800"><div className="h-full bg-cyan-400 transition-all" style={{ width: `${job.progress}%` }} /></div>
            {job.error_message && <p className="mt-2 text-sm text-red-200">{job.error_message}</p>}
          </div>
        )}
      </div>
      {playableVideoUrl && (
        <div className="space-y-2">
          <video key={playableVideoUrl} className="panel w-full bg-black" controls src={playableVideoUrl} />
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="panel p-4">
          <h3 className="mb-3 font-semibold text-white">Olay Ozeti</h3>
          {job?.status === "completed" && <p className="mb-3 text-sm text-slate-300">{incidents.length} adet gruplanmis olay bulundu. <Link className="text-cyan-300" to="/events">Olaylar sayfasinda goruntule</Link></p>}
          <div className="space-y-2">
            {incidents.map((incident) => (
              <div key={incident.id} className="flex items-center justify-between rounded-lg bg-slate-950/60 p-3">
                <span className="text-sm text-slate-300">{incident.start_time_seconds?.toFixed(1)}s - {incident.end_time_seconds?.toFixed(1)}s</span>
                <SeverityBadge value={incident.severity} />
                <span>{incident.max_score.toFixed(1)}</span>
              </div>
            ))}
            {incidents.length === 0 && <p className="text-sm text-slate-400">Analiz gruplanmis olay bekliyor.</p>}
          </div>
        </div>
        <div className="panel p-4">
          <h3 className="mb-3 font-semibold text-white">Skor Grafigi</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}><XAxis dataKey="index" /><YAxis domain={[0, 100]} /><Tooltip /><Line type="monotone" dataKey="score" stroke="#22d3ee" strokeWidth={2} /></LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 max-h-36 overflow-auto text-xs text-slate-400">{log.map((line, i) => <p key={i}>{line}</p>)}</div>
        </div>
      </div>
      {job?.performance && (
        <div className="panel grid gap-3 p-4 text-sm text-slate-300 md:grid-cols-3">
          {Object.entries(job.performance).map(([key, value]) => <p key={key}><span className="text-slate-500">{key}: </span>{String(value)}</p>)}
        </div>
      )}
    </section>
  );
}
