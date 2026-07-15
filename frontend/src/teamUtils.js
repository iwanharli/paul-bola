export function teamSlug(name = "") {
  return encodeURIComponent(name);
}

export function findTeam(teams = [], slug = "") {
  // useParams() already decodes the param; a second decode crashes on a
  // literal "%". Compare the (already decoded) name directly.
  return teams.find((team) => team.name === (slug || ""));
}

export function teamRating(team) {
  const wins = team.record?.wins || 0;
  const goalDiff = team.record?.goalDiff || 0;
  const xg = team.form?.xg || 0;
  return wins * 10 + goalDiff * 2 + xg;
}
