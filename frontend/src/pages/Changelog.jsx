import { Link } from "react-router-dom";
import { FullPageLoader, Pill, StatTile } from "../components.jsx";
import { formatGeneratedAtUtc7, pct0, usePredictions } from "../data.js";

export default function Changelog() {
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat changelog.</div>;
  if (!data) return <FullPageLoader text="Memuat changelog" />;

  const events = buildEvents(data);
  const sourceErrors = (data.dataFreshness || []).reduce((sum, row) => sum + (row.errors || 0), 0);
  const heldout = data.history?.evaluation;

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Run history</Pill>
          <h1>Changelog</h1>
          <p className="page-sub">
            Riwayat export frontend, refresh collector, dan snapshot performa
            model yang sedang ditampilkan aplikasi.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Events" value={events.length} />
          <StatTile label="Source errors" value={sourceErrors} tone={sourceErrors ? "away" : "home"} />
          <StatTile label="Model accuracy" value={heldout ? pct0(heldout.accuracy) : "-"} tone="home" />
        </div>
      </div>

      <section className="panel changelog-current">
        <div>
          <h2>Current export</h2>
          <p className="panel-sub">
            {data.model?.name || "-"} / generated {formatGeneratedAtUtc7(data.generated_at)}.
          </p>
        </div>
        <Link to="/data-dictionary">Lihat schema</Link>
      </section>

      <div className="changelog-list">
        {events.map((event) => (
          <article className={`changelog-row ${event.tone}`} key={`${event.type}-${event.title}-${event.time}`}>
            <time>{formatGeneratedAtUtc7(event.time)}</time>
            <div>
              <strong>{event.title}</strong>
              <span>{event.detail}</span>
            </div>
            {event.to ? <Link to={event.to}>{event.action}</Link> : <Pill tone={event.tone === "danger" ? "danger" : "muted"}>{event.type}</Pill>}
          </article>
        ))}
      </div>
    </>
  );
}

function buildEvents(data) {
  const events = [
    {
      type: "export",
      tone: "live",
      title: "Frontend predictions exported",
      detail: `${data.matches?.length || 0} upcoming matches, ${data.tournament?.teams?.length || 0} teams, ${data.dataFreshness?.length || 0} sources.`,
      time: data.generated_at,
      to: "/forecast",
      action: "Forecast",
    },
  ];

  (data.dataFreshness || []).forEach((row) => {
    events.push({
      type: "source",
      tone: row.errors ? "danger" : "muted",
      title: `${row.source} collector`,
      detail: `${row.runs || 0} runs, ${row.errors || 0} errors.`,
      time: row.lastRun,
      to: `/sources/${encodeURIComponent(row.source)}`,
      action: "Detail",
    });
  });

  const heldout = data.history?.evaluation;
  if (heldout) {
    events.push({
      type: "model",
      tone: "live",
      title: "Held-out backtest snapshot",
      detail: `${heldout.correct}/${heldout.total} benar, avg log-loss ${heldout.avgLogLoss}. Split ${heldout.splitDate}.`,
      time: latestHistoryDate(heldout.matches) || data.generated_at,
      to: "/model-lab",
      action: "Model lab",
    });
  }

  return events
    .filter((event) => event.time)
    .sort((a, b) => new Date(b.time) - new Date(a.time));
}

function latestHistoryDate(matches = []) {
  const latest = matches.map((row) => row.date).filter(Boolean).sort().at(-1);
  return latest ? `${latest}T23:59:00+07:00` : null;
}
