import { Link, useParams } from "react-router-dom";
import { Flag, FullPageLoader, Pill, PlayerAvatar, StatTile } from "../components.jsx";
import { pct0, usePredictions } from "../data.js";
import { buildPlayers, findPlayer } from "../playerUtils.js";
import { teamSlug } from "../teamUtils.js";

export default function PlayerDetail() {
  const { playerId } = useParams();
  const { data, error } = usePredictions();

  if (error) return <div className="state">Gagal memuat detail pemain.</div>;
  if (!data) return <FullPageLoader text="Memuat detail pemain" />;

  const player = findPlayer(buildPlayers(data), playerId);
  if (!player) {
    return <div className="state">Pemain tidak ditemukan. <Link to="/players">Kembali ke players</Link></div>;
  }

  return (
    <>
      <Link to="/players" className="back">← Semua players</Link>

      <div className="detail-hero player-detail-hero">
        <div className="detail-hero-top">
          <Pill tone={player.status && player.status !== "fit" ? "danger" : "live"}>
            {player.status || "tracked"}
          </Pill>
          <span>{player.sources.join(" / ")}</span>
        </div>
        <div className="player-profile-title">
          <PlayerAvatar name={player.name} team={player.team} />
          <div>
            <h1>{player.name}</h1>
            <Link to={`/teams/${teamSlug(player.team)}`}><Flag team={player.team} /> {player.team}</Link>
          </div>
        </div>
        <div className="detail-kpis">
          <StatTile label="Goals" value={player.goals || 0} tone="away" />
          <StatTile label="xG" value={player.xg ?? "-"} />
          <StatTile label="Anytime probability" value={player.anytimeP ? pct0(player.anytimeP) : "-"} tone="home" />
          <StatTile label="Penalty taker" value={player.penTaker ? "Yes" : "No"} />
        </div>
      </div>

      <div className="detail-grid equal">
        <section className="panel">
          <h2>Status pemain</h2>
          <div className="history-audit-notes">
            <div>
              <span>Status</span>
              <strong>{player.status || "Tidak ada status khusus"}</strong>
            </div>
            <div>
              <span>Reason</span>
              <strong>{player.reason || "Tidak ada catatan availability."}</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>Sumber sinyal</h2>
          <div className="endpoint-list">
            {player.sources.map((source) => <span key={source}>{source}</span>)}
          </div>
        </section>
      </div>
    </>
  );
}
