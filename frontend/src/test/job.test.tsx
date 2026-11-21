import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import JobPage from "../pages/JobPage";
import cancelled from "./fixtures/job_cancelled.json";
import done from "./fixtures/job_done.json";
import downloading from "./fixtures/job_downloading.json";
import failed from "./fixtures/job_failed.json";
import merging from "./fixtures/job_merging.json";
import rendering from "./fixtures/job_rendering.json";
import transcribing from "./fixtures/job_transcribing.json";
import { mockApi, renderRoute } from "./helpers";

const open = (job: { id: string }, extra: Record<string, unknown> = {}) => {
  const calls = mockApi({ [`GET /api/jobs/${job.id}`]: job, ...extra });
  renderRoute(<JobPage />, { path: "/jobs/:id", route: `/jobs/${job.id}` });
  return calls;
};
const bar = (name: string) => screen.getByRole("progressbar", { name });
const step = (name: RegExp) => screen.getByText(name).closest("li")!;

describe("Job page: live progress", () => {
  it("download: percent, size, speed, time left and the active step", async () => {
    open(downloading);
    expect(await screen.findByText("Downloading video: 33%")).toBeInTheDocument();
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
    expect(screen.getByText("921.6 MB of 2.7 GB · 3.4 MB/s · about 9:01 left")).toBeInTheDocument();
    expect(bar("Current step")).toHaveAttribute("aria-valuenow", "34");
    expect(bar("Overall progress")).toHaveAttribute("aria-valuenow", String(Math.round(downloading.progress * 100)));
    expect(within(step(/get the video/i)).getByText("In progress")).toBeInTheDocument();
    expect(within(step(/transcribe/i)).getByText("Waiting")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByText("Working")).toBeInTheDocument();
  });

  it("merging: says it is finishing the download", async () => {
    open(merging);
    expect(await screen.findByText(/finishing the download: merging video and audio/i)).toBeInTheDocument();
  });

  it("transcribing: shows where in the audio it is, and earlier steps as done", async () => {
    open(transcribing);
    expect(await screen.findByText(transcribing.message)).toBeInTheDocument();
    expect(transcribing.message).toMatch(/^Transcribing speech: \d+:\d\d of \d+:\d\d$/);
    expect(screen.getByText("Step 2 of 4")).toBeInTheDocument();
    expect(within(step(/get the video/i)).getByText("Done")).toBeInTheDocument();
    expect(within(step(/transcribe/i)).getByText("In progress")).toBeInTheDocument();
    expect(bar("Current step")).toBeInTheDocument();
  });

  it("rendering: which clip, and its title", async () => {
    open(rendering);
    expect(await screen.findByText(`Rendering clip ${rendering.render!.index} of ${rendering.render!.total}`)).toBeInTheDocument();
    expect(screen.getByText(rendering.render!.title)).toBeInTheDocument();
    expect(screen.getByText("Step 4 of 4")).toBeInTheDocument();
    expect(within(step(/render the clips/i)).getByText("In progress")).toBeInTheDocument();
  });

  it("keeps polling while running and follows the job to the next stage", async () => {
    let n = 0;
    mockApi({ [`GET /api/jobs/${downloading.id}`]: () => (++n === 1 ? downloading : { ...transcribing, id: downloading.id }) });
    renderRoute(<JobPage />, { path: "/jobs/:id", route: `/jobs/${downloading.id}` });
    expect(await screen.findByText("Downloading video: 33%")).toBeInTheDocument();
    expect(await screen.findByText(transcribing.message, undefined, { timeout: 4000 })).toBeInTheDocument();
  });

  it("cancel asks the server to stop", async () => {
    const calls = open(downloading, { [`POST /api/jobs/${downloading.id}/cancel`]: null });
    await userEvent.click(await screen.findByRole("button", { name: /cancel/i }));
    expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/cancel"))).toBe(true);
  });
});

describe("Job page: finished states", () => {
  it("done: a player and a download link for every clip", async () => {
    open(done);
    expect(await screen.findByText(`${done.clips.length} clips`)).toBeInTheDocument();
    const c = done.clips[0];
    const video = screen.getByLabelText(`Preview of ${c.title}`);
    expect(video).toHaveAttribute("src", `/api/jobs/${done.id}/clips/${c.id}/video?v=${c.rev}`);
    const links = screen.getAllByRole("link", { name: /download/i });
    expect(links).toHaveLength(done.clips.length);
    expect(links[0]).toHaveAttribute("href", `/api/jobs/${done.id}/clips/${c.id}/download`);
    expect(screen.queryByRole("progressbar", { name: "Overall progress" })).not.toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("failed: shows the real error and a way to try again", async () => {
    open(failed);
    expect(await screen.findByText(failed.error!)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /try again/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
    expect(within(step(/find the best moments/i)).getByText("Failed")).toBeInTheDocument();
  });

  it("cancelled: says so", async () => {
    open(cancelled);
    expect(await screen.findByText(/you cancelled this job/i)).toBeInTheDocument();
  });

  it("delete asks first, then removes the job", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const calls = open(done, { [`DELETE /api/jobs/${done.id}`]: null });
    await userEvent.click(await screen.findByRole("button", { name: /delete/i }));
    expect(await screen.findByText("LIBRARY PAGE")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "DELETE")).toBe(true);
  });

  it("delete does nothing if you say no", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const calls = open(done);
    await userEvent.click(await screen.findByRole("button", { name: /delete/i }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("an unknown job shows a clear message", async () => {
    mockApi({ "GET /api/jobs/nope": new Response(JSON.stringify({ detail: "Job not found." }), { status: 404 }) });
    renderRoute(<JobPage />, { path: "/jobs/:id", route: "/jobs/nope" });
    expect(await screen.findByText("Job not found.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to the library/i })).toBeInTheDocument();
  });
});
