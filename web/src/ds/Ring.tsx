import React from "react";

/** A thin progress ring (0-1) with its content in the middle. The arc is lime on a light track, like the sliders. */
export const Ring: React.FC<{ value: number; size?: number; stroke?: number; track?: string; color?: string; children?: React.ReactNode; label?: string }> = (
  { value, size = 120, stroke = 8, track = "rgba(255,255,255,0.35)", color = "#fff", children, label },
) => {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.min(Math.max(value, 0), 1);
  return (
    <div className="ring" style={{ width: size, height: size }} role="img" aria-label={label ?? `${Math.round(v * 100)} percent`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - v)} transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.22, 0.9, 0.25, 1)" }} />
      </svg>
      <div className="ring-in">{children}</div>
    </div>
  );
};
