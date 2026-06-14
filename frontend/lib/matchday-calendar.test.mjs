/**
 * Calendar bucketing invariant (mirrors frontend/lib/matchday.ts).
 * A match's calendar DAY is its UTC kickoff bucketed in the ACTIVE display zone -
 * the same zone used to show kickoff times - never local_date or a UTC slice.
 * Run: node --test lib/matchday-calendar.test.mjs
 */

import test from "node:test";
import assert from "node:assert/strict";

function getMatchLocalDate(iso, zone) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-CA", zone ? { timeZone: zone } : undefined);
}

function matchDateKey(match, zone) {
  return getMatchLocalDate(match.kickoff_at, zone) ?? match.local_date ?? null;
}

function matchesForDay(matches, day, zone) {
  return matches.filter((m) => matchDateKey(m, zone) === day);
}

function dayCountsFromMatches(matches, zone) {
  const counts = {};
  for (const m of matches) {
    const key = matchDateKey(m, zone);
    if (key) counts[key] = (counts[key] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([date, match_count]) => ({ date, match_count }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

test("day badge counts match the rendered day lists (in the active zone)", () => {
  const zone = "America/New_York";
  const matches = [
    { kickoff_at: "2026-06-11T19:00:00+00:00" },
    { kickoff_at: "2026-06-12T02:00:00+00:00" },
    { kickoff_at: "2026-06-12T23:00:00+00:00" },
  ];
  const days = dayCountsFromMatches(matches, zone);
  for (const day of days) {
    assert.equal(matchesForDay(matches, day.date, zone).length, day.match_count, day.date);
  }
});

test("buckets by kickoff in the active zone, not local_date or UTC", () => {
  // 13 Jun 19:00 UTC == 14 Jun 00:30 in Asia/Kolkata (UTC+5:30).
  const match = { local_date: "2026-06-13", kickoff_at: "2026-06-13T19:00:00+00:00" };
  assert.equal(matchDateKey(match, "Asia/Kolkata"), "2026-06-14"); // counts under the 14th
  assert.notEqual(matchDateKey(match, "Asia/Kolkata"), match.local_date);
});

test("the same match buckets to different days in different countries' zones", () => {
  const match = { kickoff_at: "2026-06-14T00:30:00+00:00" };
  assert.equal(matchDateKey(match, "America/New_York"), "2026-06-13"); // 13 Jun 20:30 EDT
  assert.equal(matchDateKey(match, "Asia/Tokyo"), "2026-06-14"); // 14 Jun 09:30 JST
});

function localTodayKey(zone, now = new Date()) {
  return now.toLocaleDateString("en-CA", zone ? { timeZone: zone } : undefined);
}

function defaultMatchDay(dates, zone, now = new Date()) {
  if (!dates.length) return "";
  const today = localTodayKey(zone, now);
  const window = { start: "2026-06-11", end: "2026-07-19" };
  const inWindow = today >= window.start && today <= window.end;
  if (inWindow && dates.includes(today)) return today;
  if (inWindow) {
    const future = dates.find((d) => d >= today);
    if (future) return future;
  }
  return dates[0];
}

test("localTodayKey resolves the day in the active zone", () => {
  // 2026-06-14T00:30Z: still the 13th in New York, already the 14th in Tokyo.
  const now = new Date("2026-06-14T00:30:00+00:00");
  assert.equal(localTodayKey("America/New_York", now), "2026-06-13");
  assert.equal(localTodayKey("Asia/Tokyo", now), "2026-06-14");
});

test("defaultMatchDay aligns with today's zone-bucketed date", () => {
  const now = new Date("2026-06-14T00:30:00+00:00");
  const dates = ["2026-06-13", "2026-06-14"];
  assert.equal(defaultMatchDay(dates, "America/New_York", now), "2026-06-13");
  assert.equal(defaultMatchDay(dates, "Asia/Tokyo", now), "2026-06-14");
});
