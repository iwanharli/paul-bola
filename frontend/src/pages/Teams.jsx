import { Link } from "react-router-dom";
import { Flag, FullPageLoader, Pill, StatTile } from "../components.jsx";
import { pct0, usePredictions } from "../data.js";
import { teamSlug } from "../teamUtils.js";

export default function Teams() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat teams.</div>;
  if (!data) return <FullPageLoader text="Memuat profil tim" />;

  const teams = data.tournament?.teams || [];
  const topAttack = [...teams].sort((a, b) => (b.strength?.attack ?? -99) - (a.strength?.attack ?? -99))[0];
  const topXg = [...teams].sort((a, b) => (b.form?.xg || 0) - (a.form?.xg || 0))[0];
  const unbeaten = teams.filter((team) => team.record?.losses === 0).length;

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Team profiles</Pill>
          <h1>Teams</h1>
          <p className="page-sub">
            Profil tiap tim dari data model: Elo, attack/defense strength,
            xG, goals-xG, record, top scorer, dan route pertandingan.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Teams" value={teams.length} />
          <StatTile label="Top attack" value={topAttack?.name || "-"} tone="home" />
          <StatTile label="Unbeaten" value={unbeaten} />
        </div>
      </div>

      {topXg && (
        <section className="panel source-summary">
          <div>
            <h2>Signal utama</h2>
            <p className="panel-sub">
              {topXg.name} memimpin total xG turnamen ({topXg.form.xg}), sementara
              goals-xG membantu melihat finishing over/under-performance.
            </p>
          </div>
          <Pill tone="muted">Klik tim untuk detail</Pill>
        </section>
      )}

      <div className="team-grid">
        {teams.map((team) => (
          <TeamCard team={team} key={team.name} />
        ))}
      </div>
    </>
  );
}

function TeamCard({ team }) {
  const record = team.record || {};
  const topScorer = team.topScorers?.[0];
  const goalDiff = record.goalDiff || 0;
  const over = team.goalsMinusXg || 0;
  const winRate = record.played ? record.wins / record.played : 0;

  return (
    <Link to={`/teams/${teamSlug(team.name)}`} className="team-card">
      <div className="team-card-head">
        <div>
          <Flag team={team.name} />
          <strong>{team.name}</strong>
        </div>
        <Pill tone={goalDiff >= 0 ? "live" : "danger"}>{goalDiff >= 0 ? `+${goalDiff}` : goalDiff} GD</Pill>
      </div>

      <div className="team-card-stats">
        <StatTile label="Record" value={`${record.wins || 0}-${record.draws || 0}-${record.losses || 0}`} />
        <StatTile label="Win rate" value={pct0(winRate)} tone="home" />
        <StatTile label="xG" value={team.form?.xg ?? "-"} />
        <StatTile label="Goals-xG" value={formatSigned(over)} tone={over > 0 ? "away" : "home"} />
      </div>

      <div className="team-card-foot">
        <span>Elo {team.strength?.elo ?? "-"}</span>
        <span>{topScorer ? `${topScorer.name} ${topScorer.goals}G` : "No scorer data"}</span>
      </div>
    </Link>
  );
}

function formatSigned(value) {
  return `${value >= 0 ? "+" : ""}${Number(value).toFixed(1)}`;
}
