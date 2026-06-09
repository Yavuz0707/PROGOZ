import { useEffect, useState } from "react";
import { Bell, BellOff, Play, Square } from "lucide-react";
import { api, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { useWebSocket } from "../hooks/useWebSocket";
import type { Camera } from "../types";

type LiveMessage = { type: string; camera_id: number; fps: number; latency_ms: number; alarm_level: string; score: number; severity?: string; plate?: string; confidence?: number; snapshot_url?: string };
type CameraDevice = { id: number; name: string; type: string };

export default function LiveCameraPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [devices, setDevices] = useState<CameraDevice[]>([]);
  // selectedValue format: "cam:{db_id}" for registered cameras, "dev:{device_id}" for webcams
  const [selectedValue, setSelectedValue] = useState<string>("");
  const [alarmSound, setAlarmSound] = useState(true);
  const [plateToast, setPlateToast] = useState<LiveMessage | null>(null);

  // Numeric ID used for WS channel and MJPEG stream URL
  const cameraId: number | null = (() => {
    if (!selectedValue) return null;
    const n = Number(selectedValue.split(":")[1]);
    return isNaN(n) ? null : n;
  })();

  const isWebcam = selectedValue.startsWith("dev:");
  const selectedCamera = !isWebcam && cameraId !== null
    ? cameras.find((c) => c.id === cameraId)
    : null;

  const { lastMessage, connected } = useWebSocket<LiveMessage>(cameraId !== null ? `/ws/live/${cameraId}` : null);
  const level = lastMessage?.alarm_level || "NORMAL";

  useEffect(() => {
    Promise.all([
      unwrap<Camera[]>(api.get("/cameras")).catch(() => [] as Camera[]),
      unwrap<CameraDevice[]>(api.get("/cameras/devices")).catch(() => [] as CameraDevice[]),
    ]).then(([cams, devs]) => {
      setCameras(cams);
      setDevices(devs);
      if (cams.length > 0) setSelectedValue(`cam:${cams[0].id}`);
      else if (devs.length > 0) setSelectedValue(`dev:${devs[0].id}`);
    });
  }, []);

  useEffect(() => {
    if (lastMessage?.type === "plate_detected") {
      setPlateToast(lastMessage);
      window.setTimeout(() => setPlateToast(null), 5000);
    }
    if (alarmSound && lastMessage && ["KAVGA", "OLASI_KAVGA"].includes(level)) {
      const audio = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=");
      audio.play().catch(() => undefined);
    }
  }, [lastMessage, alarmSound, level]);

  function handleStart() {
    if (cameraId === null) return;
    if (isWebcam) {
      unwrap(api.post("/cameras/webcam/start", { device_id: cameraId })).catch(console.error);
    } else {
      unwrap(api.post(`/cameras/${cameraId}/start`)).catch(console.error);
    }
  }

  function handleStop() {
    if (cameraId === null) return;
    if (isWebcam) {
      unwrap(api.post("/cameras/webcam/stop", { device_id: cameraId })).catch(console.error);
    } else {
      unwrap(api.post(`/cameras/${cameraId}/stop`)).catch(console.error);
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-2xl font-semibold text-white">Canli Kamera</h2><p className="text-sm text-slate-400">Dusuk gecikmeli skor ve alarm takibi</p></div>
        <button onClick={() => setAlarmSound((v) => !v)} className="focus-ring rounded-lg border border-line p-2 text-cyan-100" title="Sesli alarm">{alarmSound ? <Bell size={18} /> : <BellOff size={18} />}</button>
      </div>
      <div className="panel flex flex-wrap items-center gap-3 p-4">
        <select
          className="focus-ring min-w-56 rounded-lg border border-line bg-slate-950 px-3 py-2"
          value={selectedValue}
          onChange={(e) => setSelectedValue(e.target.value)}
        >
          {cameras.length > 0 && (
            <optgroup label="Kayitli Kameralar">
              {cameras.map((c) => (
                <option key={`cam:${c.id}`} value={`cam:${c.id}`}>{c.name}</option>
              ))}
            </optgroup>
          )}
          {devices.length > 0 && (
            <optgroup label="Bagli Cihazlar">
              {devices.map((d) => (
                <option key={`dev:${d.id}`} value={`dev:${d.id}`}>{d.name}</option>
              ))}
            </optgroup>
          )}
          {cameras.length === 0 && devices.length === 0 && (
            <option value="">Kamera bulunamadi</option>
          )}
        </select>
        <button disabled={cameraId === null} onClick={handleStart} className="focus-ring rounded-lg bg-emerald-400/20 p-2 text-emerald-200"><Play size={18} /></button>
        <button disabled={cameraId === null} onClick={handleStop} className="focus-ring rounded-lg bg-yellow-400/20 p-2 text-yellow-100"><Square size={18} /></button>
        <span className="text-sm text-slate-400">{connected ? "WebSocket bagli" : "Beklemede"}</span>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <div className="panel aspect-video overflow-hidden bg-black">
          {cameraId !== null ? <img className="h-full w-full object-contain" src={`/api/stream/${cameraId}/mjpeg`} /> : <div className="grid h-full place-items-center text-slate-400">Kamera secin</div>}
        </div>
        <div className={`panel p-4 ${level === "KAVGA" ? "border-red-400/70" : ""}`}>
          {plateToast && <div className="mb-4 rounded-lg border border-cyan-400/40 bg-cyan-400/10 p-3 text-sm text-cyan-100">Plaka: <strong>{plateToast.plate}</strong> {Math.round(Number(plateToast.confidence || 0) * 100)}%</div>}
          <div className="mb-4 flex items-center justify-between"><span className="text-slate-400">Alarm</span><SeverityBadge value={level} /></div>
          <p className="text-5xl font-semibold text-white">{(lastMessage?.score ?? 0).toFixed(1)}</p>
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-slate-400">FPS</dt><dd>{lastMessage?.fps ?? "-"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-400">Gecikme</dt><dd>{lastMessage?.latency_ms ?? "-"} ms</dd></div>
            <div className="flex justify-between"><dt className="text-slate-400">Kaynak</dt><dd>{isWebcam ? "webcam" : selectedCamera?.source_type || "-"}</dd></div>
          </dl>
        </div>
      </div>
    </section>
  );
}
