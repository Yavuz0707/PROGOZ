import { useEffect, useState } from "react";
import { api, unwrap } from "../api/client";
import type { SystemStatus } from "../types";

export default function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  useEffect(() => { unwrap<SystemStatus>(api.get("/system/status")).then(setStatus).catch(console.error); }, []);

  return (
    <section className="space-y-5">
      <div><h2 className="text-2xl font-semibold text-white">Ayarlar</h2><p className="text-sm text-slate-400">Calisma parametreleri .env uzerinden kalici hale getirilir.</p></div>
      <div className="panel grid gap-4 p-4 md:grid-cols-2">
        <label><span className="text-sm text-slate-300">Confidence threshold</span><input readOnly className="mt-2 w-full rounded-lg border border-line bg-slate-950 px-3 py-2" value={status?.confidence ?? ""} /></label>
        <label><span className="text-sm text-slate-300">Frame skip</span><input readOnly className="mt-2 w-full rounded-lg border border-line bg-slate-950 px-3 py-2" value={status?.frame_skip ?? ""} /></label>
        <label><span className="text-sm text-slate-300">Input size</span><input readOnly className="mt-2 w-full rounded-lg border border-line bg-slate-950 px-3 py-2" value={status?.input_size ?? ""} /></label>
        <label><span className="text-sm text-slate-300">CUDA</span><input readOnly className="mt-2 w-full rounded-lg border border-line bg-slate-950 px-3 py-2" value={status?.cuda_available ? status.cuda_device : "CPU fallback"} /></label>
      </div>
      <div className="panel p-4 text-sm text-slate-300">
        <p>Alarm esikleri: NORMAL &lt; 30, SUPHELI &gt;= 30 ve 2 frame, OLASI_KAVGA &gt;= 45 ve 3 frame, KAVGA &gt;= 60 ve 4 frame.</p>
      </div>
    </section>
  );
}

