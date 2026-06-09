import { useEffect, useMemo, useState } from "react";
import { Camera, Film, Search, X, ChevronRight } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { assetUrl } from "../api/client";
import { cleanupUnreadablePlates, getPlates, getPlateStats } from "../api/plates";
import type { PlateRecord, PlateStats } from "../types";
import type { Camera as CameraType } from "../types";
import { api, unwrap } from "../api/client";

type SourceItem = {
  key: string;
  label: string;
  type: "video" | "camera";
  count: number;
  lastAt: string;
  jobId?: number;
  cameraId?: number;
};

function buildSources(plates: PlateRecord[], cameras: CameraType[]): SourceItem[] {
  const map = new Map<string, SourceItem>();
  for (const p of plates) {
    if (p.source_type === "video") {
      const key = `video_${p.analysis_job_id}`;
      if (!map.has(key)) {
        map.set(key, {
          key, type: "video",
          label: p.video_filename || `Video #${p.analysis_job_id}`,
          count: 0, lastAt: p.last_seen_at || p.created_at,
          jobId: p.analysis_job_id ?? undefined,
        });
      }
      const s = map.get(key)!;
      s.count++;
      const d = p.last_seen_at || p.created_at;
      if (d > s.lastAt) s.lastAt = d;
    } else {
      const key = `camera_${p.camera_id}`;
      const cam = cameras.find((c) => c.id === p.camera_id);
      if (!map.has(key)) {
        map.set(key, {
          key, type: "camera",
          label: cam?.name || p.camera_name || `Kamera #${p.camera_id}`,
          count: 0, lastAt: p.last_seen_at || p.created_at,
          cameraId: p.camera_id ?? undefined,
        });
      }
      const s = map.get(key)!;
      s.count++;
      const d = p.last_seen_at || p.created_at;
      if (d > s.lastAt) s.lastAt = d;
    }
  }
  return [...map.values()].sort((a, b) => b.lastAt.localeCompare(a.lastAt));
}

