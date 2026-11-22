import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "../App";
import LibraryPage from "../pages/LibraryPage";
import SettingsPage from "../pages/SettingsPage";
import config from "./fixtures/config.json";
import jobs from "./fixtures/jobs.json";
import { mockApi, renderApp, renderRoute } from "./helpers";

describe("Library", () => {
  it("lists jobs with status, newest first, linking to each", async () => {
    mockApi({ "GET /api/jobs": jobs });
    renderRoute(<LibraryPage />, { path: "/library", route: "/library" });
    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(jobs.length);
    const first = within(items[0]).getByRole("link");
    expect(first).toHaveAttribute("href", `/jobs/${jobs[0].id}`);
    expect(within(items[0]).getByText(/done|failed|cancelled|working|queued/i)).toBeInTheDocument();
  });

  it("has a friendly empty state", async () => {
    mockApi({ "GET /api/jobs": [] });
    renderRoute(<LibraryPage />, { path: "/library", route: "/library" });
    expect(await screen.findByText("Nothing here yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /make your first clips/i })).toBeInTheDocument();
  });
});

describe("Settings", () => {
  it("shows what is connected and lets you sign out of a signed-in account", async () => {
    let cfg = { ...config, youtube_ready: true, accounts: [{ name: "main", signed_in: true }, { name: "second", signed_in: false }] };
    const calls = mockApi({ "GET /api/config": () => cfg, "POST /api/accounts/main/sign-out": () => { cfg = { ...cfg, accounts: [{ name: "main", signed_in: false }, cfg.accounts[1]] }; return null; } });
    renderRoute(<SettingsPage />, { path: "/settings", route: "/settings" });
    expect(await screen.findByText("Key found")).toBeInTheDocument();
    expect(screen.getByText("Credentials found")).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: /sign out/i });
    expect(buttons).toHaveLength(1); // only the signed-in account
    await userEvent.click(buttons[0]);
    expect(calls.some((c) => c.method === "POST" && c.url === "/api/accounts/main/sign-out")).toBe(true);
    await screen.findAllByText(/not signed in yet/i);
    expect(screen.queryByRole("button", { name: /sign out/i })).not.toBeInTheDocument();
  });

  it("says what to do when keys are missing", async () => {
    mockApi({ "GET /api/config": { ...config, gemini_key_set: false, youtube_ready: false } });
    renderRoute(<SettingsPage />, { path: "/settings", route: "/settings" });
    expect(await screen.findByText("Key missing")).toBeInTheDocument();
    expect(screen.getByText("client_secret.json missing")).toBeInTheDocument();
  });
});

describe("App shell", () => {
  it("has navigation and switches between dark and light", async () => {
    mockApi({ "GET /api/jobs": jobs, "GET /api/config": config });
    document.documentElement.classList.add("dark"); // how index.html starts
    renderApp(<App />, "/library");
    expect(screen.getAllByRole("link", { name: /new clips/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /library/i }).length).toBeGreaterThan(0);
    await userEvent.click(screen.getAllByRole("button", { name: /switch to light theme/i })[0]);
    expect(document.documentElement).not.toHaveClass("dark");
    expect(localStorage.getItem("vc.theme")).toBe("light");
    await userEvent.click(screen.getAllByRole("button", { name: /switch to dark theme/i })[0]);
    expect(document.documentElement).toHaveClass("dark");
  });

  it("unknown pages show a 404 with a way back", async () => {
    mockApi({});
    renderApp(<App />, "/nowhere");
    expect(await screen.findByText("404")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to start/i })).toBeInTheDocument();
  });
});
