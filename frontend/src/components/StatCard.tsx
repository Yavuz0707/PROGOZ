import type { LucideIcon } from "lucide-react";

type Props = {
  label: string;
  value: string | number;
  detail?: string;
  icon: LucideIcon;
};

export function StatCard({ label, value, detail, icon: Icon }: Props) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-slate-400">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
        </div>
        <div className="grid h-11 w-11 place-items-center rounded-lg bg-cyan-400/12 text-cyan-200">
          <Icon size={22} />
        </div>
      </div>
      {detail && <p className="mt-3 text-xs text-slate-400">{detail}</p>}
    </div>
  );
}

