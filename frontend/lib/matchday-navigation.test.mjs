/**
 * MatchDay navigation + notification filtering tests.
 * Run: node --test lib/matchday-navigation.test.mjs
 */

import test from "node:test";
import assert from "node:assert/strict";

function matchDetailHref(matchId) {
  if (!Number.isFinite(matchId) || matchId <= 0) return "/matchday";
  return `/matchday/${matchId}`;
}

function navigateToMatchDetail(navigate, matchId) {
  navigate(matchDetailHref(matchId));
}

const PROB_SWING_THRESHOLD = 0.15;

const MEANINGFUL_ALERT_TYPES = new Set([
  "goal_alert",
  "yellow_card_alert",
  "red_card_alert",
  "substitution_alert",
  "penalty_alert",
  "var_alert",
  "match_start_alert",
  "match_halftime_alert",
  "match_end_alert",
  "momentum_alert",
]);

function shouldShowAlert(data) {
  const type = String(data.type ?? "");
  if (!MEANINGFUL_ALERT_TYPES.has(type)) return false;
  if (type === "momentum_alert") {
    const shift = typeof data.shift === "number" ? data.shift : 0;
    return shift >= PROB_SWING_THRESHOLD;
  }
  return Boolean(data.message);
}

test("matchDetailHref builds detail route from match id", () => {
  assert.equal(matchDetailHref(42), "/matchday/42");
  assert.equal(matchDetailHref(1), "/matchday/1");
});

test("matchDetailHref rejects invalid ids", () => {
  assert.equal(matchDetailHref(0), "/matchday");
  assert.equal(matchDetailHref(NaN), "/matchday");
});

test("navigateToMatchDetail pushes canonical href", () => {
  let pushed = null;
  navigateToMatchDetail((href) => {
    pushed = href;
  }, 7);
  assert.equal(pushed, "/matchday/7");
});

test("clicking a match card should target its detail href", () => {
  const matchId = 104;
  const href = matchDetailHref(matchId);
  const navigated = [];
  navigateToMatchDetail((h) => navigated.push(h), matchId);
  assert.deepEqual(navigated, [href]);
  assert.match(href, /^\/matchday\/\d+$/);
});

test("shouldShowAlert allows free-tier supported types", () => {
  assert.equal(shouldShowAlert({ type: "goal_alert", message: "GOAL!" }), true);
  assert.equal(shouldShowAlert({ type: "yellow_card_alert", message: "YELLOW" }), true);
  assert.equal(shouldShowAlert({ type: "red_card_alert", message: "RED" }), true);
  assert.equal(shouldShowAlert({ type: "substitution_alert", message: "SUB" }), true);
  assert.equal(shouldShowAlert({ type: "penalty_alert", message: "PEN" }), true);
  assert.equal(shouldShowAlert({ type: "var_alert", message: "VAR" }), true);
  assert.equal(shouldShowAlert({ type: "match_start_alert", message: "KICK OFF" }), true);
  assert.equal(shouldShowAlert({ type: "match_halftime_alert", message: "HALF TIME" }), true);
  assert.equal(shouldShowAlert({ type: "match_end_alert", message: "FULL TIME" }), true);
});

test("shouldShowAlert suppresses sub-15% momentum ticks", () => {
  assert.equal(
    shouldShowAlert({ type: "momentum_alert", message: "small", shift: 0.05 }),
    false
  );
  assert.equal(
    shouldShowAlert({ type: "momentum_alert", message: "big swing", shift: 0.15 }),
    true
  );
});

test("shouldShowAlert rejects unsupported play-by-play types", () => {
  assert.equal(shouldShowAlert({ type: "corner_alert", message: "Corner" }), false);
  assert.equal(shouldShowAlert({ type: "shot_alert", message: "Shot" }), false);
  assert.equal(shouldShowAlert({ type: "foul_alert", message: "Foul" }), false);
  assert.equal(shouldShowAlert({ type: "tick", message: "noise" }), false);
});
