import { Link } from "react-router-dom";
import { usePredictions } from "../data.js";
import { FullPageLoader, Pill, StatTile } from "../components.jsx";

export default function Sources() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat sumber data.</div>;
  if (!data) return <FullPageLoader text="Memuat sumber data" />;

  const rows = data.dataFreshness || [];
  const totalRuns = rows.reduce((sum, row) => sum + row.runs, 0);
  const totalErrors = rows.reduce((sum, row) => sum + row.errors, 0);
  const latest = rows
    .map((row) => row.lastRun)
    .filter(Boolean)
    .sort()
    .at(-1);

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Freshness data</Pill>
          <h1>Sumber data</h1>
          <p className="page-sub">
            Pantau kapan tiap collector terakhir berjalan, jumlah run, dan error
            yang tercatat di database. Semua waktu ditampilkan dalam UTC+7.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Sources" value={rows.length} />
          <StatTile label="Total runs" value={totalRuns} />
          <StatTile label="Errors" value={totalErrors} tone={totalErrors ? "away" : "home"} />
        </div>
      </div>

      <section className="panel source-summary">
        <div>
          <h2>Export frontend</h2>
          <p className="panel-sub">
            Generated at {formatFreshness(data.generated_at)}. Last collector run {formatFreshness(latest)}.
          </p>
        </div>
        <Pill tone={totalErrors ? "danger" : "live"}>
          {totalErrors ? `${totalErrors} errors` : "Healthy"}
        </Pill>
      </section>

      <div className="source-grid">
        {rows.map((row) => (
          <SourceCard row={row} key={row.source} />
        ))}
      </div>
    </>
  );
}

function SourceCard({ row }) {
  const hasErrors = row.errors > 0;
  return (
    <Link
      to={`/sources/${encodeURIComponent(row.source)}`}
      className={`source-card ${hasErrors ? "has-errors" : ""}`}
    >
      <div className="source-head">
        <div>
          <strong>{row.source}</strong>
          <span>Last run: {formatFreshness(row.lastRun)}</span>
        </div>
        <Pill tone={hasErrors ? "danger" : "live"}>{hasErrors ? "Attention" : "OK"}</Pill>
      </div>

      <div className="source-stats">
        <StatTile label="Runs" value={row.runs} />
        <StatTile label="Errors" value={row.errors} tone={hasErrors ? "away" : "home"} />
      </div>
    </Link>
  );
}

function formatFreshness(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("id-ID", {
    timeZone: "Asia/Jakarta",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
}
