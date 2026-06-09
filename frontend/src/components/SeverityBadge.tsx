type ToneStyle = { background: string; color: string; borderColor: string };

const tone: Record<string, ToneStyle> = {
  KAVGA:       { background: "rgba(239,68,68,0.12)",  color: "#ef4444",  borderColor: "rgba(239,68,68,0.35)"  },
  OLASI_KAVGA: { background: "rgba(245,158,11,0.12)", color: "#f59e0b",  borderColor: "rgba(245,158,11,0.3)"  },
  SUPHELI:     { background: "rgba(136,136,136,0.1)", color: "#888888",  borderColor: "rgba(136,136,136,0.25)"},
  NORMAL:      { background: "#141414",               color: "#555555",  borderColor: "#2a2a2a"               },
};

export function SeverityBadge({ value }: { value: string }) {
  const style = tone[value] ?? tone.NORMAL;
  return (
    <span
      className="rounded border px-2 py-1 text-xs font-semibold"
      style={style}
    >
      {value}
    </span>
  );
}
