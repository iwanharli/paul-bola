import { Link, useParams } from "react-router-dom";
import { Flag, FullPageLoader, Pill, ProbBar, StatTile } from "../components.jsx";
import { pct0, usePredictions } from "../data.js";

export default function NarrativeDetail() {
  const { matchId } = useParams();
  const { data, error } = usePredictions();

  if (error) return <div className="state">Gagal memuat detail narrative.</div>;
  if (!data) return <FullPageLoader text="Memuat narrative detail" />;

  const match = (data.matches || []).find((row) => row.id === matchId);
  if (!match) return <div className="state">Narrative tidak ditemukan. <Link to="/narratives">Kembali</Link></div>;

  const card = buildNarrative(match, data);
  const p = match.prediction;

  return (
    <>
      <Link to="/narratives" className="back">← Semua narratives</Link>
      <div className="detail-hero">
        <div className="detail-hero-top">
          <Pill tone={card.status === "ready" ? "live" : "danger"}>{card.status}</Pill>
          <span>Target model {card.model}</span>
        </div>
        <div className="team-profile-title">
          <Flag team={match.home} />
          <h1>{match.home} vs {match.away}</h1>
          <Flag team={match.away} />
        </div>
        <div className="detail-kpis">
          <StatTile label={`${match.home} 90m`} value={pct0(p.result90.home)} tone="home" />
          <StatTile label="Draw" value={pct0(p.result90.draw)} />
          <StatTile label={`${match.away} 90m`} value={pct0(p.result90.away)} tone="away" />
          <StatTile label="Top score" value={p.scorelines?.[0]?.score || "-"} />
        </div>
      </div>

      <section className="panel primary-panel">
        <h2>{card.headline}</h2>
        <p className="panel-sub">{card.summary}</p>
        <ProbBar home={p.result90.home} draw={p.result90.draw} away={p.result90.away} homeName={match.home} awayName={match.away} />
      </section>

      <div className="detail-grid equal">
        <section className="panel">
          <h2>Key factors</h2>
          <ul className="notes">
            <li>xG projection: {p.xg.home} - {p.xg.away}</li>
            <li>Top scoreline: {p.scorelines?.[0]?.score || "-"} ({p.scorelines?.[0] ? pct0(p.scorelines[0].p) : "-"})</li>
            <li>Model validation: {data.history?.evaluation ? `${pct0(data.history.evaluation.accuracy)} accuracy` : "-"}</li>
          </ul>
        </section>
        <section className="panel">
          <h2>Model risks</h2>
          <ul className="notes">
            {card.missing.length ? card.missing.map((item) => <li key={item}>Missing {item}</li>) : <li>Packet cukup lengkap.</li>}
            <li>Scoreline adalah skenario probabilistik, bukan kepastian.</li>
          </ul>
        </section>
      </div>
    </>
  );
}

function buildNarrative(match, data) {
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

  return {
    status: missing.length >= 3 ? "needs-data" : "ready",
    model: "gpt-5.6-terra",
    headline: `${favorite} unggul ${pct0(favoriteProb)}, tetapi match tetap terbuka`,
    summary: `Narasi final sebaiknya menekankan bahwa ${match.home} vs ${match.away} adalah prediksi probabilistik: ${match.home} ${pct0(p.result90.home)}, draw ${pct0(p.result90.draw)}, ${match.away} ${pct0(p.result90.away)}.`,
    missing,
  };
}
