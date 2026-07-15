import { Link } from "react-router-dom";
import { Flag, FullPageLoader, Pill, StatTile } from "../components.jsx";
import { pct0, usePredictions } from "../data.js";

const CHECKS = [
  ["weather", "Cuaca"],
  ["teamStats", "Stat tim"],
  ["availability", "Team news"],
  ["lineups", "Lineups"],
  ["h2h", "H2H"],
  ["odds", "Odds"],
  ["referee", "Referee"],
  ["route", "Route"],
];

export default function DataQuality() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat data quality.</div>;
  if (!data) return <FullPageLoader text="Memuat data quality" />;

  const rows = (data.matches || []).map(scoreMatchQuality);
  const avg = rows.length ? rows.reduce((sum, row) => sum + row.score, 0) / rows.length : 0;
  const weak = rows.filter((row) => row.score < 0.65).length;

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Data quality</Pill>
          <h1>Data Quality</h1>
          <p className="page-sub">
            Berbeda dari freshness collector: halaman ini mengecek apakah setiap
            match punya konteks yang cukup untuk analisis model dan narasi AI.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Avg completeness" value={pct0(avg)} tone="home" />
          <StatTile label="Matches checked" value={rows.length} />
          <StatTile label="Weak packets" value={weak} tone={weak ? "away" : "home"} />
        </div>
      </div>

      <div className="quality-list">
        {rows.map((row) => (
          <QualityCard row={row} key={row.match.id} />
        ))}
      </div>
    </>
  );
}

function scoreMatchQuality(match) {
  const intel = match.intelligence || {};
  const checks = {
    weather: Boolean(intel.weather),
    teamStats: Boolean(intel.teamStats?.home && intel.teamStats?.away),
    availability: Boolean(intel.availability?.length || intel.availabilityCoverage?.length),
    lineups: Boolean(intel.lineups?.home?.length && intel.lineups?.away?.length),
    h2h: Boolean(intel.h2h?.length),
    odds: Boolean(intel.odds?.length),
    referee: Boolean(intel.referee),
    route: Boolean(intel.route?.home?.length && intel.route?.away?.length),
  };
  const passed = Object.values(checks).filter(Boolean).length;
  return {
    match,
    checks,
    score: passed / CHECKS.length,
    missing: CHECKS.filter(([key]) => !checks[key]).map(([, label]) => label),
  };
}

function QualityCard({ row }) {
  const tone = row.score >= 0.75 ? "live" : row.score >= 0.5 ? "muted" : "danger";
  return (
    <article className={`quality-card ${tone}`}>
      <div className="quality-head">
        <div>
          <strong><Flag team={row.match.home} /> {row.match.home} vs {row.match.away} <Flag team={row.match.away} /></strong>
          <span>{row.match.round} / {row.match.venue}</span>
        </div>
        <Pill tone={tone === "danger" ? "danger" : tone}>{pct0(row.score)}</Pill>
      </div>

      <div className="quality-checks">
        {CHECKS.map(([key, label]) => (
          <span className={row.checks[key] ? "ok" : "missing"} key={key}>
            {label}
          </span>
        ))}
      </div>

      <div className="quality-foot">
        <span>{row.missing.length ? `Missing: ${row.missing.join(", ")}` : "Packet lengkap untuk narasi tajam."}</span>
        <Link to={`/match/${row.match.id}`}>Lihat match</Link>
      </div>
    </article>
  );
}
