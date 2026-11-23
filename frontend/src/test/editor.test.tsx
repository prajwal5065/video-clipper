import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Job } from "../api/types";
import JobPage from "../pages/JobPage";
import config from "./fixtures/config.json";
import states from "./fixtures/clip_states.json";
import done from "./fixtures/job_done.json";
import { mockApi, renderRoute, withClip, type Call } from "./helpers";

const id = done.id;
const clip0 = done.clips[0];

function setup(initial: Job = done as unknown as Job) {
  let job = initial;
  const calls: Call[] = mockApi({
    "GET /api/config": config,
    [`GET /api/jobs/${id}`]: () => job,
    [`GET /api/jobs/${id}/clips/c1/caption-text`]: { text: "word2 word3 word4 word5", count: 4 },
    [`POST /api/jobs/${id}/clips/c1/edit`]: (body: unknown) => {
      const b = body as { mode: "preview" | "final" };
      job = withClip(job, { edit: { state: "rendering", kind: b.mode, progress: 0.4, error: null } });
      return { started: true };
    },
  });
  renderRoute(<JobPage />, { path: "/jobs/:id", route: `/jobs/${id}` });
  return { calls, set: (j: Job) => { job = j; }, get: () => job };
}
const openEditor = async () => {
  await userEvent.click((await screen.findAllByRole("button", { name: /^edit$/i }))[0]);
  return screen.findByRole("dialog", { name: /edit clip/i });
};
const body = (calls: Call[]) => calls.filter((c) => c.method === "POST" && c.url.endsWith("/edit")).at(-1)!.body;

describe("Clip editor", () => {
  it("opens from the card with the clip's current trim and frames from the source video", async () => {
    setup();
    const dialog = await openEditor();
    expect(within(dialog).getByLabelText("Start (seconds)")).toHaveValue(clip0.start);
    expect(within(dialog).getByLabelText("End (seconds)")).toHaveValue(clip0.end);
    expect(within(dialog).getByText(`${(clip0.end - clip0.start).toFixed(1)} s long`)).toBeInTheDocument();
    expect(within(dialog).getByAltText("Frame at the start")).toHaveAttribute("src", `/api/jobs/${id}/frame?t=${clip0.start.toFixed(2)}&w=360`);
    expect(within(dialog).getByLabelText("Current clip")).toBeInTheDocument();
    expect(await within(dialog).findByLabelText("Caption text")).toHaveValue("word2 word3 word4 word5");
  });

  it("refuses clips outside 3-180 seconds", async () => {
    setup();
    const dialog = await openEditor();
    fireEvent.change(within(dialog).getByLabelText("End (seconds)"), { target: { value: String(clip0.start + 1) } });
    expect(within(dialog).getByRole("alert")).toHaveTextContent("between 3 and 180 seconds");
    expect(within(dialog).getByRole("button", { name: /preview/i })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: /save changes/i })).toBeDisabled();
  });

  it("preview: sends the settings, shows progress, then plays the preview without saving", async () => {
    const t = setup();
    const dialog = await openEditor();
    fireEvent.change(within(dialog).getByLabelText("Start (seconds)"), { target: { value: "2" } });
    await userEvent.click(within(dialog).getByRole("radio", { name: /full frame, black bars/i }));
    await userEvent.click(within(dialog).getByRole("button", { name: /preview/i }));
    await waitFor(() => expect(body(t.calls)).toMatchObject({ mode: "preview", start: 2, end: clip0.end, crop: "fit-black", captions: true }));
    expect(body(t.calls)).not.toHaveProperty("text");
    expect(await within(dialog).findByRole("progressbar", { name: "Render progress" })).toHaveAttribute("aria-valuenow", "40");
    expect(within(dialog).getByRole("button", { name: /save changes/i })).toBeDisabled();

    const p = states.previewed.preview!;
    t.set(withClip(done, { preview: p, edit: { state: "idle", kind: "preview", progress: 1, error: null } }));
    const video = await within(dialog).findByLabelText("Preview of your edit", undefined, { timeout: 4000 });
    expect(video).toHaveAttribute("src", `/api/jobs/${id}/clips/c1/preview?v=${p.rev}`);
    expect(within(dialog).getByText(/preview, not saved yet/i)).toBeInTheDocument();
  });

  it("save: re-renders, then closes itself when the new version is ready", async () => {
    const t = setup();
    const dialog = await openEditor();
    await userEvent.click(within(dialog).getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(body(t.calls)).toMatchObject({ mode: "final" }));
    expect(await within(dialog).findByText(/saving the clip/i)).toBeInTheDocument();
    t.set(withClip(done, { rev: clip0.rev + 1, edit: { state: "idle", kind: "final", progress: 1, error: null } }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument(), { timeout: 4000 });
    expect(await screen.findByText("Edited")).toBeInTheDocument();
  });

  it("caption text: same word count only, and not together with a trim change", async () => {
    const t = setup();
    const dialog = await openEditor();
    const box = await within(dialog).findByLabelText("Caption text");
    await userEvent.clear(box);
    await userEvent.type(box, "only three words");
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Keep the same number of words: the clip has 4, you wrote 3.");
    expect(within(dialog).getByRole("button", { name: /save changes/i })).toBeDisabled();

    await userEvent.type(box, " here");
    expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Start (seconds)"), { target: { value: "2" } });
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Save the new start and end first");

    fireEvent.change(within(dialog).getByLabelText("Start (seconds)"), { target: { value: String(clip0.start) } });
    await userEvent.click(within(dialog).getByRole("button", { name: /save changes/i }));
    await waitFor(() => expect(body(t.calls)).toMatchObject({ mode: "final", text: "only three words here" }));
  });

  it("turning captions off disables the style and the text", async () => {
    setup();
    const dialog = await openEditor();
    await userEvent.click(within(dialog).getByRole("switch", { name: "Captions" }));
    expect(within(dialog).getByLabelText("Caption style")).toBeDisabled();
    expect(within(dialog).getByLabelText("Caption text")).toBeDisabled();
  });

  it("shows a failed render and the server's refusal", async () => {
    setup(withClip(done, { edit: { state: "error", kind: "preview", error: "FFmpeg failed: boom" } }));
    const dialog = await openEditor();
    expect(within(dialog).getByText("FFmpeg failed: boom")).toBeInTheDocument();
  });

  it("shows the server's message if it refuses the request", async () => {
    mockApi({
      "GET /api/config": config, [`GET /api/jobs/${id}`]: done,
      [`GET /api/jobs/${id}/clips/c1/caption-text`]: { text: "a b", count: 2 },
      [`POST /api/jobs/${id}/clips/c1/edit`]: new Response(JSON.stringify({ detail: "This clip is already rendering." }), { status: 409 }),
    });
    renderRoute(<JobPage />, { path: "/jobs/:id", route: `/jobs/${id}` });
    const dialog = await openEditor();
    await userEvent.click(within(dialog).getByRole("button", { name: /preview/i }));
    expect(await within(dialog).findByText("This clip is already rendering.")).toBeInTheDocument();
  });

  it("closes with the X button", async () => {
    setup();
    const dialog = await openEditor();
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
