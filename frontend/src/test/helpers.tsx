import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

type Handler = unknown | ((body: unknown) => unknown);
export interface Call { url: string; method: string; body: unknown }

/** Fake the API. Keys look like "GET /api/jobs". A function value receives the parsed request body. */
export function mockApi(routes: Record<string, Handler>): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ url, method, body });
    const handler = routes[`${method} ${url}`];
    if (handler === undefined) return new Response(JSON.stringify({ detail: `unmocked ${method} ${url}` }), { status: 404 });
    const value = typeof handler === "function" ? (handler as (b: unknown) => unknown)(body) : handler;
    if (value instanceof Response) return value;
    if (value === null) return new Response(null, { status: 204 });
    return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}

export function renderRoute(ui: ReactElement, { path = "/", route = "/", state }: { path?: string; route?: string; state?: unknown } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: route, state }]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path={path} element={ui} />
          <Route path="/jobs/:id" element={<div>JOB PAGE</div>} />
          <Route path="/library" element={<div>LIBRARY PAGE</div>} />
          <Route path="/" element={<div>HOME PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** The whole app with its own routes (no extra test routes). */
export function renderApp(ui: ReactElement, route = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

import type { Clip, Job } from "../api/types";
/** A copy of the job with the first clip changed. */
export function withClip(job: unknown, patch: Partial<Clip>, index = 0): Job {
  const j = structuredClone(job) as Job;
  j.clips[index] = { ...j.clips[index], ...patch };
  return j;
}
