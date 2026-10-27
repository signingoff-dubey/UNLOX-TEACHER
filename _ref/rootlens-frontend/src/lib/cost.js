// Savings model from docs/ML_SPEC.md §7, mirrored in the browser so the sliders answer instantly.
// The Python cost.py is the source of truth once it exists; keep the two formulas identical.
//
// avoided_scrap_parts = volume * baseline_fail_rate * relative_reduction       (per day)
// monthly_savings     = avoided_scrap_parts * scrap_cost * days_per_month
//                       - false alarms per month * false_alarm_cost             (only when the model gates parts)
// Output is always {low, mid, high}: a range, never one number (CLAUDE.md rule 8).

export const COST_DEFAULTS = {
  volumePerDay: 1500,
  scrapCostPerPart: 1200,
  falseAlarmCost: 150,
  daysPerMonth: 26,
  falseAlarmRate: 0.02, // share of good parts the gate flags, at the chosen threshold
  gated: true,
};

export const COST_LIMITS = {
  volumePerDay: { min: 100, max: 10000, step: 100 },
  scrapCostPerPart: { min: 50, max: 10000, step: 50 },
  falseAlarmCost: { min: 0, max: 2000, step: 10 },
  daysPerMonth: { min: 1, max: 31, step: 1 },
  falseAlarmRate: { min: 0, max: 0.3, step: 0.01 },
};

const one = (p, baselineFailRate, reduction) => {
  const avoidedPerDay = p.volumePerDay * baselineFailRate * reduction;
  const gross = avoidedPerDay * p.scrapCostPerPart * p.daysPerMonth;
  const falseAlarms = p.gated ? p.volumePerDay * (1 - baselineFailRate) * p.falseAlarmRate * p.daysPerMonth : 0;
  return { avoidedPartsPerMonth: avoidedPerDay * p.daysPerMonth, gross, falseAlarmCost: falseAlarms * p.falseAlarmCost, net: gross - falseAlarms * p.falseAlarmCost };
};

export const monthlySavings = (params, baselineFailRate, reduction) => {
  if (!(baselineFailRate >= 0 && baselineFailRate <= 1)) throw new RangeError('baselineFailRate must be between 0 and 1');
  const p = { ...COST_DEFAULTS, ...params };
  return { low: one(p, baselineFailRate, reduction.low), mid: one(p, baselineFailRate, reduction.mid), high: one(p, baselineFailRate, reduction.high) };
};
