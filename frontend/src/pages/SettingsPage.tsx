import { useEffect, useState } from "react";
import { Cpu, SlidersHorizontal, ShieldAlert } from "lucide-react";
import { api, unwrap } from "../api/client";
import type { SystemStatus } from "../types";

export default function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  useEffect(() => { unwrap<SystemStatus>(api.get("/system/status")).then(setStatus).catch(console.error); }, []);

  // Real system info rows (no mock data) — derived from /system/status
  const sysRows: [string, string][] = [
    ["CONFIDENCE", status ? String(status.confidence) : "-"],
    ["FRAME_SKIP", status ? String(status.frame_skip) : "-"],
    ["INPUT_SIZE", status ? String(status.input_size) : "-"],
    ["MODEL", status?.model || "-"],
    ["DEVICE", status?.cuda_available ? (status.cuda_device || "CUDA") : "CPU fallback"],
    ["TORCH", status?.torch_version || "-"],
    ["OPENCV", status?.opencv_version || "-"],
    ["FFMPEG", status?.ffmpeg_available ? "available" : "missing"],
  ];

  return (
    <section className="space-y-8">
      <div className="border-b border-white/10 pb-4">
        <h2 className="font-display text-[28px] font-bold uppercase tracking-hud text-white">Ayarlar</h2>
        <p className="font-data-mono text-xs text-slate-400">PROGÖZ SYSTEM CONFIGURATION UTILITY</p>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {/* Analysis parameters */}
        <section className="glass-panel p-6">
          <div className="mb-6 flex items-center gap-3">
            <SlidersHorizontal size={18} className="text-white/80" />
            <h3 className="font-headline-sm text-sm uppercase tracking-widestx text-white">Analiz Parametreleri</h3>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-1">
              <span className="font-label-caps text-[10px] text-slate-400">Confidence Threshold</span>
              <input readOnly className="w-full rounded border border-white/15 bg-black/40 px-3 py-2 font-data-mono text-sm text-white" value={status?.confidence ?? ""} />
            </label>
            <label className="space-y-1">
              <span className="font-label-caps text-[10px] text-slate-400">Frame Skip</span>
              <input readOnly className="w-full rounded border border-white/15 bg-black/40 px-3 py-2 font-data-mono text-sm text-white" value={status?.frame_skip ?? ""} />
            </label>
            <label className="space-y-1">
              <span className="font-label-caps text-[10px] text-slate-400">Input Size</span>
              <input readOnly className="w-full rounded border border-white/15 bg-black/40 px-3 py-2 font-data-mono text-sm text-white" value={status?.input_size ?? ""} />
            </label>
            <label className="space-y-1">
              <span className="font-label-caps text-[10px] text-slate-400">CUDA</span>
              <input readOnly className="w-full rounded border border-white/15 bg-black/40 px-3 py-2 font-data-mono text-sm text-white" value={status?.cuda_available ? status.cuda_device : "CPU fallback"} />
            </label>
          </div>
          <p className="mt-4 font-data-mono text-[11px] text-slate-500">
            Çalışma parametreleri <span className="text-white/70">.env</span> üzerinden kalıcı hale getirilir.
          </p>
        </section>

        {/* Alarm thresholds */}
        <section className="glass-panel p-6">
          <div className="mb-6 flex items-center gap-3">
            <ShieldAlert size={18} className="text-white/80" />
            <h3 className="font-headline-sm text-sm uppercase tracking-widestx text-white">Alarm Eşikleri</h3>
          </div>
          <div className="space-y-2">
            {[
              ["NORMAL", "< 30", "text-slate-400"],
              ["ŞÜPHELİ", "≥ 30 · 2 frame", "text-status-amber"],
              ["OLASI KAVGA", "≥ 45 · 3 frame", "text-status-amber"],
              ["KAVGA", "≥ 60 · 4 frame", "text-status-red"],
            ].map(([label, val, color]) => (
              <div key={label} className="flex items-center justify-between border-b border-white/5 py-2.5">
                <span className={`font-label-caps text-[11px] ${color}`}>{label}</span>
                <span className="font-data-mono text-sm text-white">{val}</span>
              </div>
            ))}
          </div>
        </section>

        {/* System info — terminal style, real values only */}
        <section className="glass-panel p-6 xl:col-span-2">
          <div className="mb-6 flex items-center gap-3">
            <Cpu size={18} className="text-white/80" />
            <h3 className="font-headline-sm text-sm uppercase tracking-widestx text-white">Sistem Bilgisi</h3>
          </div>
          <div className="rounded border border-white/5 bg-black/40 p-4 font-data-mono text-[13px] leading-relaxed">
            {sysRows.map(([k, v], i) => (
              <div key={k} className={`flex justify-between py-2 ${i < sysRows.length - 1 ? "border-b border-white/5" : ""}`}>
                <span className="text-slate-500">{k}</span>
                <span className="text-white">{v}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
