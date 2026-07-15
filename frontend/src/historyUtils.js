export function historyMatchId(match) {
  return encodeURIComponent(`${match.date}__${match.home}__${match.away}`);
}

export function findHistoryMatch(matches = [], id = "") {
  const decoded = decodeURIComponent(id);
  return matches.find((match) => `${match.date}__${match.home}__${match.away}` === decoded);
}
