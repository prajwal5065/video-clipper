import type { DownloadInfo, Status } from "../api/types";

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function humanSize(n?: number | null): string {
  let v = Number(n ?? 0);
  const units = ["B", "KB", "MB", "GB"];
  for (let i = 0; i < units.length; i++) {
    if (v < 1024 || i === units.length - 1) return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
    v /= 1024;
  }
  return "";
}

export function humanTime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  const pad = (x: number) => String(x).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
}

/** Same wording as `describe()` in clipper/download.py. */
export function describeDownload(d: DownloadInfo): { headline: string; detail: string } {
  if (d.stage === "processing") {
    return { headline: "Finishing the download: merging video and audio", detail: "This can take a minute for large videos." };
  }
  const frac = d.fraction;
  const headline = frac != null ? `Downloading video: ${Math.floor(Math.min(frac, 1) * 100)}%` : "Downloading video";
  const parts: string[] = [];
  if (d.done != null) parts.push(d.total ? `${humanSize(d.done)} of ${humanSize(d.total)}` : humanSize(d.done));
  if (d.speed) parts.push(`${humanSize(d.speed)}/s`);
  if (d.eta != null) parts.push(`about ${humanTime(d.eta)} left`);
  return { headline, detail: parts.join(" · ") };
}

export function timeAgo(epochSeconds: number, nowMs = Date.now()): string {
  const s = Math.max(0, Math.floor(nowMs / 1000 - epochSeconds));
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(epochSeconds * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export const ACTIVE: Status[] = ["queued", "running"];
export const isActive = (s?: Status) => !!s && ACTIVE.includes(s);

export function clipLength(start: number, end: number): string {
  return `${Math.round(end - start)}s`;
}

/** Split "a, b #c" style input into clean words. */
export function splitList(text: string): string[] {
  return text.split(/[,\n]/).map((x) => x.trim().replace(/^#/, "")).filter(Boolean);
}

/** The value for <input type="datetime-local"> (local time, minutes) `minutes` from now. */
export function localInputValue(minutesFromNow: number, now = new Date()): string {
  const d = new Date(now.getTime() + minutesFromNow * 60_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function isFutureEnough(localValue: string, minMinutes = 10, now = Date.now()): boolean {
  const t = new Date(localValue).getTime();
  return Number.isFinite(t) && t > now + minMinutes * 60_000;
}

export function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}
