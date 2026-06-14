import { useEffect, useState } from "react";
import { Globe, Play, Square, Trash2, Wifi, WifiOff } from "lucide-react";
import { api, unwrap } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { useWebSocket } from "../hooks/useWebSocket";
import type { Camera } from "../types";

type LiveMsg = {
  type: string;
  camera_id?: number;
  fps?: number;
  latency_ms?: number;
  alarm_level?: string;
  score?: number;
  plate?: string;
  confidence?: number;
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
  const level = lastMessage?.alarm_level ?? "NORMAL";

  // Load existing web cameras on mount
  useEffect(() => {
    loadSavedCams();
  }, []);

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
      <div>
        <h2 className="text-2xl font-semibold text-white">Web Yayini</h2>
        <p className="text-sm text-slate-400">
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
            <div className="panel aspect-video overflow-hidden bg-black">
              {isRunning ? (
                <img
                  className="h-full w-full object-contain"
                  src={`/api/stream/${activeCam.id}/mjpeg`}
                  alt="Canli yayin"
                />
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
                {(lastMessage?.score ?? 0).toFixed(1)}
              </p>
              <dl className="mt-5 space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-400">FPS</dt>
                  <dd>{lastMessage?.fps ?? "-"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-400">Gecikme</dt>
                  <dd>{lastMessage?.latency_ms != null ? `${lastMessage.latency_ms} ms` : "-"}</dd>
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
