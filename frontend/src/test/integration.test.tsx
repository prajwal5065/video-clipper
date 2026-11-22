// Runs the real React pages against a LIVE backend (scripts/demo_server.py), over real HTTP.
// Skipped unless API_URL is set:   API_URL=http://127.0.0.1:8010 npx vitest run src/test/integration.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

  it("edit a clip (preview, then save) and schedule it on YouTube", async () => {
    app();
    await screen.findByRole("tablist");
    await userEvent.type(screen.getByLabelText("Video link"), "https://www.youtube.com/watch?v=editme");
    await userEvent.click(screen.getByRole("radio", { name: "Draft" }));
    await userEvent.click(screen.getByRole("button", { name: /generate clips/i }));
    expect(await screen.findByText("3 clips", undefined, { timeout: 60000 })).toBeInTheDocument();

    // --- editor: trim, preview (real FFmpeg render), then save ---
    await userEvent.click(screen.getAllByRole("button", { name: /^edit$/i })[0]);
    const editor = await screen.findByRole("dialog", { name: /edit clip/i });
    expect(await within(editor).findByLabelText("Caption text")).not.toHaveValue("");
    fireEvent.change(within(editor).getByLabelText("Start (seconds)"), { target: { value: "2" } });
    fireEvent.change(within(editor).getByLabelText("End (seconds)"), { target: { value: "8" } });
    await userEvent.click(within(editor).getByRole("button", { name: /preview/i }));
    const preview = await within(editor).findByLabelText("Preview of your edit", undefined, { timeout: 30000 });
    const head = await fetch(preview.getAttribute("src")!, { headers: { Range: "bytes=0-99" } });
    expect(head.status).toBe(206);
    await userEvent.click(within(editor).getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument(), { timeout: 30000 });
    expect(await screen.findByText("Edited")).toBeInTheDocument();
    expect(screen.getAllByText("6s").length).toBeGreaterThan(0); // the clip is now 6 seconds

    // --- YouTube: AI details, schedule, uploaded ---
    await userEvent.click(screen.getAllByRole("button", { name: /youtube/i })[0]);
    const panel = await screen.findByRole("dialog", { name: /publish to youtube/i });
    await userEvent.click(within(panel).getByRole("button", { name: /write with ai/i }));
    await waitFor(() => expect(within(panel).getByLabelText("Title")).toHaveValue("Demo title"));
    await userEvent.click(within(panel).getByRole("radio", { name: "Schedule" }));
    fireEvent.change(within(panel).getByLabelText("Publish at"), { target: { value: "2099-06-01T10:00" } });
    await userEvent.click(within(panel).getByRole("button", { name: /schedule upload/i }));
    expect(await within(panel).findByText(/scheduled on main/i, undefined, { timeout: 30000 })).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: /open on youtube/i })).toHaveAttribute("href", "https://youtu.be/demo");
  }, 150000);
});

