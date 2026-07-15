import { Link } from "react-router-dom";
import { formatGeneratedAtUtc7, formatMatchTimeUtc7, usePredictions, pct0 } from "../data.js";
import { Flag, FullPageLoader, ProbBar, Pill, StatTile } from "../components.jsx";

export default function MatchList() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat prediksi.</div>;
  if (!data) return <FullPageLoader text="Memuat forecast" />;

  const mainMatch = data.matches[0];
  const scenarioCount = data.matches.filter((m) => m.status === "scenario").length;

  return (
    <>
      <div className="page-hero">
        <div>
          <Pill tone="live">Live forecast</Pill>
          <h1>Pertandingan mendatang</h1>
          <p className="page-sub">
            Ringkasan peluang 90 menit, peluang lolos, dan dasar penilaian model.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Match tracked" value={data.matches.length} />
          <StatTile label="Scenario" value={scenarioCount} />
          <StatTile label="Generated UTC+7" value={formatGeneratedAtUtc7(data.generated_at)} />
        </div>
      </div>

      <div className="match-grid">
        {data.matches.map((m) => {
          const r = m.prediction.result90;
          const favHome = m.prediction.advance
            ? m.prediction.advance.home >= m.prediction.advance.away
            : r.home >= r.away;
          const favorite = favHome ? m.home : m.away;
          const favoriteProb = favHome ? r.home : r.away;
          const topScore = m.prediction.scorelines?.[0];
          const weather = m.intelligence?.weather;
          return (
            <Link to={`/match/${m.id}`} className="match-card" key={m.id}>
              <div className="match-card-top">
                <Pill tone={m.status === "scenario" ? "muted" : m.status === "finished" ? "danger" : "live"}>
                  {m.status === "finished" ? "Selesai" : m.round}
                </Pill>
                <span className="match-meta">{formatMatchTimeUtc7(m)}</span>
              </div>

              {m.status === "finished" && m.actualResult && (
                <div className={`result-banner ${m.actualResult.modelWasRight ? "hit" : "miss"}`}>
                  <span className="result-score">
                    {m.home} {m.actualResult.home_goals}–{m.actualResult.away_goals} {m.away}
                  </span>
                  <span className="result-verdict">
                    {m.actualResult.modelWasRight
                      ? "✓ Prediksi model tepat"
                      : `✗ Model jagokan ${m.actualResult.modelPick}`}
                  </span>
                </div>
              )}

              <div className="teams">
                <div className={`team ${favHome ? "team-fav" : ""}`}>
                  <Flag team={m.home} />
                  <span className="team-name">{m.home}</span>
                </div>
                <span className="vs">vs</span>
                <div className={`team team-right ${!favHome ? "team-fav" : ""}`}>
                  <span className="team-name">{m.away}</span>
                  <Flag team={m.away} />
                </div>
              </div>

              <div className="match-summary">
                <div>
                  <span>Favorit model</span>
                  <strong>{favorite} {pct0(favoriteProb)}</strong>
                </div>
                {topScore && (
                  <div>
                    <span>Skor teratas</span>
                    <strong>{topScore.score}</strong>
                  </div>
                )}
                <div>
                  <span>xG</span>
                  <strong>{m.prediction.xg.home} - {m.prediction.xg.away}</strong>
                </div>
                {weather && (
                  <div>
                    <span>Cuaca</span>
                    <strong>{weather.temperatureC}C / {weather.humidityPct}%</strong>
                  </div>
                )}
              </div>

              <ProbBar
                home={r.home}
                draw={r.draw}
                away={r.away}
                homeName={m.home}
                awayName={m.away}
                compact
              />

              {m.prediction.advance && (
                <div className="advance-row">
                  <span>Peluang lolos</span>
                  <strong>
                    {m.prediction.advance.home >= m.prediction.advance.away
                      ? `${m.home} ${pct0(m.prediction.advance.home)}`
                      : `${m.away} ${pct0(m.prediction.advance.away)}`}
                  </strong>
                </div>
              )}

              <div className="match-venue">{m.venue}</div>
            </Link>
          );
        })}
      </div>

      {mainMatch && (
        <div className="model-note">
          <strong>{data.model.name}</strong>
          <span>
            Market blend dipakai sebagai angka akhir karena performanya paling
            kuat pada validasi held-out.
          </span>
        </div>
      )}

    </>
  );
}
