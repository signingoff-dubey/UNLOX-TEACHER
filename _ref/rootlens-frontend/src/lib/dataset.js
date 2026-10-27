// Public facts about the demo dataset that the API does not return. Everything numeric comes from /api/overview.
export const DATASET = { name: 'SECOM', line: 'Semiconductor fab line (anonymised)' };

// "2008-10-05 19:45:00" -> "2008-10-05"
export const day = (ts) => ts.slice(0, 10);
