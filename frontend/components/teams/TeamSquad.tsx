"use client";

import { FootballLoader } from "@/components/FootballLoader";
import type { SquadPlayer, TeamProfile } from "@/lib/teams";
import { SQUAD_POSITION_LABELS, SQUAD_POSITION_ORDER } from "@/lib/teams";

function SquadTable({ players }: { players: SquadPlayer[] }) {
  return (
    <div className="squad-table-wrap">
      <table className="squad-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Player</th>
            <th>Club</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => (
            <tr key={`${p.jersey ?? "x"}-${p.name}`}>
              <td className="squad-num">{p.jersey ?? "-"}</td>
              <td className="squad-name">
                {p.name}
                {p.is_captain ? <span className="squad-captain-badge">C</span> : null}
              </td>
              <td className="squad-club">{p.club ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TeamSquadBlock({ profile }: { profile: TeamProfile }) {
  const { squad } = profile;

  if (squad.status === "loading") {
    return (
      <div className="squad-state">
        <FootballLoader size="sm" label="Loading squad…" />
      </div>
    );
  }

  if (squad.status === "unavailable") {
    return (
      <div className="squad-placeholder">
        <div className="squad-placeholder-title">Squad not yet available</div>
        <p className="squad-placeholder-copy">
          Zafronix has not published a full roster for this team yet. Check back closer to the
          tournament.
        </p>
      </div>
    );
  }

  const groups = SQUAD_POSITION_ORDER.filter(
    (pos) => (squad.players_by_position[pos]?.length ?? 0) > 0
  );

  if (groups.length === 0) {
    return (
      <div className="squad-placeholder">
        <div className="squad-placeholder-title">Squad not yet available</div>
      </div>
    );
  }

  return (
    <div className="squad-groups">
      {groups.map((pos) => (
        <section key={pos} className="squad-group md-glass">
          <h3 className="squad-group-title">{SQUAD_POSITION_LABELS[pos] ?? pos}</h3>
          <SquadTable players={squad.players_by_position[pos] ?? []} />
        </section>
      ))}
    </div>
  );
}
