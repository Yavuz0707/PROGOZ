import { useEffect, useState } from "react";
import { Users, ShieldAlert } from "lucide-react";
import { api, unwrap, assetUrl } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";
import { useWebSocket } from "../hooks/useWebSocket";
import type { Camera } from "../types";

type LivePerson = { id: number; crop: string | null; age_sec: number; flagged: boolean; level: string };
type SavedPerson = {
  id: number;
  camera_id: number | null;
  camera_name: string | null;
  track_id: number;
  level: string;
  score: number | null;
  crop: string | null;
  detected_at: string | null;
};
type PersonsMsg = { type: string; camera_id?: number; persons?: LivePerson[] };

export default function PersonTrackingPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [camId, setCamId] = useState<number | null>(null);
  const [live, setLive] = useState<LivePerson[]>([]);
  const [saved, setSaved] = useState<SavedPerson[]>([]);

  const { lastMessage, connected } = useWebSocket<PersonsMsg>(camId ? `/ws/live/${camId}` : null);

  // Kameralari yukle (web + webcam); ilkini sec
  useEffect(() => {
    unwrap<Camera[]>(api.get("/cameras"))
      .then((cams) => {
        setCameras(cams);
        if (cams.length && camId === null) setCamId(cams[0].id);
      })
      .catch(() => {});
  }, []);

  // Canli persons_update mesajlari
  useEffect(() => {
    if (lastMessage?.type === "persons_update") setLive(lastMessage.persons ?? []);
  }, [lastMessage]);

  // Kamera degisince canli listeyi sifirla
  useEffect(() => {
    setLive([]);
  }, [camId]);

  // Kaydedilen (anomaliye karisan) kisileri periyodik cek
  useEffect(() => {
    let active = true;
    const load = () => {
      const params = camId ? { camera_id: camId } : {};
      unwrap<{ items: SavedPerson[] }>(api.get("/tracked-persons", { params }))
        .then((d) => active && setSaved(d.items ?? []))
        .catch(() => {});
    };
    load();
    const t = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [camId]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">KİŞİ TAKİBİ</h1>
        <p className="text-sm text-slate-400">
          Görüntüdeki her kişi ayrı ID alır; anomaliye karışan kişiler otomatik kaydedilir, karışmayanlar 60 sn sonra silinir.
        </p>
      </div>

      {/* Kamera secici */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-400">Kamera:</span>
        <select
          value={camId ?? ""}
          onChange={(e) => setCamId(Number(e.target.value))}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none"
        >
          {cameras.length === 0 && <option value="">Kamera yok</option>}
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.source_type})
            </option>
          ))}
        </select>
        <span className={`text-xs ${connected ? "text-emerald-400" : "text-slate-500"}`}>
          {connected ? "● canlı bağlı" : "○ bağlı değil"}
        </span>
      </div>

      {/* Canli takip */}
      <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
        <div className="mb-4 flex items-center gap-2">
          <Users size={18} className="text-indigo-400" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Canlı Takip ({live.length} kişi)
          </h2>
        </div>
        {live.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            Şu an takip edilen kişi yok. (Kamerayı <span className="text-slate-300">Web Yayını</span> sayfasından başlatın.)
          </p>
        ) : (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8">
            {live.map((p) => (
              <div
                key={p.id}
                className={`overflow-hidden rounded-xl border ${
                  p.flagged ? "border-red-500" : "border-slate-700"
                } bg-slate-950`}
              >
                <div className="aspect-[3/4] w-full bg-slate-800">
                  {p.crop ? (
                    <img src={assetUrl(p.crop) ?? undefined} alt={`ID ${p.id}`} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-slate-600">…</div>
                  )}
                </div>
                <div className="flex items-center justify-between px-2 py-1.5">
                  <span className="font-mono text-xs font-bold text-white">ID {p.id}</span>
                  <span className="text-[10px] text-slate-400">{p.age_sec}s</span>
                </div>
                {p.flagged && (
                  <div className="px-2 pb-1.5">
                    <SeverityBadge value={p.level} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Anomaliye karisip kaydedilenler */}
      <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
        <div className="mb-4 flex items-center gap-2">
          <ShieldAlert size={18} className="text-red-400" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Anomaliye Karışanlar — Kaydedilenler ({saved.length})
          </h2>
        </div>
        {saved.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">Henüz kaydedilmiş anomali kişisi yok.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {saved.map((p) => (
              <div key={p.id} className="overflow-hidden rounded-xl border border-slate-700 bg-slate-950">
                <div className="aspect-[3/4] w-full bg-slate-800">
                  {p.crop ? (
                    <img src={assetUrl(p.crop) ?? undefined} alt={`ID ${p.track_id}`} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs text-slate-600">resim yok</div>
                  )}
                </div>
                <div className="space-y-1 px-2 py-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-white">ID {p.track_id}</span>
                    <SeverityBadge value={p.level} />
                  </div>
                  <div className="text-[10px] text-slate-400">{p.camera_name ?? `Kamera ${p.camera_id ?? "-"}`}</div>
                  <div className="text-[10px] text-slate-500">
                    {p.detected_at ? new Date(p.detected_at).toLocaleString("tr-TR") : ""}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
