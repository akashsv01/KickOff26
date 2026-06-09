/**
 * Calendar bucketing invariant (mirrors frontend/lib/matchday.ts).
 * Run: node --test lib/matchday-calendar.test.mjs
 */

import test from "node:test";
import assert from "node:assert/strict";

function matchDateKey(match) {
  return match.local_date ?? null;
}

function matchesForDay(matches, day) {
  return matches.filter((m) => matchDateKey(m) === day);
}

function dayCountsFromMatches(matches) {
  const counts = {};
  for (const m of matches) {
    const key = matchDateKey(m);
    if (key) counts[key] = (counts[key] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([date, match_count]) => ({ date, match_count }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

test("day badge counts match rendered lists", () => {
  const matches = [
    { local_date: "2026-06-11", kickoff_at: "2026-06-11T19:00:00+00:00" },
    { local_date: "2026-06-11", kickoff_at: "2026-06-12T02:00:00+00:00" },
    { local_date: "2026-06-12", kickoff_at: "2026-06-12T19:00:00+00:00" },
  ];
  const days = dayCountsFromMatches(matches);
  for (const day of days) {
    const rendered = matchesForDay(matches, day.date);
    assert.equal(rendered.length, day.match_count, day.date);
  }
});

test("ignores utc kickoff when local_date is set", () => {
  const match = {
    local_date: "2026-06-11",
    kickoff_at: "2026-06-12T02:00:00+00:00",
  };
  assert.equal(matchDateKey(match), "2026-06-11");
  assert.equal(matchesForDay([match], "2026-06-11").length, 1);
  assert.equal(matchesForDay([match], "2026-06-12").length, 0);
});
