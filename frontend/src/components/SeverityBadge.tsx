import clsx from "clsx";

const tone: Record<string, string> = {
  KAVGA: "bg-red-500/20 text-red-200 border-red-400/60",
  OLASI_KAVGA: "bg-orange-500/20 text-orange-200 border-orange-400/60",
  SUPHELI: "bg-yellow-500/20 text-yellow-100 border-yellow-400/60",
  NORMAL: "bg-emerald-500/20 text-emerald-200 border-emerald-400/60"
};

export function SeverityBadge({ value }: { value: string }) {
  return <span className={clsx("rounded border px-2 py-1 text-xs font-semibold", tone[value] || tone.NORMAL)}>{value}</span>;
}

