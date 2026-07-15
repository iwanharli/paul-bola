import { useParams, Link } from "react-router-dom";
import { formatMatchTimeUtc7, usePredictions, pct, pct0 } from "../data.js";
import { Flag, FullPageLoader, PlayerAvatar, ProbBar, Meter, Pill, StatTile } from "../components.jsx";

export default function MatchDetail() {
  const { id } = useParams();
  const { data, error } = usePredictions();
  if (error) return <div className="state">Gagal memuat detail.</div>;
  if (!data) return <FullPageLoader text="Memuat detail pertandingan" />;

  const m = data.matches.find((x) => x.id === id);
  if (!m) return <div className="state">Match tidak ditemukan. <Link to="/">Kembali</Link></div>;

  const p = m.prediction;
  const b = m.basis;
  const intel = m.intelligence || {};
  const bestScore = p.scorelines[0];
  const homeOver = b.form.home.goals - b.form.home.xg;
  const awayOver = b.form.away.goals - b.form.away.xg;

  return (
    <>
      <Link to="/" className="back">← Semua pertandingan</Link>

      <div className="detail-hero">
        <div className="detail-hero-top">
          <Pill tone={m.status === "scenario" ? "muted" : "live"}>{m.round}</Pill>
          <span>{formatMatchTimeUtc7(m)}</span>
        </div>
        <div className="detail-teams">
          <div className="detail-team">
            <Flag team={m.home} />
            <span>{m.home}</span>
          </div>
          <div className="detail-xg">
            <span className="xg-num">{p.xg.home}</span>
            <span className="xg-label">xG</span>
            <span className="xg-num">{p.xg.away}</span>
          </div>
          <div className="detail-team detail-team-right">
            <span>{m.away}</span>
            <Flag team={m.away} />
          </div>
        </div>
        <div className="detail-meta">{m.venue}</div>
        <div className="detail-kpis">
          <StatTile label="Skor paling mungkin" value={bestScore ? bestScore.score : "-"} />
          <StatTile label={`${m.home} 90m`} value={pct0(p.result90.home)} tone="home" />
          <StatTile label="Draw 90m" value={pct0(p.result90.draw)} />
          <StatTile label={`${m.away} 90m`} value={pct0(p.result90.away)} tone="away" />
        </div>
      </div>

      <section className="panel primary-panel">
        <div className="panel-head">
          <div>
            <h2>Hasil 90 menit</h2>
            <p className="panel-sub">Probabilitas win / draw / win dari model.</p>
          </div>
        </div>
        <ProbBar home={p.result90.home} draw={p.result90.draw} away={p.result90.away}
                 homeName={m.home} awayName={m.away} />
        {p.advance && (
          <div className="advance-grid">
            <div>
              <span className="k">{m.home} lolos</span>
              <Meter value={p.advance.home} tone="home" />
            </div>
            <div>
              <span className="k">{m.away} lolos</span>
              <Meter value={p.advance.away} tone="away" />
            </div>
          </div>
        )}
      </section>

      {p.knockout && (
        <section className="panel">
          <h2>Kalau seri: extra time &amp; adu penalti</h2>
          <p className="panel-sub">
            Dari {pct0(p.knockout.draw_after_90)} peluang masih seri di menit 90,
            begini pecahannya:
          </p>
          <Meter value={p.knockout.et_win_home_given_draw} tone="home"
                 label={`${m.home} menang di ET`} />
          <Meter value={p.knockout.et_win_away_given_draw} tone="away"
                 label={`${m.away} menang di ET`} />
          <Meter value={p.knockout.shootout_given_still_level} tone="accent"
                 label="Masih imbang → adu penalti" />
          {p.knockout.shootout_is_coinflip_assumption && (
            <p className="tiny-note" style={{ marginTop: 10 }}>
              Adu penalti sendiri dihitung 50/50 (koin lempar) — tidak ada data
              histori adu penalti di database untuk dijadikan model. Catatan:
              kiper Argentina Emiliano Martínez punya rekam jejak adu penalti
              yang kuat (final Piala Dunia 2022, 2x juara Copa America) yang
              sengaja belum dimasukkan ke perhitungan ini.
            </p>
          )}
        </section>
      )}

      {p.market && (
        <section className="panel">
          <h2>Model vs market</h2>
          <p className="panel-sub">
            Angka final memakai 25% model dan 75% market karena kombinasi ini
            paling kuat di validasi.
          </p>
          <div className="compare">
            <CompareRow label="Model" v={p.result90} home={m.home} away={m.away} />
            <CompareRow label="Market" v={p.market} home={m.home} away={m.away} />
            <CompareRow label="Blend" v={p.blend} home={m.home} away={m.away} highlight />
          </div>
        </section>
      )}

      <AINarrativePacketCard match={m} evaluation={data.history?.evaluation} />

      <div className="intelligence-grid">
        <WeatherCard weather={intel.weather} />
        <TeamNewsCard items={intel.availability} coverage={intel.availabilityCoverage} />
        <OddsCard odds={intel.odds} />
        <RefereeCard referee={intel.referee} />
      </div>

      <div className="detail-grid">
        <section className="panel">
          <h2>Skor paling mungkin</h2>
          <div className="scorelines">
            {p.scorelines.map((s) => (
              <div className="scoreline" key={s.score}>
                <span className="scoreline-score">{s.score}</span>
                <div className="scoreline-bar">
                  <div style={{ width: `${(s.p / p.scorelines[0].p) * 100}%` }} />
                </div>
                <span className="scoreline-p">{pct(s.p)}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Dasar penilaian</h2>
          <div className="basis-grid compact-basis">
            <BasisTeam name={m.home} s={b.strength.home} f={b.form.home} />
            <BasisTeam name={m.away} s={b.strength.away} f={b.form.away} />
          </div>
        </section>
      </div>

      <section className="panel">
        <h2>Ringkasan form</h2>
        <div className="form-strip">
          <StatTile label={`${m.home} xG`} value={b.form.home.xg} tone="home" />
          <StatTile label={`${m.home} goals-xG`} value={formatDiff(homeOver)} />
          <StatTile label={`${m.away} xG`} value={b.form.away.xg} tone="away" />
          <StatTile label={`${m.away} goals-xG`} value={formatDiff(awayOver)} />
        </div>
        <ul className="notes">
          {b.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      </section>

      <section className="panel">
        <h2>Stat tim dari ESPN</h2>
        <p className="panel-sub">Rata-rata per match dari pertandingan yang sudah tersedia di feed ESPN.</p>
        <TeamStatsCompare home={m.home} away={m.away} stats={intel.teamStats} />
      </section>

      <div className="detail-grid equal">
        <RouteCard title={`Route ${m.home}`} rows={intel.route?.home} />
        <RouteCard title={`Route ${m.away}`} rows={intel.route?.away} />
      </div>

      <div className="detail-grid equal">
        <H2HCard rows={intel.h2h} />
        <LeadersCard rows={data.tournament?.topScorers} />
      </div>

      {p.scorers && (
        <section className="panel">
          <h2>Anytime goalscorer</h2>
          <div className="scorer-cols">
            <ScorerCol title={m.home} list={p.scorers.home} />
            <ScorerCol title={m.away} list={p.scorers.away} />
          </div>
        </section>
      )}

      <section className="panel">
        <h2>Validasi model</h2>
        <p className="panel-sub">
          Train di fase grup, diuji pada knockout. Log-loss lebih rendah berarti
          kalibrasi lebih baik.
        </p>
        <table className="valtable">
          <thead>
            <tr><th>Model</th><th>Akurasi</th><th>Log-loss</th></tr>
          </thead>
          <tbody>
            {data.model.heldout.map((row) => (
              <tr key={row.model}>
                <td>{row.model}</td>
                <td>{pct0(row.acc)}</td>
                <td>{row.logloss.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div className="model-note">
        <strong>Freshness data</strong>
        <span>Sumber data dan status collector tersedia di halaman khusus.</span>
        <Link to="/sources">Lihat sources</Link>
      </div>
    </>
  );
}

function formatDiff(value) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

function CompareRow({ label, v, home, away, highlight }) {
  return (
    <div className={`compare-row ${highlight ? "compare-hi" : ""}`}>
      <span className="compare-label">{label}</span>
      <ProbBar home={v.home} draw={v.draw} away={v.away} homeName={home} awayName={away} />
    </div>
  );
}

function AINarrativePacketCard({ match, evaluation }) {
  const packet = buildNarrativePacket(match, evaluation);
  return (
    <section className="panel ai-packet-panel">
      <div className="panel-head ai-packet-head">
        <div>
          <h2>Narasi AI</h2>
          <p className="panel-sub">
            Paket data yang siap dikirim ke AI agar analisis match tajam, probabilistik, dan tidak mengarang.
          </p>
        </div>
        <Pill tone="muted">Prepared packet</Pill>
      </div>

      <div className="ai-packet-grid">
        {packet.items.map((item) => (
          <div className="ai-packet-item" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            {item.note && <em>{item.note}</em>}
          </div>
        ))}
      </div>

      <div className="ai-packet-bottom">
        <div>
          <strong>Instruksi narasi</strong>
          <span>
            Gunakan hanya data di paket ini; jelaskan peluang, faktor pembeda,
            risiko model, pemain kunci, dan batasan data.
          </span>
        </div>
        <div>
          <strong>Data warning</strong>
          <span>{packet.warnings.length ? packet.warnings.join(" / ") : "Tidak ada gap besar pada paket ini."}</span>
        </div>
      </div>
    </section>
  );
}

function buildNarrativePacket(match, evaluation) {
  const p = match.prediction;
  const b = match.basis;
  const intel = match.intelligence || {};
  const homeOver = b.form.home.goals - b.form.home.xg;
  const awayOver = b.form.away.goals - b.form.away.xg;
  const favoriteHome = p.advance
    ? p.advance.home >= p.advance.away
    : p.result90.home >= p.result90.away;
  const favorite = favoriteHome ? match.home : match.away;
  const favoriteProb = p.advance
    ? (favoriteHome ? p.advance.home : p.advance.away)
    : (favoriteHome ? p.result90.home : p.result90.away);

  const warnings = [];
  if (!intel.weather) warnings.push("cuaca kosong");
  if (!intel.odds?.length) warnings.push("odds snapshot kosong");
  if (!intel.h2h?.length) warnings.push("H2H khusus kosong");
  if (!intel.referee) warnings.push("referee tendency kosong");
  if (!intel.availability?.length && !intel.availabilityCoverage?.length) warnings.push("team news kosong");

  return {
    items: [
      {
        label: "Match",
        value: `${match.home} vs ${match.away}`,
        note: `${match.round} / ${formatMatchTimeUtc7(match)}`,
      },
      {
        label: "Angka utama",
        value: `${match.home} ${pct0(p.result90.home)} / Draw ${pct0(p.result90.draw)} / ${match.away} ${pct0(p.result90.away)}`,
        note: p.blend ? "Narasi harus memakai blend sebagai angka akhir." : "Narasi memakai output model.",
      },
      {
        label: "Favorit",
        value: `${favorite} ${pct0(favoriteProb)}`,
        note: p.advance ? "berdasarkan peluang lolos" : "berdasarkan peluang 90 menit",
      },
      {
        label: "xG prediksi",
        value: `${p.xg.home} - ${p.xg.away}`,
        note: `${match.home} vs ${match.away}`,
      },
      {
        label: "Top scoreline",
        value: p.scorelines?.[0] ? `${p.scorelines[0].score} (${pct(p.scorelines[0].p)})` : "-",
        note: "dipakai sebagai skenario, bukan kepastian",
      },
      {
        label: "Finishing signal",
        value: `${match.home} ${formatDiff(homeOver)} / ${match.away} ${formatDiff(awayOver)}`,
        note: "goals minus xG turnamen",
      },
      {
        label: "Pemain kunci",
        value: topScorerLine(p.scorers, match.home, match.away),
        note: "anytime goalscorer tertinggi per tim",
      },
      {
        label: "Validasi model",
        value: evaluation?.accuracy ? `${pct0(evaluation.accuracy)} acc / ${evaluation.avgLogLoss} log-loss` : "Belum ada audit",
        note: evaluation?.splitDate ? `split ${evaluation.splitDate}` : null,
      },
    ],
    warnings,
  };
}

function topScorerLine(scorers, home, away) {
  if (!scorers) return "-";
  const homeTop = scorers.home?.[0];
  const awayTop = scorers.away?.[0];
  return [
    homeTop ? `${homeTop.name} ${pct0(homeTop.p)}` : `${home} -`,
    awayTop ? `${awayTop.name} ${pct0(awayTop.p)}` : `${away} -`,
  ].join(" / ");
}

function WeatherCard({ weather }) {
  return (
    <section className="panel compact-panel">
      <h2>Cuaca</h2>
      {weather ? (
        <div className="mini-grid">
          <StatTile label="Temp" value={`${weather.temperatureC}C`} />
          <StatTile label="Humidity" value={`${weather.humidityPct}%`} />
          <StatTile label="Rain" value={`${weather.precipitationMm}mm`} />
          <StatTile label="Wind" value={`${weather.windKmh}km/h`} />
        </div>
      ) : (
        <EmptyText text="Belum ada data cuaca untuk match ini." />
      )}
    </section>
  );
}

function TeamNewsCard({ items = [], coverage = [] }) {
  return (
    <section className="panel compact-panel">
      <h2>Team news</h2>
      {items.length ? (
        <div className="info-list">
          {items.map((item) => (
            <div className="info-row" key={`${item.team}-${item.player}`}>
              <div className="player-info">
                <PlayerAvatar name={item.player} team={item.team} size="sm" />
                <div>
                  <strong>{item.player}</strong>
                  <span><Flag team={item.team} /> {item.team} / {item.reason}</span>
                </div>
              </div>
              <em className={`status ${item.status}`}>{item.status}</em>
            </div>
          ))}
        </div>
      ) : coverage.length ? (
        <div className="info-list">
          {coverage.map((item) => (
            <div className="info-row" key={item.team}>
              <div>
                <strong><Flag team={item.team} /> {item.team}</strong>
                <span>{item.playerCount} pemain dicek dari squad feed. {item.note}</span>
              </div>
              <em className="status fit">{item.specialStatusCount ? `${item.specialStatusCount} flagged` : "checked"}</em>
            </div>
          ))}
        </div>
      ) : (
        <EmptyText text="Tidak ada status pemain khusus." />
      )}
    </section>
  );
}

function OddsCard({ odds = [] }) {
  return (
    <section className="panel compact-panel">
      <h2>Market odds</h2>
      {odds.length ? (
        <div className="info-list">
          {odds.slice(0, 3).map((row) => (
            <div className="info-row" key={`${row.bookmaker}-${row.market}`}>
              <div>
                <strong>{row.bookmaker}</strong>
                <span>{row.market}</span>
              </div>
              <code>{row.team1Odds}{row.drawOdds ? ` / ${row.drawOdds}` : ""} / {row.team2Odds}</code>
            </div>
          ))}
        </div>
      ) : (
        <EmptyText text="Belum ada odds snapshot untuk match ini." />
      )}
    </section>
  );
}

function RefereeCard({ referee }) {
  return (
    <section className="panel compact-panel">
      <h2>Referee</h2>
      {referee ? (
        <>
          <div className="referee-name">{referee.name}</div>
          <div className="mini-grid two">
            <StatTile label="Sample" value={referee.matchesSampled} />
            <StatTile label="Avg YC" value={referee.avgYellow} />
          </div>
          <p className="tiny-note">{referee.notes}</p>
        </>
      ) : (
        <EmptyText text="Belum ada referee tendency." />
      )}
    </section>
  );
}

function TeamStatsCompare({ home, away, stats }) {
  const homeStats = stats?.home;
  const awayStats = stats?.away;
  if (!homeStats || !awayStats) return <EmptyText text="Stat ESPN belum lengkap untuk kedua tim." />;

  const rows = [
    ["Matches", "matches"],
    ["Possession", "possession", "%"],
    ["Shots", "shots"],
    ["Corners", "corners"],
    ["Fouls", "fouls"],
    ["Yellows", "yellows"],
    ["Reds", "reds"],
  ];

  return (
    <div className="stat-compare">
      <div className="compare-head">
        <span className="compare-team"><Flag team={home} /> {home}</span>
        <span />
        <span className="compare-team compare-team-right">{away} <Flag team={away} /></span>
      </div>
      {rows.map(([label, key, suffix = ""]) => (
        <div className="compare-stat" key={key}>
          <strong>{formatStat(homeStats[key], suffix)}</strong>
          <span>{label}</span>
          <strong>{formatStat(awayStats[key], suffix)}</strong>
        </div>
      ))}
    </div>
  );
}

function RouteCard({ title, rows = [] }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {rows.length ? (
        <div className="route-list">
          {rows.map((row) => (
            <div className="route-row" key={`${row.date}-${row.round}-${row.opponent}`}>
              <em className={`result ${row.result}`}>{row.result}</em>
              <div>
                <strong>
                  <span className="route-score">{row.score}</span>
                  <span className="route-vs">vs</span>
                  <Flag team={row.opponent} />
                  <span>{row.opponent}</span>
                </strong>
                <span>{row.round} / {row.ground}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyText text="Belum ada route historis." />
      )}
    </section>
  );
}

function H2HCard({ rows = [] }) {
  return (
    <section className="panel">
      <h2>Head-to-head</h2>
      {rows.length ? (
        <div className="timeline">
          {rows.map((row) => (
            <div className="timeline-row" key={`${row.year}-${row.score}`}>
              <span>{row.year}</span>
              <div>
                <strong>{row.score}</strong>
                <em>{row.round}{row.notes ? ` / ${row.notes}` : ""}</em>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyText text="Tidak ada H2H khusus untuk matchup ini." />
      )}
    </section>
  );
}

function LeadersCard({ rows = [] }) {
  return (
    <section className="panel">
      <h2>Top scorers turnamen</h2>
      <div className="leader-list">
        {rows.slice(0, 6).map((row, index) => (
          <div className="leader-row" key={`${row.name}-${row.team}`}>
            <span>{index + 1}</span>
            <PlayerAvatar name={row.name} team={row.team} size="sm" />
            <strong>{row.name}</strong>
            <em><Flag team={row.team} /> {row.team}</em>
            <b>{row.goals}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function EmptyText({ text }) {
  return <p className="empty-text">{text}</p>;
}

function formatStat(value, suffix = "") {
  if (value === null || value === undefined) return "-";
  return `${value}${suffix}`;
}

function ScorerCol({ title, list }) {
  return (
    <div className="scorer-col">
      <h3>{title}</h3>
      {list.map((s) => (
        <div className="scorer" key={s.name}>
          <div className="scorer-main">
            <div className="scorer-player">
              <PlayerAvatar name={s.name} team={title} size="sm" />
              <span className="scorer-name">
                {s.name}{s.penTaker && <span className="pen-tag">PEN</span>}
              </span>
            </div>
            <span className="scorer-p">{pct0(s.p)}</span>
          </div>
          <div className="scorer-bar"><div style={{ width: pct0(s.p) }} /></div>
          <div className="scorer-sub">{s.goals} goals · {s.xg} xG this tournament</div>
        </div>
      ))}
    </div>
  );
}

function BasisTeam({ name, s, f }) {
  const over = f.goals - f.xg;
  return (
    <div className="basis-team">
      <h3><Flag team={name} /> <span>{name}</span></h3>
      <div className="basis-stat"><span>Attack</span><b>{s.attack.toFixed(2)}</b></div>
      <div className="basis-stat"><span>Defense</span><b>{s.defense.toFixed(2)}</b></div>
      <div className="basis-stat"><span>Elo rating</span><b>{s.elo}</b></div>
      <div className="basis-stat"><span>Turnamen xG</span><b>{f.xg}</b></div>
      <div className="basis-stat">
        <span>Goals - xG</span>
        <b className={over > 0.5 ? "over" : over < -0.5 ? "under" : ""}>
          {f.goals} ({formatDiff(over)})
        </b>
      </div>
    </div>
  );
}
