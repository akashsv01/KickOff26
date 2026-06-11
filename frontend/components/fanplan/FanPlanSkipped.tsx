"use client";

type Props = {
  notes: string[];
};

export function FanPlanSkipped({ notes }: Props) {
  if (notes.length === 0) return null;

  return (
    <section className="fanplan-skipped" aria-labelledby="fanplan-skipped-heading">
      <div className="fanplan-skipped-header">
        <p id="fanplan-skipped-heading" className="fanplan-skipped-title">
          Not included
        </p>
        <p className="fanplan-skipped-sub">
          Matches skipped by budget, schedule, or city limits - estimates only.
        </p>
      </div>
      <ul className="fanplan-skipped-list">
        {notes.map((note, i) => {
          const dash = note.indexOf(" - ");
          const headline = dash >= 0 ? note.slice(0, dash) : note;
          const reason = dash >= 0 ? note.slice(dash + 3) : "";
          return (
            <li key={i} className="fanplan-skipped-row">
              <span className="fanplan-skipped-dot" aria-hidden="true" />
              <div>
                <p className="fanplan-skipped-match">{headline.replace(/^Skipped\s+/i, "")}</p>
                {reason ? <p className="fanplan-skipped-reason">{reason}</p> : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function FanPlanInfoNotes({ notes }: { notes: string[] }) {
  if (notes.length === 0) return null;
  return (
    <ul className="fanplan-info-notes">
      {notes.map((n, i) => (
        <li key={i}>{n}</li>
      ))}
    </ul>
  );
}
