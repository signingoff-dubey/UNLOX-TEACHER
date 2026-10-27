import { test } from 'node:test';
import assert from 'node:assert/strict';
import { monthlySavings } from '../src/lib/cost.js';

const R = { low: 0.1, mid: 0.2, high: 0.3 };

test('ungated: savings follow the ML_SPEC formula', () => {
  const s = monthlySavings({ volumePerDay: 1000, scrapCostPerPart: 100, daysPerMonth: 20, gated: false }, 0.05, R);
  // 1000 * 0.05 * 0.2 = 10 parts/day, * 100 * 20 = 20000
  assert.equal(s.mid.net, 20000);
  assert.equal(s.mid.avoidedPartsPerMonth, 200);
  assert.equal(s.mid.falseAlarmCost, 0);
});

test('always a range, ordered low <= mid <= high', () => {
  const s = monthlySavings({}, 0.066, R);
  assert.ok(s.low.net <= s.mid.net && s.mid.net <= s.high.net);
});

test('gating subtracts false-alarm cost, can go negative', () => {
  const s = monthlySavings({ volumePerDay: 1000, scrapCostPerPart: 10, falseAlarmCost: 100, falseAlarmRate: 0.1, daysPerMonth: 1, gated: true }, 0.05, R);
  // gross 1000*0.05*0.2*10 = 100; false alarms 1000*0.95*0.1 = 95 * 100 = 9500
  assert.equal(s.mid.gross, 100);
  assert.equal(s.mid.falseAlarmCost, 9500);
  assert.ok(s.mid.net < 0);
});

test('rejects a fail rate outside 0..1', () => {
  assert.throws(() => monthlySavings({}, 1.5, R), RangeError);
});
