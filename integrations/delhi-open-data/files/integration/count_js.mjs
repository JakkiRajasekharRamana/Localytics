// Parity helper for test_advisor.py: run web/src/filters.js on the real data for each criteria set and print the matching ids.
// usage: node count_js.mjs <ncr.json> <criteria.json>
import { readFileSync } from 'node:fs';
import { DEFAULT_CRITERIA, matchSociety } from '../web/src/filters.js';

const [dataPath, criteriaPath] = process.argv.slice(2);
const societies = JSON.parse(readFileSync(dataPath, 'utf8')).societies;
const cases = JSON.parse(readFileSync(criteriaPath, 'utf8'));
const out = cases.map((c) => {
  const crit = { ...structuredClone(DEFAULT_CRITERIA), ...c };
  return societies.filter((s) => ['match', 'likely', 'probable'].includes(matchSociety(s, crit))).map((s) => s.id).sort();
});
process.stdout.write(JSON.stringify(out));
