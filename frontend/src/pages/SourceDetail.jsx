import { Link, useParams } from "react-router-dom";
import { usePredictions } from "../data.js";
import { FullPageLoader, Pill, StatTile } from "../components.jsx";

export default function SourceDetail() {
  const { source: encodedSource } = useParams();
  const source = decodeURIComponent(encodedSource || "");
  const { data, error } = usePredictions();

  if (error) return <div className="state">Gagal memuat detail source.</div>;
  if (!data) return <FullPageLoader text="Memuat detail source" />;

  const summary = (data.dataFreshness || []).find((row) => row.source === source);
  const detail = data.sourceDetails?.[source];

  if (!summary || !detail) {
    return (
      <div className="state">
        Source tidak ditemukan. <Link to="/sources">Kembali ke sources</Link>
      </div>
    );
  }

  const hasErrors = summary.errors > 0;
  const statusCounts = detail.statusCounts || {};

  return (
    <>
      <Link to="/sources" className="back">← Semua sumber data</Link>

      <div className="page-hero history-hero">
        <div>
          <Pill tone={hasErrors ? "danger" : "live"}>{hasErrors ? "Attention" : "Healthy"}</Pill>
          <h1>{source}</h1>
          <p className="page-sub">
            Detail collector log untuk source ini: endpoint yang pernah berjalan,
            status terakhir, dan catatan run terbaru dari database.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Runs" value={summary.runs} />
          <StatTile label="Errors" value={summary.errors} tone={hasErrors ? "away" : "home"} />
          <StatTile label="Last run" value={formatFreshness(summary.lastRun)} />
        </div>
      </div>

      <section className="panel source-summary">
        <div>
          <h2>Status summary</h2>
          <p className="panel-sub">
            Last run {formatFreshness(summary.lastRun)}. Recent log ditampilkan maksimal 30 entri terbaru.
          </p>
        </div>
        <div className="status-counts">
          {Object.entries(statusCounts).map(([status, count]) => (
            <Pill tone={status === "error" ? "danger" : "live"} key={status}>
              {status}: {count}
            </Pill>
          ))}
        </div>
      </section>

      <div className="detail-grid equal">
        <section className="panel">
          <h2>Endpoints</h2>
          <div className="endpoint-list">
            {(detail.endpoints || []).map((endpoint) => (
              <span key={endpoint}>{endpoint}</span>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Source health</h2>
          <div className="mini-grid">
            <StatTile label="Success" value={statusCounts.success || 0} tone="home" />
            <StatTile label="Error" value={statusCounts.error || 0} tone={hasErrors ? "away" : "home"} />
            <StatTile label="Partial" value={statusCounts.partial || 0} />
            <StatTile label="Endpoint count" value={(detail.endpoints || []).length} />
          </div>
        </section>
      </div>

      <section className="panel">
        <h2>Recent collector log</h2>
        <div className="source-log-list">
          {(detail.recentLogs || []).map((log, index) => (
            <LogRow log={log} key={`${log.runAt}-${log.endpoint}-${log.scope}-${index}`} />
          ))}
        </div>
      </section>
    </>
  );
}

function LogRow({ log }) {
  const isError = log.status === "error";
  return (
    <div className={`source-log-row ${isError ? "error" : ""}`}>
      <div>
        <Pill tone={isError ? "danger" : "live"}>{log.status}</Pill>
      </div>
      <div>
        <strong>{log.endpoint}</strong>
        <span>{log.scope}</span>
        {log.detail && <em>{log.detail}</em>}
      </div>
      <time>{formatFreshness(log.runAt)}</time>
    </div>
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
