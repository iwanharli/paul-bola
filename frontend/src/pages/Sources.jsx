import { Link } from "react-router-dom";
import { usePredictions } from "../data.js";
import { FullPageLoader, Pill, StatTile } from "../components.jsx";

export default function Sources() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat sumber data.</div>;
  if (!data) return <FullPageLoader text="Memuat sumber data" />;

  const rows = data.dataFreshness || [];
  const totalRuns = rows.reduce((sum, row) => sum + row.runs, 0);
  const attentionCount = rows.filter((row) => row.needsAttention).length;
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
          <StatTile label="Perlu perhatian" value={attentionCount} tone={attentionCount ? "away" : "home"} />
        </div>
      </div>

      <section className="panel source-summary">
        <div>
          <h2>Export frontend</h2>
          <p className="panel-sub">
            Generated at {formatFreshness(data.generated_at)}. Last collector run {formatFreshness(latest)}.
            Status dinilai dari kesehatan terkini (error 24 jam terakhir atau run terakhir gagal), bukan error lama.
          </p>
        </div>
        <Pill tone={attentionCount ? "danger" : "live"}>
          {attentionCount ? `${attentionCount} perlu perhatian` : "Healthy"}
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
  const needsAttention = row.needsAttention;
  return (
    <Link
      to={`/sources/${encodeURIComponent(row.source)}`}
      className={`source-card ${needsAttention ? "has-errors" : ""}`}
    >
      <div className="source-head">
        <div>
          <strong>{row.source}</strong>
          <span>Last run: {formatFreshness(row.lastRun)}</span>
        </div>
        <Pill tone={needsAttention ? "danger" : "live"}>{needsAttention ? "Attention" : "OK"}</Pill>
      </div>

      <div className="source-stats">
        <StatTile label="Runs" value={row.runs} />
        <StatTile
          label="Error (24 jam)"
          value={row.recentErrors ?? 0}
          tone={needsAttention ? "away" : "home"}
        />
      </div>
      {row.errors > 0 && (row.recentErrors ?? 0) === 0 && (
        <span className="source-note">{row.errors} error lama (tidak berulang)</span>
      )}
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
