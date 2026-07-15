import { Link } from "react-router-dom";
import { FullPageLoader, Pill, StatTile } from "../components.jsx";
import { formatGeneratedAtUtc7, usePredictions } from "../data.js";

const DICTIONARY = [
  {
    key: "matches[].prediction.result90",
    layer: "Forecast",
    type: "probability",
    use: "Probabilitas 90 menit: home, draw, away.",
    fe: "Forecast card, match detail, narrative detail.",
  },
  {
    key: "matches[].prediction.advance",
    layer: "Forecast",
    type: "probability",
    use: "Peluang lolos pada fase knockout setelah extra time/penalty scenario.",
    fe: "Match detail dan bracket interpretation.",
  },
  {
    key: "matches[].prediction.scorelines",
    layer: "Forecast",
    type: "ranked scenario",
    use: "Skenario skor paling mungkin beserta probabilitasnya.",
    fe: "Match detail, AI narrative prompt.",
  },
  {
    key: "matches[].prediction.scorers",
    layer: "Players",
    type: "player probability",
    use: "Prediksi anytime scorer, xG, goals, dan penalty taker.",
    fe: "Players, player detail, match detail.",
  },
  {
    key: "matches[].basis",
    layer: "Model basis",
    type: "explainability",
    use: "Dasar penilaian model seperti xG, Elo, market blend, dan form.",
    fe: "Match detail, data dictionary.",
  },
  {
    key: "matches[].intelligence.weather",
    layer: "Context",
    type: "environment",
    use: "Kondisi cuaca venue untuk memperkaya konteks pertandingan.",
    fe: "Match detail, data quality, AI narrative.",
  },
  {
    key: "matches[].intelligence.teamStats",
    layer: "Context",
    type: "team stats",
    use: "Possession, shots, corners, fouls, cards untuk kedua tim.",
    fe: "Match detail, compare, team detail.",
  },
  {
    key: "matches[].intelligence.availability",
    layer: "Context",
    type: "team news",
    use: "Cedera/suspensi/availability pemain yang memengaruhi analisis.",
    fe: "Match detail, players, AI narrative.",
  },
  {
    key: "matches[].intelligence.h2h",
    layer: "Context",
    type: "history",
    use: "Riwayat head-to-head untuk tambahan narasi dan risiko.",
    fe: "Match detail, AI narrative.",
  },
  {
    key: "history.evaluation.matches",
    layer: "Audit",
    type: "backtest",
    use: "Pertandingan lama untuk mengukur akurasi dan log-loss model.",
    fe: "History, history detail, model lab.",
  },
  {
    key: "dataFreshness[]",
    layer: "Ops",
    type: "collector health",
    use: "Last run, total run, dan error per sumber data.",
    fe: "Sources, changelog, source gaps.",
  },
  {
    key: "sourceDetails{}",
    layer: "Ops",
    type: "collector logs",
    use: "Endpoint, status count, dan log terbaru tiap source.",
    fe: "Source detail, changelog.",
  },
  {
    key: "tournament.teams[]",
    layer: "Tournament",
    type: "team profile",
    use: "Strength, form, record, route, top scorers, dan availability per tim.",
    fe: "Teams, team detail, compare, dashboard.",
  },
];

export default function DataDictionary() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat data dictionary.</div>;
  if (!data) return <FullPageLoader text="Memuat data dictionary" />;

  const fieldCount = DICTIONARY.length;
  const layers = new Set(DICTIONARY.map((row) => row.layer)).size;
  const sourceCount = data.dataFreshness?.length || 0;

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Data dictionary</Pill>
          <h1>Data Dictionary</h1>
          <p className="page-sub">
            Peta field utama yang dipakai frontend dan paket narasi AI. Ini
            membantu membaca data model tanpa perlu membuka JSON mentah.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Field mapped" value={fieldCount} />
          <StatTile label="Layers" value={layers} />
          <StatTile label="Sources" value={sourceCount} tone="home" />
        </div>
      </div>

      <section className="panel dictionary-summary">
        <div>
          <h2>Export schema</h2>
          <p className="panel-sub">
            Generated {formatGeneratedAtUtc7(data.generated_at)} dari model {data.model?.name || "-"}.
          </p>
        </div>
        <Link to="/sources">Lihat sumber data</Link>
      </section>

      <div className="dictionary-grid">
        {DICTIONARY.map((row) => (
          <article className="dictionary-card" key={row.key}>
            <div className="dictionary-card-head">
              <Pill tone="muted">{row.layer}</Pill>
              <span>{row.type}</span>
            </div>
            <h2>{row.key}</h2>
            <p>{row.use}</p>
            <em>{row.fe}</em>
          </article>
        ))}
      </div>
    </>
  );
}
