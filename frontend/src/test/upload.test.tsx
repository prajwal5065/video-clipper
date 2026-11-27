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
const ytConfig = { ...config, youtube_ready: true, accounts: [{ name: "main", signed_in: true }, { name: "second", signed_in: false }] };
const generated = states.meta;

function setup(initial: Job = done as unknown as Job, cfg: unknown = ytConfig) {
  let job = initial;
  const calls: Call[] = mockApi({
    "GET /api/config": cfg,
    [`GET /api/jobs/${id}`]: () => job,
    [`POST /api/jobs/${id}/clips/c1/metadata`]: generated,
    [`PUT /api/jobs/${id}/clips/c1/metadata`]: (b: unknown) => b,
    [`POST /api/jobs/${id}/clips/c1/upload`]: () => {
      job = withClip(job, { yt: { state: "uploading", account: "main", url: null, error: null, scheduled: null, message: "Preparing the upload" } });
      return { started: true };
    },
  });
  renderRoute(<JobPage />, { path: "/jobs/:id", route: `/jobs/${id}` });
  return { calls, set: (j: Job) => { job = j; } };
}
const openUpload = async () => {
  await userEvent.click((await screen.findAllByRole("button", { name: /youtube/i }))[0]);
  return screen.findByRole("dialog", { name: /publish to youtube/i });
};
const posts = (calls: Call[], suffix: string, method = "POST") => calls.filter((c) => c.method === method && c.url.endsWith(suffix));

