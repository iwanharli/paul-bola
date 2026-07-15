export function teamSlug(name = "") {
  return encodeURIComponent(name);
}

export function findTeam(teams = [], slug = "") {
  const name = decodeURIComponent(slug || "");
  return teams.find((team) => team.name === name);
}

export function teamRating(team) {
  const wins = team.record?.wins || 0;
  const goalDiff = team.record?.goalDiff || 0;
  const xg = team.form?.xg || 0;
  return wins * 10 + goalDiff * 2 + xg;
}
