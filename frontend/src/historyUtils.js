export function historyMatchId(match) {
  return encodeURIComponent(`${match.date}__${match.home}__${match.away}`);
}

export function findHistoryMatch(matches = [], id = "") {
  // useParams() already decodes the param; don't decode again (a literal "%"
  // in a team name would throw and blank the page).
  return matches.find((match) => `${match.date}__${match.home}__${match.away}` === (id || ""));
}
