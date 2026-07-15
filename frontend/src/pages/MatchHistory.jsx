import { Link } from "react-router-dom";
import { pct0, usePredictions } from "../data.js";
import { Flag, FullPageLoader, Pill, ProbBar, StatTile } from "../components.jsx";
import { historyMatchId } from "../historyUtils.js";

export default function MatchHistory() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat histori.</div>;
  if (!data) return <FullPageLoader text="Memuat history pertandingan" />;

  const evaluation = data.history?.evaluation;
  if (!evaluation) return <div className="state">Belum ada data evaluasi.</div>;

  const wrong = evaluation.total - evaluation.correct;
  const rows = [...evaluation.matches].reverse();

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Model audit</Pill>
          <h1>Match history</h1>
          <p className="page-sub">
            Pertandingan lama dipakai sebagai backtest held-out: model dilatih
            pada match sebelum split date, lalu prediksinya dibandingkan dengan
            hasil aktual.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Evaluated" value={evaluation.total} />
          <StatTile label="Accuracy" value={pct0(evaluation.accuracy)} tone="home" />
          <StatTile label="Avg log-loss" value={evaluation.avgLogLoss} />
        </div>
      </div>

      <section className="panel audit-summary">
        <div>
          <h2>Akurasi model</h2>
          <p className="panel-sub">{evaluation.method} Split date: {evaluation.splitDate}.</p>
        </div>
        <div className="audit-score">
          <strong>{evaluation.correct}</strong>
          <span>benar</span>
          <em>{wrong} salah</em>
        </div>
      </section>

      <div className="history-list">
        {rows.map((m) => (
          <HistoryCard match={m} key={`${m.date}-${m.home}-${m.away}-${m.actualScore}`} />
        ))}
      </div>

      <div className="model-note">
        <strong>Catatan evaluasi</strong>
        <span>
          Ini mengukur result 90 menit atau skor regulasi yang tersedia di data model,
          bukan klaim bahwa model mengetahui susunan pemain/odds saat match berlangsung.
        </span>
      </div>
    </>
  );
}

function HistoryCard({ match }) {
  return (
    <article className={`history-card ${match.correct ? "correct" : "wrong"}`}>
      <div className="history-main">
        <div className="history-meta">
          <Pill tone={match.correct ? "live" : "danger"}>
            {match.correct ? "Tepat" : "Meleset"}
          </Pill>
          <span>{match.round || "Finished"} / {match.date}</span>
        </div>

        <div className="history-teams">
          <div>
            <Flag team={match.home} />
            <strong>{match.home}</strong>
          </div>
          <span className="history-score">{match.actualScore}</span>
          <div>
            <strong>{match.away}</strong>
            <Flag team={match.away} />
          </div>
        </div>

        <ProbBar
          home={match.probabilities.home}
          draw={match.probabilities.draw}
          away={match.probabilities.away}
          homeName={match.home}
          awayName={match.away}
          compact
        />
      </div>

      <div className="history-result">
        <div>
          <span>Prediksi</span>
          <strong><ResultName name={match.predictedName} /></strong>
        </div>
        <div>
          <span>Aktual</span>
          <strong><ResultName name={match.actualName} /></strong>
        </div>
        <div>
          <span>Prob aktual</span>
          <strong>{pct0(match.actualProbability)}</strong>
        </div>
        <div>
          <span>Log-loss</span>
          <strong>{match.logLoss}</strong>
        </div>
      </div>

      <div className="history-foot">
        <span>{match.ground || "Venue unknown"}</span>
        <Link to={`/history/${historyMatchId(match)}`}>Lihat detail audit</Link>
      </div>
    </article>
  );
}

function ResultName({ name }) {
  if (!name || name === "Draw") return <>{name || "-"}</>;
  return <><Flag team={name} /> {name}</>;
}