function fmtDate(iso?: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function fmtSeconds(s?: number | null) {
  if (s == null) return "-";
  const m = Math.floor(s / 60).toString().padStart(2, "0");
  const sec = (s % 60).toFixed(0).padStart(2, "0");
  return `${m}:${sec}`;
}

function confidenceColor(c: number) {
  if (c >= 0.8) return "text-emerald-400";
  if (c >= 0.5) return "text-yellow-300";
  return "text-red-400";
}

// ——— Detail Modal ———
function PlateModal({ plate, cameras, onClose }: { plate: PlateRecord; cameras: CameraType[]; onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const sourceName = plate.source_type === "video"
    ? (plate.video_filename || `Video #${plate.analysis_job_id}`)
    : (cameras.find((c) => c.id === plate.camera_id)?.name || plate.camera_name || `Kamera #${plate.camera_id}`);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl border border-line bg-slate-900 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <h3 className="font-bold text-lg text-white font-mono">{plate.plate_text_normalized || plate.plate_text_raw}</h3>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 transition">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Snapshot */}
          {(plate.best_snapshot_url || plate.crop_url) && (
            <div className="rounded-xl overflow-hidden bg-slate-800 max-h-52 flex items-center justify-center">
              <img src={assetUrl(plate.best_snapshot_url || plate.crop_url)} className="w-full object-contain max-h-52" alt="plaka" />
            </div>
          )}

          {/* Crop */}
          {plate.crop_url && plate.best_snapshot_url && (
            <div className="rounded-lg overflow-hidden bg-slate-800 h-16 flex items-center justify-center">
              <img src={assetUrl(plate.crop_url)} className="h-full object-contain" alt="crop" />
            </div>
          )}

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[
              ["Ham Metin", plate.plate_text_raw || "-"],
              ["Normalize", plate.plate_text_normalized || "-"],
              ["Format", plate.is_valid_format ? "✓ Geçerli" : "✗ Geçersiz"],
              ["Güven", `%${Math.round(plate.confidence * 100)}`],
              ["OCR Güven", `%${Math.round(plate.ocr_confidence * 100)}`],
              ["Tespit Güven", `%${Math.round(plate.detection_confidence * 100)}`],
              ["Görülme", `${plate.seen_count}x`],
              ["Kaynak", sourceName],
              ["İlk Görülme", plate.source_type === "video" ? fmtSeconds(plate.first_seen_time_seconds) : fmtDate(plate.first_seen_at)],
              ["Son Görülme", plate.source_type === "video" ? fmtSeconds(plate.last_seen_time_seconds) : fmtDate(plate.last_seen_at)],
              ["Frame", plate.frame_index ? `#${plate.frame_index}` : "-"],
              ["OCR Motoru", plate.recognition_source || "-"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg bg-slate-950/60 px-3 py-2">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="text-white font-medium truncate">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ——— Main Page ———
export default function PlatesPage() {
  const [searchParams] = useSearchParams();
  const [plates, setPlates] = useState<PlateRecord[]>([]);
  const [cameras, setCameras] = useState<CameraType[]>([]);
  const [stats, setStats] = useState<PlateStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedKey, setSelectedKey] = useState<string>(() => {
    const jobId = searchParams.get("analysis_job_id");
    const camId = searchParams.get("camera_id");
    if (jobId) return `video_${jobId}`;
    if (camId) return `camera_${camId}`;
    return "__all__";
  });
  const [sourceTab, setSourceTab] = useState<"video" | "camera">("video");
  const [search, setSearch] = useState("");
  const [confidenceFilter, setConfidenceFilter] = useState<"" | "high" | "low">("");
  const [selectedPlate, setSelectedPlate] = useState<PlateRecord | null>(null);
  const [cleanupMsg, setCleanupMsg] = useState("");

  useEffect(() => {
    Promise.all([
      getPlates({ show_unreadable: false }),
      getPlateStats(),
      unwrap<CameraType[]>(api.get("/cameras")),
    ]).then(([ps, st, cams]) => {
      setPlates(ps);
      setStats(st);
      setCameras(cams);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const allSources = useMemo(() => buildSources(plates, cameras), [plates, cameras]);
  const videoSources = useMemo(() => allSources.filter((s) => s.type === "video"), [allSources]);
  const cameraSources = useMemo(() => allSources.filter((s) => s.type === "camera"), [allSources]);
  const currentSources = sourceTab === "video" ? videoSources : cameraSources;

  const filteredPlates = useMemo(() => {
    let list = [...plates];
    if (selectedKey !== "__all__") {
      if (selectedKey.startsWith("video_")) {
        const jobId = Number(selectedKey.replace("video_", ""));
        list = list.filter((p) => p.analysis_job_id === jobId);
      } else if (selectedKey.startsWith("camera_")) {
        const camId = Number(selectedKey.replace("camera_", ""));
        list = list.filter((p) => p.camera_id === camId);
      }
    }
    if (search) {
      const q = search.toUpperCase();
      list = list.filter((p) => (p.plate_text_normalized || p.plate_text_raw || "").toUpperCase().includes(q));
    }
    if (confidenceFilter === "high") list = list.filter((p) => p.confidence >= 0.8);
    if (confidenceFilter === "low") list = list.filter((p) => p.confidence < 0.5);
    return list.sort((a, b) => (b.last_seen_at || b.created_at).localeCompare(a.last_seen_at || a.created_at));
  }, [plates, selectedKey, search, confidenceFilter]);

  async function handleCleanup() {
    try {
      const result = await cleanupUnreadablePlates();
      setCleanupMsg(`${result.deleted} kayıt temizlendi.`);
      const fresh = await getPlates({ show_unreadable: false });
      setPlates(fresh);
    } catch {
      setCleanupMsg("Admin yetkisi gerekli.");
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-white">Plakalar</h2>
          <p className="text-sm text-slate-400">Kaynağa göre filtrelenebilir plaka kayıtları</p>
        </div>
        {/* Stats Row */}
        <div className="hidden xl:flex items-center gap-5 text-sm">
          {[
            ["Toplam", stats?.total ?? plates.length],
            ["Bugün", stats?.today ?? "-"],
            ["Geçerli", stats?.valid ?? "-"],
          ].map(([label, value]) => (
            <div key={String(label)} className="text-center">
              <p className="text-slate-400 text-xs">{label}</p>
              <p className="text-white font-semibold">{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        {/* LEFT PANEL */}
        <aside className="space-y-2">
          {/* Tabs */}
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

          <button
            onClick={() => setSelectedKey("__all__")}
            className={`w-full rounded-xl border px-3 py-2.5 text-left text-sm transition ${selectedKey === "__all__" ? "border-cyan-400/60 bg-cyan-400/10 text-white" : "border-line bg-slate-900 text-slate-300 hover:border-slate-600"}`}
          >
            <span className="font-medium">Tüm Kaynaklar</span>
            <span className="ml-2 rounded-full bg-slate-700 px-1.5 py-0.5 text-xs">{plates.length}</span>
          </button>

          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="rounded-xl border border-line bg-slate-900 p-3 animate-pulse space-y-1.5">
                  <div className="h-3 w-3/4 rounded bg-slate-700" />
                  <div className="h-3 w-1/2 rounded bg-slate-800" />
                </div>
              ))
            : currentSources.length === 0 ? (
              <p className="rounded-xl border border-line bg-slate-900 p-4 text-sm text-slate-500 text-center">
                {sourceTab === "video" ? "Video kaydı yok" : "Kamera kaydı yok"}
              </p>
            ) : (
              currentSources.map((src) => (
                <button
                  key={src.key}
                  onClick={() => setSelectedKey(src.key)}
                  className={`w-full rounded-xl border px-3 py-2.5 text-left transition ${selectedKey === src.key ? "border-cyan-400/60 bg-cyan-400/10" : "border-line bg-slate-900 hover:border-slate-600"}`}
                >
                  <div className="flex items-start justify-between gap-1">
                    <p className={`text-sm font-medium truncate ${selectedKey === src.key ? "text-white" : "text-slate-200"}`}>
                      {src.label}
                    </p>
                    <span className="shrink-0 rounded-full bg-cyan-400/20 px-1.5 py-0.5 text-xs text-cyan-300">
                      {src.count}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">{fmtDate(src.lastAt)}</p>
                </button>
              ))
            )}

          {/* Cleanup */}
          <div className="pt-2">
            <button
              onClick={handleCleanup}
              className="w-full rounded-lg border border-red-400/30 bg-red-400/8 px-3 py-2 text-xs text-red-300 hover:bg-red-400/15 transition"
            >
              Okunamayan kayıtları temizle
            </button>
            {cleanupMsg && <p className="mt-1 text-xs text-slate-500 text-center">{cleanupMsg}</p>}
          </div>
        </aside>

        {/* RIGHT PANEL */}
        <div className="space-y-3">
          {/* Search + Filter bar */}
          <div className="flex flex-wrap gap-2">
            <label className="flex items-center gap-2 rounded-lg border border-line bg-slate-900 px-3 py-2 flex-1 min-w-40">
              <Search size={14} className="text-slate-500 shrink-0" />
              <input
                className="min-w-0 flex-1 bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-600"
                placeholder="Plaka ara (örn: 34ABC)"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              {search && (
                <button onClick={() => setSearch("")} className="text-slate-500 hover:text-slate-300">
                  <X size={14} />
                </button>
              )}
            </label>
            {[
              { label: "Tümü", value: "" as const },
              { label: "Yüksek güven (>%80)", value: "high" as const },
              { label: "Düşük güven (<50%)", value: "low" as const },
            ].map((f) => (
              <button
                key={f.value}
                onClick={() => setConfidenceFilter(f.value)}
                className={`rounded-lg px-3 py-2 text-sm transition ${confidenceFilter === f.value ? "bg-cyan-400 text-slate-950 font-semibold" : "border border-line bg-slate-900 text-slate-300 hover:border-slate-500"}`}
              >
                {f.label}
              </button>
            ))}
            <span className="ml-auto self-center text-sm text-slate-500">{filteredPlates.length} plaka</span>
          </div>

          {/* Plate Cards */}
          {loading ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="rounded-xl border border-line bg-slate-900 p-4 animate-pulse space-y-2">
                  <div className="h-12 rounded-lg bg-slate-700 w-full" />
                  <div className="h-4 w-2/3 rounded bg-slate-700" />
                  <div className="h-3 w-1/2 rounded bg-slate-800" />
                </div>
              ))}
            </div>
          ) : filteredPlates.length === 0 ? (
            <div className="rounded-xl border border-line bg-slate-900 p-10 text-center">
              <Search size={32} className="mx-auto mb-3 text-slate-600" />
              <p className="text-slate-400">Plaka bulunamadı</p>
              <p className="text-sm text-slate-600 mt-1">Arama kriterini veya kaynağı değiştirin</p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {filteredPlates.map((plate) => {
                const sourceName = plate.source_type === "video"
                  ? (plate.video_filename || `Video #${plate.analysis_job_id}`)
                  : (cameras.find((c) => c.id === plate.camera_id)?.name || plate.camera_name || `Kamera #${plate.camera_id}`);
                return (
                  <button
                    key={plate.id}
                    onClick={() => setSelectedPlate(plate)}
                    className="rounded-xl border border-line bg-slate-900 p-4 text-left hover:border-slate-600 hover:bg-slate-800/60 transition group"
                  >
                    {/* Crop Image */}
                    {(plate.crop_url || plate.best_snapshot_url) && (
                      <div className="mb-3 h-12 rounded-lg overflow-hidden bg-slate-800">
                        <img
                          src={assetUrl(plate.crop_url || plate.best_snapshot_url)}
                          className="w-full h-full object-cover"
                          alt="plaka crop"
                        />
                      </div>
                    )}

                    {/* Plate Text */}
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-base font-bold text-white tracking-widest">
                        {plate.plate_text_normalized || plate.plate_text_raw || "?"}
                      </span>
                      <ChevronRight size={14} className="text-slate-600 group-hover:text-slate-400 transition" />
                    </div>

                    {/* Confidence */}
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-sm font-semibold ${confidenceColor(plate.confidence)}`}>
                        %{Math.round(plate.confidence * 100)}
                      </span>
                      <span className={`rounded px-1.5 py-0.5 text-xs ${plate.status === "valid" ? "bg-emerald-400/16 text-emerald-300" : "bg-yellow-400/16 text-yellow-200"}`}>
                        {plate.status === "valid" ? "Geçerli" : "Belirsiz"}
                      </span>
                    </div>

                    {/* Meta */}
                    <div className="text-xs text-slate-500 space-y-0.5">
                      <p className="truncate">{sourceName}</p>
                      <p>
                        {plate.seen_count}x görüldü ·{" "}
                        {plate.source_type === "video"
                          ? fmtSeconds(plate.first_seen_time_seconds)
                          : fmtDate(plate.first_seen_at)}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      {selectedPlate && (
        <PlateModal plate={selectedPlate} cameras={cameras} onClose={() => setSelectedPlate(null)} />
      )}
    </section>
  );
}
