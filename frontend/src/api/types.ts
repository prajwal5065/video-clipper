// Shapes returned by the Python API (see server/jobs.py). Fixtures in src/test/fixtures are real API output.
export type Crop = "face" | "center" | "fit" | "fit-black";
export type Quality = "draft" | "standard" | "high" | "max";
export type Status = "queued" | "running" | "done" | "failed" | "cancelled" | "interrupted";
export type Stage = "queued" | "download" | "transcribe" | "select" | "render" | "done";

export interface Option { id: string; label: string; description: string }

export interface Defaults {
  gemini_model: string; privacy: "private" | "unlisted" | "public"; made_for_kids: boolean;
  clips: number; min_len: number; max_len: number; whisper: string; device: "auto" | "cpu" | "cuda";
  compute_type: "int8" | "float16"; crop: Crop; quality: Quality; captions: boolean; style: string;
}

export interface Config {
  gemini_key_set: boolean; youtube_ready: boolean;
  accounts: { name: string; signed_in: boolean }[];
  framing: Option[]; quality: Option[]; whisper_models: string[]; caption_styles: string[]; gemini_models: string[];
  defaults: Defaults;
}

export interface JobSpec {
  source_type: "link" | "path"; source: string; clips: number; min_len: number; max_len: number;
  whisper: string; device: "auto" | "cpu" | "cuda"; compute_type: "int8" | "float16";
  crop: Crop; quality: Quality; captions: boolean; style: string; model: string | null;
}

export interface DownloadInfo {
  stage: "downloading" | "processing" | "done"; done?: number; total?: number | null;
  fraction?: number | null; speed?: number | null; eta?: number | null; kind?: string; best: number;
}

export interface Clip {
  id: string; index: number; title: string; reason: string; score: number | null; start: number; end: number;
  file: string; crop: Crop; style: string; captions: boolean; quality: Quality; rev: number;
  meta: { title: string; description: string; hashtags: string[]; tags: string[] } | null;
  yt: { state: string; account: string; url: string | null; error: string | null; scheduled: string | null } | null;
  edit: { state: string; kind?: string; progress?: number; error?: string | null } | null;
  preview: { file: string; rev: number; start: number; end: number } | null;
}

export interface Job {
  id: string; created: number; updated: number; status: Status; stage: Stage; progress: number; message: string;
  label: string; spec: JobSpec; error: string | null; download: DownloadInfo | null;
  transcribe: { done: number; total: number } | null;
  render: { index: number; total: number; title: string } | null;
  duration: number | null; source: { path: string; name: string } | null; clips: Clip[];
}

export interface JobSummary {
  id: string; created: number; status: Status; stage: Stage; progress: number; message: string; label: string;
  clips: number; thumbnail_clip: string | null;
}
