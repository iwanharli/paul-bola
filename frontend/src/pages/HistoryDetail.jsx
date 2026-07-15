import { Link, useParams } from "react-router-dom";
import { pct, pct0, usePredictions } from "../data.js";
import { Flag, FullPageLoader, Pill, ProbBar, StatTile } from "../components.jsx";
import { findHistoryMatch } from "../historyUtils.js";

export default function HistoryDetail() {
  const { matchId } = useParams();
  const { data, error } = usePredictions();

  if (error) return <div className="state">Gagal memuat detail histori.</div>;
  if (!data) return <FullPageLoader text="Memuat detail audit" />;

  const evaluation = data.history?.evaluation;
  const match = findHistoryMatch(evaluation?.matches, matchId);

  if (!match) {
    return (
      <div className="state">
        Detail history tidak ditemukan. <Link to="/history">Kembali ke history</Link>
      </div>
    );
  }

  const isWrong = !match.correct;
  const outcomeRows = [
    { key: "home", label: match.home, value: match.probabilities.home },
    { key: "draw", label: "Draw", value: match.probabilities.draw },
    { key: "away", label: match.away, value: match.probabilities.away },
  ].sort((a, b) => b.value - a.value);

  return (
    <>
      <Link to="/history" className="back">← Semua history</Link>

      <div className={`detail-hero history-detail-hero ${isWrong ? "wrong" : "correct"}`}>
        <div className="detail-hero-top">
          <Pill tone={match.correct ? "live" : "danger"}>{match.correct ? "Prediksi tepat" : "Prediksi meleset"}</Pill>
          <span>{match.round || "Finished"} / {match.date}</span>
        </div>

        <div className="detail-teams">
          <div className="detail-team">
            <Flag team={match.home} />
            <span>{match.home}</span>
          </div>
          <div className="history-detail-score">{match.actualScore}</div>
          <div className="detail-team detail-team-right">
            <span>{match.away}</span>
            <Flag team={match.away} />
          </div>
        </div>

        <div className="detail-meta">{match.ground || "Venue unknown"}</div>
        <div className="detail-kpis">
          <StatTile label="Prediksi model" value={<ResultName name={match.predictedName} />} tone={match.correct ? "home" : "away"} />
          <StatTile label="Hasil aktual" value={<ResultName name={match.actualName} />} tone="home" />
          <StatTile label="Prob aktual" value={pct0(match.actualProbability)} />
          <StatTile label="Log-loss" value={match.logLoss} tone={isWrong ? "away" : ""} />
        </div>
      </div>

      {match.actualXg && (match.actualXg.home != null || match.actualXg.away != null) && (
        <section className="panel">
          <h2>Gol vs xG aktual</h2>
          <p className="panel-sub">
            Apakah tiap tim mencetak sesuai kualitas peluang (xG) mereka di laga ini?
            Selisih besar = keberuntungan/penyelesaian tak berkelanjutan.
          </p>
          <div className="detail-grid equal">
            <XgVsGoals name={match.home} goals={Number(match.actualScore.split("-")[0])} xg={match.actualXg.home} />
            <XgVsGoals name={match.away} goals={Number(match.actualScore.split("-")[1])} xg={match.actualXg.away} />
          </div>
        </section>
      )}

      {match.scorers && (match.scorers.home.length > 0 || match.scorers.away.length > 0) && (
        <section className="panel">
          <h2>Pencetak gol</h2>
          <div className="scorer-cols">
            <ScorerList title={match.home} list={match.scorers.home} />
            <ScorerList title={match.away} list={match.scorers.away} />
          </div>
        </section>
      )}

      {match.betting && match.betting.markets?.length > 0 && (
        <section className="panel panel-market">
          <div className="panel-head">
            <div>
              <h2>Audit taruhan</h2>
              <p className="panel-sub">
                Tebakan pasar taruhan model (dari probabilitas pra-laga yang
                dikunci) vs hasil aktual. Bukan hindsight.
              </p>
            </div>
            <Pill tone={match.betting.hits >= match.betting.total / 2 ? "live" : "danger"}>
              {match.betting.hits}/{match.betting.total} tepat
            </Pill>
          </div>
          <div className="betting-audit">
            {match.betting.markets.map((mk, i) => (
              <div className={`betting-row ${mk.hit ? "hit" : "miss"}`} key={i}>
                <span className="betting-icon">{mk.hit ? "✓" : "✗"}</span>
                <div className="betting-info">
                  <strong>{mk.market}</strong>
                  <span>Pick: {mk.pick} ({pct0(mk.prob)}) · Hasil: {mk.outcome}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel primary-panel">
        <div className="panel-head">
          <div>
            <h2>Probabilitas saat diuji</h2>
            <p className="panel-sub">
              Outcome dengan probabilitas terbesar menjadi prediksi model. Warna merah berarti outcome aktual bukan pilihan teratas model.
            </p>
          </div>
        </div>
        <ProbBar
          home={match.probabilities.home}
          draw={match.probabilities.draw}
          away={match.probabilities.away}
          homeName={match.home}
          awayName={match.away}
        />
      </section>

      <div className="detail-grid equal">
        <section className="panel">
          <h2>Ranking outcome</h2>
          <div className="outcome-list">
            {outcomeRows.map((row, index) => (
              <div
                className={`outcome-row ${row.label === match.actualName ? "actual" : ""} ${index === 0 ? "predicted" : ""}`}
                key={row.key}
              >
                <span>{index + 1}</span>
                <strong><ResultName name={row.label} /></strong>
                <b>{pct(row.value)}</b>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Dasar audit</h2>
          <div className="history-audit-notes">
            <div>
              <span>Metode</span>
              <strong>{evaluation.method}</strong>
            </div>
            <div>
              <span>Split date</span>
              <strong>{evaluation.splitDate}</strong>
            </div>
            <div>
              <span>Yang dinilai</span>
              <strong>Prediksi result 90 menit dibandingkan hasil aktual di data model.</strong>
            </div>
          </div>
        </section>
      </div>

      <div className="model-note">
        <strong>Interpretasi log-loss</strong>
        <span>
          Log-loss membesar jika model memberi probabilitas kecil pada hasil yang benar.
          Jadi match meleset dengan confidence tinggi akan terlihat lebih buruk.
        </span>
      </div>
    </>
  );
}

function ResultName({ name }) {
  if (!name || name === "Draw") return <>{name || "-"}</>;
  return <><Flag team={name} /> {name}</>;
}

function XgVsGoals({ name, goals, xg }) {
  const diff = xg != null ? goals - xg : null;
  return (
    <div className="basis-team">
      <h3><Flag team={name} /> <span>{name}</span></h3>
      <div className="basis-stat"><span>Gol</span><b>{goals}</b></div>
      <div className="basis-stat"><span>xG aktual</span><b>{xg ?? "-"}</b></div>
      {diff != null && (
        <div className="basis-stat">
          <span>Gol − xG</span>
          <b className={diff > 0.5 ? "over" : diff < -0.5 ? "under" : ""}>
            {diff >= 0 ? "+" : ""}{diff.toFixed(1)}
          </b>
        </div>
      )}
    </div>
  );
}

function ScorerList({ title, list }) {
  return (
    <div className="scorer-col">
      <h3>{title}</h3>
      {list.length === 0 ? (
        <p className="tiny-note">Tidak mencetak gol.</p>
      ) : (
        list.map((s, i) => (
          <div className="history-scorer" key={`${s.name}-${s.minute}-${i}`}>
            <span>{s.name}</span>
            <em>
              {s.minute}'{s.penalty && <span className="pen-tag">PEN</span>}
            </em>
          </div>
        ))
      )}
    </div>
  );
}