describe("YouTube upload panel", () => {
  it("offers the configured accounts and safe defaults", async () => {
    setup();
    const dialog = await openUpload();
    const account = within(dialog).getByLabelText("YouTube account");
    expect(within(account).getAllByRole("option").map((o) => o.textContent)).toEqual(["main", "second (sign in on first upload)"]);
    expect(within(dialog).getByRole("radio", { name: "Private" })).toHaveAttribute("aria-checked", "true");
    expect(within(dialog).getByRole("switch", { name: "Made for kids" })).toHaveAttribute("aria-checked", "false");
    expect(within(dialog).getByRole("button", { name: /upload now/i })).toBeEnabled();
  });

  it("writes the title, description and tags with AI and fills the fields", async () => {
    const t = setup();
    const dialog = await openUpload();
    await userEvent.click(within(dialog).getByRole("button", { name: /write with ai/i }));
    await waitFor(() => expect(within(dialog).getByLabelText("Title")).toHaveValue(generated.title));
    expect(within(dialog).getByLabelText("Description")).toHaveValue(generated.description);
    expect(within(dialog).getByLabelText("Hashtags")).toHaveValue("Shorts, growth");
    expect(within(dialog).getByLabelText("Search tags")).toHaveValue("youtube growth, creator tips");
    expect(posts(t.calls, "/metadata")).toHaveLength(1);
    expect(within(dialog).getByRole("button", { name: /rewrite with ai/i })).toBeInTheDocument();
  });

  it("saves your edits, then uploads with the chosen account and visibility", async () => {
    const t = setup();
    const dialog = await openUpload();
    await userEvent.type(within(dialog).getByLabelText("Title"), "My own title");
    await userEvent.type(within(dialog).getByLabelText("Hashtags"), "#growth, tips");
    await userEvent.type(within(dialog).getByLabelText("Search tags"), "one, two");
    await userEvent.selectOptions(within(dialog).getByLabelText("YouTube account"), "second");
    await userEvent.click(within(dialog).getByRole("radio", { name: "Unlisted" }));
    await userEvent.click(within(dialog).getByRole("switch", { name: "Made for kids" }));
    await userEvent.click(within(dialog).getByRole("button", { name: /upload now/i }));

    await waitFor(() => expect(posts(t.calls, "/upload")).toHaveLength(1));
    expect(posts(t.calls, "/metadata", "PUT")[0].body).toEqual({ title: "My own title", description: "", hashtags: ["growth", "tips"], tags: ["one", "two"] });
    const upload = posts(t.calls, "/upload")[0].body as Record<string, unknown>;
    expect(upload).toMatchObject({ account: "second", privacy: "unlisted", made_for_kids: true });
    expect(upload).not.toHaveProperty("publish_at");
    // metadata is saved before the upload starts
    expect(t.calls.findIndex((c) => c.method === "PUT")).toBeLessThan(t.calls.findIndex((c) => c.url.endsWith("/upload")));
    expect(await within(dialog).findByText(/uploading to main/i)).toBeInTheDocument();
  });

  it("with an empty title it skips saving and lets the server write everything", async () => {
    const t = setup();
    const dialog = await openUpload();
    await userEvent.click(within(dialog).getByRole("button", { name: /upload now/i }));
    await waitFor(() => expect(posts(t.calls, "/upload")).toHaveLength(1));
    expect(posts(t.calls, "/metadata", "PUT")).toHaveLength(0);
  });

  it("scheduling: needs a time at least 10 minutes ahead and sends it as an exact moment", async () => {
    const t = setup();
    const dialog = await openUpload();
    await userEvent.click(within(dialog).getByRole("radio", { name: "Schedule" }));
    const at = within(dialog).getByLabelText("Publish at");
    fireEvent.change(at, { target: { value: "2020-01-01T10:00" } });
    expect(within(dialog).getByRole("alert")).toHaveTextContent("at least 10 minutes from now");
    expect(within(dialog).getByRole("button", { name: /schedule upload/i })).toBeDisabled();

    fireEvent.change(at, { target: { value: "2099-06-01T10:00" } });
    expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: /schedule upload/i }));
    await waitFor(() => expect(posts(t.calls, "/upload")).toHaveLength(1));
    expect(posts(t.calls, "/upload")[0].body).toMatchObject({ publish_at: new Date("2099-06-01T10:00").toISOString() });
  });

  it("shows the live upload, then the link when it is done", async () => {
    const t = setup(withClip(done, states.yt_uploading.yt ? { yt: states.yt_uploading.yt as never } : {}));
    const dialog = await openUpload();
    expect(await within(dialog).findByText(/uploading to second/i)).toBeInTheDocument();
    expect(within(dialog).getByText(states.yt_uploading.yt!.message!)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /upload now/i })).toBeDisabled();

    t.set(withClip(done, { yt: states.yt_done.yt as never }));
    const link = await within(dialog).findByRole("link", { name: /open on youtube/i }, { timeout: 4000 });
    expect(link).toHaveAttribute("href", "https://youtu.be/abc123");
    expect(within(dialog).getByText("Uploaded to second")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /upload again/i })).toBeEnabled();
  });

  it("shows why an upload failed", async () => {
    setup(withClip(done, { yt: { state: "error", account: "main", url: null, error: "'client_secret.json' not found.", scheduled: null } }));
    const dialog = await openUpload();
    expect(within(dialog).getByText("'client_secret.json' not found.")).toBeInTheDocument();
  });

  it("explains and blocks uploading when YouTube is not set up", async () => {
    setup(done as unknown as Job, { ...config, youtube_ready: false });
    const dialog = await openUpload();
    expect(within(dialog).getByText(/youtube is not set up yet/i)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /upload now/i })).toBeDisabled();
  });

  it("the card shows where each clip stands", async () => {
    setup(withClip(done, { yt: { state: "done", account: "main", url: "https://youtu.be/x", error: null, scheduled: "2099-06-01T10:00:00.000Z" } }));
    const link = await screen.findByRole("link", { name: /scheduled/i });
    expect(link).toHaveAttribute("href", "https://youtu.be/x");
  });
});

