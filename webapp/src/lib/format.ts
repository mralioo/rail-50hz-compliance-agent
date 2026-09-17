const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31536000],
  ["month", 2592000],
  ["week", 604800],
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
];

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** "2h ago" / "3d ago" style relative time from an ISO 8601 timestamp. */
export function formatRelativeTime(iso: string): string {
  if (!iso) return "";
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 45) return "just now";
  for (const [unit, secondsInUnit] of UNITS) {
    const value = Math.floor(seconds / secondsInUnit);
    if (value >= 1) return rtf.format(-value, unit);
  }
  return "just now";
}
