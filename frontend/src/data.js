// Loads the model's exported predictions (written by model/export_predictions.py).
import { useEffect, useState } from "react";

// Stale-while-revalidate + polling: show the cached copy instantly (if any),
// but always refetch in the background and again every POLL_INTERVAL_MS, so
// the site reflects the orchestrator's 15-min data refresh WITHOUT the user
// needing to hard-reload the browser. Cache-busted so a CDN/browser HTTP
// cache in front of the static predictions.json can't serve a stale copy.
const POLL_INTERVAL_MS = 3 * 60 * 1000; // 3 min -- catches each 15-min cron run promptly

let cache = null;
let cacheError = null;
const subscribers = new Set();

function notify() {
  subscribers.forEach((fn) => fn(cache, cacheError));
}

async function fetchPredictions() {
  try {
    const url = `${import.meta.env.BASE_URL}predictions.json?t=${Date.now()}`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`Failed to load predictions.json (${res.status})`);
    const json = await res.json();
    cache = json;
    cacheError = null;
  } catch (err) {
    // keep serving the last good cache on a transient failure; only surface
    // the error if we have nothing to show yet
    cacheError = cache ? null : err;
  }
  notify();
}

let pollStarted = false;
function ensurePolling() {
  if (pollStarted) return;
  pollStarted = true;
  fetchPredictions();
  setInterval(fetchPredictions, POLL_INTERVAL_MS);
}

export function usePredictions() {
  const [data, setData] = useState(cache);
  const [error, setError] = useState(cacheError);

  useEffect(() => {
    const onUpdate = (json, err) => {
      setData(json);
      setError(err);
    };
    subscribers.add(onUpdate);
    ensurePolling();
    return () => subscribers.delete(onUpdate);
  }, []);

  return { data, error };
}

// simple flag emoji lookup for the teams in play
export const FLAGS = {
  Algeria: "🇩🇿",
  Argentina: "🇦🇷",
  Australia: "🇦🇺",
  Austria: "🇦🇹",
  Belgium: "🇧🇪",
  "Bosnia & Herzegovina": "🇧🇦",
  "Bosnia and Herzegovina": "🇧🇦",
  Brazil: "🇧🇷",
  "Cabo Verde": "🇨🇻",
  Canada: "🇨🇦",
  "Cape Verde": "🇨🇻",
  Colombia: "🇨🇴",
  "Congo DR": "🇨🇩",
  Croatia: "🇭🇷",
  "Côte d'Ivoire": "🇨🇮",
  "DR Congo": "🇨🇩",
  Ecuador: "🇪🇨",
  Egypt: "🇪🇬",
  England: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  France: "🇫🇷",
  Germany: "🇩🇪",
  Ghana: "🇬🇭",
  "Ivory Coast": "🇨🇮",
  Japan: "🇯🇵",
  Jordan: "🇯🇴",
  Mexico: "🇲🇽",
  Morocco: "🇲🇦",
  Netherlands: "🇳🇱",
  Norway: "🇳🇴",
  Panama: "🇵🇦",
  Paraguay: "🇵🇾",
  Portugal: "🇵🇹",
  Senegal: "🇸🇳",
  "South Africa": "🇿🇦",
  Spain: "🇪🇸",
  Sweden: "🇸🇪",
  Switzerland: "🇨🇭",
  USA: "🇺🇸",
  Uruguay: "🇺🇾",
};

const TEAM_COLORS = {
  Argentina: ["#60a5fa", "#f8fafc"],
  England: ["#ef4444", "#f8fafc"],
  France: ["#2563eb", "#ef4444"],
  Spain: ["#ef4444", "#facc15"],
  Norway: ["#ef4444", "#2563eb"],
  Morocco: ["#ef4444", "#16a34a"],
  Belgium: ["#facc15", "#ef4444"],
  Mexico: ["#16a34a", "#ef4444"],
  Portugal: ["#16a34a", "#ef4444"],
  Germany: ["#111827", "#facc15"],
};

const AVATAR_PALETTES = [
  ["#2563eb", "#22c55e"],
  ["#db2777", "#f59e0b"],
  ["#7c3aed", "#06b6d4"],
  ["#dc2626", "#facc15"],
  ["#0f766e", "#84cc16"],
  ["#4f46e5", "#fb7185"],
];

