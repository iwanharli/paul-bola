import { Link } from "react-router-dom";
import { Flag, FullPageLoader, Pill, StatTile } from "../components.jsx";
import { formatGeneratedAtUtc7, pct0, usePredictions } from "../data.js";
import { buildPlayers } from "../playerUtils.js";
import { teamSlug } from "../teamUtils.js";

export default function Dashboard() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat dashboard.</div>;
  if (!data) return <FullPageLoader text="Memuat dashboard" />;

  const nextMatch = data.matches?.[0];
  const teams = data.tournament?.teams || [];
  const players = buildPlayers(data);
  const qualityRows = (data.matches || []).map(matchQuality);
  const avgQuality = qualityRows.length
    ? qualityRows.reduce((sum, row) => sum + row, 0) / qualityRows.length
    : 0;
  const latestSource = (data.dataFreshness || [])
    .map((row) => row.lastRun)
    .filter(Boolean)
    .sort()
    .at(-1);

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Overview</Pill>
          <h1>Dashboard</h1>
          <p className="page-sub">
            Ringkasan cepat forecast, kesehatan data, kekuatan model, tim,
            pemain, dan workflow narasi AI.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Generated UTC+7" value={formatGeneratedAtUtc7(data.generated_at)} />
          <StatTile label="Data quality" value={pct0(avgQuality)} tone="home" />
          <StatTile label="Latest source" value={formatGeneratedAtUtc7(latestSource)} />
        </div>
      </div>

      {nextMatch && (
        <section className="dashboard-next">
          <div>
            <span className="eyebrow">Next forecast</span>
            <h2><Flag team={nextMatch.home} /> {nextMatch.home} vs {nextMatch.away} <Flag team={nextMatch.away} /></h2>
            <p>{nextMatch.round} / {nextMatch.venue}</p>
          </div>
          <div className="dashboard-next-stats">
            <StatTile label={`${nextMatch.home} 90m`} value={pct0(nextMatch.prediction.result90.home)} tone="home" />
            <StatTile label="Draw" value={pct0(nextMatch.prediction.result90.draw)} />
            <StatTile label={`${nextMatch.away} 90m`} value={pct0(nextMatch.prediction.result90.away)} tone="away" />
          </div>
          <Link to={`/match/${nextMatch.id}`}>Buka detail</Link>
        </section>
      )}

      <section className="dashboard-section">
        <div className="section-head">
          <div>
            <h2>Main workspace</h2>
            <p>Menu analisis yang paling sering dipakai.</p>
          </div>
        </div>
        <div className="dashboard-grid">
        <DashboardCard title="Forecast" to="/forecast" value={`${data.matches.length} match`} text="Pertandingan mendatang dan scenario final." />
        <DashboardCard title="Bracket" to="/bracket" value={`${data.bracket?.matches?.length || 0} nodes`} text="Peta knockout fullscreen dengan audit warna." />
        <DashboardCard title="Compare" to="/compare" value="2 teams" text="Head-to-head strength, form, dan ESPN stats." />
        <DashboardCard title="History" to="/history" value={data.history?.evaluation ? `${data.history.evaluation.total} audit` : "-"} text="Backtest pertandingan lama dan akurasi model." />
        <DashboardCard title="Teams" to="/teams" value={`${teams.length} teams`} text={`Top: ${teams[0]?.name || "-"}`} />
        <DashboardCard title="Players" to="/players" value={`${players.length} players`} text={`Top: ${players[0]?.name || "-"}`} />
        </div>
      </section>

      <section className="dashboard-section ops-section">
        <div className="section-head">
          <div>
            <h2>Ops center</h2>
            <p>Pengelolaan data, model, narasi, dan konfigurasi.</p>
          </div>
          <Link to="/sources">Sumber data</Link>
        </div>
        <div className="ops-grid">
          <OpsCard title="Quality" to="/data-quality" value={pct0(avgQuality)} />
          <OpsCard title="Sources" to="/sources" value={`${data.dataFreshness?.length || 0} src`} />
          <OpsCard title="Data Gaps" to="/source-gaps" value="Audit" />
          <OpsCard title="Model Lab" to="/model-lab" value={data.history?.evaluation ? pct0(data.history.evaluation.accuracy) : "-"} />
          <OpsCard title="Narratives" to="/narratives" value={`${data.matches.length} drafts`} />
          <OpsCard title="Dictionary" to="/data-dictionary" value="Schema" />
          <OpsCard title="Changelog" to="/changelog" value="Runs" />
          <OpsCard title="Settings" to="/settings" value="Admin" />
        </div>
      </section>

      <div className="detail-grid equal">
        <section className="panel">
          <h2>Top teams</h2>
          <div className="team-scorer-list">
            {teams.slice(0, 5).map((team) => (
              <Link to={`/teams/${teamSlug(team.name)}`} className="team-scorer-row" key={team.name}>
                <Flag team={team.name} />
                <strong>{team.name}</strong>
                <b>{team.record?.wins || 0}W</b>
              </Link>
            ))}
          </div>
        </section>
        <section className="panel">
          <h2>Top players</h2>
          <div className="team-scorer-list">
            {players.slice(0, 5).map((player) => (
              <Link to={`/players/${encodeURIComponent(`${player.name}__${player.team}`)}`} className="team-scorer-row" key={`${player.name}-${player.team}`}>
                <Flag team={player.team} />
                <strong>{player.name}</strong>
                <b>{player.goals || 0}G</b>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

function DashboardCard({ title, to, value, text }) {
  return (
    <Link to={to} className="dashboard-card">
      <span>{title}</span>
      <strong>{value}</strong>
      <em>{text}</em>
    </Link>
  );
}

function OpsCard({ title, to, value }) {
  return (
    <Link to={to} className="ops-card">
      <span>{title}</span>
      <strong>{value}</strong>
    </Link>
  );
}

function matchQuality(match) {
  const intel = match.intelligence || {};
  const checks = [
    intel.weather,
    intel.teamStats?.home && intel.teamStats?.away,
    intel.availability?.length,
    intel.h2h?.length,
    intel.odds?.length,
    intel.referee,
    intel.route?.home?.length && intel.route?.away?.length,
  ];
  return checks.filter(Boolean).length / checks.length;
}
