import { useState } from "react";
import { Flag, FullPageLoader, Pill, StatTile } from "../components.jsx";
import { usePredictions } from "../data.js";

export default function Compare() {
  const { data, error } = usePredictions();
  const teams = data?.tournament?.teams || [];
  const [leftName, setLeftName] = useState("England");
  const [rightName, setRightName] = useState("Argentina");

  if (error) return <div className="state">Gagal memuat compare.</div>;
  if (!data) return <FullPageLoader text="Memuat compare" />;

  const left = teams.find((team) => team.name === leftName) || teams[0];
  const right = teams.find((team) => team.name === rightName) || teams[1] || teams[0];

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Compare</Pill>
          <h1>Compare teams</h1>
          <p className="page-sub">
            Bandingkan dua tim berdasarkan record, xG, Elo, attack/defense,
            finishing, dan statistik ESPN.
          </p>
        </div>
        <div className="compare-selects">
          <SelectTeam value={left.name} setValue={setLeftName} teams={teams} />
          <SelectTeam value={right.name} setValue={setRightName} teams={teams} />
        </div>
      </div>

      <section className="compare-board">
        <TeamCompareHeader team={left} />
        <div className="compare-versus">vs</div>
        <TeamCompareHeader team={right} right />
      </section>

      <section className="panel">
        <h2>Stat comparison</h2>
        <div className="compare-matrix">
          <CompareMetric label="Record" left={recordText(left)} right={recordText(right)} />
          <CompareMetric label="Elo" left={left.strength?.elo} right={right.strength?.elo} numeric />
          <CompareMetric label="Attack" left={left.strength?.attack} right={right.strength?.attack} numeric />
          <CompareMetric label="Defense" left={left.strength?.defense} right={right.strength?.defense} numeric />
          <CompareMetric label="xG" left={left.form?.xg} right={right.form?.xg} numeric />
          <CompareMetric label="Goals-xG" left={left.goalsMinusXg} right={right.goalsMinusXg} numeric />
          <CompareMetric label="Shots" left={left.teamStats?.shots} right={right.teamStats?.shots} numeric />
          <CompareMetric label="Possession" left={left.teamStats?.possession} right={right.teamStats?.possession} numeric />
        </div>
      </section>
    </>
  );
}

function SelectTeam({ value, setValue, teams }) {
  return (
    <label>
      <span>Team</span>
      <select value={value} onChange={(event) => setValue(event.target.value)}>
        {teams.map((team) => <option value={team.name} key={team.name}>{team.name}</option>)}
      </select>
    </label>
  );
}

function TeamCompareHeader({ team, right = false }) {
  return (
    <div className={`compare-team-card ${right ? "right" : ""}`}>
      <Flag team={team.name} />
      <div>
        <h2>{team.name}</h2>
        <span>{recordText(team)} / GD {signed(team.record?.goalDiff || 0, 0)}</span>
      </div>
    </div>
  );
}

function CompareMetric({ label, left, right, numeric = false }) {
  const leftNum = Number(left);
  const rightNum = Number(right);
  const leftWins = numeric && Number.isFinite(leftNum) && Number.isFinite(rightNum) && leftNum > rightNum;
  const rightWins = numeric && Number.isFinite(leftNum) && Number.isFinite(rightNum) && rightNum > leftNum;
  return (
    <div className="compare-metric">
      <strong className={leftWins ? "win" : ""}>{formatValue(left)}</strong>
      <span>{label}</span>
      <strong className={rightWins ? "win" : ""}>{formatValue(right)}</strong>
    </div>
  );
}

function recordText(team) {
  const record = team.record || {};
  return `${record.wins || 0}-${record.draws || 0}-${record.losses || 0}`;
}

function signed(value, digits = 1) {
  return `${value >= 0 ? "+" : ""}${Number(value).toFixed(digits)}`;
}

function formatValue(value) {
  if (value === null || value === undefined) return "-";
  return typeof value === "number" ? Number(value).toFixed(Math.abs(value) < 10 ? 2 : 0) : value;
}
