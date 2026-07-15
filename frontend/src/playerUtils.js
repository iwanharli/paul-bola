export function playerSlug(name = "", team = "") {
  return encodeURIComponent(`${name}__${team}`);
}

export function findPlayer(players = [], slug = "") {
  // React Router's useParams() already decodes the route param once, so we
  // must NOT decodeURIComponent again -- a second decode throws URIError on a
  // name containing a literal "%" and crashes the page. Split the (already
  // decoded) "name__team" directly.
  const [name, team] = (slug || "").split("__");
  return players.find((player) => player.name === name && player.team === team);
}

export function buildPlayers(data) {
  const players = new Map();

  function upsert(name, team, patch = {}) {
    if (!name || !team) return;
    const key = `${name}__${team}`;
    const current = players.get(key) || {
      name,
      team,
      goals: 0,
      xg: null,
      anytimeP: null,
      penTaker: false,
      status: null,
      reason: null,
      sources: new Set(),
    };

    current.goals = Math.max(current.goals || 0, patch.goals || 0);
    current.xg = patch.xg ?? current.xg;
    current.anytimeP = patch.anytimeP ?? current.anytimeP;
    current.penTaker = Boolean(current.penTaker || patch.penTaker);
    current.status = patch.status ?? current.status;
    current.reason = patch.reason ?? current.reason;
    if (patch.source) current.sources.add(patch.source);
    players.set(key, current);
  }

  (data.tournament?.topScorers || []).forEach((row) => {
    upsert(row.name, row.team, { goals: row.goals, source: "topScorers" });
  });

  (data.tournament?.teams || []).forEach((team) => {
    (team.topScorers || []).forEach((row) => {
      upsert(row.name, team.name, { goals: row.goals, source: "teamTopScorers" });
    });
    (team.availability || []).forEach((row) => {
      upsert(row.player, team.name, {
        status: row.status,
        reason: row.reason,
        source: "availability",
      });
    });
  });

  (data.matches || []).forEach((match) => {
    [
      [match.home, match.prediction?.scorers?.home],
      [match.away, match.prediction?.scorers?.away],
    ].forEach(([team, scorers]) => {
      (scorers || []).forEach((row) => {
        upsert(row.name, team, {
          goals: row.goals,
          xg: row.xg,
          anytimeP: row.p,
          penTaker: row.penTaker,
          source: "anytime",
        });
      });
    });
    (match.intelligence?.availability || []).forEach((row) => {
      upsert(row.player, row.team, {
        status: row.status,
        reason: row.reason,
        source: "matchAvailability",
      });
    });
  });

  return [...players.values()]
    .map((player) => ({ ...player, sources: [...player.sources] }))
    .sort((a, b) => (
      (b.goals || 0) - (a.goals || 0)
      || (b.anytimeP || 0) - (a.anytimeP || 0)
      || a.name.localeCompare(b.name)
    ));
}
