import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FullPageLoader, Pill, PlayerAvatar, StatTile } from "../components.jsx";
import { FLAGS, pct0, usePredictions } from "../data.js";
import { buildPlayers, playerSlug } from "../playerUtils.js";

export default function Players() {
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("all");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("goals");
  const [penOnly, setPenOnly] = useState(false);
  const { data, error } = usePredictions();
  const players = useMemo(() => (data ? buildPlayers(data) : []), [data]);
  const teamOptions = [...new Set(players.map((player) => player.team))].sort();
  const filteredPlayers = useMemo(() => {
    const q = query.trim().toLowerCase();
    return players
      .filter((player) => {
        const matchesQuery = !q
          || player.name.toLowerCase().includes(q)
          || player.team.toLowerCase().includes(q);
        const matchesTeam = team === "all" || player.team === team;
        const matchesPen = !penOnly || player.penTaker;
        const matchesStatus = status === "all"
          || (status === "available" && (!player.status || player.status === "fit"))
          || (status === "unavailable" && player.status && player.status !== "fit")
          || (status === "anytime" && player.anytimeP)
          || (status === "scorer" && player.goals > 0);
        return matchesQuery && matchesTeam && matchesPen && matchesStatus;
      })
      .sort((a, b) => sortPlayers(a, b, sort));
  }, [players, query, team, status, sort, penOnly]);

  if (error) return <div className="state">Gagal memuat players.</div>;
  if (!data) return <FullPageLoader text="Memuat profil pemain" />;

  const topGoal = players[0];
  const penTakers = players.filter((player) => player.penTaker).length;
  const unavailable = players.filter((player) => player.status && player.status !== "fit").length;
  const anytimeLeaders = players.filter((player) => player.anytimeP).slice(0, 5);
  const topAnytime = anytimeLeaders[0];

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Player profiles</Pill>
          <h1>Players</h1>
          <p className="page-sub">
            Pemain dari top scorer, anytime goalscorer, dan team news. Klik pemain
            untuk melihat probabilitas, xG, status, dan sumber datanya.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Players" value={players.length} />
          <StatTile label="Top goals" value={topGoal ? `${topGoal.name} ${topGoal.goals}` : "-"} tone="away" />
          <StatTile label="Unavailable" value={unavailable} tone={unavailable ? "away" : "home"} />
        </div>
      </div>

      <div className="player-insights">
        <InsightPlayer title="Top goals" player={topGoal} metric={topGoal ? `${topGoal.goals}G` : "-"} />
        <InsightPlayer title="Top anytime" player={topAnytime} metric={topAnytime ? pct0(topAnytime.anytimeP) : "-"} />
        <div className="player-insight-stat">
          <span>Penalty takers</span>
          <strong>{penTakers}</strong>
        </div>
        <div className="player-insight-stat">
          <span>Unavailable</span>
          <strong>{unavailable}</strong>
        </div>
      </div>

      <div className="player-table-panel">
        <div className="player-table-head">
          <div>
            <h2>Player pool</h2>
            <p>{filteredPlayers.length} shown / {players.length} total · {penTakers} penalty taker / {unavailable} unavailable watchlist</p>
          </div>
          <Pill tone="muted">Top scorers + availability</Pill>
        </div>
        <PlayerFilters
          query={query}
          setQuery={setQuery}
          team={team}
          setTeam={setTeam}
          status={status}
          setStatus={setStatus}
          sort={sort}
          setSort={setSort}
          penOnly={penOnly}
          setPenOnly={setPenOnly}
          teamOptions={teamOptions}
        />
        <div className="player-table">
          {filteredPlayers.map((player, index) => (
            <PlayerRow player={player} rank={index + 1} key={`${player.name}-${player.team}`} />
          ))}
          {!filteredPlayers.length && (
            <div className="player-empty">
              Tidak ada pemain yang cocok dengan filter ini.
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function PlayerFilters({
  query,
  setQuery,
  team,
  setTeam,
  status,
  setStatus,
  sort,
  setSort,
  penOnly,
  setPenOnly,
  teamOptions,
}) {
  return (
    <div className="player-filters">
      <label className="search-field">
        <span>Search</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Cari nama pemain atau negara..."
        />
      </label>

      <label>
        <span>Team</span>
        <select value={team} onChange={(event) => setTeam(event.target.value)}>
          <option value="all">Semua tim</option>
          {teamOptions.map((option) => (
            <option value={option} key={option}>{option}</option>
          ))}
        </select>
      </label>

      <label>
        <span>Signal</span>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="all">Semua signal</option>
          <option value="scorer">Punya gol</option>
          <option value="anytime">Ada anytime</option>
          <option value="available">Available/normal</option>
          <option value="unavailable">Unavailable</option>
        </select>
      </label>

      <label>
        <span>Sort</span>
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="goals">Goals</option>
          <option value="anytime">Anytime</option>
          <option value="xg">xG</option>
          <option value="name">Nama</option>
          <option value="team">Team</option>
        </select>
      </label>

      <button
        className={`filter-toggle ${penOnly ? "active" : ""}`}
        type="button"
        onClick={() => setPenOnly((value) => !value)}
      >
        PEN taker
      </button>
    </div>
  );
}

function sortPlayers(a, b, sort) {
  if (sort === "anytime") {
    return (b.anytimeP || 0) - (a.anytimeP || 0) || (b.goals || 0) - (a.goals || 0);
  }
  if (sort === "xg") {
    return (b.xg || 0) - (a.xg || 0) || (b.goals || 0) - (a.goals || 0);
  }
  if (sort === "name") {
    return a.name.localeCompare(b.name) || a.team.localeCompare(b.team);
  }
  if (sort === "team") {
    return a.team.localeCompare(b.team) || a.name.localeCompare(b.name);
  }
  return (b.goals || 0) - (a.goals || 0) || (b.anytimeP || 0) - (a.anytimeP || 0);
}

function InsightPlayer({ title, player, metric }) {
  if (!player) {
    return (
      <div className="player-insight-card">
        <span>{title}</span>
        <strong>-</strong>
      </div>
    );
  }

  return (
    <Link to={`/players/${playerSlug(player.name, player.team)}`} className="player-insight-card">
      <span>{title}</span>
      <div>
        <PlayerAvatar name={player.name} team={player.team} size="sm" />
        <strong>{player.name}</strong>
      </div>
      <em><i aria-hidden="true">{flagFor(player.team)}</i>{player.team}</em>
      <b>{metric}</b>
    </Link>
  );
}

function PlayerRow({ player, rank }) {
  return (
    <Link to={`/players/${playerSlug(player.name, player.team)}`} className="player-row">
      <span className="player-rank">{rank}</span>
      <PlayerAvatar name={player.name} team={player.team} size="sm" />
      <div className="player-row-name">
        <strong>{player.name}</strong>
        <span className="player-team-line"><i aria-hidden="true">{flagFor(player.team)}</i>{player.team}</span>
      </div>
      <div className="player-row-metric">
        <span>Goals</span>
        <strong>{player.goals || 0}</strong>
      </div>
      <div className="player-row-metric">
        <span>xG</span>
        <strong>{player.xg ?? "-"}</strong>
      </div>
      <div className="player-row-metric">
        <span>Anytime</span>
        <strong>{player.anytimeP ? pct0(player.anytimeP) : "-"}</strong>
      </div>
      <div className="player-row-status">
        <Pill tone={player.status && player.status !== "fit" ? "danger" : player.penTaker ? "muted" : ""}>
          {player.status || (player.penTaker ? "PEN" : "tracked")}
        </Pill>
      </div>
    </Link>
  );
}

function flagFor(team) {
  return FLAGS[team] || "🏳️";
}