describe("Schedule all", () => {
  const open = async (initial: Job = done as unknown as Job) => {
    const t = setup(initial);
    await userEvent.click(await screen.findByRole("button", { name: /schedule all/i }));
    return { t, dialog: await screen.findByRole("dialog", { name: /schedule all clips/i }) };
  };

  it("uploads every clip with times spaced by the chosen number of days", async () => {
    const { t, dialog } = await open();
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(done.clips.length);
    fireEvent.change(within(dialog).getByLabelText("First clip is published at"), { target: { value: "2099-06-01T10:00" } });
    fireEvent.change(within(dialog).getByLabelText("Days between clips"), { target: { value: "2" } });
    await userEvent.selectOptions(within(dialog).getByLabelText("YouTube account"), "second");
    await userEvent.click(within(dialog).getByRole("button", { name: /upload and schedule/i }));

    expect(await within(dialog).findByText("Queued")).toBeInTheDocument();
    const sent = t.calls.filter((c) => c.method === "POST" && c.url.endsWith("/upload"));
    expect(sent.map((c) => c.url)).toEqual(done.clips.map((c) => `/api/jobs/${id}/clips/${c.id}/upload`));
    const first = new Date("2099-06-01T10:00").getTime();
    expect(sent.map((c) => (c.body as { publish_at: string }).publish_at)).toEqual(
      done.clips.map((_, i) => new Date(first + i * 2 * 86_400_000).toISOString()));
    expect(sent.every((c) => (c.body as { account: string }).account === "second")).toBe(true);
  });

  it("can send the first clips to one account and the rest to another, each with its own schedule", async () => {
    const { t, dialog } = await open();
    const n = done.clips.length;
    fireEvent.change(within(dialog).getByLabelText("First clip is published at"), { target: { value: "2099-06-01T10:00" } });
    fireEvent.change(within(dialog).getByLabelText("First clips"), { target: { value: "1" } });
    await userEvent.selectOptions(within(dialog).getByLabelText("The rest go to"), "second");
    await userEvent.click(within(dialog).getByRole("button", { name: /apply split/i }));
    expect(within(dialog).getByText(/browser window opens once to sign in to second/i)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: /upload and schedule/i }));

    expect(await within(dialog).findByText("Queued")).toBeInTheDocument();
    const sent = t.calls.filter((c) => c.method === "POST" && c.url.endsWith("/upload")).map((c) => c.body as { account: string; publish_at: string });
    expect(sent.map((b) => b.account)).toEqual(done.clips.map((_, i) => (i < 1 ? "main" : "second")));
    const first = new Date("2099-06-01T10:00").getTime();
    // "main" has one clip at the first time; "second" starts again at the first time, one day apart
    expect(sent.map((b) => b.publish_at)).toEqual(
      done.clips.map((_, i) => new Date(first + Math.max(0, i - 1) * 86_400_000).toISOString()));
    expect(n).toBeGreaterThan(1);
  });

  it("lets you pick the account of a single clip", async () => {
    const { t, dialog } = await open();
    const rows = within(dialog).getAllByRole("listitem");
    await userEvent.selectOptions(within(rows[0]).getByRole("combobox"), "second");
    fireEvent.change(within(dialog).getByLabelText("First clip is published at"), { target: { value: "2099-06-01T10:00" } });
    await userEvent.click(within(dialog).getByRole("button", { name: /upload and schedule/i }));
    await within(dialog).findByText("Queued");
    const sent = t.calls.filter((c) => c.method === "POST" && c.url.endsWith("/upload")).map((c) => (c.body as { account: string }).account);
    expect(sent[0]).toBe("second");
    expect(sent.slice(1).every((a) => a === "main")).toBe(true);
  });

  it("rejects a first time in the past", async () => {
    const { dialog } = await open();
    fireEvent.change(within(dialog).getByLabelText("First clip is published at"), { target: { value: "2020-01-01T10:00" } });
    expect(within(dialog).getByRole("alert")).toHaveTextContent("at least 10 minutes from now");
    expect(within(dialog).getByRole("button", { name: /upload and schedule/i })).toBeDisabled();
  });

  it("leaves out clips that are already on YouTube", async () => {
    const { dialog } = await open(withClip(done, { yt: states.yt_done.yt as never }));
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(done.clips.length - 1);
  });
});
