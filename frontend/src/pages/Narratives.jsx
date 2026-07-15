import { Link } from "react-router-dom";
import { Flag, FullPageLoader, Pill, StatTile } from "../components.jsx";
import { pct0, usePredictions } from "../data.js";

export default function Narratives() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat narratives.</div>;
  if (!data) return <FullPageLoader text="Memuat AI narratives" />;

  const cards = (data.matches || []).map((match) => buildNarrativeCard(match, data));
  const ready = cards.filter((card) => card.status === "ready").length;
  const weak = cards.filter((card) => card.status === "needs-data").length;

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">AI narrative</Pill>
          <h1>Narratives</h1>
          <p className="page-sub">
            Draft narasi berbasis packet data. Ini belum memanggil API AI, tapi
            sudah menunjukkan status, model target, dan preview yang akan digenerate.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Narratives" value={cards.length} />
          <StatTile label="Ready" value={ready} tone="home" />
          <StatTile label="Needs data" value={weak} tone={weak ? "away" : "home"} />
        </div>
      </div>

      <div className="narrative-list">
        {cards.map((card) => (
          <NarrativeCard card={card} key={card.match.id} />
        ))}
      </div>
    </>
  );
}

function buildNarrativeCard(match, data) {
  const p = match.prediction;
  const intel = match.intelligence || {};
  const favoriteHome = p.advance ? p.advance.home >= p.advance.away : p.result90.home >= p.result90.away;
  const favorite = favoriteHome ? match.home : match.away;
  const favoriteProb = p.advance
    ? (favoriteHome ? p.advance.home : p.advance.away)
    : (favoriteHome ? p.result90.home : p.result90.away);
  const missing = [
    !intel.weather && "weather",
    !intel.odds?.length && "odds",
    !intel.h2h?.length && "h2h",
    !intel.referee && "referee",
    !intel.availability?.length && "team news",
  ].filter(Boolean);
  const status = missing.length >= 3 ? "needs-data" : "ready";

  return {
    match,
    status,
    model: "gpt-5.6-terra",
    headline: `${favorite} sedikit di depan, tapi margin tetap probabilistik`,
    summary: `${match.home} vs ${match.away} diproyeksikan ketat: ${match.home} ${pct0(p.result90.home)}, draw ${pct0(p.result90.draw)}, ${match.away} ${pct0(p.result90.away)}. Sinyal utama datang dari xG ${p.xg.home}-${p.xg.away}, route terbaru, dan validasi model ${pct0(data.history?.evaluation?.accuracy || 0)}.`,
    missing,
    favorite,
    favoriteProb,
  };
}

function NarrativeCard({ card }) {
  return (
    <article className={`narrative-card ${card.status}`}>
      <div className="narrative-head">
        <div>
          <strong><Flag team={card.match.home} /> {card.match.home} vs {card.match.away} <Flag team={card.match.away} /></strong>
          <span>{card.match.round} / model target {card.model}</span>
        </div>
        <Pill tone={card.status === "ready" ? "live" : "danger"}>{card.status}</Pill>
      </div>
      <h2>{card.headline}</h2>
      <p>{card.summary}</p>
      <div className="narrative-foot">
        <span>{card.missing.length ? `Missing: ${card.missing.join(", ")}` : "Packet cukup lengkap."}</span>
        <Link to={`/narratives/${card.match.id}`}>Detail narasi</Link>
        <Link to={`/match/${card.match.id}`}>Packet match</Link>
      </div>
    </article>
  );
}
