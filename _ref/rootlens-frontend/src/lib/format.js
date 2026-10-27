// Number formatting shared by the screens. Indian grouping, to match the PS2 frontend.
export const pct = (v, digits = 1) => `${(v * 100).toFixed(digits)}%`;
export const num = (v, digits = 2) => Number(v).toLocaleString('en-IN', { maximumFractionDigits: digits });
export const ci = ([lo, hi], f = (v) => v.toFixed(2)) => `${f(lo)} to ${f(hi)}`;
export const rupees = (v) => `${v < 0 ? '-' : ''}Rs ${Math.abs(Math.round(v)).toLocaleString('en-IN')}`;
