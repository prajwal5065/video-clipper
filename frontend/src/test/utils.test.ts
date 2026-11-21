import { describe, expect, it } from "vitest";
import type { DownloadInfo } from "../api/types";
import { describeDownload, humanSize, humanTime, timeAgo } from "../lib/utils";
import downloading from "./fixtures/job_downloading.json";
import done from "./fixtures/job_done.json";
import failed from "./fixtures/job_failed.json";
import running from "./fixtures/job_transcribing.json";
import { stageStates } from "../components/StageStepper";
import type { Job } from "../api/types";

describe("number formatting (same wording as the Python side)", () => {
  it("sizes", () => {
    expect(humanSize(512)).toBe("512 B");
    expect(humanSize(1536)).toBe("1.5 KB");
    expect(humanSize(5 * 1024 ** 2)).toBe("5.0 MB");
    expect(humanSize(2.67 * 1024 ** 3)).toBe("2.7 GB");
    expect(humanSize(null)).toBe("0 B");
  });
  it("times", () => {
    expect(humanTime(45)).toBe("0:45");
    expect(humanTime(366)).toBe("6:06");
    expect(humanTime(3725)).toBe("1:02:05");
    expect(humanTime(-5)).toBe("0:00");
  });
  it("time ago", () => {
    const now = 1_700_000_000_000;
    expect(timeAgo(now / 1000 - 10, now)).toBe("just now");
    expect(timeAgo(now / 1000 - 600, now)).toBe("10 min ago");
    expect(timeAgo(now / 1000 - 7200, now)).toBe("2 h ago");
  });
});

describe("describeDownload", () => {
  it("shows percent, size, speed and time left for a real recorded download", () => {
    const d = describeDownload((downloading as unknown as Job).download as DownloadInfo);
    expect(d.headline).toBe("Downloading video: 33%");
    expect(d.detail).toBe("921.6 MB of 2.7 GB · 3.4 MB/s · about 9:01 left");
  });
  it("handles an unknown total and the merge step", () => {
    expect(describeDownload({ stage: "downloading", done: 5 * 1024 ** 2, total: null, fraction: null, best: 0 }))
      .toEqual({ headline: "Downloading video", detail: "5.0 MB" });
    expect(describeDownload({ stage: "processing", best: 1 }).headline).toMatch(/merging video and audio/);
  });
});

describe("stageStates", () => {
  it("marks earlier steps done and the current one active", () => {
    expect(stageStates(running as unknown as Job)).toEqual(["done", "active", "pending", "pending"]);
    expect(stageStates(downloading as unknown as Job)).toEqual(["active", "pending", "pending", "pending"]);
  });
  it("everything is done when the job is done; a failed job shows where it stopped", () => {
    expect(stageStates(done as unknown as Job)).toEqual(["done", "done", "done", "done"]);
    expect(stageStates(failed as unknown as Job)).toEqual(["done", "done", "failed", "pending"]);
    expect(stageStates({ status: "queued", stage: "queued" })).toEqual(["pending", "pending", "pending", "pending"]);
  });
});
