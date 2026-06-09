import assert from "node:assert/strict";
import { test } from "node:test";
import {
  buildR32Pairings,
  buildR32SlotTeams,
  qualifierTeamCodes,
  seedR32FromStandings,
  validateR32SlotTeams,
} from "./r32Seeding.ts";
import { rankThirdPlaced } from "./bracketGroups.ts";

function row(code, points, gd = 0, gf = 0) {
  return {
    code,
    name: code,
    played: 3,
    won: 0,
    drawn: 0,
    lost: 0,
    gf,
    ga: gf - gd,
    gd,
    points,
    rank: 0,
  };
}

function fullStandings() {
  const standings = {};
  const groups = "ABCDEFGHIJKL";
  for (let i = 0; i < groups.length; i++) {
    const group = groups[i];
    const thirdPts = 6 - (i % 5);
    standings[group] = [
      row(`W${group}`, 9, 3, 5),
      row(`R${group}`, 6, 1, 4),
      row(`T${group}`, thirdPts, 0, 2 + (i % 2)),
      row(`L${group}`, 0, -4, 1),
    ];
  }
  return standings;
}

test("save group results -> seed R32 -> 32 unique qualifiers matching saved set", () => {
  const standings = fullStandings();
  const thirdAdvancers = rankThirdPlaced(standings);
  assert.equal(thirdAdvancers.length, 8);

  const slotTeams = seedR32FromStandings(standings, thirdAdvancers);
  assert.equal(Object.keys(slotTeams).length, 32);

  const codes = Object.values(slotTeams);
  assert.equal(new Set(codes).size, 32);

  const expected = qualifierTeamCodes(standings, thirdAdvancers);
  assert.equal(expected.size, 32);
  for (const code of codes) assert.ok(expected.has(code));
  assert.ok(validateR32SlotTeams(slotTeams, standings, thirdAdvancers));
});

test("R32 pairings contain no duplicate teams", () => {
  const standings = fullStandings();
  const thirdAdvancers = rankThirdPlaced(standings);
  const pairings = buildR32Pairings(standings, thirdAdvancers);
  assert.equal(pairings.length, 16);

  const all = pairings.flat();
  assert.equal(all.length, 32);
  assert.equal(new Set(all).size, 32);
});

test("first R32 match is runner-up A vs runner-up B per official template", () => {
  const standings = fullStandings();
  const thirdAdvancers = rankThirdPlaced(standings);
  const pairings = buildR32Pairings(standings, thirdAdvancers);
  assert.deepEqual(pairings[0], ["RA", "RB"]);
});