export function playerAvatarSrc(name, team = "") {
  const seed = hashText(`${name}-${team}`);
  const colors = TEAM_COLORS[team] || AVATAR_PALETTES[seed % AVATAR_PALETTES.length];
  const initials = initialsFor(name);
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
      <defs>
        <linearGradient id="g" x1="12" x2="84" y1="8" y2="88" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="${colors[0]}"/>
          <stop offset="1" stop-color="${colors[1]}"/>
        </linearGradient>
      </defs>
      <rect width="96" height="96" rx="48" fill="#0b0f16"/>
      <circle cx="48" cy="48" r="45" fill="url(#g)" opacity="0.96"/>
      <circle cx="48" cy="34" r="17" fill="rgba(255,255,255,0.86)"/>
      <path d="M19 84c4-19 15-29 29-29s25 10 29 29" fill="rgba(255,255,255,0.82)"/>
      <text x="48" y="55" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="24" font-weight="800" fill="#0b0f16">${initials}</text>
    </svg>
  `;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function initialsFor(name = "") {
  const words = name
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return "?";
  const first = words[0][0] || "";
  const last = words.length > 1 ? words[words.length - 1][0] : words[0][1] || "";
  return `${first}${last}`.toUpperCase();
}

function hashText(text = "") {
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export const pct = (x) => `${(x * 100).toFixed(1)}%`;
export const pct0 = (x) => `${Math.round(x * 100)}%`;

const UTC7_TIME_ZONE = "Asia/Jakarta";
const SOURCE_TIME_ZONE = "America/New_York";

const utc7Formatter = new Intl.DateTimeFormat("id-ID", {
  timeZone: UTC7_TIME_ZONE,
  weekday: "short",
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZoneName: "short",
});

const utc7DateTimeFormatter = new Intl.DateTimeFormat("id-ID", {
  timeZone: UTC7_TIME_ZONE,
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZoneName: "short",
});

const utc7ShortDateFormatter = new Intl.DateTimeFormat("id-ID", {
  timeZone: UTC7_TIME_ZONE,
  weekday: "short",
  day: "2-digit",
  month: "short",
});

export function formatMatchTimeUtc7(match) {
  const date = matchDateTimeFromSource(match.date, match.time);
  return date ? utc7Formatter.format(date) : `${match.date} / ${match.time}`;
}

export function formatShortMatchDateUtc7(match) {
  const date = matchDateTimeFromSource(match.date, match.time);
  if (date) return utc7ShortDateFormatter.format(date);
  if (!match.date) return "-";
  return utc7ShortDateFormatter.format(new Date(`${match.date}T00:00:00+07:00`));
}

export function formatGeneratedAtUtc7(value) {
  if (!value) return "-";
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const date = new Date(hasTimezone ? value : `${value}+07:00`);
  if (Number.isNaN(date.getTime())) return "-";
  return utc7DateTimeFormatter.format(date);
}

function matchDateTimeFromSource(dateText, timeText) {
  if (!dateText || !timeText) return null;
  const dateParts = dateText.split("-").map(Number);
  const timeMatch = timeText.match(/^(\d{1,2}):(\d{2})\s*ET$/i);
  if (dateParts.length !== 3 || !timeMatch) return null;

  const [year, month, day] = dateParts;
  const hour = Number(timeMatch[1]);
  const minute = Number(timeMatch[2]);
  return zonedTimeToUtc({ year, month, day, hour, minute }, SOURCE_TIME_ZONE);
}

function zonedTimeToUtc(parts, timeZone) {
  const target = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute);
  let guess = target;
  for (let i = 0; i < 3; i += 1) {
    const zoned = getZonedParts(new Date(guess), timeZone);
    const zonedAsUtc = Date.UTC(zoned.year, zoned.month - 1, zoned.day, zoned.hour, zoned.minute);
    guess += target - zonedAsUtc;
  }
  return new Date(guess);
}

function getZonedParts(date, timeZone) {
  const formatted = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);

  return Object.fromEntries(
    formatted
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, Number(part.value)])
  );
}
