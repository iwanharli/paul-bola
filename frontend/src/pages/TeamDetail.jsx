import { Link, useParams } from "react-router-dom";
import { Flag, FullPageLoader, Pill, PlayerAvatar, StatTile } from "../components.jsx";
import { usePredictions } from "../data.js";
import { findTeam } from "../teamUtils.js";

export default function TeamDetail() {
  const { teamId } = useParams();
  const { data, error } = usePredictions();

  if (error) return <div className="state">Gagal memuat detail tim.</div>;
  if (!data) return <FullPageLoader text="Memuat detail tim" />;

  const teams = data.tournament?.teams || [];
  const team = findTeam(teams, teamId);
  if (!team) {
    return <div className="state">Tim tidak ditemukan. <Link to="/teams">Kembali ke teams</Link></div>;
  }

  const record = team.record || {};
  const stats = team.teamStats;
  const relatedMatches = (data.matches || []).filter((match) => match.home === team.name || match.away === team.name);

  return (
    <>
      <Link to="/teams" className="back">← Semua teams</Link>

      <div className="detail-hero team-detail-hero">
        <div className="detail-hero-top">
          <Pill tone="live">Team profile</Pill>
          <span>{record.played || 0} matches tracked</span>
        </div>
        <div className="team-profile-title">
          <Flag team={team.name} />
          <h1>{team.name}</h1>
        </div>
        <div className="detail-kpis">
          <StatTile label="Record" value={`${record.wins || 0}-${record.draws || 0}-${record.losses || 0}`} />
          <StatTile label="Goal diff" value={formatSigned(record.goalDiff || 0, 0)} tone={(record.goalDiff || 0) >= 0 ? "home" : "away"} />
          <StatTile label="xG / Goals" value={`${team.form?.xg ?? "-"} / ${team.form?.goals ?? "-"}`} />
          <StatTile label="Goals-xG" value={formatSigned(team.goalsMinusXg || 0)} tone={(team.goalsMinusXg || 0) > 0 ? "away" : "home"} />
        </div>
      </div>

      <div className="detail-grid equal">
        <section className="panel">
          <h2>Model strength</h2>
          <div className="team-strength-grid">
            <StatTile label="Elo" value={team.strength?.elo ?? "-"} />
            <StatTile label="Attack" value={formatNullable(team.strength?.attack)} tone="home" />
            <StatTile label="Defense" value={formatNullable(team.strength?.defense)} />
            <StatTile label="Goals for" value={record.goalsFor || 0} tone="away" />
          </div>
        </section>

        <section className="panel">
          <h2>Stat ESPN</h2>
          {stats ? (
            <div className="team-strength-grid">
              <StatTile label="Possession" value={`${stats.possession}%`} />
              <StatTile label="Shots" value={stats.shots} tone="home" />
              <StatTile label="Corners" value={stats.corners} />
              <StatTile label="Cards" value={`${stats.yellows}Y / ${stats.reds}R`} tone={stats.reds ? "away" : ""} />
            </div>
          ) : (
            <EmptyText text="Stat ESPN belum tersedia untuk tim ini." />
          )}
        </section>
      </div>

      <div className="detail-grid equal">
        <RoutePanel team={team} />
        <ScorersPanel team={team} />
      </div>

      <div className="detail-grid equal">
        <AvailabilityPanel team={team} />
        <section className="panel">
          <h2>Match terkait</h2>
          {relatedMatches.length ? (
            <div className="team-related-list">
              {relatedMatches.map((match) => (
                <Link to={`/match/${match.id}`} className="team-related-row" key={match.id}>
                  <span>{match.round}</span>
                  <strong>{match.home} vs {match.away}</strong>
                  <em>{match.status}</em>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyText text="Belum ada forecast aktif untuk tim ini." />
          )}
        </section>
      </div>
    </>
  );
}

function RoutePanel({ team }) {
  return (
    <section className="panel">
      <h2>Route {team.name}</h2>
      {team.route?.length ? (
        <div className="route-list">
          {team.route.map((row) => (
            <div className="route-row" key={`${row.date}-${row.round}-${row.opponent}`}>
              <em className={`result ${row.result}`}>{row.result}</em>
              <div>
                <strong>
                  <span className="route-score">{row.score}</span>
                  <span className="route-vs">vs</span>
                  <Flag team={row.opponent} />
                  <span>{row.opponent}</span>
                </strong>
                <span>{row.round} / {row.ground}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyText text="Route belum tersedia." />
      )}
    </section>
  );
}

function ScorersPanel({ team }) {
  return (
    <section className="panel">
      <h2>Top scorers</h2>
      {team.topScorers?.length ? (
        <div className="team-scorer-list">
          {team.topScorers.map((player) => (
            <div className="team-scorer-row" key={player.name}>
              <PlayerAvatar name={player.name} team={team.name} size="sm" />
              <strong>{player.name}</strong>
              <b>{player.goals}G</b>
            </div>
          ))}
        </div>
      ) : (
        <EmptyText text="Belum ada data scorer." />
      )}
    </section>
  );
}

function AvailabilityPanel({ team }) {
  return (
    <section className="panel">
      <h2>Team news</h2>
      {team.availability?.length ? (
        <div className="info-list">
          {team.availability.map((item) => (
            <div className="info-row" key={`${item.player}-${item.status}`}>
              <div className="player-info">
                <PlayerAvatar name={item.player} team={team.name} size="sm" />
                <div>
                  <strong>{item.player}</strong>
                  <span>{item.reason}</span>
                </div>
              </div>
              <em className={`status ${item.status}`}>{item.status}</em>
            </div>
          ))}
        </div>
      ) : (
        <CoverageText coverage={team.availabilityCoverage} />
      )}
    </section>
  );
}

function CoverageText({ coverage }) {
  if (!coverage) return <EmptyText text="Tidak ada status pemain khusus." />;
  return (
    <div className="info-row">
      <div>
        <strong>Squad status checked</strong>
        <span>{coverage.playerCount} pemain dicek dari {coverage.source}. Ini bukan confirmed injury report.</span>
      </div>
      <em className="status fit">{coverage.specialStatusCount ? `${coverage.specialStatusCount} flagged` : "checked"}</em>
    </div>
  );
}

function EmptyText({ text }) {
  return <p className="empty-text">{text}</p>;
}

function formatSigned(value, digits = 1) {
  return `${value >= 0 ? "+" : ""}${Number(value).toFixed(digits)}`;
}

function formatNullable(value) {
  return value === null || value === undefined ? "-" : Number(value).toFixed(2);
}
