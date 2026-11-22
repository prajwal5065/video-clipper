import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { Job } from "./types";
import { isActive } from "../lib/utils";
import { api } from "./client";

export const useConfig = () => useQuery({ queryKey: ["config"], queryFn: api.config, staleTime: 15_000 });

/** Polls once a second while the job is running, then stops. */
export const useJob = (id: string) =>
  useQuery({
    queryKey: ["job", id],
    queryFn: () => api.job(id),
    refetchInterval: (q) => (isActive(q.state.data?.status) || hasBusyClip(q.state.data) ? 1000 : false),
  });

/** A finished job still changes while a clip is re-rendering or uploading. */
export const hasBusyClip = (job?: Job) =>
  !!job?.clips?.some((c) => c.edit?.state === "rendering" || c.yt?.state === "uploading");

export const useJobs = () =>
  useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: (q) => (q.state.data?.some((j) => isActive(j.status)) ? 2500 : false),
  });

/** A clock that ticks, for elapsed-time displays. */
export function useNow(intervalMs = 1000, enabled = true): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) return;
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs, enabled]);
  return now;
}

export function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try { localStorage.setItem("vc.theme", theme); } catch { /* private mode */ }
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}
