// Runs the real React pages against a LIVE backend (scripts/demo_server.py), over real HTTP.
// Skipped unless API_URL is set:   API_URL=http://127.0.0.1:8010 npx vitest run src/test/integration.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CreatePage from "../pages/CreatePage";
import JobPage from "../pages/JobPage";

const API = process.env.API_URL;

function app() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<CreatePage />} />
          <Route path="/jobs/:id" element={<JobPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe.skipIf(!API)("React app <-> live backend", () => {
  beforeEach(() => {
    const real = globalThis.fetch;
    vi.stubGlobal("fetch", (url: string, init?: RequestInit) => real(url.startsWith("/") ? `${API}${url}` : url, init));
  });

  it("paste a link, generate, watch every step, get playable clips", async () => {
    app();
    await screen.findByRole("tablist");
    await userEvent.type(screen.getByLabelText("Video link"), "https://www.youtube.com/watch?v=demo");
    await userEvent.click(screen.getByRole("radio", { name: "Draft" }));
    await userEvent.click(screen.getByRole("radio", { name: /full frame, blurred background/i }));
    await userEvent.click(screen.getByRole("button", { name: /generate clips/i }));

    // live download numbers from the real API
    expect(await screen.findByText(/^Downloading video: \d+%$/, undefined, { timeout: 15000 })).toBeInTheDocument();
    expect(await screen.findByText(/MB\/s · about \d+:\d\d left/)).toBeInTheDocument();
    // then the later steps
    expect(await screen.findByText(/^Transcribing speech: \d+:\d\d of \d+:\d\d$/, undefined, { timeout: 20000 })).toBeInTheDocument();
    expect(await screen.findByText(/^Rendering clip \d of 3$/, undefined, { timeout: 30000 })).toBeInTheDocument();
    // finished: three clips, each with a player pointing at a real, seekable video
    expect(await screen.findByText("3 clips", undefined, { timeout: 60000 })).toBeInTheDocument();
    const videos = document.querySelectorAll("video");
    expect(videos).toHaveLength(3);
    const src = videos[0].getAttribute("src")!;
    const range = await fetch(src, { headers: { Range: "bytes=0-99" } });
    expect(range.status).toBe(206);
    expect(range.headers.get("content-type")).toBe("video/mp4");
    expect(screen.getAllByRole("link", { name: /download/i })).toHaveLength(3);
  }, 120000);

  it("cancel stops a running job", async () => {
    app();
    await screen.findByRole("tablist");
    await userEvent.type(screen.getByLabelText("Video link"), "https://www.youtube.com/watch?v=cancelme");
    await userEvent.click(screen.getByRole("button", { name: /generate clips/i }));
    await userEvent.click(await screen.findByRole("button", { name: /cancel/i }, { timeout: 15000 }));
    expect(await screen.findByText(/you cancelled this job/i, undefined, { timeout: 15000 })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("link", { name: /try again/i })).toBeInTheDocument());
  }, 60000);
});
