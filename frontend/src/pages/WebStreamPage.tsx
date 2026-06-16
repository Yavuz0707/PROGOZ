import { useEffect, useRef, useState } from "react";
import { Globe, Play, Square, Trash2, Wifi, WifiOff } from "lucide-react";
import { api, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { useWebSocket } from "../hooks/useWebSocket";
import type { Camera } from "../types";

type OverlayBox = { id: number; x1: number; y1: number; x2: number; y2: number; conf: number };

type LiveMsg = {
  type: string;
  camera_id?: number;
  fps?: number;
  latency_ms?: number;
  alarm_level?: string;
  level?: string;
  score?: number;
  plate?: string;
  confidence?: number;
  // overlay_update (web stream only)
  boxes?: OverlayBox[];
  plates?: { plate: string; confidence: number }[];
  frame_w?: number;
  frame_h?: number;
  timestamp?: number;
};

type Overlay = { boxes: OverlayBox[]; level: string; score: number; frameW: number; frameH: number };

// Bounding box renkleri (seviyeye gore)
const LEVEL_COLORS: Record<string, string> = {
  KAVGA: "#ef4444", // kirmizi
  OLASI_KAVGA: "#f97316", // turuncu
  SUPHELI: "#eab308", // sari
  NORMAL: "#22c55e", // yesil
};

export default function WebStreamPage() {
  const [pageUrl, setPageUrl] = useState("");
  const [camName, setCamName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCam, setActiveCam] = useState<Camera | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [plateToast, setPlateToast] = useState<string | null>(null);
  const [savedCams, setSavedCams] = useState<Camera[]>([]);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const { lastMessage, connected } = useWebSocket<LiveMsg>(
    activeCam ? `/ws/live/${activeCam.id}` : null
  );

  // Analyzer outputs (web stream): boxes/score come via "overlay_update",
  // fps/latency via "frame_status". Both are tracked so the panel + canvas stay in sync.
  const [overlay, setOverlay] = useState<Overlay | null>(null);
  const [status, setStatus] = useState<{ fps?: number; latency_ms?: number; level?: string; score?: number }>({});
  const videoWrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [wrapSize, setWrapSize] = useState({ w: 0, h: 0 });

  const level = overlay?.level ?? status.level ?? lastMessage?.alarm_level ?? "NORMAL";
  const score = overlay?.score ?? status.score ?? 0;

  // Load existing web cameras on mount
  useEffect(() => {
    loadSavedCams();
  }, []);

  // Route incoming WS messages by type (overlay_update / frame_status)
  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === "overlay_update") {
      setOverlay({
        boxes: lastMessage.boxes ?? [],
        level: lastMessage.level ?? "NORMAL",
        score: lastMessage.score ?? 0,
        frameW: lastMessage.frame_w ?? 0,
        frameH: lastMessage.frame_h ?? 0,
      });
    } else if (lastMessage.type === "frame_status") {
      setStatus({
        fps: lastMessage.fps,
        latency_ms: lastMessage.latency_ms,
        level: lastMessage.alarm_level,
        score: lastMessage.score,
      });
    }
  }, [lastMessage]);

  // Clear stale overlay when the stream stops or the camera changes
  useEffect(() => {
    if (!isRunning) {
      setOverlay(null);
    }
  }, [isRunning, activeCam]);

  // Track the rendered size of the video container (for canvas coordinate scaling)
  useEffect(() => {
    const el = videoWrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        setWrapSize({ w: e.contentRect.width, h: e.contentRect.height });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [isRunning, activeCam]);

  // Draw bounding boxes onto the transparent overlay canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const { w: CW, h: CH } = wrapSize;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = CW;
    canvas.height = CH;
    ctx.clearRect(0, 0, CW, CH);
    if (!overlay || !overlay.frameW || !overlay.frameH || CW === 0 || CH === 0) return;
    // The MJPEG <img> uses object-contain: compute the letterboxed content rect.
    const scale = Math.min(CW / overlay.frameW, CH / overlay.frameH);
    const contentW = overlay.frameW * scale;
    const contentH = overlay.frameH * scale;
    const offX = (CW - contentW) / 2;
    const offY = (CH - contentH) / 2;
    const color = LEVEL_COLORS[overlay.level] ?? LEVEL_COLORS.NORMAL;
    ctx.lineWidth = 2;
    ctx.strokeStyle = color;
    ctx.font = "12px monospace";
    for (const b of overlay.boxes) {
      const x = offX + b.x1 * scale;
      const y = offY + b.y1 * scale;
      const w = (b.x2 - b.x1) * scale;
      const h = (b.y2 - b.y1) * scale;
      ctx.strokeRect(x, y, w, h);
      const label = `ID ${b.id}`;
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = color;
      ctx.fillRect(x, Math.max(0, y - 15), tw + 6, 15);
      ctx.fillStyle = "#000";
      ctx.fillText(label, x + 3, Math.max(11, y - 4));
    }
  }, [overlay, wrapSize]);

  function loadSavedCams() {
    unwrap<Camera[]>(api.get("/cameras"))
      .then((cams) => setSavedCams(cams.filter((c) => c.source_type === "web")))
      .catch(() => {});
  }

  useEffect(() => {
    if (lastMessage?.type === "plate_detected" && lastMessage.plate) {
      setPlateToast(lastMessage.plate);
      const t = window.setTimeout(() => setPlateToast(null), 5000);
      return () => window.clearTimeout(t);
    }
  }, [lastMessage]);

  async function handleConnect() {
    const trimmedUrl = pageUrl.trim();
    if (!trimmedUrl) return;
    setLoading(true);
    setError(null);
    try {
      const cam = await unwrap<Camera>(
        api.post("/cameras", {
          name: camName.trim() || trimmedUrl.slice(0, 60),
          source_type: "web",
          rtsp_url: trimmedUrl,
          location: null,
        })
      );
      await unwrap(api.post(`/cameras/${cam.id}/start`));
      setActiveCam(cam);
      setIsRunning(true);
      loadSavedCams();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Baglanti basarisiz";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleConnectExisting(cam: Camera) {
    setLoading(true);
    setError(null);
    try {
      await unwrap(api.post(`/cameras/${cam.id}/start`));
      setActiveCam(cam);
      setIsRunning(true);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Baglanti basarisiz";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    if (!activeCam) return;
    await unwrap(api.post(`/cameras/${activeCam.id}/stop`)).catch(() => {});
    setIsRunning(false);
  }

  async function handleRestart() {
    if (!activeCam) return;
    setLoading(true);
    setError(null);
    try {
      await unwrap(api.post(`/cameras/${activeCam.id}/start`));
      setIsRunning(true);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Yeniden baslatma basarisiz";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(cam: Camera) {
    setDeletingId(cam.id);
    try {
      // Stop first, then delete
      await unwrap(api.post(`/cameras/${cam.id}/stop`)).catch(() => {});
      await unwrap(api.delete(`/cameras/${cam.id}`));
      // If this was the active camera, clear the view
      if (activeCam?.id === cam.id) {
        setActiveCam(null);
        setIsRunning(false);
        setError(null);
      }
      loadSavedCams();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Silinemedi";
      setError(msg);
    } finally {
      setDeletingId(null);
    }
  }

  function handleReset() {
    if (activeCam) {
      unwrap(api.post(`/cameras/${activeCam.id}/stop`)).catch(() => {});
    }
    setActiveCam(null);
    setIsRunning(false);
    setError(null);
  }

  return (
    <section className="space-y-5">
      <div className="border-b border-white/10 pb-4">
        <h2 className="font-display text-[28px] font-bold uppercase tracking-hud text-white">Web Yayini</h2>
        <p className="font-data-mono text-xs text-slate-400">
          Canli guvenlik kamerasi veya web yayini adresini girin — model gercek zamanli analiz etsin
        </p>
      </div>

      {/* URL input form — visible when not watching */}
      {!isRunning && (
        <div className="panel space-y-4 p-5">
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">
              Yayin Adresi
            </label>
            <input
              type="url"
              placeholder="https://www.canliseyir.com/..."
              value={pageUrl}
              onChange={(e) => setPageUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !loading && handleConnect()}
              className="focus-ring w-full rounded-lg border border-line bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-600"
            />
            <p className="mt-1.5 text-xs text-slate-500">
              HLS (m3u8), RTSP, RTMP veya canli yayin sayfasi URL'si desteklenir
            </p>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400">
              Kamera Adi (opsiyonel)
            </label>
            <input
              type="text"
              placeholder="orn. Colorado Ouray Kamerasi"
              value={camName}
              onChange={(e) => setCamName(e.target.value)}
              className="focus-ring w-full rounded-lg border border-line bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-600"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-sm text-red-300 whitespace-pre-wrap">
              {error}
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              disabled={!pageUrl.trim() || loading}
              onClick={handleConnect}
              className="focus-ring flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-medium text-black disabled:opacity-40"
            >
              <Globe size={16} />
              {loading ? "Yayin aliniyor..." : "Baglan & Analiz Et"}
            </button>
            {loading && (
              <span className="text-xs text-slate-500">
                Stream adresi ayiklaniyor, birkaç saniye surebilir...
              </span>
            )}
          </div>

          {/* Saved web cameras list */}
          {savedCams.length > 0 && (
            <div className="border-t border-line pt-4">
              <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
                Kayitli Web Kameralari
              </p>
              <ul className="space-y-2">
                {savedCams.map((cam) => (
                  <li
                    key={cam.id}
                    className="flex items-center gap-2 rounded-lg border border-line bg-slate-950/60 px-3 py-2"
                  >
                    <Globe size={14} className="shrink-0 text-slate-500" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-white">{cam.name}</p>
                      <p className="truncate text-xs text-slate-500">{cam.rtsp_url}</p>
                    </div>
                    <button
                      onClick={() => handleConnectExisting(cam)}
                      disabled={loading}
                      className="focus-ring shrink-0 rounded-lg bg-emerald-400/15 px-2.5 py-1 text-xs text-emerald-300 hover:bg-emerald-400/25 disabled:opacity-40"
                    >
                      Baglan
                    </button>
                    <button
                      onClick={() => handleDelete(cam)}
                      disabled={deletingId === cam.id}
                      className="focus-ring shrink-0 rounded-lg p-1.5 text-slate-500 hover:bg-red-400/15 hover:text-red-400 disabled:opacity-40"
                      title="Sil"
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Live view — visible once a camera is active */}
      {activeCam && (
        <>
          <div className="panel flex items-center justify-between gap-3 p-3">
            <div className="flex items-center gap-2.5">
              {connected ? (
                <Wifi size={16} className="text-emerald-400" />
              ) : (
                <WifiOff size={16} className="text-slate-500" />
              )}
              <span className="max-w-xs truncate text-sm font-medium text-white">
                {activeCam.name}
              </span>
              <span className="text-xs text-slate-500">
                {connected ? "WebSocket bagli" : "Beklemede"}
              </span>
            </div>
            <div className="flex gap-2">
              {isRunning ? (
                <button
                  onClick={handleStop}
                  className="focus-ring flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-slate-300 hover:bg-white/5"
                >
                  <Square size={14} /> Durdur
                </button>
              ) : (
                <button
                  onClick={handleRestart}
                  disabled={loading}
                  className="focus-ring flex items-center gap-1.5 rounded-lg bg-emerald-400/20 px-3 py-1.5 text-sm text-emerald-200 disabled:opacity-50"
                >
                  <Play size={14} /> {loading ? "Baslatiliyor..." : "Devam Et"}
                </button>
              )}
              <button
                onClick={handleReset}
                className="focus-ring rounded-lg border border-line px-3 py-1.5 text-sm text-slate-400 hover:bg-white/5"
              >
                Yeni URL
              </button>
              <button
                onClick={() => handleDelete(activeCam)}
                disabled={deletingId === activeCam.id}
                title="Bu kaydi sil"
                className="focus-ring flex items-center gap-1.5 rounded-lg border border-red-400/30 px-3 py-1.5 text-sm text-red-400 hover:bg-red-400/10 disabled:opacity-40"
              >
                <Trash2 size={14} /> Sil
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-sm text-red-300 whitespace-pre-wrap">
              {error}
            </div>
          )}

          <div className="grid gap-4 xl:grid-cols-[1fr_300px]">
            <div ref={videoWrapRef} className="panel relative aspect-video overflow-hidden bg-black">
              {isRunning ? (
                <>
                  {/* Thread 1: ham MJPEG video — analizden bagimsiz, akici akar */}
                  <img
                    className="h-full w-full object-contain"
                    src={`/api/stream/${activeCam.id}/mjpeg`}
                    alt="Canli yayin"
                  />
                  {/* Thread 2 ciktisi: overlay_update ile gelen bounding box'lar */}
                  <canvas
                    ref={canvasRef}
                    className="pointer-events-none absolute inset-0 h-full w-full"
                  />
                </>
              ) : (
                <div className="grid h-full place-items-center text-sm text-slate-500">
                  Yayin durduruldu
                </div>
              )}
            </div>

            <div className={`panel p-4 ${level === "KAVGA" ? "border-red-400/70" : ""}`}>
              {plateToast && (
                <div className="mb-4 rounded-lg border border-cyan-400/40 bg-cyan-400/10 p-3 text-sm text-cyan-100">
                  Plaka: <strong>{plateToast}</strong>
                </div>
              )}
              <div className="mb-4 flex items-center justify-between">
                <span className="text-slate-400">Alarm</span>
                <SeverityBadge value={level} />
              </div>
              <p className="text-5xl font-semibold text-white">
                {score.toFixed(1)}
              </p>
              <dl className="mt-5 space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-400">FPS</dt>
                  <dd>{status.fps ?? "-"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-400">Gecikme</dt>
                  <dd>{status.latency_ms != null ? `${status.latency_ms} ms` : "-"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-400">Kaynak</dt>
                  <dd className="max-w-[140px] truncate text-right text-xs text-slate-400">
                    {activeCam.rtsp_url}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
