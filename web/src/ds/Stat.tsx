import React from "react";
import { DotNumber } from "./DotNumber";

/** One pill: the number in dots and its label side by side at the same height. */
export const Stat: React.FC<{ value: string | number; label: string; accent?: boolean; size?: number }> = ({ value, label, accent, size = 22 }) => (
  <div className={accent ? "stat accent" : "stat"}>
    <DotNumber value={value} size={size} />
    <span className="stat-label">{label}</span>
  </div>
);

