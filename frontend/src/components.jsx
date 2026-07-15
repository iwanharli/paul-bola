import { FLAGS, pct0, playerAvatarSrc } from "./data.js";

export function AppLogo({ className = "" }) {
  return (
    <img
      className={`app-logo ${className}`}
      src={`${import.meta.env.BASE_URL}paul-logo.png`}
      alt="Paul"
    />
  );
}

export function FullPageLoader({ text = "Memuat aplikasi" }) {
  return (
    <div className="full-loader" role="status" aria-live="polite">
      <div className="loader-orbit" aria-hidden="true">
        <AppLogo className="loader-logo" />
      </div>
      <strong>{text}</strong>
      <span>Menyiapkan data forecast dan audit model</span>
      <div className="loader-line" aria-hidden="true" />
    </div>
  );
}

export function Flag({ team }) {
  return (
    <span className="flag" title={team} aria-label={team}>
      <span aria-hidden="true">{FLAGS[team] || "🏳️"}</span>
    </span>
  );
}

export function PlayerAvatar({ name, team, size = "" }) {
  return (
    <img
      className={`player-avatar ${size}`}
      src={playerAvatarSrc(name, team)}
      alt=""
      loading="lazy"
      aria-hidden="true"
    />
  );
}

// three-way win / draw / win probability bar
export function ProbBar({ home, draw, away, homeName, awayName, compact = false }) {
  return (
    <div className={`probbar-wrap ${compact ? "compact" : ""}`}>
      <div className="probbar">
        <div className="seg seg-home" style={{ width: pct0(home) }} title={`${homeName} ${pct0(home)}`} />
        <div className="seg seg-draw" style={{ width: pct0(draw) }} title={`Draw ${pct0(draw)}`} />
        <div className="seg seg-away" style={{ width: pct0(away) }} title={`${awayName} ${pct0(away)}`} />
      </div>
      <div className="probbar-legend">
        <span><i className="dot dot-home" /> {homeName} {pct0(home)}</span>
        <span><i className="dot dot-draw" /> Draw {pct0(draw)}</span>
        <span><i className="dot dot-away" /> {awayName} {pct0(away)}</span>
      </div>
    </div>
  );
}

// horizontal meter for a single probability (0..1)
export function Meter({ value, tone = "accent", label, right }) {
  return (
    <div className="meter-row">
      {label && <div className="meter-label">{label}</div>}
      <div className="meter-track">
        <div className={`meter-fill tone-${tone}`} style={{ width: pct0(value) }} />
      </div>
      <div className="meter-value">{right ?? pct0(value)}</div>
    </div>
  );
}

export function Pill({ children, tone = "" }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

export function StatTile({ label, value, tone = "" }) {
  return (
    <div className={`stat-tile ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
