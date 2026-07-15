import { Link } from "react-router-dom";
import { Flag, FullPageLoader, Pill, StatTile } from "../components.jsx";
import { pct0, usePredictions } from "../data.js";

const CHECKS = [
  ["weather", "Weather", "Weather/venue context", (match) => Boolean(match.intelligence?.weather)],
  ["teamStats", "Team stats", "ESPN team statistics", (match) => Boolean(match.intelligence?.teamStats?.home && match.intelligence?.teamStats?.away)],
  ["availability", "Team news", "Availability/injury/suspension coverage", (match) => Boolean(match.intelligence?.availability?.length || match.intelligence?.availabilityCoverage?.length)],
  ["lineups", "Lineups", "FIFA match sheet / confirmed lineup", (match) => Boolean(match.intelligence?.lineups?.home?.length && match.intelligence?.lineups?.away?.length)],
  ["h2h", "H2H", "Historical meetings", (match) => Boolean(match.intelligence?.h2h?.length)],
  ["odds", "Odds", "Market prices", (match) => Boolean(match.intelligence?.odds?.length)],
  ["referee", "Referee", "Referee profile", (match) => Boolean(match.intelligence?.referee)],
  ["route", "Route", "Recent tournament route", (match) => Boolean(match.intelligence?.route?.home?.length && match.intelligence?.route?.away?.length)],
];

export default function SourceGaps() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat source gaps.</div>;
  if (!data) return <FullPageLoader text="Memuat source gaps" />;

  const rows = buildRows(data.matches || []);
  const complete = rows.filter((row) => row.missing.length === 0).length;
  const gaps = rows.reduce((sum, row) => sum + row.missing.length, 0);
  const bySource = CHECKS.map(([key, label]) => ({
    key,
    label,
    missing: rows.filter((row) => row.missing.some((item) => item.key === key)).length,
  }));

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Source gaps</Pill>
          <h1>Data Gaps</h1>
          <p className="page-sub">
            Audit cepat field yang hilang per pertandingan. Halaman ini berguna
            sebelum membuat narasi AI supaya analisis tidak dangkal.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Matches checked" value={rows.length} />
          <StatTile label="Complete" value={complete} tone="home" />
          <StatTile label="Open gaps" value={gaps} tone={gaps ? "away" : "home"} />
        </div>
      </div>

      <section className="gap-strip">
        {bySource.map((item) => (
          <div className={`gap-source ${item.missing ? "warn" : "ok"}`} key={item.key}>
            <span>{item.label}</span>
            <strong>{item.missing ? `${item.missing} gaps` : "OK"}</strong>
          </div>
        ))}
      </section>

      <div className="gap-list">
        {rows.map((row) => (
          <article className={`gap-card ${row.missing.length ? "warn" : "ok"}`} key={row.match.id}>
            <div className="gap-card-head">
              <div>
                <strong><Flag team={row.match.home} /> {row.match.home} vs {row.match.away} <Flag team={row.match.away} /></strong>
                <span>{row.match.round} / {row.match.venue}</span>
              </div>
              <Pill tone={row.missing.length ? "danger" : "live"}>{pct0(row.score)}</Pill>
            </div>
            <div className="quality-checks">
              {CHECKS.map(([key, label]) => (
                <span className={row.missing.some((item) => item.key === key) ? "missing" : "ok"} key={key}>
                  {label}
                </span>
              ))}
            </div>
            <div className="quality-foot">
              <span>{row.missing.length ? row.missing.map((item) => item.description).join(", ") : "Semua konteks utama tersedia."}</span>
              <Link to={`/match/${row.match.id}`}>Match detail</Link>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}

function buildRows(matches) {
  return matches.map((match) => {
    const missing = CHECKS
      .filter(([, , , isPresent]) => !isPresent(match))
      .map(([key, label, description]) => ({ key, label, description }));
    return {
      match,
      missing,
      score: (CHECKS.length - missing.length) / CHECKS.length,
    };
  });
}
