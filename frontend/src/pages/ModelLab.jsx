import { FullPageLoader, Pill, StatTile } from "../components.jsx";
import { pct0, usePredictions } from "../data.js";

export default function ModelLab() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat model lab.</div>;
  if (!data) return <FullPageLoader text="Memuat model lab" />;

  const rows = data.model?.heldout || [];
  const bestAccuracy = [...rows].sort((a, b) => b.acc - a.acc)[0];
  const bestLogloss = [...rows].sort((a, b) => a.logloss - b.logloss)[0];
  const evaluation = data.history?.evaluation;

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Model lab</Pill>
          <h1>Model Lab</h1>
          <p className="page-sub">
            Bandingkan variasi model, akurasi held-out, log-loss, dan alasan
            final forecast memakai xG/goals blend plus market signal.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Best accuracy" value={`${bestAccuracy?.model || "-"} ${bestAccuracy ? pct0(bestAccuracy.acc) : ""}`} tone="home" />
          <StatTile label="Best log-loss" value={`${bestLogloss?.logloss ?? "-"}`} />
          <StatTile label="Evaluated" value={evaluation?.total ?? "-"} />
        </div>
      </div>

      <section className="panel source-summary">
        <div>
          <h2>Final choice</h2>
          <p className="panel-sub">
            Standalone xG memberi explanation layer, tetapi market tetap sinyal paling kuat.
            Forecast akhir memakai blend karena validasi held-out paling stabil.
          </p>
        </div>
        <Pill tone="muted">{data.model?.name}</Pill>
      </section>

      <div className="model-lab-list">
        {rows.map((row) => (
          <ModelRow row={row} bestAccuracy={bestAccuracy} bestLogloss={bestLogloss} key={row.model} />
        ))}
      </div>
    </>
  );
}

function ModelRow({ row, bestAccuracy, bestLogloss }) {
  const isBestAcc = row.model === bestAccuracy?.model;
  const isBestLoss = row.model === bestLogloss?.model;
  return (
    <article className={`model-row-card ${isBestAcc || isBestLoss ? "best" : ""}`}>
      <div>
        <strong>{row.model}</strong>
        <span>
          {isBestAcc && "Best accuracy"}
          {isBestAcc && isBestLoss && " / "}
          {isBestLoss && "Best calibration"}
          {!isBestAcc && !isBestLoss && "Held-out model variant"}
        </span>
      </div>
      <div className="model-bars">
        <MetricBar label="Accuracy" value={row.acc} display={pct0(row.acc)} />
        <MetricBar label="Log-loss" value={1 - Math.min(row.logloss, 1.2) / 1.2} display={row.logloss.toFixed(3)} inverse />
      </div>
    </article>
  );
}

function MetricBar({ label, value, display, inverse = false }) {
  return (
    <div className="metric-bar">
      <div>
        <span>{label}</span>
        <strong>{display}</strong>
      </div>
      <div className={`metric-track ${inverse ? "inverse" : ""}`}>
        <i style={{ width: pct0(value) }} />
      </div>
    </div>
  );
}
