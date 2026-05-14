import { FormEvent, useEffect, useState } from "react";
import { Play, Square, Trash2 } from "lucide-react";
import { api, unwrap } from "../api/client";
import type { Camera } from "../types";

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [name, setName] = useState("Webcam Demo");
  const [sourceType, setSourceType] = useState<"webcam" | "rtsp">("webcam");
  const [rtspUrl, setRtspUrl] = useState("");

  const load = () => unwrap<Camera[]>(api.get("/cameras")).then(setCameras).catch(console.error);
  useEffect(() => {
    void load();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    await unwrap<Camera>(api.post("/cameras", { name, source_type: sourceType, rtsp_url: sourceType === "rtsp" ? rtspUrl : null, location: "Demo" }));
    load();
  }

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-white">Kameralar</h2>
        <p className="text-sm text-slate-400">Webcam veya RTSP kaynaklarini yonet.</p>
      </div>
      <form onSubmit={submit} className="panel grid gap-3 p-4 md:grid-cols-[1fr_150px_1fr_auto]">
        <input className="focus-ring rounded-lg border border-line bg-slate-950 px-3 py-2" value={name} onChange={(e) => setName(e.target.value)} />
        <select className="focus-ring rounded-lg border border-line bg-slate-950 px-3 py-2" value={sourceType} onChange={(e) => setSourceType(e.target.value as "webcam" | "rtsp")}>
          <option value="webcam">Webcam</option>
          <option value="rtsp">RTSP</option>
        </select>
        <input className="focus-ring rounded-lg border border-line bg-slate-950 px-3 py-2" placeholder="rtsp://..." value={rtspUrl} onChange={(e) => setRtspUrl(e.target.value)} />
        <button className="focus-ring rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950">Ekle</button>
      </form>
      <div className="grid gap-3">
        {cameras.map((camera) => (
          <div key={camera.id} className="panel flex flex-wrap items-center justify-between gap-3 p-4">
            <div><p className="font-semibold text-white">{camera.name}</p><p className="text-sm text-slate-400">{camera.source_type} {camera.location}</p></div>
            <div className="flex gap-2">
              <button title="Baslat" onClick={() => unwrap(api.post(`/cameras/${camera.id}/start`))} className="focus-ring rounded-lg bg-emerald-400/16 p-2 text-emerald-200"><Play size={18} /></button>
              <button title="Durdur" onClick={() => unwrap(api.post(`/cameras/${camera.id}/stop`))} className="focus-ring rounded-lg bg-yellow-400/16 p-2 text-yellow-100"><Square size={18} /></button>
              <button title="Sil" onClick={() => unwrap(api.delete(`/cameras/${camera.id}`)).then(load)} className="focus-ring rounded-lg bg-red-400/16 p-2 text-red-200"><Trash2 size={18} /></button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
