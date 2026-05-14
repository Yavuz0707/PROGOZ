import { useEffect, useState } from "react";
import { Bell, BellOff, Play, Square } from "lucide-react";
import { api, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { useWebSocket } from "../hooks/useWebSocket";
import type { Camera } from "../types";

type LiveMessage = { type: string; camera_id: number; fps: number; latency_ms: number; alarm_level: string; score: number; severity?: string };

export default function LiveCameraPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [cameraId, setCameraId] = useState<number | null>(null);
  const [alarmSound, setAlarmSound] = useState(true);
  const { lastMessage, connected } = useWebSocket<LiveMessage>(cameraId ? `/ws/live/${cameraId}` : null);
  const selected = cameras.find((c) => c.id === cameraId);
  const level = lastMessage?.alarm_level || "NORMAL";

  useEffect(() => {
    unwrap<Camera[]>(api.get("/cameras")).then((items) => {
      setCameras(items);
      setCameraId(items[0]?.id ?? null);
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (alarmSound && lastMessage && ["KAVGA", "OLASI_KAVGA"].includes(level)) {
      const audio = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=");
      audio.play().catch(() => undefined);
    }
  }, [lastMessage, alarmSound, level]);

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-2xl font-semibold text-white">Canli Kamera</h2><p className="text-sm text-slate-400">Dusuk gecikmeli skor ve alarm takibi</p></div>
        <button onClick={() => setAlarmSound((v) => !v)} className="focus-ring rounded-lg border border-line p-2 text-cyan-100" title="Sesli alarm">{alarmSound ? <Bell size={18} /> : <BellOff size={18} />}</button>
      </div>
      <div className="panel flex flex-wrap items-center gap-3 p-4">
        <select className="focus-ring min-w-56 rounded-lg border border-line bg-slate-950 px-3 py-2" value={cameraId ?? ""} onChange={(e) => setCameraId(Number(e.target.value))}>
          {cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}
        </select>
        <button disabled={!cameraId} onClick={() => unwrap(api.post(`/cameras/${cameraId}/start`))} className="focus-ring rounded-lg bg-emerald-400/20 p-2 text-emerald-200"><Play size={18} /></button>
        <button disabled={!cameraId} onClick={() => unwrap(api.post(`/cameras/${cameraId}/stop`))} className="focus-ring rounded-lg bg-yellow-400/20 p-2 text-yellow-100"><Square size={18} /></button>
        <span className="text-sm text-slate-400">{connected ? "WebSocket bagli" : "Beklemede"}</span>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <div className="panel aspect-video overflow-hidden bg-black">
          {cameraId ? <img className="h-full w-full object-contain" src={`/api/stream/${cameraId}/mjpeg`} /> : <div className="grid h-full place-items-center text-slate-400">Kamera secin</div>}
        </div>
        <div className={`panel p-4 ${level === "KAVGA" ? "border-red-400/70" : ""}`}>
          <div className="mb-4 flex items-center justify-between"><span className="text-slate-400">Alarm</span><SeverityBadge value={level} /></div>
          <p className="text-5xl font-semibold text-white">{(lastMessage?.score ?? 0).toFixed(1)}</p>
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-slate-400">FPS</dt><dd>{lastMessage?.fps ?? "-"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-400">Gecikme</dt><dd>{lastMessage?.latency_ms ?? "-"} ms</dd></div>
            <div className="flex justify-between"><dt className="text-slate-400">Kaynak</dt><dd>{selected?.source_type || "-"}</dd></div>
          </dl>
        </div>
      </div>
    </section>
  );
}

