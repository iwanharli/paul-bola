import { useMemo } from "react";
import { ReactFlow, Background, Controls, Handle, Position } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { formatShortMatchDateUtc7 } from "./data.js";
import { Flag } from "./components.jsx";

const nodeTypes = {
  match: MatchNode,
  roundLabel: RoundLabelNode,
};

const roundNames = {
  "Round of 32": "Round of 32",
  "Round of 16": "Round of 16",
  "Quarter-final": "Quarter-finals",
  "Semi-final": "Semi-finals",
  Final: "Final",
};

function MatchNode({ data }) {
  const { match, audit } = data;
  const isFinished = match.status === "finished";

  return (
    <article className={`bracket-node-card ${match.status} ${auditClass(audit)}`}>
      <Handle type="target" position={Position.Left} className="bracket-handle" />
      <div className="bracket-node-head">
        <span>{formatShortMatchDateUtc7(match)}</span>
        <b>{audit ? (audit.correct ? "TEPAT" : "MELESET") : match.period}</b>
      </div>
      <TeamRow match={match} side="home" muted={isFinished && match.winner && match.winner !== "home"} />
      <TeamRow match={match} side="away" muted={isFinished && match.winner && match.winner !== "away"} />
      <Handle type="source" position={Position.Right} className="bracket-handle" />
    </article>
  );
}

function auditClass(audit) {
  if (!audit) return "";
  return audit.correct ? "audit-correct" : "audit-wrong";
}

function RoundLabelNode({ data }) {
  return <div className="bracket-round-label">{data.label}</div>;
}

function TeamRow({ match, side, muted }) {
  const team = side === "home" ? match.home : match.away;
  const score = teamScore(match, side);
  const winner = match.winner === side;

  return (
    <div className={`bracket-team-row ${winner ? "winner" : ""} ${muted ? "muted" : ""}`}>
      <Flag team={team} />
      <span className="bracket-team-name">{team}</span>
      <strong>{score}</strong>
    </div>
  );
}

function teamScore(match, side) {
  const score = match.score || {};
  const prefix = side === "home" ? "home" : "away";
  const main = score[`${prefix}Et`] ?? score[prefix];
  const pens = score[`${prefix}Pens`];
  if (main === null || main === undefined) return "-";
  return pens === null || pens === undefined ? String(main) : `${main} (${pens})`;
}

function buildFlow(bracket, evaluation) {
  const auditByTeams = new Map();
  (evaluation?.matches || []).forEach((match) => {
    auditByTeams.set(teamPairKey(match.home, match.away), match);
  });

  const rounds = (bracket?.rounds || []).filter((round) =>
    (bracket?.matches || []).some((match) => match.round === round)
  );
  const grouped = new Map();
  rounds.forEach((round) => {
    grouped.set(
      round,
      (bracket.matches || [])
        .filter((match) => match.round === round)
        .sort((a, b) => a.matchNum - b.matchNum)
    );
  });

  const columnGap = 410;
  const rowGap = 172;
  const nodes = [];
  const edges = [];

  rounds.forEach((round, roundIndex) => {
    const matches = grouped.get(round) || [];
    const roundSpan = 2 ** roundIndex;
    const yOffset = ((roundSpan - 1) * rowGap) / 2;
    const x = roundIndex * columnGap;

    nodes.push({
      id: `label-${round}`,
      type: "roundLabel",
      position: { x, y: -74 },
      data: { label: roundNames[round] || round },
      selectable: false,
      draggable: false,
    });

    matches.forEach((match, matchIndex) => {
      nodes.push({
        id: `match-${match.matchNum}`,
        type: "match",
        position: { x, y: yOffset + matchIndex * rowGap * roundSpan },
        data: {
          match,
          audit: match.status === "finished" ? auditByTeams.get(teamPairKey(match.home, match.away)) : null,
        },
        selectable: false,
        draggable: false,
      });
    });
  });

  for (let roundIndex = 1; roundIndex < rounds.length; roundIndex += 1) {
    const previous = grouped.get(rounds[roundIndex - 1]) || [];
    const current = grouped.get(rounds[roundIndex]) || [];
    current.forEach((match, matchIndex) => {
      [previous[matchIndex * 2], previous[matchIndex * 2 + 1]].filter(Boolean).forEach((source) => {
        edges.push({
          id: `edge-${source.matchNum}-${match.matchNum}`,
          source: `match-${source.matchNum}`,
          target: `match-${match.matchNum}`,
          type: "step",
          selectable: false,
          style: { stroke: "rgba(148, 163, 184, 0.28)", strokeWidth: 2 },
        });
      });
    });
  }

  return { nodes, edges };
}

function teamPairKey(a, b) {
  return [a, b].filter(Boolean).sort().join("::");
}

export default function BracketFlow({ bracket, evaluation, showHeader = true, fullscreen = false }) {
  const { nodes, edges } = useMemo(() => buildFlow(bracket, evaluation), [bracket, evaluation]);
  if (!nodes.length) return null;

  return (
    <section className="bracket-section">
      {showHeader && (
        <div className="section-head">
          <div>
            <span className="eyebrow">Knockout map</span>
            <h2>Bracket turnamen</h2>
          </div>
          <p>Alur pertandingan dari Round of 32 sampai final, ditampilkan dalam waktu UTC+7.</p>
        </div>
      )}
      <div className={`bracket-shell ${fullscreen ? "fullscreen" : ""}`}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          defaultViewport={{ x: 28, y: 92, zoom: 0.82 }}
          minZoom={0.35}
          maxZoom={1.2}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          proOptions={{ hideAttribution: true }}
        >
          <Background color="rgba(148, 163, 184, 0.12)" gap={26} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </section>
  );
}
