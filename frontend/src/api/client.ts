import type { Config, Job, JobSpec, JobSummary } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** FastAPI errors are {"detail": "text"} or {"detail": [{"loc": [...], "msg": "text"}]}. */
async function readDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const d = body?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => `${(x.loc ?? []).slice(1).join(".")}: ${x.msg}`.replace(/^: /, "")).join("; ");
  } catch { /* not JSON */ }
  return `Request failed (${res.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Cannot reach the Video Clipper server. Is it running (py -3.11 -m server)?");
  }
  if (!res.ok) throw new ApiError(res.status, await readDetail(res));
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  config: () => request<Config>("/api/config"),
  jobs: () => request<JobSummary[]>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  createJob: (spec: JobSpec) => request<Job>("/api/jobs", json("POST", spec)),
  cancelJob: (id: string) => request<void>(`/api/jobs/${id}/cancel`, json("POST")),
  deleteJob: (id: string) => request<void>(`/api/jobs/${id}`, json("DELETE")),
  signOut: (account: string) => request<void>(`/api/accounts/${encodeURIComponent(account)}/sign-out`, json("POST")),
  videoUrl: (jobId: string, clipId: string, rev = 1) => `/api/jobs/${jobId}/clips/${clipId}/video?v=${rev}`,
  downloadUrl: (jobId: string, clipId: string) => `/api/jobs/${jobId}/clips/${clipId}/download`,
};

/** Upload with progress (fetch cannot report upload progress, XMLHttpRequest can). */
export function uploadVideo(file: File, onProgress: (fraction: number) => void) {
  return new Promise<{ path: string; name: string; size: number }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/uploads");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
      else reject(new ApiError(xhr.status, `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new ApiError(0, "Cannot reach the Video Clipper server."));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
