import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import CreatePage from "../pages/CreatePage";
import config from "./fixtures/config.json";
import failed from "./fixtures/job_failed.json";
import done from "./fixtures/job_done.json";
import { mockApi, renderRoute } from "./helpers";

const generate = () => screen.getByRole("button", { name: /generate clips/i });
const ready = async () => { await screen.findByRole("tablist"); };

describe("Create page", () => {
  it("shows the options the server offers and waits for a video", async () => {
    mockApi({ "GET /api/config": config });
    renderRoute(<CreatePage />);
    await ready();
    expect(screen.getByRole("heading", { name: /turn long videos into shorts/i })).toBeInTheDocument();
    expect(screen.getAllByRole("radio", { name: /full frame, blurred background/i })[0]).toBeInTheDocument();
    for (const q of ["Draft", "Standard", "High", "Max"]) expect(screen.getByRole("radio", { name: q })).toBeInTheDocument();
    expect(generate()).toBeDisabled();
    expect(screen.getByText(/choose a video above/i)).toBeInTheDocument();
  });

  it("validates the link before enabling Generate", async () => {
    mockApi({ "GET /api/config": config });
    renderRoute(<CreatePage />);
    await ready();
    const link = screen.getByLabelText("Video link");
    await userEvent.type(link, "not a link");
    expect(screen.getByText(/must start with http/i)).toBeInTheDocument();
    expect(generate()).toBeDisabled();
    await userEvent.clear(link);
    await userEvent.type(link, "https://youtu.be/abc");
    expect(generate()).toBeEnabled();
  });

  it("sends the chosen settings and opens the job page", async () => {
    const calls = mockApi({
      "GET /api/config": config,
      "POST /api/jobs": () => ({ ...done, id: "newjob1" }),
    });
    renderRoute(<CreatePage />);
    await ready();
    await userEvent.type(screen.getByLabelText("Video link"), "https://youtu.be/abc");
    await userEvent.click(screen.getByRole("radio", { name: /full frame, black bars/i }));
    await userEvent.click(screen.getByRole("radio", { name: "High" }));
    screen.getByRole("slider", { name: "Number of clips" }).focus();
    await userEvent.keyboard("{End}");
    await userEvent.click(generate());

    expect(await screen.findByText("JOB PAGE")).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.url === "/api/jobs")!;
    expect(post.body).toMatchObject({
      source_type: "link", source: "https://youtu.be/abc", clips: 20, crop: "fit-black", quality: "high",
      captions: true, style: "classic", whisper: "small", min_len: 20, max_len: 60,
    });
  });

  it("local paths are sent as paths, quotes removed", async () => {
    const calls = mockApi({ "GET /api/config": config, "POST /api/jobs": () => ({ ...done, id: "p1" }) });
    renderRoute(<CreatePage />);
    await ready();
    await userEvent.click(screen.getByRole("tab", { name: /local file path/i }));
    await userEvent.type(screen.getByLabelText("Local file path"), '"C:\\Videos\\talk.mp4"');
    await userEvent.click(generate());
    await screen.findByText("JOB PAGE");
    expect(calls.find((c) => c.method === "POST")!.body).toMatchObject({ source_type: "path", source: "C:\\Videos\\talk.mp4" });
  });

  it("shows the server's error if starting fails", async () => {
    mockApi({
      "GET /api/config": config,
      "POST /api/jobs": new Response(JSON.stringify({ detail: "File not found: x.mp4" }), { status: 422 }),
    });
    renderRoute(<CreatePage />);
    await ready();
    await userEvent.type(screen.getByLabelText("Video link"), "https://youtu.be/abc");
    await userEvent.click(generate());
    expect(await screen.findByRole("alert")).toHaveTextContent("File not found: x.mp4");
  });

  it("blocks Generate and explains when the Gemini key is missing", async () => {
    mockApi({ "GET /api/config": { ...config, gemini_key_set: false } });
    renderRoute(<CreatePage />);
    await ready();
    expect(screen.getByText(/gemini api key not found/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Video link"), "https://youtu.be/abc");
    expect(generate()).toBeDisabled();
  });

  it("remembers the last settings", async () => {
    localStorage.setItem("vc.settings", JSON.stringify({ crop: "fit", quality: "max", style: "hormozi", whisper: "base" }));
    mockApi({ "GET /api/config": config });
    renderRoute(<CreatePage />);
    await ready();
    expect(screen.getByRole("radio", { name: /full frame, blurred background/i })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Max" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByLabelText("Caption style")).toHaveValue("hormozi");
    expect(screen.getByLabelText(/speech model/i)).toHaveValue("base");
  });

  it("ignores saved values the server no longer offers", async () => {
    localStorage.setItem("vc.settings", JSON.stringify({ crop: "zoom", quality: "ultra", clips: 999 }));
    mockApi({ "GET /api/config": config });
    renderRoute(<CreatePage />);
    await ready();
    expect(screen.getByRole("radio", { name: "Standard" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("slider", { name: "Number of clips" })).toHaveAttribute("aria-valuenow", "20");
  });

  it("'Try again' opens the form with the old job's settings", async () => {
    mockApi({ "GET /api/config": config });
    renderRoute(<CreatePage />, { state: { spec: failed.spec } });
    await ready();
    expect(screen.getByLabelText("Local file path")).toHaveValue(failed.spec.source);
    expect(generate()).toBeEnabled();
  });

  it("explains when the server cannot be reached", async () => {
    const fail = () => { throw new TypeError("Failed to fetch"); };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any).fetch = fail;
    renderRoute(<CreatePage />);
    await waitFor(() => expect(screen.getByText(/cannot reach the video clipper server/i)).toBeInTheDocument());
  });
});
